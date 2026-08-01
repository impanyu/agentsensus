import json
import math
import os
import uuid

import yaml

from society.actions import Action, Message
from society.events import EventLog
from society.ltm import SharedMemory
from society.persistence import load_checkpoint, restore_society, save_checkpoint
from society.run import resume_scenario, run_scenario
from society.scenario import build_society
from tests.helpers import FakeLLM, afake_embed
from tests.test_stm import make_fake_embed


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
# 1b. defaults.cache_strategy/cache_alpha wired through the real
#     build_society config-reading path (not just STM(strategy=...)
#     constructed directly), then survives a save/restore round-trip.
# ----------------------------------------------------------------------

def _cache_strategy_cfg(strategy: str) -> dict:
    return {
        "scenario": f"cache_strategy_{strategy}",
        "language": "zh",
        "defaults": {
            "stats_interval": 100,
            "distance": 3,
            "fifo_size": 3,
            "cache_strategy": strategy,
            "cache_alpha": 0.5,
        },
        "agents": [
            {"id": "hall", "kind": "environment", "brain": "rule", "profile": "hall"},
            {"id": "amy", "kind": "character", "brain": "rule", "profile": "amy",
             "status": {"location": "hall"}},
        ],
        "map": {"default_distance": 3},
    }


async def _assert_cache_strategy_wired_and_survives_restore(strategy: str, vectors: dict, tmp_path):
    embed_fn = make_fake_embed(vectors)

    cfg = _cache_strategy_cfg(strategy)
    kernel = await build_society(cfg, llm=FakeLLM(), embed_fn=embed_fn, event_log=EventLog(None))
    agent = kernel.agents["amy"]

    # The config-reading path (build_agents_and_map, via build_society)
    # actually wired defaults.cache_strategy/cache_alpha and the embed_fn
    # into this agent's real FifoCache -- not just STM(strategy=...)
    # constructed directly in a unit test.
    assert agent.stm.fifo._strategy == strategy
    assert agent.stm.fifo._embed_fn is embed_fn

    await agent.stm.fifo.append({"name": "p1"}, {})
    await agent.stm.fifo.append({"name": "p2"}, {})
    await agent.stm.fifo.append({"name": "p3"}, {})
    await agent.stm.fifo.append({"name": "new"}, {})  # fifo_size=3 -> forces eviction
    names = [a["name"] for a, _ in agent.stm.fifo.items()]
    assert len(agent.stm.fifo) == 3
    assert "p2" not in names  # evicted by strategy, not fifo's oldest-first (which drops p1)
    assert names == ["p1", "p3", "new"]

    ckpt_path = str(tmp_path / f"ckpt_{strategy}.json")
    save_checkpoint(kernel, ckpt_path)
    ckpt = load_checkpoint(ckpt_path)

    # Restore must not raise -- guards the fix that threads embed_fn into
    # restore_society's build_agents_and_map call, which relevance/hybrid
    # need for the lazy embed of restore_items-loaded pairs on next append.
    restored = await restore_society(
        ckpt, llm=FakeLLM(), embed_fn=embed_fn,
        event_log=EventLog(None, start_seq=ckpt["event_seq"]),
    )
    r_agent = restored.agents["amy"]
    assert r_agent.stm.fifo._strategy == strategy
    assert [a["name"] for a, _ in r_agent.stm.fifo.items()] == names

    # Exercise the restored cache's embed_fn wiring: a relevance/hybrid
    # append that forces eviction must lazily embed the restore_items-
    # loaded (embedding=None) pairs rather than crashing.
    await r_agent.stm.fifo.append({"name": "p2"}, {})
    assert len(r_agent.stm.fifo) == 3


async def test_cache_strategy_relevance_wired_and_survives_restore(tmp_path):
    # Mirrors test_stm.py's test_relevance_evicts_least_similar_pair
    # vectors: new=(1,0); p2 is orthogonal (cos=0.0) -> least relevant.
    vectors = {
        "p1": (0.9, math.sqrt(0.19)),
        "p2": (0.0, 1.0),
        "p3": (0.1, math.sqrt(0.99)),
        "new": (1.0, 0.0),
    }
    await _assert_cache_strategy_wired_and_survives_restore("relevance", vectors, tmp_path)


