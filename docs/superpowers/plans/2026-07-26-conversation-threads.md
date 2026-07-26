# Conversation Threads Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the per-agent FIFO inbox with kernel-held per-interlocutor conversation threads: an email-style roster in the view, a `read_thread` action, a unified `say` (default co-located, per-target worldmap-distance delay, wakes recipients), and all interaction records (incl. locations/readables) unified into threads.

**Architecture:** A pure `society/conversations.py` (`Thread` + `ConversationStore`) holds `{agent_id: {other_id: Thread}}`. The kernel owns one `ConversationStore`, routes every message through a distance-delayed pending queue, and records deliveries into both sides' threads. `STM.inbox` is removed; the view exposes a compact roster; `say`/`gesture` route through the store; `broadcast`/`pop_message`/`peek_inbox` are removed and `read_thread` added.

**Tech Stack:** Python 3.14, asyncio, pytest. No new deps.

## Global Constraints

- Do NOT change `society/ltm.py` (memory) or the memory backends. This is the messaging layer only.
- `say(targets?, content, wake?)`: `targets` optional → default = all **co-located characters** at send time; per-target `delay = 0` if co-located else `worldmap.distance(sender_loc, target_loc)` (unroutable → `worldmap.default_distance`); `wake` default True; NO co-location gate (remote targets allowed). Omitted `targets` + nobody co-located → logged no-op `ActionResult(True, data={"delivered": 0})`.
- `gesture` stays a SEPARATE action, identical routing/delay/threading to `say`, non-verbal kind.
- On delivery of a message to `recipient` from `sender`: append to BOTH `recipient`'s thread-with-`sender` (unread+1) AND `sender`'s thread-with-`recipient` (unread+0, own copy); if `msg.wake`, clear `recipient.waiting_until`.
- Co-located delivery keeps today's timing: `delay=0` → delivered on the very next tick (same as current `say`).
- REMOVE actions `broadcast`, `pop_message`, `peek_inbox`; ADD `read_thread(target, k?)`.
- `observe`/`act_on`/`read` keep their exact current return values; each ALSO records one message into the actor's thread with the target env/carrier (unread_delta=0).
- `STM.inbox` (the `asyncio.Queue`) and `STM.inbox_items` are removed; `Agent.build_view` drops `inbox_size`/`inbox_head`.
- Recipient moving mid-flight: delivered per the send-time schedule (no chasing).
- Tests run under the venv: `venv/bin/python -m pytest -q`. TDD; one logical change per commit.

## File Structure

- Create `society/conversations.py` — `Thread`, `ConversationStore` (pure; no kernel/asyncio deps).
- Modify `society/kernel.py` — own a `ConversationStore`; replace `send`/`deliver_pending` with a distance-delayed pending queue that records into threads; unify `say`, add `read_thread`, drop `broadcast`/`pop_message`/`peek_inbox` dispatch; `_build_agent_view` roster; `observe`/`act_on`/`read` thread-logging.
- Modify `society/actions.py` — catalog: remove `broadcast`/`pop_message`/`peek_inbox`, add `read_thread`; `say`/`gesture` `targets` optional.
- Modify `society/agent.py` — `build_view` drops inbox fields.
- Modify `society/stm.py` — remove `inbox`/`inbox_items`.
- Modify `society/persistence.py` — checkpoint `conversations`, drop inbox.
- Modify `society/skills/actions_skill_{zh,en}.md` — one `say`, `read_thread`, roster; remove old actions.
- Create `tests/test_conversations.py`; update `tests/` and `scenarios/*.yaml` kickoff that use removed actions.

---

### Task 1: `conversations.py` — Thread + ConversationStore

**Files:** Create `society/conversations.py`; Test `tests/test_conversations.py`.

