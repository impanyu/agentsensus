"""Task S4 -- simulation liveness: goal-lifecycle guidance (goal_hint +
skill docs) and the `wake_all_characters` config-gated mode. See
scratchpad/taskS4-liveness-brief.md."""

import json

import pytest
import yaml

from society.agent import Agent
from society.brains.rule_brain import RuleBrain
from society.events import EventLog
from society.kernel import Kernel
from society.scenario import build_society, load_scenario
from society.stm import STM
from society.worldmap import WorldMap
from tests.helpers import FakeLLM, afake_embed


def char(aid, loc, goals=None, archived=False):
    return Agent(aid, "character", RuleBrain(), STM(status={"location": loc}, goals=goals or []),
                 archived=archived)


def env(aid):
    return Agent(aid, "environment", RuleBrain(), STM())


def carrier(aid, loc):
    return Agent(aid, "info_carrier", RuleBrain(), STM(status={"location": loc}))


def build(agents, config=None):
    envs = [a.id for a in agents if a.kind == "environment"]
    return Kernel({a.id: a for a in agents}, WorldMap(envs, default_distance=4),
                  EventLog(None), config=config)


# ----------------------------------------------------------------------
# Fix 1: goal_hint text pushes goal-first
# ----------------------------------------------------------------------

def test_goal_hint_zh_mentions_push_goal_first():
    assert "push_goal" in Kernel._GOAL_HINT_ZH
    # must instruct pushing a goal BEFORE popping the message so the agent
    # stays eligible -- not a bare pop_message/recall-then-stop.
    assert "先" in Kernel._GOAL_HINT_ZH and "push_goal" in Kernel._GOAL_HINT_ZH
    assert "pop" in Kernel._GOAL_HINT_ZH.lower()


def test_goal_hint_en_mentions_push_goal_first():
    assert "push_goal" in Kernel._GOAL_HINT_EN
    assert "first" in Kernel._GOAL_HINT_EN.lower()
    assert "pop" in Kernel._GOAL_HINT_EN.lower()


# ----------------------------------------------------------------------
# Fix 2: wake_all_characters
# ----------------------------------------------------------------------

async def test_wake_all_makes_idle_character_eligible():
    a = char("a", "hall")   # empty goals, empty inbox, not waiting
    k = build([a, env("hall")], config={"wake_all_characters": True})
    assert k.is_eligible(a) is True


async def test_wake_all_does_not_make_idle_environment_eligible():
    hall = env("hall")
    k = build([char("a", "hall"), hall], config={"wake_all_characters": True})
    assert k.is_eligible(hall) is False


async def test_wake_all_does_not_make_idle_carrier_eligible():
    book = carrier("book", "hall")
    k = build([char("a", "hall"), env("hall"), book], config={"wake_all_characters": True})
    assert k.is_eligible(book) is False


async def test_wake_all_archived_character_still_ineligible():
    a = char("a", "hall", archived=True)
    k = build([a, env("hall")], config={"wake_all_characters": True})
    assert k.is_eligible(a) is False


async def test_wake_all_transit_character_still_ineligible():
    a = char("a", "hall")
    a.transit = {"dest": "garden", "arrive_at": 5}
    k = build([a, env("hall")], config={"wake_all_characters": True})
    assert k.is_eligible(a) is False


async def test_wake_all_false_idle_character_still_ineligible():
    a = char("a", "hall")
    k = build([a, env("hall")], config={"wake_all_characters": False})
    assert k.is_eligible(a) is False


async def test_wake_all_absent_from_config_idle_character_still_ineligible():
    a = char("a", "hall")
    k = build([a, env("hall")], config={})
    assert k.is_eligible(a) is False


# ----------------------------------------------------------------------
# Plumbing: build_society -> kernel.config, run_sim override
# ----------------------------------------------------------------------

def _scen(wake_all=None):
    cfg = {
        "scenario": "s4_plumbing",
        "language": "zh",
        "defaults": {"stats_interval": 1000},
        "agents": [
            {"id": "worker", "kind": "character", "brain": "rule", "goals": ["work"]},
        ],
    }
    if wake_all is not None:
        cfg["defaults"]["wake_all_characters"] = wake_all
    return cfg


async def test_build_society_threads_wake_all_characters_true_into_kernel_config():
    cfg = _scen(wake_all=True)
    llm = FakeLLM(fn=lambda p, s=None: '{"action": "noop", "params": {}}')
    kernel = await build_society(cfg, llm=llm, embed_fn=afake_embed, event_log=EventLog(None))
    assert kernel.config.get("wake_all_characters") is True


async def test_build_society_defaults_wake_all_characters_false():
    cfg = _scen(wake_all=None)
    llm = FakeLLM(fn=lambda p, s=None: '{"action": "noop", "params": {}}')
    kernel = await build_society(cfg, llm=llm, embed_fn=afake_embed, event_log=EventLog(None))
    assert kernel.config.get("wake_all_characters", False) is False


async def test_run_sim_override_wins_over_scenario_default(tmp_path, monkeypatch):
    from society.actions import Action
    from experiments.run_sim import run_sim

    async def scripted_decide(self, view):
        return Action("noop", {})
    monkeypatch.setattr(RuleBrain, "decide", scripted_decide)

    cfg = _scen(wake_all=False)   # scenario default False
    spath = tmp_path / "scen.yaml"
    spath.write_text(yaml.safe_dump(cfg, allow_unicode=True), encoding="utf-8")

    captured = {}
    orig_build_society = build_society

    async def spy_build_society(*args, **kwargs):
        kernel = await orig_build_society(*args, **kwargs)
        captured["kernel"] = kernel
        return kernel

    monkeypatch.setattr("experiments.run_sim.build_society", spy_build_society)

    llm = FakeLLM(fn=lambda p, s=None: '{"action": "wait", "params": {}}')
    await run_sim(
        str(spath), "consensus", str(tmp_path / "out"),
        max_ticks=1, llm=llm, embed_fn=afake_embed,
        wake_all_characters=True,
    )
    # kernel.config is checked AFTER run_sim finishes (not inside the spy,
    # which fires before run_sim applies the override) so this asserts the
    # override actually took effect, not just the scenario default.
    assert captured["kernel"].config.get("wake_all_characters") is True


async def test_run_sim_none_override_uses_scenario_default(tmp_path, monkeypatch):
    from society.actions import Action
    from experiments.run_sim import run_sim

    async def scripted_decide(self, view):
        return Action("noop", {})
    monkeypatch.setattr(RuleBrain, "decide", scripted_decide)

    cfg = _scen(wake_all=True)   # scenario default True
    spath = tmp_path / "scen.yaml"
    spath.write_text(yaml.safe_dump(cfg, allow_unicode=True), encoding="utf-8")

    captured = {}
    orig_build_society = build_society

    async def spy_build_society(*args, **kwargs):
        kernel = await orig_build_society(*args, **kwargs)
        captured["kernel"] = kernel
        return kernel

    monkeypatch.setattr("experiments.run_sim.build_society", spy_build_society)

    llm = FakeLLM(fn=lambda p, s=None: '{"action": "wait", "params": {}}')
    await run_sim(
        str(spath), "consensus", str(tmp_path / "out"),
        max_ticks=1, llm=llm, embed_fn=afake_embed,
        wake_all_characters=None,
    )
    assert captured["kernel"].config.get("wake_all_characters") is True