async def test_cache_strategy_hybrid_wired_and_survives_restore(tmp_path):
    # Mirrors test_stm.py's test_hybrid_disagrees_with_fifo_and_pure_relevance
    # vectors: hybrid(alpha=0.5) picks p2 as victim -- a distinct choice from
    # both fifo (would drop oldest p1) and pure relevance (would drop p3).
    vectors = {
        "p1": (0.9, math.sqrt(0.19)),
        "p2": (0.1, math.sqrt(0.99)),
        "p3": (0.0, 1.0),
        "new": (1.0, 0.0),
    }
    await _assert_cache_strategy_wired_and_survives_restore("hybrid", vectors, tmp_path)


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
            '{"action": "read_thread", "params": {"target": "amy"}}',
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

    # The STM inbox is gone -- conversation threads (kernel.conversations)
    # are the sole delivery target now, and they round-trip as a whole.
    assert restored.conversations.export() == kernel.conversations.export()

    orig_ltm = sorted(
        (e["id"], tuple(e["owners"])) for e in kernel.shared_memory.all_entries()
    )
    restored_ltm = sorted(
        (e["id"], tuple(e["owners"])) for e in restored.shared_memory.all_entries()
    )
    assert orig_ltm == restored_ltm


# ----------------------------------------------------------------------
# 2b. Message.wake survives a checkpoint save/restore round-trip, for both
#     already-delivered inbox messages and still-pending (queued) ones.
# ----------------------------------------------------------------------

WAKE_CKPT_SCEN = {
    "scenario": "wake_ckpt_test", "language": "zh",
    "defaults": {"stats_interval": 100, "distance": 3},
    "agents": [
        {"id": "room_a", "kind": "environment", "brain": "rule"},
        {"id": "room_b", "kind": "environment", "brain": "rule"},
        {"id": "amy", "kind": "character", "brain": "rule", "status": {"location": "room_a"}},
        {"id": "ben", "kind": "character", "brain": "rule", "status": {"location": "room_b"}},
    ],
    "map": {"default_distance": 3, "edges": [["room_a", "room_b", 2]]},
}


async def test_message_wake_survives_checkpoint_roundtrip(tmp_path):
    """The STM inbox is gone, so `wake` is only observable on still-pending
    (not-yet-delivered) `Kernel._pending` entries now -- once delivered, the
    thread record `_deliver_due` writes into `kernel.conversations` doesn't
    carry `wake` forward, since its only effect (clearing the recipient's
    `waiting_until`) has already happened at delivery time. This exercises
    wake fidelity across a checkpoint for two still-in-flight messages to a
    forever-waiting `ben`: a wake=False one that must not wake him on
    delivery, and a wake=True one (delivered a tick later) that must --
    both after a save/restore round-trip in between.
    """
    kernel = await build_society(
        WAKE_CKPT_SCEN, llm=FakeLLM(), embed_fn=afake_embed, event_log=EventLog(None)
    )
    ben = kernel.agents["ben"]
    ben.waiting_until = -1   # forever-wait

    kernel._pending.append(
        {"msg": Message(id="quiet", sender="amy", recipients=["ben"], kind="say",
                         content="fyi", tick_sent=0, wake=False),
         "recipient": "ben", "deliver_at": 2}
    )
    kernel._pending.append(
        {"msg": Message(id="loud", sender="amy", recipients=["ben"], kind="say",
                         content="hi", tick_sent=0, wake=True),
         "recipient": "ben", "deliver_at": 3}
    )

    ckpt_path = str(tmp_path / "wake_ckpt.json")
    save_checkpoint(kernel, ckpt_path)
    ckpt = load_checkpoint(ckpt_path)

    pending_wake = {p["msg"]["id"]: p["msg"]["wake"] for p in ckpt["pending"]}
    assert pending_wake == {"quiet": False, "loud": True}

    restored = await restore_society(
        ckpt, llm=FakeLLM(), embed_fn=afake_embed, event_log=EventLog(None)
    )
    r_ben = restored.agents["ben"]
    assert r_ben.waiting_until == -1

    restored.tick = 2
    assert restored._deliver_due() is True
    assert r_ben.waiting_until == -1   # wake=False delivery did not clear it
    assert [m["content"] for m in restored.conversations.read("ben", "amy", k=10)] == ["fyi"]

    restored.tick = 3
    assert restored._deliver_due() is True
    assert r_ben.waiting_until is None   # wake=True delivery cleared it