**Interfaces — Produces:**
- `class Thread`: `__init__(self, other_id, kind=None)`; `messages: list[dict]`; `unread: int`; `append(self, msg: dict) -> None`; `mark_read(self) -> None`; `recent(self, k: int) -> list[dict]`; `to_dict()/from_dict(d)`.
- `class ConversationStore`: `record(self, owner, other, msg: dict, *, unread_delta=1, kind=None) -> None`; `read(self, owner, other, k=10) -> list[dict]`; `roster(self, owner, colocated_ids: set, agents: dict) -> list[dict]`; `export() -> dict`; `restore(self, data: dict) -> None`.
- A `msg` here is a plain dict `{"sender","kind","content","tick"}` (the thread record — NOT the full Message).

- [ ] **Step 1: Write failing tests**

```python
# tests/test_conversations.py
from society.conversations import Thread, ConversationStore


def _m(sender, content, tick=0, kind="say"):
    return {"sender": sender, "kind": kind, "content": content, "tick": tick}


def test_thread_append_unread_read():
    t = Thread("bob", kind="character")
    t.append(_m("bob", "hi"))
    t.append(_m("bob", "there"))
    assert t.unread == 2 and len(t.messages) == 2
    assert t.recent(1) == [_m("bob", "there")]
    t.mark_read()
    assert t.unread == 0


def test_store_record_both_sides_and_roster():
    s = ConversationStore()
    s.record("alice", "bob", _m("bob", "hi"), unread_delta=1, kind="character")
    s.record("bob", "alice", _m("bob", "hi"), unread_delta=0, kind="character")
    agents = {"bob": type("A", (), {"kind": "character", "name": "Bob"})(),
              "carol": type("A", (), {"kind": "character", "name": "Carol"})()}
    roster = s.roster("alice", colocated_ids={"bob", "carol"}, agents=agents)
    by = {r["other"]: r for r in roster}
    assert by["bob"]["unread"] == 1 and by["bob"]["colocated"] is True
    assert by["bob"]["last_preview"].startswith("hi")
    # carol: co-located but no thread yet -> present with unread 0
    assert by["carol"]["unread"] == 0 and by["carol"]["colocated"] is True


def test_store_read_marks_read_and_export_restore():
    s = ConversationStore()
    s.record("alice", "bob", _m("bob", "hi"))
    assert s.read("alice", "bob", k=10)[0]["content"] == "hi"
    # read marks it read
    assert s.roster("alice", set(), {"bob": type("A", (), {"kind": "character"})()})[0]["unread"] == 0
    s2 = ConversationStore(); s2.restore(s.export())
    assert s2.read("alice", "bob")[0]["content"] == "hi"
```

- [ ] **Step 2: Run → fail** — `venv/bin/python -m pytest tests/test_conversations.py -q`.

- [ ] **Step 3: Implement**

