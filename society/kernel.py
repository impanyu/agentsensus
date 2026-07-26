import asyncio
import time
import uuid

from society.actions import Action, ActionResult, Message, validate_action
from society.conversations import ConversationStore
from society.llm import BudgetExceeded


class Kernel:
    """Deterministic tick-barrier scheduler for AgentSociety.

    Deterministic given deterministic brains: each tick, every *eligible*
    agent's `brain.decide(view)` runs concurrently via asyncio.gather (views
    are built from pre-decide state, so brain latency cannot affect what
    any brain observes). Once all decisions are in, validate/execute/
    fifo-append/event-log effects are applied *sequentially*, in the fixed
    order of the awake list (sorted by agent id), so event order and
    message-send order within a tick do not depend on brain latency -- only
    on agent id. (The `think` action performs an LLM call during execute,
    so it runs sequentially with the other agents' effects; this is
    acceptable.) A brain exception is caught and recorded as a failed
    action for that agent rather than aborting the tick.

    Messages sent during a tick are only delivered into recipient
    conversation threads (`self.conversations`) after all steps of that
    tick have completed, so they become visible starting the next tick.
    """

    def __init__(
        self,
        agents: dict[str, "Agent"],
        worldmap,
        event_log,
        shared_memory=None,
        llm=None,
        metrics=None,
        config: dict | None = None,
    ):
        self.agents = agents
        self.worldmap = worldmap
        self.event_log = event_log
        self.shared_memory = shared_memory
        self.llm = llm
        self.metrics = metrics
        self.config = config or {}

        self.tick = 0
        self._pending: list[dict] = []
        self._budget_hit = False

        # Per-interlocutor conversation threads (Task 2): kernel-held store
        # that `_deliver_due` records into on delivery -- the sole delivery
        # target now that the STM inbox is gone (removed in Task 4).
        self.conversations = ConversationStore()

        # Per-agent count of remember-worthy events accumulated since the
        # agent last called `remember` (a plot beat it took part in but has
        # not yet deposited to shared LTM): its own say/gesture/act_on,
        # plus every say/gesture it *receives*. When this reaches
        # `_remember_hint_threshold`, `_build_agent_view` injects a
        # `remember_hint` into the agent's decision view (the empirical fix
        # for agents never picking the discretionary `remember` action on
        # their own -- the static skill-doc guidance alone never fired it).
        # Reset to 0 on a successful `remember`.
        self._unremembered: dict[str, int] = {}
        self._remember_hint_threshold: int = int(
            self.config.get("remember_hint_threshold", 2)
        )

        self.presence: dict[str, set] = {}
        self._build_presence()

        # Display-name -> agent-id alias map (Fix 1a). Lets brains refer to
        # an agent by its scenario "name" (e.g. a Chinese character name)
        # in addition to its raw id (usually pinyin/ascii). Built once at
        # construction time; every agent's own id always maps to itself,
        # and on a name/id collision the first agent encountered wins.
        self._alias: dict[str, str] = {}
        self._build_alias()

        # Set by build_society (holds the loaded scenario cfg dict, incl.
        # "_dir") so a checkpoint can record enough to rebuild the society
        # on resume. None until build_society wires it up.
        self.scenario_cfg: dict | None = None
        # When set (by run.py's --checkpoint flag), run() writes a
        # checkpoint to this path on each periodic metrics snapshot and
        # once more right before returning, regardless of stop reason.
        self.checkpoint_path: str | None = None

    # ------------------------------------------------------------------
    # Presence index
    # ------------------------------------------------------------------
    def _build_presence(self) -> None:
        self.presence = {}
        for agent in self.agents.values():
            if agent.kind == "environment":
                continue
            if getattr(agent, "archived", False):
                continue
            loc = agent.location()
            if loc is not None:
                self.presence.setdefault(loc, set()).add(agent.id)

    def _build_alias(self) -> None:
        self._alias = {}
        # Pass 1: every agent's own id always resolves to itself. Done
        # first so a later agent's display name can never shadow an
        # earlier (or any) agent's real id.
        for agent in self.agents.values():
            self._alias[agent.id] = agent.id
        # Pass 2: display names, first agent with a given name wins.
        for agent in self.agents.values():
            name = getattr(agent, "name", None)
            if name and name not in self._alias:
                self._alias[name] = agent.id

    def _resolve_ref(self, ref):
        """Resolve a single ref through the alias map. Unknown strings
        (not a key in _alias) pass through unchanged."""
        if isinstance(ref, str) and ref in self._alias:
            return self._alias[ref]
        return ref

    def _resolve_action_refs(self, action: Action) -> None:
        """Resolve target/destination/targets refs in `action.params` in
        place, through the display-name -> id alias map (Fix 1a). Unknown
        strings are left untouched so existing "no such target" error
        paths still fire for genuinely unknown refs."""
        params = dict(action.params)
        for key in ("target", "destination"):
            if key in params:
                params[key] = self._resolve_ref(params[key])
        targets = params.get("targets")
        if isinstance(targets, list):
            params["targets"] = [self._resolve_ref(t) for t in targets]
        action.params = params

    def _presence_move(self, agent_id: str, origin, dest) -> None:
        if origin is not None:
            occupants = self.presence.get(origin)
            if occupants is not None:
                occupants.discard(agent_id)
                if not occupants:
                    del self.presence[origin]
        if dest is not None:
            self.presence.setdefault(dest, set()).add(agent_id)

    # ------------------------------------------------------------------
    # Messaging
    # ------------------------------------------------------------------
    def send(self, msg: Message) -> None:
        """Queue a message for delivery next tick, with NO distance delay
        (delay 0) -- used for kernel-internal / system messages (arrival,
        departure, "X arrived"/"X departed") where the recipient IS the
        origin/destination location itself, so there is nothing to delay
        by distance. Player-facing `say`/`gesture` go through
        `route()` instead, which computes a per-recipient delay from
        `self.worldmap.distance`.
        """
        for rid in msg.recipients:
            self._pending.append({"msg": msg, "recipient": rid, "deliver_at": self.tick})

    def route(self, msg: Message, sender_loc) -> None:
        """Enqueue `msg` to each recipient with a distance-based delay from
        `sender_loc` (the sender's location at send time). Co-located
        (same location, including both None) is delay 0 -- delivered next
        tick, same as `send`. A recipient in a different, connected
        location is delayed by `self.worldmap.distance(sender_loc, rloc)`
        ticks; if the map reports no route (`None`), falls back to
        `self.worldmap.default_distance` rather than dropping the message.

        Guard: never enqueues a recipient equal to `msg.sender` (an agent
        can't have a conversation thread with itself).
        """
        for rid in msg.recipients:
            if rid == msg.sender:
                continue
            r = self.agents.get(rid)
            if r is None:
                self.event_log.append(
                    self.tick,
                    "system",
                    "kernel",
                    {"note": "undeliverable", "recipient": rid, "message_id": msg.id},
                )
                continue
            rloc = r.location()
            if rloc is None or rloc == sender_loc:
                delay = 0
            else:
                d = self.worldmap.distance(sender_loc, rloc)
                delay = d if d is not None else self.worldmap.default_distance
            self._pending.append(
                {"msg": msg, "recipient": rid, "deliver_at": self.tick + delay}
            )

    def _deliver_due(self) -> bool:
        """Deliver all pending messages whose deliver_at <= current tick,
        recording each into BOTH the recipient's thread (unread+1) and the
        sender's own copy of that thread (unread+0), via
        `self.conversations`. Delivery clears the recipient's waiting state
        only for messages with wake=True -- a wake=False message (e.g. a
        `say`/`gesture` sent with wake=False) is still recorded (readable via
        `conversations.read` once the agent is awake for any other reason)
        but must not by itself interrupt a `wait`. Returns True if anything
        was delivered.

        NOTE (Task 4): the STM inbox is gone -- `self.conversations` is now
        the only delivery target; `pop_message` and `peek_inbox` were
        removed as of Task 3 (superseded by `read_thread`/
        `conversations.roster`).
        """
        due = [p for p in self._pending if p["deliver_at"] <= self.tick]
        self._pending = [p for p in self._pending if p["deliver_at"] > self.tick]
        delivered_any = False
        for p in due:
            msg, rid = p["msg"], p["recipient"]
            recipient = self.agents.get(rid)
            if recipient is None:
                continue
            # Kernel-internal system messages (arrival/departure/departing
            # notices from _process_arrivals/_execute_move, always sent via
            # `send()` with sender "kernel") are not a conversation --
            # recording them into ConversationStore would create an
            # unbounded, forever-checkpointed "kernel"-owned thread with no
            # interlocutor to read it back. They still wake the recipient
            # and get an event-log entry (below); only the thread-logging
            # is skipped. Note: this is narrower than "any kind='system'
            # message" -- an external caller's own kernel.send() with a
            # different sender (e.g. sender="system") is a real
            # conversational partner and must still be threaded (see
            # tests/test_kernel_core.py::test_external_send_wakes_sleeper_no_crash).
            is_system_msg = msg.sender == "kernel"
            if not is_system_msg:
                rec = {"sender": msg.sender, "kind": msg.kind, "content": msg.content, "tick": self.tick}
                sender_agent = self.agents.get(msg.sender)
                sender_kind = getattr(sender_agent, "kind", None)
                recipient_kind = getattr(recipient, "kind", None)
                self.conversations.record(
                    rid, msg.sender, rec, unread_delta=1, kind=sender_kind
                )
                if msg.sender != rid:
                    self.conversations.record(
                        msg.sender, rid, rec, unread_delta=0, kind=recipient_kind
                    )
            if msg.wake:
                recipient.waiting_until = None
            delivered_any = True
            self.event_log.append(
                self.tick,
                "message",
                msg.sender,
                {"message": msg.to_dict(), "recipient": rid},
            )
            if msg.kind in ("say", "gesture"):
                # Receiving a line of dialogue is itself a remember-worthy
                # event for the recipient (news/decisions reach them this
                # way), so it feeds their remember-hint backlog too.
                self._unremembered[rid] = self._unremembered.get(rid, 0) + 1
                if self.metrics is not None:
                    on_message = getattr(self.metrics, "on_message", None)
                    if on_message is not None:
                        on_message(msg.sender, rid, msg.kind)
        return delivered_any

    # ------------------------------------------------------------------
    # Eligibility
    # ------------------------------------------------------------------
    def _timeout_elapsed(self, a) -> bool:
        """Whether `a` is waiting on a real (non-forever) timeout that has
        elapsed as of the current tick. Shared by is_eligible() and the
        waiting-clear block in run() so the two never drift apart."""
        return (
            a.waiting_until is not None
            and a.waiting_until != -1
            and a.waiting_until <= self.tick
        )

    def is_eligible(self, a) -> bool:
        """Whether agent `a` should get a decide/execute cycle this tick.

        Task R (awake-based model for characters; supersedes both the
        goal-based sleep economy AND the S4 `wake_all_characters` ablation
        flag, which is removed): a character is eligible whenever it is
        AWAKE, full stop -- an awake character with an empty goal stack and
        an empty inbox still runs every tick (it is expected to `wait` on
        its own if it truly has nothing to do; see `_GOAL_HINT_*` /
        actions_skill's `wait` section). "Awake" == `waiting_until is None`
        (never slept, or a wake=True message already cleared it in
        `deliver_pending`) OR a real (non-forever) timeout has elapsed.
        There is no more inbox-peeking or goal-emptiness check here: by the
        time this runs (top of the next tick), `deliver_pending` has
        already cleared `waiting_until` for any wake=True message delivered
        last tick, so a pending wake message is always already reflected in
        `waiting_until`.

        Environments and info_carriers (Task R, Part A -- revert of S2's
        unified-agent architecture) are passive, function-driven agents:
        their act_on/read responses are computed SYNCHRONOUSLY by the
        kernel during the acting character's own apply step (see
        `_execute_act_on`/`_execute_read`), so they never take a proactive
        turn of their own and are NEVER eligible, regardless of pending
        messages or (for a directly-constructed test Agent) goals.
        """
        if getattr(a, "archived", False):
            # History-sedimentation mode (design spec §4.1): archived
            # (already-dead) agents never participate in the simulation,
            # regardless of pending inbox/goals.
            return False
        if a.transit is not None:
            return False
        if a.kind != "character":
            return False
        if a.waiting_until is None:
            return True
        # a is waiting: only a real (non-forever) timeout that has elapsed
        # makes it eligible.
        return self._timeout_elapsed(a)

    # ------------------------------------------------------------------
    # Arrivals / transit
    # ------------------------------------------------------------------
    def _process_arrivals(self) -> None:
        for agent in self.agents.values():
            if getattr(agent, "archived", False):
                # Defensive: archived agents can never issue `move` (they
                # are never eligible), so transit should never be set, but
                # skip explicitly so they can never re-enter presence.
                continue
            transit = agent.transit
            if transit is None or transit["arrive_at"] > self.tick:
                continue

            origin = agent.location()
            dest = transit["dest"]

            agent.stm.status.set("location", dest)
            self._presence_move(agent.id, origin, dest)

            # The arriving agent learns of its own arrival synchronously
            # via the status/event log (its `location` status is already
            # updated above, and the "arrival" system event below records
            # it) -- there is no more STM inbox to deliver an "arrival"
            # Message into (removed in Task 4), so waking it is the only
            # remaining effect needed here.
            agent.waiting_until = None

            if dest in self.agents:
                self.send(
                    Message(
                        id=str(uuid.uuid4()),
                        sender="kernel",
                        recipients=[dest],
                        kind="system",
                        content=f"{agent.id} arrived",
                        tick_sent=self.tick,
                    )
                )
            if origin is not None and origin in self.agents:
                self.send(
                    Message(
                        id=str(uuid.uuid4()),
                        sender="kernel",
                        recipients=[origin],
                        kind="system",
                        content=f"{agent.id} departed",
                        tick_sent=self.tick,
                    )
                )

            agent.transit = None

            self.event_log.append(
                self.tick,
                "system",
                agent.id,
                {"event": "arrival", "origin": origin, "dest": dest},
            )

    # ------------------------------------------------------------------
    # Action execution
    # ------------------------------------------------------------------
    async def execute(self, agent, action: Action) -> ActionResult:
        # Fix 1a: resolve display-name refs (e.g. Chinese character names)
        # to agent ids before any target/destination validation below, so
        # say/observe/act_on/move/read all accept either an id or a known
        # alias. Mutates action.params in place (a fresh dict) -- the
        # caller's FIFO/event-log record then reflects the resolved refs,
        # which is fine and simpler than keeping two versions around.
        self._resolve_action_refs(action)

        name = action.name
        params = action.params

        if name == "noop":
            return ActionResult(True, data="noop")

        if name == "wait":
            timeout = params.get("timeout_ticks")
            if timeout is not None:
                agent.waiting_until = self.tick + int(timeout)
            else:
                agent.waiting_until = -1
            return ActionResult(True, data="waiting")

        if name == "conclude":
            return ActionResult(True, data=params.get("text"))

        if name == "push_goal":
            agent.stm.goals.push(params["text"])
            return ActionResult(True, data="pushed")

        if name == "pop_goal":
            if agent.stm.goals.empty():
                return ActionResult(False, error="goal stack empty")
            popped = agent.stm.goals.pop()
            return ActionResult(True, data=popped)

        if name == "replace_goal":
            agent.stm.goals.replace(params["text"])
            return ActionResult(True, data="replaced")

        if name == "update_status":
            agent.stm.status.set(params["key"], params["value"])
            return ActionResult(True, data="updated")

        if name == "remove_status":
            agent.stm.status.remove(params["key"])
            return ActionResult(True, data="removed")

        if name in ("say", "gesture"):
            return self._execute_say(agent, action)

        if name == "read_thread":
            return self._execute_read_thread(agent, action)

        if name == "act_on":
            return await self._execute_act_on(agent, action)

        if name in ("add_affiliated", "remove_affiliated", "set_affiliated", "get_affiliated"):
            return self._execute_affiliated_crud(agent, action)

        if name == "observe":
            return self._execute_observe(agent, action)

        if name == "read":
            return await self._execute_read(agent, action)

        if name == "move":
            return self._execute_move(agent, action)

        if name in ("remember", "recall", "forget", "revise_memory"):
            return await self._execute_memory_action(agent, action)

        if name == "think":
            return await self._execute_think(agent, action)

        return ActionResult(False, error=f"not implemented: {name}")

    def _execute_say(self, agent, action: Action) -> ActionResult:
        """say/gesture: unified {targets?, content} shape (Task 3 -- folds
        `broadcast` into `say`/`gesture`, which are now the only two
        message-sending actions). `targets` is now OPTIONAL: when omitted
        (or not a non-empty list), it defaults to every character
        currently co-located with the sender -- i.e. a bare `say` speaks
        to the room. If the resolved target set is empty (nobody else is
        here), this is a logged no-op, NOT an error: `return
        ActionResult(True, data={"delivered": 0})`.

        Every explicit target must exist and not be archived, else no
        message is sent and the offenders are named in the error. Targets
        need NOT be co-located with the sender (Task 2): delivery is
        routed through `route()`, which delivers next tick (delay 0) to a
        co-located target and after a distance-based delay to a remote one
        -- a `say` to someone elsewhere in the world is a "letter" that
        arrives once the in-world travel time has elapsed, not an instant
        same-room utterance.

        wake defaults to True (unified say/gesture behave exactly as
        before wake existed) but may be set explicitly by the sender (a
        stringized bool from an LLM brain is parsed leniently, same as
        before)."""
        params = action.params
        content = params["content"]

        targets = params.get("targets")
        if not targets:
            targets = [
                c["id"] for c in self._colocated_view(agent) if c["kind"] == "character"
            ]

        if not targets:
            return ActionResult(True, data={"delivered": 0})

        wake = params.get("wake", True)
        # LLM brains emit JSON and sometimes stringify booleans; a lax
        # bool("false")==True would silently invert the sleep economy.
        if isinstance(wake, str):
            wake = wake.strip().lower() == "true"
        elif not isinstance(wake, bool):
            return ActionResult(False, error="wake must be a boolean")

        # An environment agent IS its own location (it has no
        # status.location -- see _colocated_view), so routing distance is
        # computed from its own id, not agent.location() (which would be
        # None for an environment).
        sender_loc = agent.id if agent.kind == "environment" else agent.location()
        offenders = []
        for tid in targets:
            target = self.agents.get(tid)
            if target is None or getattr(target, "archived", False):
                offenders.append(tid)

        if offenders:
            return ActionResult(
                False, error=f"no such target(s): {', '.join(offenders)}"
            )

        msg = Message(
            id=str(uuid.uuid4()),
            sender=agent.id,
            recipients=targets,
            kind=action.name,
            content=content,
            tick_sent=self.tick,
            wake=wake,
        )
        self.route(msg, sender_loc)
        return ActionResult(True, data={"delivered": len(targets)})

    def _execute_read_thread(self, agent, action: Action) -> ActionResult:
        """read_thread(target, k=10): returns the last `k` records of
        `agent`'s conversation thread with `target` (sender+recipient
        share the same log content, kept in each party's own thread copy
        -- see `ConversationStore`/`_deliver_due`), and marks that thread
        read (unread reset to 0) as a side effect."""
        params = action.params
        target = params["target"]
        k = params.get("k", 10)
        return ActionResult(True, data=self.conversations.read(agent.id, target, k))

    def _log_own_interaction(self, agent, target_id, kind_name, content, target_kind=None):
        """Record `agent`'s own observe/act_on/read into its OWN thread with
        `target_id` (unread_delta=0 -- it's the actor's own action, already
        "read"). Called only after the action has SUCCEEDED; failures/
        invalid targets are never logged. `target_kind` is the target
        agent's `.kind` (environment/info_carrier/character), used to tag
        the thread the same way `_deliver_due` does for message threads."""
        self.conversations.record(
            agent.id,
            target_id,
            {"sender": agent.id, "kind": kind_name, "content": content, "tick": self.tick},
            unread_delta=0,
            kind=target_kind,
        )

    async def _execute_act_on(self, agent, action: Action) -> ActionResult:
        """act_on(targets, content): targets must be a list containing
        EXACTLY ONE environment id, and the actor must be co-located with
        it (kept from S1). SYNCHRONOUS (Task R -- reverts S2's async
        message-to-inbox approach): environments are passive,
        function-driven agents (Part A) with no brain turn of their own to
        react on, so the kernel computes the effect right here, in the
        acting character's own apply step, in the SAME tick -- deposit a
        memory owned by the environment (`source="act_on"`) so the place
        "remembers" what was done there, and return immediately. No
        Message is sent, and no brain/LLM is ever called for this. If no
        shared_memory is configured, the act_on still succeeds (nothing to
        record it into)."""
        params = action.params
        targets = params["targets"]
        content = params["content"]

        if len(targets) != 1:
            return ActionResult(
                False, error="act_on targets must contain exactly one environment id"
            )
        target_id = targets[0]

        target = self.agents.get(target_id)
        if target is None or target.kind != "environment":
            return ActionResult(False, error=f"not an environment: {target_id}")
        if agent.location() != target_id:
            return ActionResult(False, error=f"not at {target_id}")

        if self.shared_memory is None:
            result = ActionResult(
                True, data={"env": target_id, "recorded": content, "note": "no shared memory"}
            )
        else:
            await self.shared_memory.remember_atomic(
                [target_id], content, tick=self.tick, source="act_on"
            )
            result = ActionResult(True, data={"env": target_id, "recorded": content})

        self._log_own_interaction(agent, target_id, action.name, content, target.kind)
        return result

    # ------------------------------------------------------------------
    # Affiliated-memory CRUD (sync; no LLM calls; delegates to SharedMemory)
    # ------------------------------------------------------------------
    def _get_owned_entry(self, memory_id: str):
        """Look up a shared-memory entry by id via the public
        `all_entries()` API. Returns None if the id doesn't exist."""
        for entry in self.shared_memory.all_entries():
            if entry["id"] == memory_id:
                return entry
        return None

    def _execute_affiliated_crud(self, agent, action: Action) -> ActionResult:
        """add_affiliated/remove_affiliated/set_affiliated/get_affiliated:
        all four operate only on memories `agent` owns. `set_affiliated`
        replaces the whole affiliated array (implemented here as
        remove-all-then-add; ltm.py itself is not modified).
        `get_affiliated` resolves each affiliated id to its text, skipping
        dangling ids (ones with no matching entry) silently."""
        if self.shared_memory is None:
            return ActionResult(False, error="no shared memory")

        params = action.params
        memory_id = params["memory_id"]

        name = action.name
        if name != "get_affiliated":
            affiliated = params.get("affiliated")
            # A bare string would be iterated character-by-character and
            # silently corrupt the persistent affiliation set.
            if not isinstance(affiliated, list) or not all(
                isinstance(x, str) for x in affiliated
            ):
                return ActionResult(False, error="affiliated must be a list of memory ids")

        entry = self._get_owned_entry(memory_id)
        if entry is None:
            return ActionResult(False, error=f"no such memory: {memory_id}")
        if agent.id not in entry["owners"]:
            return ActionResult(False, error=f"not an owner of {memory_id}")

        if name == "add_affiliated":
            self.shared_memory.add_affiliations(memory_id, params["affiliated"])
            return ActionResult(True, data="added")

        if name == "remove_affiliated":
            self.shared_memory.remove_affiliations(memory_id, params["affiliated"])
            return ActionResult(True, data="removed")

        if name == "set_affiliated":
            current = self.shared_memory.get_affiliations(memory_id)
            if current:
                self.shared_memory.remove_affiliations(memory_id, current)
            if params["affiliated"]:
                self.shared_memory.add_affiliations(memory_id, params["affiliated"])
            return ActionResult(True, data="set")

        # get_affiliated
        ids = self.shared_memory.get_affiliations(memory_id)
        id_to_text = {e["id"]: e["text"] for e in self.shared_memory.all_entries()}
        data = [{"id": i, "text": id_to_text[i]} for i in ids if i in id_to_text]
        return ActionResult(True, data=data)

    # ------------------------------------------------------------------
    # View construction (Fix 1b: discoverability of ids for say/observe/
    # act_on/move targets)
    # ------------------------------------------------------------------
    def _colocated_view(self, agent) -> list[dict]:
        """Other non-environment agents sharing `agent`'s location (or, for
        an environment agent, the agents currently present there), sorted
        by id, self excluded."""
        loc = agent.id if agent.kind == "environment" else agent.location()
        if loc is None:
            return []
        result = []
        for oid in sorted(self.presence.get(loc, set())):
            if oid == agent.id:
                continue
            other = self.agents.get(oid)
            if other is None:
                continue
            result.append(
                {"id": other.id, "kind": other.kind, "name": getattr(other, "name", None)}
            )
        return result

    def _known_locations_view(self) -> list[dict]:
        """All environment agents in the scenario, sorted by id."""
        result = [
            {"id": a.id, "name": getattr(a, "name", None)}
            for a in self.agents.values()
            if a.kind == "environment"
        ]
        result.sort(key=lambda d: d["id"])
        return result

    # Goal-bootstrap hint (design spec §4.2): shown whenever an agent's goal
    # stack is empty, so a "history sedimentation" character with no
    # scripted goals (a living sequel character, or any agent started with
    # goals=[]) knows how to get itself going: recall its own past, observe
    # its surroundings, conclude a judgment, then push a fundamental goal
    # and a current goal.
    _GOAL_HINT_ZH = (
        "你的目标栈为空。请**先 push_goal** 自举一个你此刻最想推进的目标(根据你的"
        "记忆 recall 和当前处境),**然后**围绕它持续行动(say/observe/act_on/"
        "remember…)。不要只做一次 read_thread 或 recall 就停;在唤醒模型下,即使"
        "目标栈为空,你下一 tick 仍会被调度,并不会因此自动休眠。若收件箱里有消息,"
        "可以先 push_goal(如“回应 X 的消息”)再处理——消息在你 pop 之前会一直留着。"
        "如果你此刻确实无事可做,用 `wait` 让自己休眠,直到有人给你消息再醒来——不要"
        "空转。"
    )
    _GOAL_HINT_EN = (
        "Your goal stack is empty. **First push_goal** to bootstrap a goal "
        "you most want to pursue right now (based on recall of your memory "
        "and your current situation), **then** act on it continuously "
        "(say/observe/act_on/remember...). Don't just do a single "
        "read_thread or recall and stop; under the awake model you'll still "
        "be scheduled next tick even with an empty goal stack -- it does "
        "not put you to sleep automatically. If there's a message in your "
        "inbox, you can push_goal first (e.g. \"respond to X's message\") "
        "and handle it afterward -- the message stays put until you pop "
        "it. If you truly have nothing to do right now, use `wait` to put "
        "yourself to sleep until a message wakes you -- don't spin."
    )

    # Remember-cue (empirical fix): shown at decision time once an agent has
    # accumulated `_remember_hint_threshold` remember-worthy events (its own
    # say/gesture/act_on + received dialogue) since its last `remember`.
    # The static skill-doc guidance never fired `remember` on its own; this
    # puts the cue *in the moment*, right when a plot beat has just happened.
    _REMEMBER_HINT_ZH = (
        "【记忆提示】自你上次 `remember` 以来,你已经参与了若干值得记住的进展"
        "(你的发言/行动,以及收到的对话)。如果其中有**真正发生、值得让大家共享"
        "的剧情节点**——一个决定或计策、一场交锋的结果、一条消息或情报、一个承诺、"
        "一次生死或去留——**现在就用 `remember` 把它写成一条完整的原子事实存入共享"
        "长期记忆**。不要等“反复验证”或攒着:只有 remember 写入的东西日后你和别人才"
        "recall 得到,过后就再也找不回来了。若这些进展确实都琐碎、不值得共享,可以"
        "跳过。"
    )
    _REMEMBER_HINT_EN = (
        "[Memory cue] Since your last `remember`, you've taken part in "
        "several potentially memorable developments (your own lines/actions "
        "and dialogue you received). If any of them is a **real plot beat "
        "worth sharing with everyone** -- a decision or plan, the outcome of "
        "a clash, a piece of news or intelligence, a promise, a death or "
        "departure -- **use `remember` now to write it as one complete "
        "atomic fact into shared long-term memory**. Don't wait to "
        "\"verify\" or let it pile up: only what `remember` writes can be "
        "recalled later by you or anyone else; otherwise it's lost. If these "
        "developments really are all trivial, you may skip it."
    )

    def _build_agent_view(self, agent) -> dict:
        """Build `agent`'s STM view, enriched with `colocated` and
        `known_locations` so brains can discover the exact ids to use as
        say/observe/act_on/move refs instead of guessing at display names.

        When the agent's goal stack is empty, also adds a `goal_hint`
        string (design spec §4.2) nudging it through the bootstrap
        pipeline (recall -> observe -> conclude -> push_goal x2), in the
        scenario's configured language.
        """
        view = agent.build_view(self.tick)
        view["colocated"] = self._colocated_view(agent)
        view["conversations"] = self.conversations.roster(
            agent.id, {c["id"] for c in view["colocated"]}, self.agents
        )
        view["known_locations"] = self._known_locations_view()
        language = self.config.get("language", "zh")
        if agent.stm.goals.empty():
            view["goal_hint"] = (
                self._GOAL_HINT_ZH if language == "zh" else self._GOAL_HINT_EN
            )
        if self._unremembered.get(agent.id, 0) >= self._remember_hint_threshold:
            view["remember_hint"] = (
                self._REMEMBER_HINT_ZH
                if language == "zh"
                else self._REMEMBER_HINT_EN
            )
        return view

    def _is_readable(self, agent, target) -> bool:
        """An info_carrier is readable if it shares the reader's location,
        or is portable and currently held by the reader."""
        if target.location() is not None and target.location() == agent.location():
            return True
        if target.portable and target.holder == agent.id:
            return True
        return False

    def _execute_observe(self, agent, action: Action) -> ActionResult:
        """observe(target): uniform across all three agent kinds (Task S2)
        -- returns {"kind": ..., "status": <public status view>,
        "occupants": [...]} where "occupants" is present only for an
        environment target. Visibility rules are unchanged: a character
        target must be co-located (and not archived); an info_carrier
        target must be readable (co-located or portable+held); an
        environment target follows today's rules (always observable, its
        occupants list excludes archived/absent agents). No memory content
        is ever included here -- that's what `say`/`read` are for."""
        target_id = action.params["target"]
        target = self.agents.get(target_id)
        if target is None:
            return ActionResult(False, error=f"no such target: {target_id}")

        if target.kind == "environment":
            occupants = []
            for oid in sorted(self.presence.get(target_id, set())):
                if oid == agent.id:
                    continue
                occ = self.agents.get(oid)
                if occ is None:
                    continue
                occupants.append(
                    {"id": occ.id, "kind": occ.kind, "status": occ.stm.status.public_view()}
                )
            result = ActionResult(
                True,
                data={
                    "kind": target.kind,
                    "status": target.stm.status.public_view(),
                    "occupants": occupants,
                },
            )
            self._log_own_interaction(
                agent, target_id, action.name, f"observed {target_id}", target.kind
            )
            return result

        if target.kind == "character":
            if getattr(target, "archived", False):
                return ActionResult(
                    False, error=f"{target_id} archived (已故): cannot be observed"
                )
            if target.location() != agent.location():
                return ActionResult(False, error=f"{target_id} not co-located")
            result = ActionResult(
                True, data={"kind": target.kind, "status": target.stm.status.public_view()}
            )
            self._log_own_interaction(
                agent, target_id, action.name, f"observed {target_id}", target.kind
            )
            return result

        if target.kind == "info_carrier":
            if not self._is_readable(agent, target):
                return ActionResult(False, error=f"{target_id} not observable here")
            result = ActionResult(
                True, data={"kind": target.kind, "status": target.stm.status.public_view()}
            )
            self._log_own_interaction(
                agent, target_id, action.name, f"observed {target_id}", target.kind
            )
            return result

        return ActionResult(False, error=f"cannot observe kind {target.kind}")

    async def _execute_read(self, agent, action: Action) -> ActionResult:
        """read(target, query): target must be an info_carrier OR an
        environment -- the two passive, function-driven kinds (Part A);
        co-location/holder rules are unchanged (`_is_readable` for a
        carrier: co-located, or portable and held by the reader; an
        environment target just needs the reader to be co-located, i.e.
        currently there). SYNCHRONOUS (Task R -- reverts S2's async
        message-to-inbox approach): there is no brain on the target to
        answer this on its own next tick, so the kernel itself retrieves
        the TARGET's own memories relevant to `query` -- via
        `SharedMemory.recall_of(target_id, query, top_k)`, i.e. the
        target's OWN LTM entries (deposited by sedimentation, or by an
        earlier `act_on` at this same environment) -- and returns them
        directly as `[{"id": ..., "text": ...}, ...]`, in the SAME tick. If
        no shared_memory is configured, returns an empty list."""
        params = action.params
        target_id = params["target"]
        query = params["query"]
        top_k = params.get("top_k", 5)

        target = self.agents.get(target_id)
        if target is None or target.kind not in ("info_carrier", "environment"):
            return ActionResult(False, error=f"not readable: {target_id}")

        if target.kind == "info_carrier":
            if not self._is_readable(agent, target):
                return ActionResult(False, error=f"{target_id} not readable here")
        else:  # environment
            if agent.location() != target_id:
                return ActionResult(False, error=f"not at {target_id}")

        if self.shared_memory is None:
            result = ActionResult(True, data=[])
        else:
            data = await self.shared_memory.recall_of(target_id, query, top_k)
            result = ActionResult(True, data=data)

        self._log_own_interaction(
            agent, target_id, action.name, f"read: {query}", target.kind
        )
        return result

    def _execute_move(self, agent, action: Action) -> ActionResult:
        destination = action.params["destination"]
        current = agent.location()

        dest_agent = self.agents.get(destination)
        if dest_agent is None or dest_agent.kind != "environment":
            return ActionResult(False, error=f"not an environment: {destination}")
        if destination == current:
            return ActionResult(False, error="already there")
        if not self.worldmap.connected(current, destination):
            return ActionResult(False, error=f"{destination} not connected from {current}")

        d = self.worldmap.distance(current, destination)

        self._presence_move(agent.id, current, None)
        if current is not None and current in self.agents:
            self.send(
                Message(
                    id=str(uuid.uuid4()),
                    sender="kernel",
                    recipients=[current],
                    kind="system",
                    content=f"{agent.id} departing to {destination}",
                    tick_sent=self.tick,
                )
            )

        agent.transit = {"dest": destination, "arrive_at": self.tick + d}
        return ActionResult(True, data={"eta": self.tick + d})

    async def _execute_memory_action(self, agent, action: Action) -> ActionResult:
        if self.shared_memory is None:
            return ActionResult(False, error="no shared memory")

        name = action.name
        params = action.params

        if name == "remember":
            data = await self.shared_memory.remember(agent.id, params["text"], self.tick)
            return ActionResult(True, data=data)

        if name == "recall":
            top_k = params.get("top_k", 5)
            data = await self.shared_memory.recall(agent.id, params["query"], top_k)
            return ActionResult(True, data=data)

        if name == "forget":
            data = self.shared_memory.forget(agent.id, params["memory_id"])
            return ActionResult(True, data=data)

        # revise_memory
        data = await self.shared_memory.revise(
            agent.id, params["memory_id"], params["new_text"], tick=self.tick
        )
        return ActionResult(True, data=data)

    async def _execute_think(self, agent, action: Action) -> ActionResult:
        if self.llm is None:
            return ActionResult(False, error="no llm configured")

        question = action.params["question"]
        view = self._build_agent_view(agent)
        prompt = f"Current view: {view}\n\nQuestion: {question}"
        reply = await self.llm.chat(prompt, bucket="think")
        return ActionResult(True, data=reply)

    # ------------------------------------------------------------------
    # Per-agent step (decide concurrently, apply effects sequentially)
    # ------------------------------------------------------------------
    async def _decide(self, agent) -> tuple:
        """Build the view and call brain.decide() for one agent.

        Returns (action, brain_error): brain_error is None on success, or a
        string description of the exception the brain raised. A brain
        exception is caught here (not propagated) so one misbehaving brain
        can neither abort the tick for its siblings nor leave a dangling
        background mutation after run() has moved on.
        """
        view = self._build_agent_view(agent)
        try:
            action = await agent.brain.decide(view)
        except Exception as exc:  # noqa: BLE001 - isolate brain failures per agent
            if isinstance(exc, BudgetExceeded):
                self._budget_hit = True
            return None, str(exc)
        return action, None

    async def _apply(self, agent, action, brain_error) -> None:
        """Validate + execute + fifo-append + event-log for one agent.

        Always called sequentially (never concurrently) across the awake
        set, in the fixed order the caller iterates, so event order and
        message-send order within a tick are deterministic.
        """
        if brain_error is not None:
            action = Action("<decide-error>", {})
            result = ActionResult(False, error=f"brain error: {brain_error}")
        else:
            error = validate_action(action)
            if error:
                result = ActionResult(False, error=error)
            else:
                try:
                    result = await self.execute(agent, action)
                except BudgetExceeded:
                    self._budget_hit = True
                    result = ActionResult(False, error="budget exceeded")

        await agent.stm.fifo.append(
            {"name": action.name, "params": action.params}, result.to_dict()
        )
        self.event_log.append(
            self.tick,
            "action",
            agent.id,
            {
                "action": {"name": action.name, "params": action.params},
                "result": result.to_dict(),
                "location": agent.location(),
            },
        )

        # Maintain the remember-hint counter (see __init__): a successful
        # `remember` clears the agent's backlog; a successful outbound plot
        # action (say/gesture/act_on) adds to it. Only successful
        # actions count -- a rejected say never happened.
        if result.ok:
            if action.name == "remember":
                self._unremembered[agent.id] = 0
            elif action.name in ("say", "gesture", "act_on"):
                # A say/gesture that delivered to nobody (e.g. a bare `say`
                # into an empty room -- see _execute_say) is a logged no-op,
                # not a plot beat: don't bump the backlog for it.
                data = result.data
                delivered_to_nobody = (
                    action.name in ("say", "gesture")
                    and isinstance(data, dict)
                    and data.get("delivered") == 0
                )
                if not delivered_to_nobody:
                    self._unremembered[agent.id] = (
                        self._unremembered.get(agent.id, 0) + 1
                    )

    # ------------------------------------------------------------------
    # Budget circuit-breaker
    # ------------------------------------------------------------------
    def _budget_exceeded(self) -> bool:
        """Whether the run should stop with stop_reason="budget".

        The real signal is `self._budget_hit`, set whenever a
        `society.llm.BudgetExceeded` exception surfaces from a brain's
        `decide()` (Phase 1) or from an action handler during `_apply()`
        (Phase 2, e.g. think/remember/recall/revise_memory). A duck-typed
        `metrics.budget_exceeded()` is also honored if present, so a
        Metrics subclass can opt into its own budget signal, but it is not
        required (Metrics does not implement it).
        """
        if self._budget_hit:
            return True
        if self.metrics is None:
            return False
        check = getattr(self.metrics, "budget_exceeded", None)
        if check is None:
            return False
        return bool(check())

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------
    async def run(
        self, max_ticks: int | None = None, max_wall_seconds: float | None = None
    ) -> dict:
        start = time.monotonic()
        stop_reason = None

        while True:
            if max_ticks is not None and self.tick >= max_ticks:
                stop_reason = "max_ticks"
                break
            if (
                max_wall_seconds is not None
                and (time.monotonic() - start) >= max_wall_seconds
            ):
                stop_reason = "wall_time"
                break
            if self._budget_exceeded():
                stop_reason = "budget"
                break

            self._process_arrivals()

            awake = []
            for agent in self.agents.values():
                eligible = self.is_eligible(agent)
                if eligible and self._timeout_elapsed(agent):
                    # Waking from a timeout clears the waiting state.
                    agent.waiting_until = None
                if eligible:
                    awake.append(agent)

            if awake:
                # Phase 1: decide concurrently. Views were built from
                # pre-decide state, so brain latency cannot change what any
                # brain observes this tick.
                results = await asyncio.gather(
                    *(self._decide(a) for a in awake), return_exceptions=True
                )
                decisions = {}
                for agent, res in zip(awake, results):
                    if isinstance(res, Exception):
                        if isinstance(res, BudgetExceeded):
                            self._budget_hit = True
                        decisions[agent.id] = (None, str(res))
                    else:
                        decisions[agent.id] = res

                # Phase 2: apply effects sequentially, in a fixed order
                # (agent id) so event/message ordering within a tick is
                # deterministic regardless of decide() completion order.
                for agent in sorted(awake, key=lambda a: a.id):
                    action, brain_error = decisions[agent.id]
                    await self._apply(agent, action, brain_error)

            delivered = self._deliver_due()

            if self.metrics is not None:
                maybe_snapshot = getattr(self.metrics, "maybe_snapshot", None)
                if maybe_snapshot is not None:
                    snap = maybe_snapshot(self.tick)
                    if snap is not None and self.checkpoint_path is not None:
                        from society.persistence import save_checkpoint

                        save_checkpoint(self, self.checkpoint_path)

            transit_pending = any(a.transit is not None for a in self.agents.values())
            waiting_timers = [
                a.waiting_until
                for a in self.agents.values()
                if a.waiting_until is not None and a.waiting_until != -1
            ]

            if (
                not awake
                and not delivered
                and not transit_pending
                and not waiting_timers
                and not self._pending
            ):
                stop_reason = "quiescent"
                break

            # Fast-forward only when nothing happened this tick: no agent
            # was awake AND nothing was delivered (an external kernel.send()
            # to a sleeping agent still counts as "something happened", so
            # we must not fast-forward past it -- and there may be no
            # timers/transit to compute a min() over in that case).
            if not awake and not delivered:
                candidates = [
                    a.transit["arrive_at"]
                    for a in self.agents.values()
                    if a.transit is not None
                ]
                candidates.extend(waiting_timers)
                candidates.extend(p["deliver_at"] for p in self._pending)
                if candidates:
                    self.tick = min(candidates)
                else:
                    self.tick += 1
            else:
                self.tick += 1

        if self.checkpoint_path is not None:
            from society.persistence import save_checkpoint

            save_checkpoint(self, self.checkpoint_path)

        return {"ticks_run": self.tick, "stop_reason": stop_reason}
