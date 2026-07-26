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


async def test_view_has_conversation_roster_not_inbox():
    a, b = char("a", "hall"), char("b", "hall")
    k = _k([a, b, env("hall")])
    await k.execute(a, Action("say", {"targets": ["b"], "content": "hi"}))
    k._deliver_due()
    v = k._build_agent_view(b)
    assert "conversations" in v and "inbox_head" not in v and "inbox_size" not in v
    assert any(r["other"] == "a" and r["unread"] == 1 for r in v["conversations"])


# --- Task 5: observe/act_on/read log into the ACTOR's own thread with the
# target env/carrier, unread_delta=0 (it's the actor's own action, already
# "read"), without changing the actions' existing return values. ---

async def test_act_on_logs_into_actor_thread_without_changing_return_value():
    a = char("a", "hall")
    k = _k([a, env("hall")])
    r = await k.execute(a, Action("act_on", {"targets": ["hall"], "content": "推门"}))
    assert r.ok is True
    assert r.data == {"env": "hall", "recorded": "推门", "note": "no shared memory"}
    thread = k.conversations.read("a", "hall")
    assert len(thread) == 1
    rec = thread[0]
    assert rec["kind"] == "act_on" and rec["sender"] == "a" and "推门" in rec["content"]
    assert rec["tick"] == k.tick
    # own action is already "read" -- must not bump unread
    assert k.conversations.roster("a", set(), k.agents)[0]["unread"] == 0


async def test_act_on_failure_does_not_log():
    a = char("a", "hall")
    b = char("b", "garden")
    k = _k([a, b, env("hall"), env("garden")])
    r = await k.execute(a, Action("act_on", {"targets": ["garden"], "content": "推门"}))
    assert r.ok is False
    assert k.conversations.read("a", "garden") == []


async def test_read_logs_into_actor_thread_without_changing_return_value():
    from society.brains.retrieval_brain import RetrievalBrain
    a = char("a", "hall")
    book = Agent("book", "info_carrier", RetrievalBrain("宝玉衔玉而生。"), STM(status={"location": "hall"}))
    k = _k([a, book, env("hall")])
    r = await k.execute(a, Action("read", {"target": "book", "query": "宝玉"}))
    assert r.ok is True
    assert r.data == []  # no shared_memory configured -- unchanged behavior
    thread = k.conversations.read("a", "book")
    assert len(thread) == 1
    rec = thread[0]
    assert rec["kind"] == "read" and rec["sender"] == "a" and "宝玉" in rec["content"]


async def test_read_failure_does_not_log():
    from society.brains.retrieval_brain import RetrievalBrain
    a = char("a", "garden")
    book = Agent("book", "info_carrier", RetrievalBrain("宝玉衔玉而生。"), STM(status={"location": "hall"}))
    k = _k([a, book, env("hall"), env("garden")])
    r = await k.execute(a, Action("read", {"target": "book", "query": "宝玉"}))
    assert r.ok is False
    assert k.conversations.read("a", "book") == []


async def test_observe_logs_into_actor_thread_without_changing_return_value():
    a, b = char("a", "hall"), char("b", "hall")
    k = _k([a, b, env("hall")])
    r = await k.execute(a, Action("observe", {"target": "hall"}))
    assert r.ok is True
    assert r.data["kind"] == "environment"
    assert [o["id"] for o in r.data["occupants"]] == ["b"]
    thread = k.conversations.read("a", "hall")
    assert len(thread) == 1
    rec = thread[0]
    assert rec["kind"] == "observe" and rec["sender"] == "a" and "hall" in rec["content"]


async def test_observe_failure_does_not_log():
    a = char("a", "hall")
    k = _k([a, env("hall")])
    r = await k.execute(a, Action("observe", {"target": "ghost"}))
    assert r.ok is False
    assert k.conversations.read("a", "ghost") == []


# --- C1 regression: run()'s quiescence-break/fast-forward must account for
# self._pending (in-flight remote messages), not just awake/delivered/
# transit/waiting_timers. Before the fix, a lone agent's remote `say` to an
# asleep recipient at a distance was either declared quiescent (letter
# silently dropped, wake never applied) or the tick was fast-forwarded PAST
# deliver_at (late delivery -- a distance-delay violation). This drives via
# `kernel.run()` itself (not manual `_deliver_due()` calls, as every other
# test in this file does), because that's the loop the bug actually lives
# in -- a manual-stepping test would never exercise it. ---

async def test_run_loop_delivers_remote_letter_and_wakes_recipient():
    calls = {"n": 0}

    def a_brain(view):
        calls["n"] += 1
        if calls["n"] == 1:
            return Action("say", {"targets": ["b"], "content": "letter", "wake": True})
        return Action("wait")

    a = Agent("a", "character", RuleBrain(a_brain), STM(status={"location": "hall"}))
    b = char("b", "garden")
    # Asleep "forever" (only a wake=True message clears this) -- the
    # recipient scenario from the bug report: awake=[] and delivered=False
    # for the ticks the letter is in flight, which is exactly what used to
    # trip the (pre-fix) quiescence-break/fast-forward.
    b.waiting_until = -1

    k = _k([a, b, env("hall"), env("garden")], edges=[("hall", "garden", 3)])

    result = await k.run(max_ticks=4)

    thread = k.conversations.read("b", "a")
    assert len(thread) == 1, "letter dropped -- quiescence-break fired before delivery"
    assert thread[0]["content"] == "letter"
    # sent at tick 0, distance 3 -> must land exactly at tick 3: neither
    # dropped (never arrives) nor late (fast-forwarded past deliver_at).
    assert thread[0]["tick"] == 3, "delivered off-schedule (not exactly at deliver_at)"
    assert b.waiting_until is None, "recipient never woken -- wake was lost with the letter"
    assert result["stop_reason"] == "max_ticks"


# --- M1: system messages (kernel arrival/departure/departing notices) must
# not create a "kernel"-owned conversation thread, nor a thread-with-
# "kernel" in any agent's own thread map -- but the arrival wake (and the
# event-log record) must still happen. ---

async def test_move_arrival_does_not_create_kernel_threads_but_still_wakes():
    a = char("a", "hall")
    a.waiting_until = -1  # asleep beforehand, to prove arrival wakes it
    k = _k([a, env("hall"), env("garden")], edges=[("hall", "garden", 1)])

    r = await k.execute(a, Action("move", {"destination": "garden"}))
    assert r.ok is True

    # Advance one tick and run the same process-arrivals/deliver-due
    # sequence run() itself uses, so the transit completes and the
    # kernel-internal system messages (departing/arrived/departed) flow
    # through _deliver_due().
    k.tick += 1
    k._process_arrivals()
    k._deliver_due()

    assert a.location() == "garden"
    assert a.waiting_until is None  # arrival wake still fired

    assert "kernel" not in k.conversations._threads, "a 'kernel'-owned thread was created"
    for owner, threads in k.conversations._threads.items():
        assert "kernel" not in threads, f"{owner} got a thread-with-'kernel'"


# --- M2: a bare `say` into an empty room delivers to nobody and must not
# bump the speaker's remember-hint backlog -- nothing was actually said to
# anyone. (`_apply` is the layer that maintains `_unremembered`; `execute()`
# alone -- used by every other test above -- never touches it, so this test
# calls `_apply` directly, same as the existing `_unremembered` tests in
# tests/test_liveness_s4.py.) ---

async def test_bare_say_into_empty_room_does_not_bump_unremembered():
    a = char("a", "hall")
    k = _k([a, env("hall")])
    await k._apply(a, Action("say", {"content": "..."}), None)
    assert k._unremembered.get("a", 0) == 0
