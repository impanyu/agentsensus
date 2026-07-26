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