```python
# society/conversations.py
"""Per-interlocutor conversation threads (kernel-held), replacing the STM
FIFO inbox. A ConversationStore maps {owner_id: {other_id: Thread}}; a Thread
is an ordered list of lightweight message records with an unread counter.
Pure data structures -- the kernel does routing/delay. See
docs/superpowers/specs/2026-07-26-conversation-threads-design.md."""


class Thread:
    def __init__(self, other_id, kind=None):
        self.other_id = other_id
        self.kind = kind
        self.messages = []
        self.unread = 0

    def append(self, msg, unread_delta=1):
        self.messages.append(dict(msg))
        self.unread += unread_delta

    def mark_read(self):
        self.unread = 0

    def recent(self, k):
        return [dict(m) for m in self.messages[-k:]] if k else [dict(m) for m in self.messages]

    def to_dict(self):
        return {"other_id": self.other_id, "kind": self.kind,
                "messages": [dict(m) for m in self.messages], "unread": self.unread}

    @classmethod
    def from_dict(cls, d):
        t = cls(d["other_id"], d.get("kind"))
        t.messages = [dict(m) for m in d.get("messages", [])]
        t.unread = d.get("unread", 0)
        return t


class ConversationStore:
    def __init__(self):
        self._threads = {}  # owner -> {other -> Thread}

    def _thread(self, owner, other, kind=None):
        owned = self._threads.setdefault(owner, {})
        t = owned.get(other)
        if t is None:
            t = Thread(other, kind)
            owned[other] = t
        elif kind is not None:
            t.kind = kind
        return t

    def record(self, owner, other, msg, *, unread_delta=1, kind=None):
        self._thread(owner, other, kind).append(msg, unread_delta)

    def read(self, owner, other, k=10):
        t = self._threads.get(owner, {}).get(other)
        if t is None:
            return []
        out = t.recent(k)
        t.mark_read()
        return out

    def roster(self, owner, colocated_ids, agents):
        owned = self._threads.get(owner, {})
        rows = {}
        for other, t in owned.items():
            a = agents.get(other)
            rows[other] = {
                "other": other,
                "kind": t.kind or (getattr(a, "kind", None) if a else None),
                "colocated": other in colocated_ids,
                "unread": t.unread,
                "last_preview": (t.messages[-1]["content"][:40] if t.messages else ""),
            }
        for other in colocated_ids:
            if other == owner or other in rows:
                continue
            a = agents.get(other)
            rows[other] = {"other": other, "kind": getattr(a, "kind", None) if a else None,
                           "colocated": True, "unread": 0, "last_preview": ""}
        return sorted(rows.values(), key=lambda r: (-r["unread"], r["other"]))

    def export(self):
        return {o: {k: t.to_dict() for k, t in threads.items()}
                for o, threads in self._threads.items()}

    def restore(self, data):
        self._threads = {o: {k: Thread.from_dict(td) for k, td in threads.items()}
                         for o, threads in (data or {}).items()}
```

- [ ] **Step 4: Run → pass.**  **Step 5: Commit** — `feat(conversations): Thread + ConversationStore`.

---

### Task 2: Kernel routing — distance-delayed delivery into threads

**Files:** Modify `society/kernel.py`; Test `tests/test_kernel_conversations.py` (new).

**Interfaces:**
- Consumes: `ConversationStore` (Task 1); `self.worldmap.distance(a, b)`, `self.worldmap.default_distance`; `self.presence`.
- Produces: `Kernel.conversations` (a `ConversationStore`); a `_deliver_due(self)` called each tick (replaces `deliver_pending`); `send`/routing enqueues `{msg, recipient, deliver_at}`.

- [ ] **Step 1: Write failing test** (co-located instant + remote delayed + both-sides threads):

```python
# tests/test_kernel_conversations.py
import pytest
from society.actions import Action
from society.agent import Agent
from society.brains.rule_brain import RuleBrain
from society.events import EventLog
from society.kernel import Kernel
from society.stm import STM
from society.worldmap import WorldMap


def char(aid, loc):
    return Agent(aid, "character", RuleBrain(), STM(status={"location": loc}))
def env(aid):
    return Agent(aid, "environment", RuleBrain(), STM())


def _k(agents, edges=None, dd=4):
    envs = [a.id for a in agents if a.kind == "environment"]
    return Kernel({a.id: a for a in agents}, WorldMap(envs, edges=edges, default_distance=dd),
                  EventLog(None))


async def test_say_colocated_instant_both_threads():
    a, b = char("a", "hall"), char("b", "hall")
    k = _k([a, b, env("hall")])
    await k.execute(a, Action("say", {"targets": ["b"], "content": "hi"}))
    k._deliver_due()  # next tick
    assert k.conversations.read("b", "a")[0]["content"] == "hi"   # recipient thread
    assert k.conversations.read("a", "b")[0]["content"] == "hi"   # sender's own copy
    assert b.waiting_until is None  # woken


async def test_say_remote_delayed_by_distance():
    a, b = char("a", "hall"), char("b", "garden")
    k = _k([a, b, env("hall"), env("garden")], edges=[("hall", "garden", 3)])
    await k.execute(a, Action("say", {"targets": ["b"], "content": "letter"}))
    for _ in range(2):
        k.tick += 1; k._deliver_due()
    assert k.conversations.read("b", "a") == []      # not yet (distance 3)
    k.tick += 1; k._deliver_due()
    assert k.conversations.read("b", "a")[0]["content"] == "letter"
```

