import pytest, yaml
from society.events import EventLog
from society.scenario import load_scenario, build_society
from society.baselines import make_memory
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

async def _write_consensus_multi_owner_dump(tmp_path):
    """Build a consensus (SharedMemory) store with ONE multi-owner entry
    (both "amy" and "ben" remembered the same text, forced to merge via an
    LLM that always claims a match), export it, and write it to
    tmp_path/ltm.json. Returns nothing; the file is what callers need."""
    llm = FakeLLM(fn=lambda p, s=None: "0")  # always match candidate 0 -> forces a merge
    consensus = make_memory("consensus", afake_embed, llm=llm)
    await consensus.remember("amy", "宝黛初见,泪光点点")
    await consensus.remember("ben", "宝黛初见,泪光点点")
    dump = consensus.export()
    assert len(dump) == 1
    assert sorted(dump[0]["owners"]) == ["amy", "ben"]

    import json
    (tmp_path / "ltm.json").write_text(json.dumps(dump), encoding="utf-8")


@pytest.mark.parametrize(
    "memory_kind", ["consensus", "generative_agents", "g_memory", "collaborative"]
)
async def test_build_society_all_backends_restore_and_recall(tmp_path, memory_kind):
    """Task S3: build_society must be backend-swappable via memory_kind, and
    ALL FOUR backends must restore() a holographic dump carrying a
    multi-owner ("consensus") entry without error, with recall working
    post-restore for every original owner. For a per-owner backend
    (generative_agents), the multi-owner entry restores as one owned row
    PER owner -- see society.baselines.GenerativeAgentsMemory.restore."""
    await _write_consensus_multi_owner_dump(tmp_path)
    cfg = {
        "scenario": "backend_swap_test",
        "language": "zh",
        "_dir": str(tmp_path),
        "ltm_file": "ltm.json",
        "defaults": {"stats_interval": 1000},
        "agents": [
            {"id": "amy", "kind": "character", "brain": "rule", "goals": ["chat"]},
            {"id": "ben", "kind": "character", "brain": "rule", "goals": ["chat"]},
        ],
    }
    kernel = await build_society(
        cfg,
        llm=None,
        embed_fn=afake_embed,
        event_log=EventLog(None),
        memory_kind=memory_kind,
    )

    entries = kernel.shared_memory.all_entries()
    assert entries, f"{memory_kind}: restore produced no entries"

    amy_hits = await kernel.shared_memory.recall("amy", "宝黛初见", top_k=5)
    ben_hits = await kernel.shared_memory.recall("ben", "宝黛初见", top_k=5)
    assert amy_hits, f"{memory_kind}: amy recall empty post-restore"
    assert ben_hits, f"{memory_kind}: ben recall empty post-restore"


async def test_build_society_baselines_init_per_owner_consensus_merged(tmp_path):
    """Init principle: a multi-owner sediment entry is REPLAYED per owner into
    each baseline (one row per owner, via that backend's own remember_atomic),
    while consensus restores it as its single merged owner-set row. So the one
    [amy, ben] dump entry becomes 2 rows in every baseline and 1 in consensus
    -- baselines never get consensus's cross-agent merge for free."""
    await _write_consensus_multi_owner_dump(tmp_path)  # one entry, owners=[amy,ben]

    def _cfg():
        return {
            "scenario": "init_principle_test",
            "language": "zh",
            "_dir": str(tmp_path),
            "ltm_file": "ltm.json",
            "defaults": {"stats_interval": 1000},
            "agents": [
                {"id": "amy", "kind": "character", "brain": "rule", "goals": ["chat"]},
                {"id": "ben", "kind": "character", "brain": "rule", "goals": ["chat"]},
            ],
        }

    counts = {}
    for kind in ("consensus", "generative_agents", "g_memory", "collaborative"):
        k = await build_society(
            _cfg(), llm=None, embed_fn=afake_embed,
            event_log=EventLog(None), memory_kind=kind,
        )
        counts[kind] = len(k.shared_memory.all_entries())

    assert counts["consensus"] == 1, counts
    assert counts["generative_agents"] == 2, counts
    assert counts["g_memory"] == 2, counts
    assert counts["collaborative"] == 2, counts


def test_default_memory_kind_is_consensus_shared_memory():
    """"consensus" must yield exactly today's SharedMemory instance (no
    behavior change for existing scenarios that don't pass memory_kind)."""
    from society.ltm import SharedMemory

    m = make_memory("consensus", afake_embed)
    assert isinstance(m, SharedMemory)


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
