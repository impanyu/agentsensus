"""Task R -- sim model v2: passive, function-driven environments/
info_carriers + awake-based character eligibility. This partially REVERTS
Task S2 (which gave environment/info_carrier agents an LLMBrain and
answered their act_on/read interfaces asynchronously through the inbox,
one tick later). See scratchpad/taskR-simmodel-brief.md.

Covers:
  1. `_make_brain` (scenario.py): environment/info_carrier agents ALWAYS
     get a RuleBrain now, regardless of the yaml `brain:` field or whether
     a real llm is configured; characters are unaffected by this task.
  2. Environments/info_carriers are NEVER eligible (Kernel.is_eligible),
     even with a pending wake=True message or at tick 0 -- they are
     passive and never get a proactive decide/execute turn.
  3. act_on(env) is SYNCHRONOUS: deposits an env-owned memory and returns
     ok in the SAME tick, end-to-end via build_society.
  4. read(carrier|env, query) is SYNCHRONOUS: returns the target's own
     memories (SharedMemory.recall_of) in the SAME tick, end-to-end via
     build_society.
  5. observe's uniform {kind, status, occupants?} shape (unaffected by
     this task, kept as a regression check).
  6. An environment updating its own status via update_status (unaffected
     by this task, kept as a regression check).
  7. Persistence round-trips legacy brain: rule/retrieval fields, and the
     restored env/carrier agents are still RuleBrain.
"""

from society.actions import Action
from society.brains import LLMBrain, RuleBrain
from society.events import EventLog
from society.persistence import load_checkpoint, restore_society, save_checkpoint
from society.scenario import _make_brain, build_society
from tests.helpers import FakeLLM, afake_embed


# ----------------------------------------------------------------------
# 1. _make_brain: env/carrier always RuleBrain
# ----------------------------------------------------------------------


def test_env_gets_rulebrain_regardless_of_brain_field_and_llm_presence():
    for brain_field in ("rule", "retrieval", "llm"):
        for llm in (None, FakeLLM()):
            a = {"id": "hall", "kind": "environment", "brain": brain_field, "profile": "大厅"}
            brain = _make_brain(a, llm=llm, language="zh", scenario_dir=".")
            assert isinstance(brain, RuleBrain), (brain_field, llm)


def test_carrier_gets_rulebrain_regardless_of_brain_field_and_llm_presence():
    for brain_field in ("rule", "retrieval", "llm"):
        for llm in (None, FakeLLM()):
            a = {"id": "book", "kind": "info_carrier", "brain": brain_field, "profile": "一本书"}
            brain = _make_brain(a, llm=llm, language="zh", scenario_dir=".")
            assert isinstance(brain, RuleBrain), (brain_field, llm)


def test_carrier_corpus_field_ignored_and_never_opened(tmp_path):
    # corpus points at a file that doesn't exist -- must not be opened at
    # all now that info_carriers always get a plain RuleBrain (corpus was
    # only ever read by the legacy RetrievalBrain path).
    a = {
        "id": "book", "kind": "info_carrier", "brain": "retrieval", "profile": "一本古书",
        "corpus": "corpora/does_not_exist.txt",
    }
    brain = _make_brain(a, llm=FakeLLM(), language="zh", scenario_dir=str(tmp_path))
    assert isinstance(brain, RuleBrain)


def test_character_brain_field_unaffected_by_this_task():
    a_rule = {"id": "amy", "kind": "character", "brain": "rule", "profile": "amy"}
    a_llm = {"id": "amy", "kind": "character", "brain": "llm", "profile": "amy"}
    assert isinstance(_make_brain(a_rule, llm=FakeLLM(), language="zh", scenario_dir="."), RuleBrain)
    assert isinstance(_make_brain(a_rule, llm=None, language="zh", scenario_dir="."), RuleBrain)
    assert isinstance(_make_brain(a_llm, llm=FakeLLM(), language="zh", scenario_dir="."), LLMBrain)