# ----------------------------------------------------------------------
# 2c. Conversation threads (kernel.conversations) survive a checkpoint
#     save/restore round-trip: same threads, same unread counts, same
#     `.read()` output.
# ----------------------------------------------------------------------

CONV_CKPT_SCEN = {
    "scenario": "conv_ckpt_test", "language": "zh",
    "defaults": {"stats_interval": 100, "distance": 3},
    "agents": [
        {"id": "hall", "kind": "environment", "brain": "rule", "profile": "hall"},
        {"id": "amy", "kind": "character", "brain": "rule", "status": {"location": "hall"}},
        {"id": "ben", "kind": "character", "brain": "rule", "status": {"location": "hall"}},
    ],
    "map": {"default_distance": 3},
}


async def test_conversation_threads_survive_checkpoint_roundtrip(tmp_path):
    kernel = await build_society(
        CONV_CKPT_SCEN, llm=FakeLLM(), embed_fn=afake_embed, event_log=EventLog(None)
    )

    # Record a couple of exchanged messages directly into the store (mirrors
    # what Kernel._deliver_due does on delivery): amy's own copy is
    # unread=0, ben's copy of the same message is unread=1, and so on.
    kernel.conversations.record(
        "amy", "ben", {"sender": "amy", "kind": "say", "content": "hi ben", "tick": 0},
        unread_delta=0, kind="character",
    )
    kernel.conversations.record(
        "ben", "amy", {"sender": "amy", "kind": "say", "content": "hi ben", "tick": 0},
        unread_delta=1, kind="character",
    )
    kernel.conversations.record(
        "ben", "amy", {"sender": "ben", "kind": "say", "content": "hey amy", "tick": 1},
        unread_delta=0, kind="character",
    )
    kernel.conversations.record(
        "amy", "ben", {"sender": "ben", "kind": "say", "content": "hey amy", "tick": 1},
        unread_delta=1, kind="character",
    )

    ckpt_path = str(tmp_path / "conv_ckpt.json")
    save_checkpoint(kernel, ckpt_path)
    ckpt = load_checkpoint(ckpt_path)

    restored = await restore_society(
        ckpt, llm=FakeLLM(), embed_fn=afake_embed, event_log=EventLog(None)
    )

    # Full underlying store round-trips exactly (same threads, same
    # messages, same unread counts) -- neither side has been read yet.
    assert restored.conversations.export() == kernel.conversations.export()

    # `.read()` (which also mark_read()s) produces identical output on
    # both, and each independently clears its own unread counter.
    orig_amy_view = kernel.conversations.read("amy", "ben", k=10)
    restored_amy_view = restored.conversations.read("amy", "ben", k=10)
    assert orig_amy_view == restored_amy_view
    assert orig_amy_view == [
        {"sender": "amy", "kind": "say", "content": "hi ben", "tick": 0},
        {"sender": "ben", "kind": "say", "content": "hey amy", "tick": 1},
    ]

    orig_ben_view = kernel.conversations.read("ben", "amy", k=10)
    restored_ben_view = restored.conversations.read("ben", "amy", k=10)
    assert orig_ben_view == restored_ben_view

    # Reading marked both copies read; re-reading now returns unread=0 for
    # both the original and the restored kernel.
    assert kernel.conversations.export()["amy"]["ben"]["unread"] == 0
    assert restored.conversations.export()["amy"]["ben"]["unread"] == 0


