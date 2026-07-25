"""Task S2 -- unified agent architecture: all three agent kinds
(character/environment/info_carrier) become structurally identical (LLM
brain + full STM) and all cross-agent interaction (act_on, read) becomes
uniformly async through the inbox. See
scratchpad/taskS2-unified-agents-brief.md.

Covers:
  1. Legacy `brain: rule`/`brain: retrieval` yaml values mapping to
     LLMBrain for environment/info_carrier agents when a real llm is
     configured (and staying RuleBrain/RetrievalBrain otherwise, or for
     character agents, unconditionally) -- `society.scenario._make_brain`.
  2. Kind-specific system-prompt preambles for env/carrier LLMBrains.
  3. act_on answered by an environment, end-to-end across 2-3 ticks.
  4. read answered by an info_carrier, end-to-end across 2-3 ticks.
  5. observe's uniform {kind, status, occupants?} shape.
  6. Sleep economy: an idle LLM-brained environment stays ineligible.
  7. An environment updating its own status via update_status.
  8. Persistence round-trips legacy brain: rule/retrieval fields.
"""

import json

from society.actions import Action
from society.brains import LLMBrain, RetrievalBrain, RuleBrain
from society.events import EventLog
from society.persistence import load_checkpoint, restore_society, save_checkpoint
from society.scenario import _make_brain, build_society
from tests.helpers import FakeLLM, afake_embed


# ----------------------------------------------------------------------
# 1. Legacy brain-field mapping (_make_brain)
# ----------------------------------------------------------------------


def test_legacy_rule_env_maps_to_llmbrain_when_llm_configured():
    a = {"id": "hall", "kind": "environment", "brain": "rule", "profile": "大厅"}
    brain = _make_brain(a, llm=FakeLLM(), language="zh", scenario_dir=".")
    assert isinstance(brain, LLMBrain)
    assert "大厅" in brain.profile
    assert "地点/环境" in brain.profile  # kind-specific preamble present


def test_legacy_rule_env_stays_rulebrain_without_real_llm():
    a = {"id": "hall", "kind": "environment", "brain": "rule", "profile": "大厅"}
    brain = _make_brain(a, llm=None, language="zh", scenario_dir=".")
    assert isinstance(brain, RuleBrain)


def test_legacy_retrieval_carrier_maps_to_llmbrain_and_ignores_corpus():
    # corpus points at a file that doesn't exist -- must not be opened at
    # all once the carrier is upgraded to an LLMBrain (Task S2: corpus is
    # retired from the sim path).
    a = {
        "id": "book", "kind": "info_carrier", "brain": "retrieval", "profile": "一本古书",
        "corpus": "corpora/does_not_exist.txt",
    }
    brain = _make_brain(a, llm=FakeLLM(), language="zh", scenario_dir="/no/such/dir")
    assert isinstance(brain, LLMBrain)
    assert "一本古书" in brain.profile
    assert "文书/信息载体" in brain.profile  # kind-specific preamble present


def test_legacy_retrieval_carrier_stays_retrievalbrain_without_real_llm(tmp_path):
    corpora_dir = tmp_path / "corpora"
    corpora_dir.mkdir()
    (corpora_dir / "book.txt").write_text("宝玉衔玉而生。", encoding="utf-8")
    a = {
        "id": "book", "kind": "info_carrier", "brain": "retrieval",
        "corpus": "corpora/book.txt",
    }
    brain = _make_brain(a, llm=None, language="zh", scenario_dir=str(tmp_path))
    assert isinstance(brain, RetrievalBrain)
    assert brain.corpus_text == "宝玉衔玉而生。"


def test_character_rule_brain_unaffected_by_llm_presence():
    a = {"id": "amy", "kind": "character", "brain": "rule", "profile": "amy"}
    assert isinstance(_make_brain(a, llm=FakeLLM(), language="zh", scenario_dir="."), RuleBrain)
    assert isinstance(_make_brain(a, llm=None, language="zh", scenario_dir="."), RuleBrain)


def test_explicit_llm_env_also_gets_kind_preamble():
    a = {"id": "hall", "kind": "environment", "brain": "llm", "profile": "大厅"}
    brain = _make_brain(a, llm=FakeLLM(), language="zh", scenario_dir=".")
    assert isinstance(brain, LLMBrain)
    assert "地点/环境" in brain.profile and "大厅" in brain.profile


