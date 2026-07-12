import json
import os
import uuid

import yaml

from society.events import EventLog
from society.ltm import SharedMemory
from society.persistence import load_checkpoint, restore_society, save_checkpoint
from society.run import resume_scenario, run_scenario
from society.scenario import build_society
from tests.helpers import FakeLLM, afake_embed


# ----------------------------------------------------------------------
# 1. SharedMemory holographic export/restore
# ----------------------------------------------------------------------

class _CountingEmbed:
    """Wraps afake_embed and counts how many times it's invoked."""

    def __init__(self):
        self.calls = 0

    async def __call__(self, texts):
        self.calls += 1
        return await afake_embed(texts)


async def test_ltm_export_restore_holographic():
    embed = _CountingEmbed()
    llm = FakeLLM(responses=["0"])  # consensus: candidate 0 is equivalent -> merge
    m = SharedMemory(embed, llm=llm, collection_name=f"t_{uuid.uuid4().hex[:8]}")

    await m.remember("alice", "国王死于春天")
    await m.remember("bob", "国王死于春天")  # merges -> multi-owner entry

    calls_before_export = embed.calls
    exported = m.export()
    assert embed.calls == calls_before_export  # export() makes no embed calls
    assert len(exported) == 1
    assert exported[0]["owners"] == ["alice", "bob"]
    assert exported[0]["embedding"] is not None

    embed2 = _CountingEmbed()
    m2 = SharedMemory(embed2, collection_name=f"t_{uuid.uuid4().hex[:8]}")
    await m2.restore(exported)
    assert embed2.calls == 0  # restore reused the saved embedding, no recompute

    def key(e):
        return (e["id"], e["text"], tuple(e["owners"]))

    orig = [(e["id"], e["text"], e["owners"]) for e in sorted(m.all_entries(), key=key)]
    restored = [(e["id"], e["text"], e["owners"]) for e in sorted(m2.all_entries(), key=key)]
    assert orig == restored

    got = await m2.recall("bob", "国王死于春天", top_k=5)
    assert got and got[0]["text"] == "国王死于春天"


# ----------------------------------------------------------------------
# 2. Checkpoint round-trip of full kernel state
# ----------------------------------------------------------------------

ROUNDTRIP_SCEN = {
    "scenario": "roundtrip_test", "language": "zh",
    "defaults": {"stats_interval": 100, "distance": 3},
    "agents": [
        {"id": "hall", "kind": "environment", "brain": "rule", "profile": "hall"},
        {"id": "amy", "kind": "character", "brain": "llm", "profile": "amy",
         "status": {"location": "hall"}, "goals": ["chat"]},
        {"id": "ben", "kind": "character", "brain": "llm", "profile": "ben",
         "status": {"location": "hall"}},
    ],
    "map": {"default_distance": 3},
    "kickoff": [{"to": ["amy"], "kind": "system", "content": "开始"}],
}


async def test_checkpoint_roundtrip_state(tmp_path):
    seq = {
        "amy": [
            '{"action": "say", "params": {"targets": ["ben"], "content": "hi"}}',
            '{"action": "push_goal", "params": {"text": "deepen"}}',
            '{"action": "remember", "params": {"text": "amy remembers meeting ben"}}',
            '{"action": "pop_goal", "params": {}}',
        ],
        "ben": [
            '{"action": "pop_message", "params": {}}',
            '{"action": "say", "params": {"targets": ["amy"], "content": "yo"}}',
            '{"action": "remember", "params": {"text": "ben remembers meeting amy"}}',
        ],
    }

    def fn(prompt, system=None):
        for aid, responses in seq.items():
            if system and aid in system:
                if responses:
                    return responses.pop(0)
                return '{"action": "wait", "params": {}}'
        return '{"action": "wait", "params": {}}'

    llm = FakeLLM(fn=fn)
    kernel = await build_society(
        ROUNDTRIP_SCEN, llm=llm, embed_fn=afake_embed, event_log=EventLog(None)
    )
    await kernel.run(max_ticks=5)

    ckpt_path = str(tmp_path / "ckpt.json")
    save_checkpoint(kernel, ckpt_path)
    ckpt = load_checkpoint(ckpt_path)
    assert ckpt["version"] == 1
    assert ckpt["tick"] == kernel.tick
    assert ckpt["event_seq"] == kernel.event_log._seq_counter

    fresh_event_log = EventLog(None, start_seq=ckpt["event_seq"])
    restored = await restore_society(
        ckpt, llm=FakeLLM(), embed_fn=afake_embed, event_log=fresh_event_log
    )

    assert restored.tick == kernel.tick
    assert restored.presence == kernel.presence

    for aid, agent in kernel.agents.items():
        r_agent = restored.agents[aid]
        assert len(r_agent.stm.fifo.items()) == len(agent.stm.fifo.items())
        assert r_agent.stm.goals.items() == agent.stm.goals.items()
        assert r_agent.stm.status.all() == agent.stm.status.all()
        assert r_agent.stm.inbox.qsize() == agent.stm.inbox.qsize()

    orig_ltm = sorted(
        (e["id"], tuple(e["owners"])) for e in kernel.shared_memory.all_entries()
    )
    restored_ltm = sorted(
        (e["id"], tuple(e["owners"])) for e in restored.shared_memory.all_entries()
    )
    assert orig_ltm == restored_ltm


