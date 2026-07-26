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