async def test_env_and_carrier_get_rulebrain_via_build_society_even_with_llm():
    cfg = {
        "scenario": "r_demo", "language": "zh",
        "defaults": {"stats_interval": 100, "distance": 3},
        "agents": [
            {"id": "hall", "kind": "environment", "brain": "rule", "profile": "大厅"},
            {"id": "book", "kind": "info_carrier", "brain": "retrieval", "profile": "一本书",
             "status": {"location": "hall"}, "corpus": "corpora/nope.txt"},
            {"id": "amy", "kind": "character", "brain": "llm", "profile": "amy",
             "status": {"location": "hall"}},
        ],
        "map": {"default_distance": 3},
    }
    k = await build_society(cfg, llm=FakeLLM(), embed_fn=afake_embed, event_log=EventLog(None))
    hall, book, amy = k.agents["hall"], k.agents["book"], k.agents["amy"]

    assert isinstance(hall.brain, RuleBrain)
    assert isinstance(book.brain, RuleBrain)
    assert isinstance(amy.brain, LLMBrain)


# ----------------------------------------------------------------------
# 2. Environments/info_carriers are NEVER eligible -- passive by design,
#    regardless of pending messages or tick.
# ----------------------------------------------------------------------

NEVER_ELIGIBLE_CFG = {
    "scenario": "never_eligible", "language": "zh",
    "defaults": {"stats_interval": 100, "distance": 3},
    "agents": [
        {"id": "hall", "kind": "environment", "brain": "rule", "profile": "大厅"},
        {"id": "book", "kind": "info_carrier", "brain": "retrieval", "profile": "一本书",
         "status": {"location": "hall"}},
        {"id": "amy", "kind": "character", "brain": "rule", "profile": "amy",
         "status": {"location": "hall"}},
    ],
    "map": {"default_distance": 3},
}


async def test_env_and_carrier_never_eligible_at_tick_zero():
    k = await build_society(NEVER_ELIGIBLE_CFG, llm=FakeLLM(), embed_fn=afake_embed,
                             event_log=EventLog(None))
    assert k.is_eligible(k.agents["hall"]) is False
    assert k.is_eligible(k.agents["book"]) is False
    # a goalless, never-waited character IS eligible under the awake model
    # (Part B) -- the contrast confirms env/carrier ineligibility isn't
    # just an artifact of "nobody is eligible yet".
    assert k.is_eligible(k.agents["amy"]) is True


async def test_env_and_carrier_never_eligible_even_with_pending_wake_message():
    k = await build_society(NEVER_ELIGIBLE_CFG, llm=FakeLLM(), embed_fn=afake_embed,
                             event_log=EventLog(None))
    hall, book = k.agents["hall"], k.agents["book"]

    from society.actions import Message
    k.send(Message(id="m1", sender="amy", recipients=["hall"], kind="act_on",
                    content="推门", tick_sent=0, wake=True))
    k.send(Message(id="m2", sender="amy", recipients=["book"], kind="read",
                    content="宝玉", tick_sent=0, wake=True))
    k.deliver_pending()

    assert hall.stm.inbox.qsize() == 1
    assert book.stm.inbox.qsize() == 1
    assert k.is_eligible(hall) is False
    assert k.is_eligible(book) is False


async def test_env_and_carrier_never_scheduled_across_a_full_run():
    k = await build_society(NEVER_ELIGIBLE_CFG, llm=FakeLLM(fn=lambda p, s=None:
                             '{"action": "wait", "params": {}}'),
                             embed_fn=afake_embed, event_log=EventLog(None))
    await k.run(max_ticks=5)

    for aid in ("hall", "book"):
        actions = [
            e for e in k.event_log.all() if e["kind"] == "action" and e["agent"] == aid
        ]
        assert actions == [], f"{aid} was scheduled but is supposed to be passive"


# ----------------------------------------------------------------------
# 3. act_on(env): synchronous env-owned memory deposit, same tick
# ----------------------------------------------------------------------

ACT_ON_CFG = {
    "scenario": "act_on_sync", "language": "zh",
    "defaults": {"stats_interval": 100, "distance": 3},
    "agents": [
        {"id": "hall", "kind": "environment", "brain": "rule", "profile": "一间空荡荡的大厅"},
        {"id": "amy", "kind": "character", "brain": "rule", "profile": "艾米",
         "status": {"location": "hall"}},
    ],
    "map": {"default_distance": 3},
}


async def test_act_on_deposits_env_owned_memory_and_returns_ok_same_tick():
    k = await build_society(ACT_ON_CFG, llm=FakeLLM(), embed_fn=afake_embed,
                             event_log=EventLog(None))
    amy = k.agents["amy"]

    r = await k.execute(amy, Action("act_on", {"targets": ["hall"], "content": "推开了大门"}))
    assert r.ok
    assert r.data == {"env": "hall", "recorded": "推开了大门"}

    # No message was ever sent -- hall's inbox stays empty even after a
    # delivery pass, and hall is never scheduled to "reply".
    k.deliver_pending()
    assert k.agents["hall"].stm.inbox.qsize() == 0

    hits = await k.shared_memory.recall_of("hall", "大门", top_k=5)
    assert hits and "推开了大门" in hits[0]["text"]