# ----------------------------------------------------------------------
# 3. Resume continues a run across the checkpoint boundary
# ----------------------------------------------------------------------

RESUME_SCEN = {
    "scenario": "resume_test", "language": "zh",
    "defaults": {"stats_interval": 100, "distance": 3},
    "agents": [
        {"id": "hall", "kind": "environment", "brain": "rule", "profile": "hall"},
        {"id": "amy", "kind": "character", "brain": "llm", "profile": "amy",
         "status": {"location": "hall"}, "goals": ["chat"]},
        {"id": "ben", "kind": "character", "brain": "llm", "profile": "ben",
         "status": {"location": "hall"}, "goals": ["chat"]},
    ],
    "map": {"default_distance": 3},
}


async def test_resume_continues_run(tmp_path):
    scen_dir = tmp_path / "scen"
    scen_dir.mkdir(parents=True)
    spath = scen_dir / "resume.yaml"
    spath.write_text(yaml.safe_dump(RESUME_SCEN, allow_unicode=True), encoding="utf-8")

    def fn_active(prompt, system=None):
        # Sync "observe" never pops the goal, so both llm-brain agents stay
        # eligible forever -> run reaches max_ticks deterministically.
        return json.dumps({"action": "observe", "params": {"target": "hall"}})

    llm1 = FakeLLM(fn=fn_active)
    out = str(tmp_path / "run_resume")
    summary1 = await run_scenario(
        str(spath), ticks=4, out_dir=out, llm=llm1, embed_fn=afake_embed, checkpoint=True
    )
    assert summary1["stop_reason"] == "max_ticks"

    ckpt_path = os.path.join(out, "checkpoint.json")
    assert os.path.exists(ckpt_path)

    events_pre = EventLog.load(os.path.join(out, "events.jsonl"))
    actions_pre = [e for e in events_pre if e["kind"] == "action"]
    assert actions_pre  # some actions ran before the resume boundary

    def fn_noop(prompt, system=None):
        return json.dumps({"action": "noop", "params": {}})

    llm2 = FakeLLM(fn=fn_noop)
    summary2 = await resume_scenario(out, ticks=3, llm=llm2, embed_fn=afake_embed)
    assert summary2["ticks_run"] >= summary1["ticks_run"]

    events_post = EventLog.load(os.path.join(out, "events.jsonl"))
    seqs = [e["seq"] for e in events_post]
    assert seqs == sorted(seqs)             # strictly increasing across the boundary
    assert len(seqs) == len(set(seqs))       # no duplicate seq

    actions_post = [e for e in events_post if e["kind"] == "action"]
    assert len(actions_post) > len(actions_pre)


# ----------------------------------------------------------------------
# 4. Checkpoint is written on every stop, including early quiescence
# ----------------------------------------------------------------------

QUIESCE_SCEN = {
    "scenario": "quiesce_test", "language": "zh",
    "defaults": {"stats_interval": 100, "distance": 3},
    "agents": [
        {"id": "hall", "kind": "environment", "brain": "rule", "profile": "hall"},
        {"id": "amy", "kind": "character", "brain": "rule", "profile": "amy",
         "status": {"location": "hall"}},
    ],
    "map": {"default_distance": 3},
}


async def test_checkpoint_written_on_stop(tmp_path):
    scen_dir = tmp_path / "scen"
    scen_dir.mkdir(parents=True)
    spath = scen_dir / "quiesce.yaml"
    spath.write_text(yaml.safe_dump(QUIESCE_SCEN, allow_unicode=True), encoding="utf-8")

    out = str(tmp_path / "run_quiesce")
    summary = await run_scenario(
        str(spath), ticks=10, out_dir=out, llm=FakeLLM(), embed_fn=afake_embed, checkpoint=True
    )
    assert summary["stop_reason"] == "quiescent"

    ckpt_path = os.path.join(out, "checkpoint.json")
    assert os.path.exists(ckpt_path)
    ckpt = load_checkpoint(ckpt_path)
    assert ckpt["tick"] == summary["ticks_run"]
