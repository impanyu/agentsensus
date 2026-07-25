"""Task S1 -- action-layer redesign: unified {targets, content} shapes for
gesture/act_on, Message.wake + broadcast, and the four affiliated-memory
CRUD actions. See scratchpad/taskS1-actions-brief.md."""

import uuid

from society.actions import Action, validate_action
from society.agent import Agent
from society.brains.rule_brain import RuleBrain
from society.events import EventLog
from society.kernel import Kernel
from society.ltm import SharedMemory
from society.stm import STM
from society.worldmap import WorldMap
from tests.helpers import afake_embed


def build(agents, edges=None, shared=None):
    envs = [a.id for a in agents if a.kind == "environment"]
    return Kernel({a.id: a for a in agents},
                  WorldMap(envs, edges=edges, default_distance=4),
                  EventLog(None), shared_memory=shared)


def char(aid, loc, fn=None, goals=None):
    return Agent(aid, "character", RuleBrain(fn=fn),
                 STM(status={"location": loc}, goals=goals or []))


def env(aid, act_on_fn=None):
    return Agent(aid, "environment", RuleBrain(act_on_fn=act_on_fn), STM())


def fresh_shared():
    return SharedMemory(afake_embed, llm=None, collection_name=f"t_{uuid.uuid4().hex[:8]}")


# ----------------------------------------------------------------------
# 1. Unified {targets, content} shapes for gesture/act_on
# ----------------------------------------------------------------------

def test_gesture_new_shape_validates_old_shape_rejected():
    assert validate_action(Action("gesture", {"targets": ["b"], "content": "wave"})) is None
    err = validate_action(Action("gesture", {"targets": ["b"], "description": "wave"}))
    assert err and "content" in err


def test_act_on_new_shape_validates_old_shape_rejected():
    assert validate_action(Action("act_on", {"targets": ["hall"], "content": "push door"})) is None
    err = validate_action(Action("act_on", {"target": "hall", "description": "push door"}))
    assert err and "targets" in err


async def test_gesture_executes_and_delivers_with_default_wake():
    a, b = char("a", "hall"), char("b", "hall")
    k = build([a, b, env("hall")])
    r = await k.execute(a, Action("gesture", {"targets": ["b"], "content": "wave"}))
    assert r.ok
    k.deliver_pending()
    msg = b.stm.inbox.get_nowait()
    assert msg.kind == "gesture" and msg.content == "wave" and msg.wake is True


async def test_act_on_requires_exactly_one_colocated_environment_target():
    a = char("a", "hall")
    hall = env("hall")
    k = build([a, hall])

    r_empty = await k.execute(a, Action("act_on", {"targets": [], "content": "push"}))
    assert r_empty.ok is False

    r_many = await k.execute(a, Action("act_on", {"targets": ["hall", "hall"], "content": "push"}))
    assert r_many.ok is False

    r_ok = await k.execute(a, Action("act_on", {"targets": ["hall"], "content": "push"}))
    assert r_ok.ok
    # Task R (revert of S2): act_on is SYNCHRONOUS -- no Message, no next-
    # tick round trip. hall (a passive, function-driven environment) is
    # never even scheduled to react; without shared_memory configured the
    # act_on just succeeds with a note (see test_unified_agents.py for the
    # shared_memory-backed deposit).
    assert r_ok.data["env"] == "hall" and r_ok.data["recorded"] == "push"
    k.deliver_pending()
    assert a.stm.inbox.qsize() == 0
    assert hall.stm.inbox.qsize() == 0


# ----------------------------------------------------------------------
# 2. broadcast + Message.wake
# ----------------------------------------------------------------------

def test_broadcast_validates_wake_is_optional():
    assert validate_action(Action("broadcast", {"targets": ["b"], "content": "fyi"})) is None
    assert validate_action(
        Action("broadcast", {"targets": ["b"], "content": "fyi", "wake": True})
    ) is None
    err = validate_action(Action("broadcast", {"content": "fyi"}))
    assert err and "targets" in err


