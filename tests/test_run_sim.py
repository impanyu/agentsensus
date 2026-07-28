import json
import os

import pytest
import yaml

from society.actions import Action
from society.brains.rule_brain import RuleBrain
from experiments.run_sim import run_sim
from tests.helpers import FakeLLM, afake_embed

# A tiny scenario with a single RuleBrain character whose goal stack never
# empties (so it's eligible every tick, never quiesces on its own) and no
# environment/map -- irrelevant to what's under test here (memory backend
# swap + adaptive-tick stop bookkeeping).
TINY_SCEN = {
    "scenario": "run_sim_tiny",
    "language": "zh",
    "defaults": {"stats_interval": 1000},
    "agents": [
        {"id": "worker", "kind": "character", "brain": "rule", "goals": ["work"]},
    ],
}


def _write_scenario(tmp_path, cfg=None):
    cfg = cfg or TINY_SCEN
    path = tmp_path / "scen.yaml"
    path.write_text(yaml.safe_dump(cfg, allow_unicode=True), encoding="utf-8")
    return str(path)


def _harmless_llm():
    # Never actually driven by any LLMBrain in these fixtures (only
    # RuleBrain characters), but run_sim always wants an llm object to
    # thread through (usage() must duck-type cleanly).
    return FakeLLM(fn=lambda p, s=None: '{"action": "wait", "params": {}}')


def _patch_rule_brain_noop(monkeypatch):
    """Keep the "worker" RuleBrain character eligible every tick (a plain
    Action("wait") would set waiting_until=-1 and never wake again, which
    would quiesce the kernel after tick 1 -- irrelevant to what these
    tests check, so use a harmless no-op that never stops the agent from
    being eligible: its goal stack is never popped)."""

    async def scripted_decide(self, view):
        return Action("noop", {})

    monkeypatch.setattr(RuleBrain, "decide", scripted_decide)


async def test_run_sim_writes_result_json_with_documented_keys(tmp_path, monkeypatch):
    _patch_rule_brain_noop(monkeypatch)
    spath = _write_scenario(tmp_path)
    out = str(tmp_path / "out")

    result = await run_sim(
        spath,
        "consensus",
        out,
        max_ticks=5,
        llm=_harmless_llm(),
        embed_fn=afake_embed,
    )

    assert os.path.exists(f"{out}/result.json")
    assert os.path.exists(f"{out}/events.jsonl")
    assert os.path.exists(f"{out}/transcripts/worker.md")
    assert os.path.exists(f"{out}/ltm_final.json")

    on_disk = json.load(open(f"{out}/result.json", encoding="utf-8"))
    assert on_disk == result

    expected_keys = {
        "scenario", "memory_kind", "seed", "consensus_merge", "cache_strategy",
        "continued_from", "ticks_run", "stop_reason", "footprint", "cost",
        "sediment_memories", "new_memories", "per_tick_memory",
    }
    assert set(result.keys()) == expected_keys
    assert result["memory_kind"] == "consensus"
    assert result["consensus_merge"] is True   # default knob position
    assert result["cache_strategy"] is None
    assert result["continued_from"] is None
    assert result["seed"] == 0
    assert result["ticks_run"] == 5
    assert result["stop_reason"] == "max_ticks"

    # footprint/cost present and numeric
    assert isinstance(result["footprint"]["entries"], int)
    assert isinstance(result["footprint"]["text_bytes"], int)
    assert isinstance(result["cost"]["calls"], (int, float))
    assert isinstance(result["cost"]["wall_clock_s"], float)

    assert result["sediment_memories"] == 0  # no seed_memories/ltm_file in TINY_SCEN
    assert isinstance(result["new_memories"], int)

    # per_tick_memory length == ticks_run
    assert len(result["per_tick_memory"]) == result["ticks_run"]


async def test_run_sim_records_seed_label_without_claiming_reproducibility(tmp_path, monkeypatch):
    _patch_rule_brain_noop(monkeypatch)
    spath = _write_scenario(tmp_path)
    out = str(tmp_path / "out")
    result = await run_sim(
        spath, "consensus", out, max_ticks=2, seed=7, llm=_harmless_llm(), embed_fn=afake_embed
    )
    assert result["seed"] == 7


@pytest.mark.parametrize(
    "memory_kind", ["consensus", "generative_agents", "g_memory", "collaborative"]
)
async def test_run_sim_works_across_all_backends(tmp_path, memory_kind, monkeypatch):
    _patch_rule_brain_noop(monkeypatch)
    spath = _write_scenario(tmp_path, {**TINY_SCEN, "scenario": f"tiny_{memory_kind}"})
    out = str(tmp_path / f"out_{memory_kind}")
    result = await run_sim(
        spath, memory_kind, out, max_ticks=3, llm=_harmless_llm(), embed_fn=afake_embed
    )
    assert result["memory_kind"] == memory_kind
    assert os.path.exists(f"{out}/result.json")


async def test_adaptive_stop_hits_target_before_max_ticks(tmp_path, monkeypatch):
    """A RuleBrain scripted to remember exactly one NEW memory per tick,
    with adaptive_new_memories=3, must stop with stop_reason
    "adaptive_target" at ~3 new memories, well before max_ticks."""

    async def scripted_decide(self, view):
        # A distinct text every tick -> genuinely a NEW memory each time
        # (no consensus/dedup collision), regardless of which backend is
        # under test.
        return Action("remember", {"text": f"discovery number {view['tick']}"})

    monkeypatch.setattr(RuleBrain, "decide", scripted_decide)

    spath = _write_scenario(tmp_path)
    out = str(tmp_path / "out")

    result = await run_sim(
        spath,
        "consensus",
        out,
        max_ticks=50,
        adaptive_new_memories=3,
        llm=_harmless_llm(),
        embed_fn=afake_embed,
    )

    assert result["stop_reason"] == "adaptive_target"
    assert result["new_memories"] >= 3
    assert result["ticks_run"] < 50
    assert len(result["per_tick_memory"]) == result["ticks_run"]
    # per_tick_memory is nondecreasing (memories only accumulate here)
    assert result["per_tick_memory"] == sorted(result["per_tick_memory"])


async def test_fixed_run_ignores_adaptive_when_none(tmp_path, monkeypatch):
    """adaptive_new_memories=None (default) must just run to max_ticks,
    fixed, even if memories keep accumulating."""

    async def scripted_decide(self, view):
        return Action("remember", {"text": f"discovery number {view['tick']}"})

    monkeypatch.setattr(RuleBrain, "decide", scripted_decide)

    spath = _write_scenario(tmp_path)
    out = str(tmp_path / "out")

    result = await run_sim(
        spath, "consensus", out, max_ticks=4, llm=_harmless_llm(), embed_fn=afake_embed
    )
    assert result["stop_reason"] == "max_ticks"
    assert result["ticks_run"] == 4