- [ ] **Step 2: Run → fail.**

- [ ] **Step 3: Implement.** In `Kernel.__init__` add `self.conversations = ConversationStore()` (import it) and `self._pending: list = []` stays but items become `{"msg", "recipient", "deliver_at"}`. Add a routing helper and replace `deliver_pending`:

```python
    def route(self, msg, sender_loc):
        """Enqueue msg to each recipient with a distance-based delay."""
        for rid in msg.recipients:
            r = self.agents.get(rid)
            if r is None:
                self.event_log.append(self.tick, "system", "kernel",
                    {"note": "undeliverable", "recipient": rid, "message_id": msg.id})
                continue
            rloc = r.location()
            if rloc is None or rloc == sender_loc:
                delay = 0
            else:
                d = self.worldmap.distance(sender_loc, rloc)
                delay = d if d is not None else self.worldmap.default_distance
            self._pending.append({"msg": msg, "recipient": rid, "deliver_at": self.tick + delay})

    def _deliver_due(self):
        """Deliver all pending messages whose deliver_at <= current tick into
        per-interlocutor threads (recipient + sender's own copy)."""
        due = [p for p in self._pending if p["deliver_at"] <= self.tick]
        self._pending = [p for p in self._pending if p["deliver_at"] > self.tick]
        delivered = False
        for p in due:
            msg, rid = p["msg"], p["recipient"]
            recipient = self.agents.get(rid)
            if recipient is None:
                continue
            rec = {"sender": msg.sender, "kind": msg.kind, "content": msg.content, "tick": self.tick}
            skind = getattr(recipient, "kind", None)
            self.conversations.record(rid, msg.sender, rec, unread_delta=1,
                                      kind=getattr(self.agents.get(msg.sender), "kind", None))
            self.conversations.record(msg.sender, rid, rec, unread_delta=0, kind=skind)
            if msg.wake:
                recipient.waiting_until = None
            delivered = True
            self.event_log.append(self.tick, "message", msg.sender, {"message": msg.to_dict(), "recipient": rid})
            if self.metrics is not None and msg.kind in ("say", "gesture"):
                on_message = getattr(self.metrics, "on_message", None)
                if on_message is not None:
                    on_message(msg.sender, rid, msg.kind)
        return delivered
```

Update the main loop (`run`): replace the `deliver_pending()` call with `self._deliver_due()`. Keep `send(msg)` as a thin wrapper that appends with delay 0 for internal/system messages (arrival/kickoff) OR route them too — for system messages (arrival/departure) keep delay 0: have `send` call `self.route(msg, sender_loc=<recipient's own loc>)` so system msgs are instant; simplest: `send(msg)` → for each recipient enqueue `deliver_at=self.tick` (delay 0). Provide `send` as: `self._pending.append({"msg": msg, "recipient": rid, "deliver_at": self.tick})` for every recipient (system/arrival stay instant).

- [ ] **Step 4: Run → pass** (both tests). **Step 5: Commit** — `feat(kernel): distance-delayed delivery into conversation threads`.

---

### Task 3: Unify `say`, add `read_thread`, remove `broadcast`/`pop_message`/`peek_inbox`

**Files:** Modify `society/actions.py` (catalog), `society/kernel.py` (execute dispatch + `_execute_say_or_gesture` + new `_execute_read_thread`); Test `tests/test_kernel_conversations.py` + `tests/test_actions*`.

**Interfaces:** Consumes Task 2's `route`. Produces: unified `say`/`gesture` execution; `read_thread`.

- [ ] **Step 1: Failing tests**