async def test_broadcast_delivers_to_all_targets_next_tick_default_wake_false():
    a, b, c = char("a", "hall"), char("b", "hall"), char("c", "hall")
    k = build([a, b, c, env("hall")])
    r = await k.execute(a, Action("broadcast", {"targets": ["b", "c"], "content": "listen up"}))
    assert r.ok
    assert b.stm.inbox.qsize() == 0 and c.stm.inbox.qsize() == 0   # not delivered yet
    k.deliver_pending()
    assert b.stm.inbox.qsize() == 1 and c.stm.inbox.qsize() == 1
    mb, mc = b.stm.inbox.get_nowait(), c.stm.inbox.get_nowait()
    assert mb.kind == "broadcast" and mb.content == "listen up" and mb.wake is False
    assert mc.kind == "broadcast" and mc.wake is False


async def test_broadcast_wake_false_does_not_wake_a_sleeping_agent():
    # Task R (awake-based model): a goalless, never-waited character is
    # eligible by default (no goal-emptiness requirement any more), so to
    # exercise "wake=False doesn't wake" we must first put b to sleep via
    # `wait`, then confirm a wake=False broadcast doesn't rouse it.
    a, b = char("a", "hall"), char("b", "hall")
    k = build([a, b, env("hall")])
    await k.execute(b, Action("wait", {}))
    assert k.is_eligible(b) is False

    await k.execute(a, Action("broadcast", {"targets": ["b"], "content": "psst"}))
    k.deliver_pending()

    assert b.stm.inbox.qsize() == 1
    assert k.is_eligible(b) is False


async def test_broadcast_wake_false_does_not_clear_waiting_until():
    a = char("a", "hall")
    b = char("b", "hall", goals=["g"])
    k = build([a, b, env("hall")])
    b.waiting_until = -1   # forever-wait

    await k.execute(a, Action("broadcast", {"targets": ["b"], "content": "psst"}))
    k.deliver_pending()

    assert b.waiting_until == -1              # not cleared by a wake=False delivery
    assert k.is_eligible(b) is False           # still asleep despite nonempty goals


async def test_agent_awake_for_other_reason_can_still_pop_wake_false_message():
    a = char("a", "hall")
    b = char("b", "hall", goals=["g"])   # eligible by default (awake model), not via the message
    k = build([a, b, env("hall")])

    await k.execute(a, Action("broadcast", {"targets": ["b"], "content": "psst"}))
    k.deliver_pending()

    assert k.is_eligible(b) is True
    r = await k.execute(b, Action("pop_message", {}))
    assert r.ok and r.data["kind"] == "broadcast"


async def test_broadcast_wake_true_wakes_agent():
    # Task R: put b to sleep first (awake-by-default means "eligible before
    # the broadcast" is no longer informative on its own).
    a, b = char("a", "hall"), char("b", "hall")
    k = build([a, b, env("hall")])
    await k.execute(b, Action("wait", {}))
    assert k.is_eligible(b) is False

    await k.execute(a, Action("broadcast", {"targets": ["b"], "content": "fire!", "wake": True}))
    k.deliver_pending()

    assert k.is_eligible(b) is True
    msg = b.stm.inbox.get_nowait()
    assert msg.kind == "broadcast" and msg.wake is True


async def test_say_still_wakes_by_default_end_to_end():
    a, b = char("a", "hall"), char("b", "hall")
    k = build([a, b, env("hall")])
    await k.execute(b, Action("wait", {}))
    assert k.is_eligible(b) is False

    await k.execute(a, Action("say", {"targets": ["b"], "content": "hi"}))
    k.deliver_pending()

    assert k.is_eligible(b) is True
    msg = b.stm.inbox.get_nowait()
    assert msg.wake is True


# ----------------------------------------------------------------------
# 3. wait: forever-sleep is interrupted only by a wake=True message
#    (behavior unchanged -- see also test_kernel_core's timeout test)
# ----------------------------------------------------------------------

async def test_wait_forever_interrupted_only_by_wake_true_message():
    a = char("a", "hall")
    b = char("b", "hall", goals=["g"])
    k = build([a, b, env("hall")])

    await k.execute(b, Action("wait", {}))
    assert b.waiting_until == -1
    assert k.is_eligible(b) is False

    # a wake=False broadcast does not interrupt the forever-wait
    await k.execute(a, Action("broadcast", {"targets": ["b"], "content": "psst"}))
    k.deliver_pending()
    assert b.waiting_until == -1
    assert k.is_eligible(b) is False

    # a say (wake=True by default) does interrupt it
    await k.execute(a, Action("say", {"targets": ["b"], "content": "wake up"}))
    k.deliver_pending()
    assert b.waiting_until is None
    assert k.is_eligible(b) is True