def test_carrier_preamble_picks_english_wording_for_en_scenario():
    a = {"id": "book", "kind": "info_carrier", "brain": "retrieval", "profile": "an old book"}
    brain = _make_brain(a, llm=FakeLLM(), language="en", scenario_dir=".")
    assert isinstance(brain, LLMBrain)
    assert "information carrier" in brain.profile and "an old book" in brain.profile


async def test_env_and_carrier_get_llmbrain_and_full_stm_via_build_society():
    cfg = {
        "scenario": "s2_demo", "language": "zh",
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
    hall, book = k.agents["hall"], k.agents["book"]

    assert isinstance(hall.brain, LLMBrain)
    assert isinstance(book.brain, LLMBrain)

    # Full STM (fifo/goals/status/inbox), structurally identical to a
    # character's -- an environment simply has no "location" status key
    # (it IS a location), a carrier keeps its own status/holder semantics.
    for agent in (hall, book):
        assert agent.stm.goals.empty()
        assert agent.stm.inbox.qsize() == 0
        assert agent.stm.status.all() is not None
    assert hall.stm.status.get("location") is None
    assert book.stm.status.get("location") == "hall"


# ----------------------------------------------------------------------
# 2. act_on answered by an environment, end-to-end across ticks
#    (message queued+delivered tick 0, env replies tick 1, reply visible
#    to the actor tick 2 -- see the brief's watch-out item).
# ----------------------------------------------------------------------

ACT_ON_E2E_CFG = {
    "scenario": "act_on_e2e", "language": "zh",
    "defaults": {"stats_interval": 100, "distance": 3},
    "agents": [
        {"id": "hall", "kind": "environment", "brain": "llm", "profile": "一间空荡荡的大厅"},
        {"id": "amy", "kind": "character", "brain": "llm", "profile": "艾米",
         "status": {"location": "hall"}, "goals": ["推门"]},
    ],
    "map": {"default_distance": 3},
}


async def test_act_on_answered_by_env_end_to_end_across_ticks():
    hall_calls = {"n": 0}
    amy_calls = {"n": 0}

    def fn(prompt, system=None):
        if system and "大厅" in system:
            n = hall_calls["n"]
            hall_calls["n"] += 1
            if n == 0:
                # First time hall wakes up (act_on message pending in its
                # own inbox), it replies to the actor via `say`.
                assert '"kind": "act_on"' in prompt
                return json.dumps(
                    {"action": "say", "params": {"targets": ["amy"], "content": "门开了"}}
                )
            # Consume the act_on message so hall goes back to sleep
            # (goal-less, message-less) instead of re-triggering forever.
            return json.dumps({"action": "pop_message", "params": {}})
        if system and "艾米" in system:
            n = amy_calls["n"]
            amy_calls["n"] += 1
            if n == 0:
                return json.dumps(
                    {"action": "act_on", "params": {"targets": ["hall"], "content": "推门"}}
                )
            if n == 1:
                return json.dumps({"action": "wait", "params": {}})
            return json.dumps({"action": "pop_message", "params": {}})
        return json.dumps({"action": "wait", "params": {}})

    llm = FakeLLM(fn=fn)
    event_log = EventLog(None)
    k = await build_society(ACT_ON_E2E_CFG, llm=llm, embed_fn=afake_embed, event_log=event_log)

    hall = k.agents["hall"]
    assert isinstance(hall.brain, LLMBrain)
    assert k.is_eligible(hall) is False  # idle until act_on arrives

    await k.run(max_ticks=3)

    assert hall_calls["n"] >= 2
    assert amy_calls["n"] >= 3

    events = event_log.all()
    amy_pops = [
        e for e in events
        if e["kind"] == "action" and e["agent"] == "amy"
        and e["action"]["name"] == "pop_message"
    ]
    assert amy_pops, "amy never popped a reply message"
    popped = amy_pops[0]["result"]["data"]
    assert popped["kind"] == "say" and popped["sender"] == "hall" and popped["content"] == "门开了"


# ----------------------------------------------------------------------
# 3. read answered by an info_carrier, end-to-end across ticks
# ----------------------------------------------------------------------

READ_E2E_CFG = {
    "scenario": "read_e2e", "language": "zh",
    "defaults": {"stats_interval": 100, "distance": 3},
    "agents": [
        {"id": "hall", "kind": "environment", "brain": "rule", "profile": "书房"},
        {"id": "book", "kind": "info_carrier", "brain": "llm", "profile": "一本古书",
         "status": {"location": "hall"}},
        {"id": "amy", "kind": "character", "brain": "llm", "profile": "艾米",
         "status": {"location": "hall"}, "goals": ["查阅古书"]},
    ],
    "map": {"default_distance": 3},
}


async def test_read_answered_by_carrier_end_to_end_across_ticks():
    book_calls = {"n": 0}
    amy_calls = {"n": 0}

    def fn(prompt, system=None):
        if system and "一本古书" in system:
            n = book_calls["n"]
            book_calls["n"] += 1
            if n == 0:
                assert '"kind": "read"' in prompt
                return json.dumps(
                    {"action": "say", "params": {"targets": ["amy"], "content": "宝玉衔玉而生"}}
                )
            return json.dumps({"action": "pop_message", "params": {}})
        if system and "艾米" in system:
            n = amy_calls["n"]
            amy_calls["n"] += 1
            if n == 0:
                return json.dumps(
                    {"action": "read", "params": {"target": "book", "query": "宝玉"}}
                )
            if n == 1:
                return json.dumps({"action": "wait", "params": {}})
            return json.dumps({"action": "pop_message", "params": {}})
        return json.dumps({"action": "wait", "params": {}})

    llm = FakeLLM(fn=fn)
    event_log = EventLog(None)
    k = await build_society(READ_E2E_CFG, llm=llm, embed_fn=afake_embed, event_log=event_log)

    book = k.agents["book"]
    assert isinstance(book.brain, LLMBrain)
    assert k.is_eligible(book) is False  # idle until read arrives

    await k.run(max_ticks=3)

    assert book_calls["n"] >= 2
    assert amy_calls["n"] >= 3

    events = event_log.all()
    amy_pops = [
        e for e in events
        if e["kind"] == "action" and e["agent"] == "amy"
        and e["action"]["name"] == "pop_message"
    ]
    assert amy_pops, "amy never popped the carrier's reply"
    popped = amy_pops[0]["result"]["data"]
    assert popped["kind"] == "say" and popped["sender"] == "book"
    assert popped["content"] == "宝玉衔玉而生"


# ----------------------------------------------------------------------
# 4. observe: uniform {kind, status, occupants?} shape across all kinds
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
# 5. Sleep economy: an idle LLM-brained environment stays ineligible
# ----------------------------------------------------------------------

IDLE_ENV_CFG = {
    "scenario": "idle_env", "language": "zh",
    "defaults": {"stats_interval": 100, "distance": 3},
    "agents": [
        {"id": "hall", "kind": "environment", "brain": "rule", "profile": "大厅"},
    ],
    "map": {"default_distance": 3},
}


async def test_idle_llm_brained_env_stays_ineligible():
    k = await build_society(IDLE_ENV_CFG, llm=FakeLLM(), embed_fn=afake_embed, event_log=EventLog(None))
    hall = k.agents["hall"]
    assert isinstance(hall.brain, LLMBrain)  # legacy 'rule' upgraded (real llm configured)

    assert k.is_eligible(hall) is False  # empty goals, empty inbox -> asleep

    summary = await k.run(max_ticks=5)

    hall_actions = [
        e for e in k.event_log.all() if e["kind"] == "action" and e["agent"] == "hall"
    ]
    assert hall_actions == []  # never scheduled, never decided
    assert summary["stop_reason"] == "quiescent"


# ----------------------------------------------------------------------
# 6. An environment maintains its own status via update_status; a
#    co-located character sees the change via observe.
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
# 7. Persistence round-trips legacy brain: rule/retrieval fields
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


async def test_persistence_restores_legacy_rule_retrieval_fields_as_llmbrain(tmp_path):
    k = await build_society(
        LEGACY_CKPT_CFG, llm=FakeLLM(), embed_fn=afake_embed, event_log=EventLog(None)
    )
    assert isinstance(k.agents["hall"].brain, LLMBrain)
    assert isinstance(k.agents["book"].brain, LLMBrain)

    ckpt_path = str(tmp_path / "ckpt.json")
    save_checkpoint(k, ckpt_path)
    ckpt = load_checkpoint(ckpt_path)
    assert ckpt["scenario"]["agents"][0]["brain"] == "rule"       # unchanged on disk
    assert ckpt["scenario"]["agents"][1]["brain"] == "retrieval"  # unchanged on disk

    restored = await restore_society(
        ckpt, llm=FakeLLM(), embed_fn=afake_embed, event_log=EventLog(None)
    )
    assert isinstance(restored.agents["hall"].brain, LLMBrain)
    assert isinstance(restored.agents["book"].brain, LLMBrain)