async def test_act_on_without_shared_memory_still_succeeds():
    from society.agent import Agent
    from society.stm import STM
    from society.worldmap import WorldMap
    from society.kernel import Kernel
    from society.events import EventLog as EL

    amy = Agent("amy", "character", RuleBrain(), STM(status={"location": "hall"}))
    hall = Agent("hall", "environment", RuleBrain(), STM())
    k = Kernel({"amy": amy, "hall": hall}, WorldMap(["hall"], default_distance=3), EL(None))

    r = await k.execute(amy, Action("act_on", {"targets": ["hall"], "content": "推门"}))
    assert r.ok
    assert r.data["env"] == "hall" and r.data["recorded"] == "推门"


# ----------------------------------------------------------------------
# 4. read(carrier|env): synchronous target-owner recall, same tick
# ----------------------------------------------------------------------

READ_CFG = {
    "scenario": "read_sync", "language": "zh",
    "defaults": {"stats_interval": 100, "distance": 3},
    "agents": [
        {"id": "hall", "kind": "environment", "brain": "rule", "profile": "书房"},
        {"id": "book", "kind": "info_carrier", "brain": "retrieval", "profile": "一本古书",
         "status": {"location": "hall"}},
        {"id": "amy", "kind": "character", "brain": "rule", "profile": "艾米",
         "status": {"location": "hall"}},
    ],
    "map": {"default_distance": 3},
}


async def test_read_carrier_returns_target_owned_memories_same_tick():
    k = await build_society(READ_CFG, llm=FakeLLM(), embed_fn=afake_embed,
                             event_log=EventLog(None))
    amy, book = k.agents["amy"], k.agents["book"]

    await k.shared_memory.remember_atomic(["book"], "宝玉衔玉而生", source="sediment")
    # A decoy memory owned by someone else must NOT leak into book's answer.
    await k.shared_memory.remember_atomic(["amy"], "宝玉衔玉而生的传说", source="sediment")

    r = await k.execute(amy, Action("read", {"target": "book", "query": "宝玉"}))
    assert r.ok
    assert len(r.data) == 1 and r.data[0]["text"] == "宝玉衔玉而生"

    k.deliver_pending()
    assert book.stm.inbox.qsize() == 0    # no Message ever sent


async def test_read_environment_target_returns_its_own_memories_same_tick():
    k = await build_society(READ_CFG, llm=FakeLLM(), embed_fn=afake_embed,
                             event_log=EventLog(None))
    amy = k.agents["amy"]

    await k.execute(amy, Action("act_on", {"targets": ["hall"], "content": "点亮了灯"}))
    r = await k.execute(amy, Action("read", {"target": "hall", "query": "灯"}))
    assert r.ok
    assert r.data and r.data[0]["text"] == "点亮了灯"


async def test_read_without_shared_memory_returns_empty_list():
    from society.agent import Agent
    from society.stm import STM
    from society.worldmap import WorldMap
    from society.kernel import Kernel
    from society.events import EventLog as EL

    amy = Agent("amy", "character", RuleBrain(), STM(status={"location": "hall"}))
    book = Agent("book", "info_carrier", RuleBrain(), STM(status={"location": "hall"}))
    hall = Agent("hall", "environment", RuleBrain(), STM())
    k = Kernel({"amy": amy, "book": book, "hall": hall},
               WorldMap(["hall"], default_distance=3), EL(None))

    r = await k.execute(amy, Action("read", {"target": "book", "query": "宝玉"}))
    assert r.ok and r.data == []


# ----------------------------------------------------------------------
# 5. observe: uniform {kind, status, occupants?} shape across all kinds
#    (unaffected by this task -- kept as a regression check)
# ----------------------------------------------------------------------

OBSERVE_CFG = {
    "scenario": "observe_shape", "language": "zh",
    "defaults": {"stats_interval": 100, "distance": 3},
    "agents": [
        {"id": "hall", "kind": "environment", "brain": "rule", "profile": "大厅",
         "status": {"desc": "宽敞"}},
        {"id": "book", "kind": "info_carrier", "brain": "rule", "profile": "书",
         "status": {"location": "hall"}},
        {"id": "amy", "kind": "character", "brain": "rule", "profile": "amy",
         "status": {"location": "hall", "mood": "好奇"}},
        {"id": "ben", "kind": "character", "brain": "rule", "profile": "ben",
         "status": {"location": "hall"}},
    ],
    "map": {"default_distance": 3},
}


