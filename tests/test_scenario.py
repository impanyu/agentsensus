import pytest, yaml
from society.events import EventLog
from society.scenario import load_scenario, build_society
from tests.helpers import FakeLLM, afake_embed


async def test_load_and_build_demo():
    cfg = load_scenario("scenarios/demo_min.yaml")
    assert cfg["scenario"] == "demo_min"
    llm = FakeLLM(fn=lambda p, s=None: '{"action": "noop", "params": {}}')
    k = await build_society(cfg, llm=llm, embed_fn=afake_embed, event_log=EventLog(None))
    assert set(k.agents) == {"hall", "garden", "alice", "guide_book"}
    assert k.worldmap.distance("hall", "garden") == 2
    assert "alice" in k.presence["hall"]
    entries = k.shared_memory.all_entries()
    assert any("兔子洞" in e["text"] for e in entries)      # seed loaded via consensus path
    summary = await k.run(max_ticks=3)                      # kickoff wakes alice at tick 0/1
    acted = [e for e in k.event_log.all() if e["kind"] == "action" and e["agent"] == "alice"]
    assert acted, "kickoff must wake alice"

def test_demo_red_chamber_loads():
    load_scenario("scenarios/demo_red_chamber.yaml")

def test_load_validation_errors(tmp_path):
    bad = {"scenario": "x", "agents": [{"id": "a", "kind": "character", "brain": "llm",
                                        "status": {"location": "nowhere"}}]}
    p = tmp_path / "bad.yaml"; p.write_text(yaml.safe_dump(bad), encoding="utf-8")
    with pytest.raises(ValueError):
        load_scenario(str(p))
    dup = {"scenario": "x", "agents": [{"id": "a", "kind": "environment", "brain": "rule"},
                                       {"id": "a", "kind": "environment", "brain": "rule"}]}
    p2 = tmp_path / "dup.yaml"; p2.write_text(yaml.safe_dump(dup), encoding="utf-8")
    with pytest.raises(ValueError):
        load_scenario(str(p2))