# ----------------------------------------------------------------------
# 4. Affiliated-memory CRUD (add/remove/set/get_affiliated)
# ----------------------------------------------------------------------

async def test_affiliated_crud_add_remove_set_get():
    shared = fresh_shared()
    a = char("alice", "hall")
    k = build([a, env("hall")], shared=shared)

    r1 = await shared.remember_atomic(["alice", "bob"], "国王驾崩")
    r2 = await shared.remember_atomic(["alice"], "王后哭泣")
    r3 = await shared.remember_atomic(["alice"], "百姓戴孝")
    m1, m2, m3 = r1["id"], r2["id"], r3["id"]

    add = await k.execute(a, Action("add_affiliated", {"memory_id": m1, "affiliated": [m2, m3]}))
    assert add.ok
    assert shared.get_affiliations(m1) == sorted([m2, m3])

    got = await k.execute(a, Action("get_affiliated", {"memory_id": m1}))
    assert got.ok
    assert {d["id"] for d in got.data} == {m2, m3}
    texts = {d["id"]: d["text"] for d in got.data}
    assert texts[m2] == "王后哭泣" and texts[m3] == "百姓戴孝"

    rem = await k.execute(a, Action("remove_affiliated", {"memory_id": m1, "affiliated": [m2]}))
    assert rem.ok
    assert shared.get_affiliations(m1) == [m3]

    setr = await k.execute(a, Action("set_affiliated", {"memory_id": m1, "affiliated": [m2]}))
    assert setr.ok
    assert shared.get_affiliations(m1) == [m2]   # m3 removed, m2 added -- full replace


async def test_affiliated_crud_rejects_non_owner():
    shared = fresh_shared()
    alice, bob = char("alice", "hall"), char("bob", "hall")
    k = build([alice, bob, env("hall")], shared=shared)

    r1 = await shared.remember_atomic(["alice"], "秘密日记")
    m1 = r1["id"]

    r = await k.execute(bob, Action("add_affiliated", {"memory_id": m1, "affiliated": []}))
    assert r.ok is False and "not an owner" in r.error


async def test_get_affiliated_skips_dangling_ids_silently():
    shared = fresh_shared()
    a = char("alice", "hall")
    k = build([a, env("hall")], shared=shared)

    r1 = await shared.remember_atomic(["alice"], "国王驾崩")
    m1 = r1["id"]
    shared.add_affiliations(m1, ["ghost-id-does-not-exist"])

    got = await k.execute(a, Action("get_affiliated", {"memory_id": m1}))
    assert got.ok and got.data == []


async def test_affiliated_crud_unknown_memory_id_errors():
    shared = fresh_shared()
    a = char("alice", "hall")
    k = build([a, env("hall")], shared=shared)

    r = await k.execute(a, Action("get_affiliated", {"memory_id": "does-not-exist"}))
    assert r.ok is False


# ----------------------------------------------------------------------
# Review regressions: input-validation hardening (S1 review)
# ----------------------------------------------------------------------

async def test_broadcast_stringified_wake_false_stays_false():
    # LLM brains sometimes stringify booleans; bool("false") is True, which
    # would silently invert the sleep economy. "false" must mean False.
    a, b = char("alice", "hall"), char("bob", "hall")
    k = build([a, b, env("hall")])
    r = await k.execute(a, Action("broadcast", {"targets": ["bob"], "content": "hi", "wake": "false"}))
    assert r.ok
    k.deliver_pending()
    (msg,) = b.stm.inbox_items()
    assert msg.wake is False


async def test_broadcast_non_bool_wake_rejected():
    a, b = char("alice", "hall"), char("bob", "hall")
    k = build([a, b, env("hall")])
    r = await k.execute(a, Action("broadcast", {"targets": ["bob"], "content": "hi", "wake": 123}))
    assert not r.ok and "boolean" in r.error


async def test_affiliated_bare_string_rejected_no_corruption():
    # A bare string would be iterated char-by-char into the affiliation set.
    shared = fresh_shared()
    a = char("alice", "hall")
    k = build([a, env("hall")], shared=shared)
    m = await shared.remember_atomic(["alice"], "国王驾崩")
    r = await k.execute(a, Action("add_affiliated", {"memory_id": m["id"], "affiliated": "xyz123"}))
    assert not r.ok and "list" in r.error
    assert shared.get_affiliations(m["id"]) == []