async def test_observe_uniform_shape_across_kinds():
    k = await build_society(OBSERVE_CFG, llm=None, embed_fn=afake_embed, event_log=EventLog(None))
    amy = k.agents["amy"]

    r_env = await k.execute(amy, Action("observe", {"target": "hall"}))
    assert r_env.ok
    assert r_env.data["kind"] == "environment"
    assert r_env.data["status"] == {"desc": "宽敞"}
    assert {o["id"] for o in r_env.data["occupants"]} == {"ben", "book"}

    r_char = await k.execute(amy, Action("observe", {"target": "ben"}))
    assert r_char.ok
    assert r_char.data == {"kind": "character", "status": {"location": "hall"}}
    assert "occupants" not in r_char.data

    r_carrier = await k.execute(amy, Action("observe", {"target": "book"}))
    assert r_carrier.ok
    assert r_carrier.data == {"kind": "info_carrier", "status": {"location": "hall"}}
    assert "occupants" not in r_carrier.data


# ----------------------------------------------------------------------
# 6. An environment maintains its own status via update_status; a
#    co-located character sees the change via observe. (unaffected by this
#    task -- kept as a regression check)
# ----------------------------------------------------------------------

ENV_STATUS_CFG = {
    "scenario": "env_self_status", "language": "zh",
    "defaults": {"stats_interval": 100, "distance": 3},
    "agents": [
        {"id": "hall", "kind": "environment", "brain": "rule", "profile": "大厅"},
        {"id": "amy", "kind": "character", "brain": "rule", "profile": "amy",
         "status": {"location": "hall"}},
    ],
    "map": {"default_distance": 3},
}


async def test_env_updates_own_status_and_character_observes_it():
    k = await build_society(ENV_STATUS_CFG, llm=FakeLLM(), embed_fn=afake_embed, event_log=EventLog(None))
    hall, amy = k.agents["hall"], k.agents["amy"]

    r = await k.execute(hall, Action("update_status", {"key": "灯光", "value": "昏暗"}))
    assert r.ok

    obs = await k.execute(amy, Action("observe", {"target": "hall"}))
    assert obs.ok
    assert obs.data["status"]["灯光"] == "昏暗"


# ----------------------------------------------------------------------
# 7. Persistence round-trips legacy brain: rule/retrieval fields; restored
#    env/carrier agents are still RuleBrain (not LLMBrain).
# ----------------------------------------------------------------------

LEGACY_CKPT_CFG = {
    "scenario": "legacy_ckpt", "language": "zh",
    "defaults": {"stats_interval": 100, "distance": 3},
    "agents": [
        {"id": "hall", "kind": "environment", "brain": "rule", "profile": "大厅"},
        {"id": "book", "kind": "info_carrier", "brain": "retrieval", "profile": "书",
         "status": {"location": "hall"}, "corpus": "corpora/x.txt"},
        {"id": "amy", "kind": "character", "brain": "llm", "profile": "amy",
         "status": {"location": "hall"}, "goals": ["chat"]},
    ],
    "map": {"default_distance": 3},
}


async def test_persistence_restores_legacy_rule_retrieval_fields_as_rulebrain(tmp_path):
    k = await build_society(
        LEGACY_CKPT_CFG, llm=FakeLLM(), embed_fn=afake_embed, event_log=EventLog(None)
    )
    assert isinstance(k.agents["hall"].brain, RuleBrain)
    assert isinstance(k.agents["book"].brain, RuleBrain)
    assert isinstance(k.agents["amy"].brain, LLMBrain)

    ckpt_path = str(tmp_path / "ckpt.json")
    save_checkpoint(k, ckpt_path)
    ckpt = load_checkpoint(ckpt_path)
    assert ckpt["scenario"]["agents"][0]["brain"] == "rule"       # unchanged on disk
    assert ckpt["scenario"]["agents"][1]["brain"] == "retrieval"  # unchanged on disk

    restored = await restore_society(
        ckpt, llm=FakeLLM(), embed_fn=afake_embed, event_log=EventLog(None)
    )
    assert isinstance(restored.agents["hall"].brain, RuleBrain)
    assert isinstance(restored.agents["book"].brain, RuleBrain)