# ----------------------------------------------------------------------
# 2d. Task 2 changed each `Kernel._pending` entry from a raw Message to a
#     dict ({"msg", "recipient", "deliver_at"}) so distance-delayed
#     delivery could carry a per-recipient deliver tick. A checkpoint taken
#     while such a message is still in flight (recipient in a different,
#     distance>0 location) must not crash on save or restore, and the
#     message must still deliver at the correct tick afterwards.
# ----------------------------------------------------------------------

PENDING_CKPT_SCEN = {
    "scenario": "pending_ckpt_test", "language": "zh",
    "defaults": {"stats_interval": 100, "distance": 3},
    "agents": [
        {"id": "room_a", "kind": "environment", "brain": "rule"},
        {"id": "room_b", "kind": "environment", "brain": "rule"},
        {"id": "amy", "kind": "character", "brain": "rule", "status": {"location": "room_a"}},
        {"id": "ben", "kind": "character", "brain": "rule", "status": {"location": "room_b"}},
    ],
    "map": {"default_distance": 3, "edges": [["room_a", "room_b", 2]]},
}


async def test_pending_delayed_message_survives_checkpoint_roundtrip(tmp_path):
    kernel = await build_society(
        PENDING_CKPT_SCEN, llm=FakeLLM(), embed_fn=afake_embed, event_log=EventLog(None)
    )
    amy = kernel.agents["amy"]

    # amy (room_a) says something to ben (room_b), 2 ticks away -> queued
    # into _pending with deliver_at = tick(0) + 2, NOT yet delivered.
    r = await kernel.execute(amy, Action("say", {"targets": ["ben"], "content": "hello from afar"}))
    assert r.ok

    assert len(kernel._pending) == 1
    pending_entry = kernel._pending[0]
    assert pending_entry["recipient"] == "ben"
    assert pending_entry["deliver_at"] == 2
    assert pending_entry["msg"].content == "hello from afar"

    # Nothing has been delivered yet -- ben's thread with amy is still empty.
    assert kernel.conversations.read("ben", "amy") == []

    ckpt_path = str(tmp_path / "pending_ckpt.json")
    save_checkpoint(kernel, ckpt_path)  # must not crash (Task 2 dict-shape bug)
    ckpt = load_checkpoint(ckpt_path)

    ckpt_pending = ckpt["pending"][0]
    assert ckpt_pending["recipient"] == "ben"
    assert ckpt_pending["deliver_at"] == 2
    assert ckpt_pending["msg"]["content"] == "hello from afar"

    restored = await restore_society(
        ckpt, llm=FakeLLM(), embed_fn=afake_embed, event_log=EventLog(None)
    )  # must not crash either

    assert len(restored._pending) == 1
    r_entry = restored._pending[0]
    assert r_entry["recipient"] == "ben"
    assert r_entry["deliver_at"] == 2
    assert isinstance(r_entry["msg"], Message)
    assert r_entry["msg"].content == "hello from afar"
    assert r_entry["msg"].sender == "amy"

    # Still not due at tick 1 -- delivery must respect deliver_at, not fire
    # early just because it survived a restore.
    restored.tick = 1
    assert restored._deliver_due() is False
    assert restored.conversations.read("ben", "amy") == []

    # Due at tick 2 -- delivers into both ben's and amy's thread.
    restored.tick = 2
    assert restored._deliver_due() is True
    assert len(restored._pending) == 0
    ben_view = restored.conversations.read("ben", "amy")
    assert len(ben_view) == 1
    assert ben_view[0]["sender"] == "amy"
    assert ben_view[0]["content"] == "hello from afar"
    assert ben_view[0]["tick"] == 2


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
    # capped wait (max_wait_ticks=20): sleepers now carry a real wake timer
    # beyond ticks=10, so the run fast-forwards to max_ticks rather than
    # quiescing -- the checkpoint-on-stop behavior under test is unchanged.
    assert summary["stop_reason"] == "max_ticks"

    ckpt_path = os.path.join(out, "checkpoint.json")
    assert os.path.exists(ckpt_path)
    ckpt = load_checkpoint(ckpt_path)
    assert ckpt["tick"] == summary["ticks_run"]