```python
async def test_say_default_targets_all_colocated():
    a, b, c = char("a", "hall"), char("b", "hall"), char("c", "hall")
    k = _k([a, b, c, env("hall")])
    await k.execute(a, Action("say", {"content": "hello room"}))   # no targets
    k._deliver_due()
    assert k.conversations.read("b", "a") and k.conversations.read("c", "a")


async def test_say_no_targets_no_colocated_is_noop():
    a = char("a", "hall")
    k = _k([a, env("hall")])
    r = await k.execute(a, Action("say", {"content": "..."}))
    assert r.ok is True and r.data == {"delivered": 0}


async def test_read_thread_returns_and_marks_read():
    a, b = char("a", "hall"), char("b", "hall")
    k = _k([a, b, env("hall")])
    await k.execute(a, Action("say", {"targets": ["b"], "content": "hi"}))
    k._deliver_due()
    got = await k.execute(b, Action("read_thread", {"target": "a"}))
    assert got.ok and got.data[0]["content"] == "hi"
    # roster now shows unread 0
    assert k.conversations.roster("b", set(), k.agents)[0]["unread"] == 0


async def test_removed_actions_rejected():
    from society.actions import validate_action
    assert validate_action(Action("broadcast", {"targets": [], "content": "x"})) is not None
    assert validate_action(Action("pop_message", {})) is not None
    assert validate_action(Action("peek_inbox", {})) is not None
```

- [ ] **Step 2: Run → fail.**

- [ ] **Step 3: Implement.**
  - `society/actions.py`: remove `"broadcast"` from `ASYNC_ACTIONS`; remove `"pop_message"`,`"peek_inbox"` from `SYNC_ACTIONS`; add `"read_thread"` to `SYNC_ACTIONS`; in `REQUIRED_PARAMS` remove `broadcast`/`pop_message`/`peek_inbox`, add `"read_thread": ["target"]`, and change `"say": ["content"]`, `"gesture": ["content"]` (targets now optional — drop from required; keep the list-type check on targets when present).
  - `society/kernel.py` `execute` dispatch: remove the `pop_message`/`peek_inbox` branches; add `if name == "read_thread": return self._execute_read_thread(agent, action)`.
  - Rewrite `_execute_say_or_gesture` → `_execute_say`: resolve `targets` (default = co-located characters via `self._colocated_view(agent)` filtered to kind character, or `presence`); if targets empty → `return ActionResult(True, data={"delivered": 0})`; build one `Message(kind=action.name, recipients=targets, wake=params.get("wake", True))`; `self.route(msg, sender_loc)`; return `ActionResult(True, data={"delivered": len(targets)})`. No co-location gate. Parse `wake` leniently (stringized bool) as today.
  - Add `_execute_read_thread(agent, action)`: `target=params["target"]`, `k=params.get("k", 10)`; return `ActionResult(True, data=self.conversations.read(agent.id, target, k))`.

- [ ] **Step 4: Run → pass.** **Step 5: Commit** — `feat(actions): unify say, add read_thread, remove broadcast/pop_message/peek_inbox`.

---

### Task 4: View roster + remove STM inbox

**Files:** Modify `society/kernel.py` (`_build_agent_view`), `society/agent.py` (`build_view`), `society/stm.py` (remove inbox). Test: extend `tests/test_kernel_conversations.py` / `tests/test_alias_and_view.py`.

- [ ] **Step 1: Failing test** — a view has `conversations` (roster) and NO `inbox_head`/`inbox_size`:

```python
async def test_view_has_conversation_roster_not_inbox():
    a, b = char("a", "hall"), char("b", "hall")
    k = _k([a, b, env("hall")])
    await k.execute(a, Action("say", {"targets": ["b"], "content": "hi"}))
    k._deliver_due()
    v = k._build_agent_view(b)
    assert "conversations" in v and "inbox_head" not in v and "inbox_size" not in v
    assert any(r["other"] == "a" and r["unread"] == 1 for r in v["conversations"])
```

- [ ] **Step 2: Run → fail.**
- [ ] **Step 3: Implement.**
  - `_build_agent_view`: after `colocated`, add `view["conversations"] = self.conversations.roster(agent.id, {c["id"] for c in view["colocated"]}, self.agents)`.
  - `society/agent.py` `build_view`: remove `inbox_size`, `inbox_head`, and the `inbox_items()` usage.
  - `society/stm.py`: remove `self.inbox = asyncio.Queue()` and `inbox_items`. Grep for remaining `.inbox`/`inbox_items` uses in kernel/persistence and remove/replace (Task 2/3 removed the pop paths; any leftover is a compile break to fix here).
- [ ] **Step 4: Run → pass;** then full suite `venv/bin/python -m pytest -q` (expect failures only in tests/scenarios still using removed actions — those are Task 8).
- [ ] **Step 5: Commit** — `feat(view): conversation roster; remove STM inbox`.

---

### Task 5: `observe`/`act_on`/`read` log into threads

**Files:** Modify `society/kernel.py` (`_execute_observe`, `_execute_act_on`, `_execute_read`). Test: extend `tests/test_kernel_conversations.py`.

- [ ] Each of the three, after computing its (unchanged) return value, records one message into the ACTOR's thread with the target env/carrier: `self.conversations.record(agent.id, target_id, {"sender": agent.id, "kind": action.name, "content": <short desc of what was done/seen/read>, "tick": self.tick}, unread_delta=0, kind=<target kind>)`. Return values unchanged.
- Test: after `act_on(env, content="推门")`, `conversations.read(actor, env_id)` contains an `act_on` record; the `act_on` ActionResult is unchanged. Same for `read`(carrier) and `observe`(env).
- Commit — `feat(kernel): log observe/act_on/read into interlocutor threads`.

---

### Task 6: Skill docs

**Files:** Modify `society/skills/actions_skill_zh.md`, `society/skills/actions_skill_en.md`.

- [ ] Replace the `say`/`gesture`/`broadcast` section with the unified `say` (targets optional → co-located default; remote targets = delayed letter by distance; wakes recipients; no-op if alone) + `gesture` (non-verbal twin). Remove `broadcast`, `pop_message`, `peek_inbox`. Add `read_thread(target, k?)` and describe the `conversations` roster in the view (unread + preview; open a thread with read_thread). Keep zh/en synced; keep the remember/goal guidance intact. Update the "pipeline" examples that referenced pop_message → read_thread + the roster.
- Commit — `docs(skills): unified say + read_thread + conversation roster`.

---

### Task 7: Persistence

**Files:** Modify `society/persistence.py`. Test: extend `tests/test_persistence.py`.

- [ ] `_build_checkpoint_dict`: add `"conversations": kernel.conversations.export()`; remove any per-agent inbox snapshot. `restore_society`: `kernel.conversations.restore(ckpt.get("conversations", {}))`; remove inbox restore. Test: a kernel with some threads → checkpoint → restore → same threads/unread (`conversations.read` round-trips).
- Commit — `feat(persistence): checkpoint conversation threads`.

---

### Task 8: Scenario + test cleanup; suite green

**Files:** `scenarios/*.yaml` (kickoff `broadcast`→`say`), any tests using removed actions.

- [ ] Grep `broadcast|pop_message|peek_inbox` across `scenarios/` and `tests/`; convert kickoff `kind: broadcast` to `say`; rewrite/remove tests asserting the old inbox/pop behavior (superseded by the thread tests). Run `venv/bin/python -m pytest -q` → all green.
- Commit — `chore: migrate scenarios/tests off removed messaging actions`.

---

## Self-Review

- **Spec coverage:** kernel-held store → T1/T2; roster view → T4; read_thread → T3; unified say (default co-located, distance delay, wake, no-op) → T3 + constraints; gesture separate → T3; env/carrier threading → T5; remove broadcast/pop/peek → T3; STM inbox removal → T4; persistence → T7; docs → T6; scenario/test cleanup → T8. Covered.
- **Placeholders:** T1-T4 fully coded; T5-T8 specify files, exact edits, and test intent (the executing subagent writes the concrete edits) — acceptable for mechanical/doc tasks.
- **Type consistency:** thread record dict `{sender,kind,content,tick}` used uniformly (store, kernel delivery, read_thread, env-logging); `ConversationStore` method names identical across T1→T2→T3→T4→T7; `route`/`_deliver_due` names consistent T2→T3.
- **Scope:** Effort B only; memory layer untouched.
