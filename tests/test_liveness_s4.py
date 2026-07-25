"""Task S4 -- simulation liveness: goal-lifecycle guidance (goal_hint).

Task R (revert of part of S4/S2): the `wake_all_characters` config-gated
ablation flag added here is REMOVED -- Task R's awake-based eligibility
model (see society/kernel.py::is_eligible) supersedes it outright: a
character is eligible whenever it is awake (`waiting_until is None` or a
real timeout has elapsed), full stop, with no goal-emptiness requirement
and no separate "wake everyone" arm to bypass it. See
scratchpad/taskR-simmodel-brief.md.
"""

from society.actions import Action
from society.agent import Agent
from society.brains.rule_brain import RuleBrain
from society.events import EventLog
from society.kernel import Kernel
from society.scenario import build_society
from society.stm import STM
from society.worldmap import WorldMap
from tests.helpers import FakeLLM, afake_embed


def char(aid, loc, goals=None, archived=False):
    return Agent(aid, "character", RuleBrain(), STM(status={"location": loc}, goals=goals or []),
                 archived=archived)


def env(aid):
    return Agent(aid, "environment", RuleBrain(), STM())


def build(agents, config=None):
    envs = [a.id for a in agents if a.kind == "environment"]
    return Kernel({a.id: a for a in agents}, WorldMap(envs, default_distance=4),
                  EventLog(None), config=config)


# ----------------------------------------------------------------------
# Fix 1: goal_hint text pushes goal-first, and (Task R) tells an idle
# agent to wait rather than spin.
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


def test_goal_hint_zh_tells_idle_agent_to_wait():
    assert "wait" in Kernel._GOAL_HINT_ZH
    assert "休眠" in Kernel._GOAL_HINT_ZH


def test_goal_hint_en_tells_idle_agent_to_wait():
    assert "wait" in Kernel._GOAL_HINT_EN
    assert "sleep" in Kernel._GOAL_HINT_EN.lower()


# ----------------------------------------------------------------------
# Task R: awake-based eligibility for characters -- no goal requirement,
# no wake_all_characters ablation arm (removed).
# ----------------------------------------------------------------------

async def test_awake_goalless_character_is_eligible():
    # Empty goals, empty inbox, never waited -- under the awake model this
    # is eligible every tick (the S4 goal-emptiness requirement is gone).
    a = char("a", "hall")
    k = build([a, env("hall")])
    assert k.is_eligible(a) is True


async def test_character_after_wait_is_not_eligible():
    a = char("a", "hall", goals=["g"])
    k = build([a, env("hall")])
    await k.execute(a, Action("wait", {}))
    assert k.is_eligible(a) is False


async def test_archived_character_still_ineligible_even_though_awake():
    a = char("a", "hall", archived=True)
    k = build([a, env("hall")])
    assert k.is_eligible(a) is False


async def test_transit_character_still_ineligible_even_though_awake():
    a = char("a", "hall")
    a.transit = {"dest": "garden", "arrive_at": 5}
    k = build([a, env("hall")])
    assert k.is_eligible(a) is False


async def test_wake_all_characters_config_key_no_longer_has_any_effect():
    # The flag is gone -- passing it in config must not resurrect the old
    # ablation-arm behavior (nothing reads this key any more).
    a = char("a", "hall", archived=True)
    k = build([a, env("hall")], config={"wake_all_characters": True})
    assert k.is_eligible(a) is False


# ----------------------------------------------------------------------
# Plumbing: build_society no longer threads any wake_all_characters key
# into kernel.config (the flag was removed, not defaulted).
# ----------------------------------------------------------------------

def _scen():
    return {
        "scenario": "s4_plumbing",
        "language": "zh",
        "defaults": {"stats_interval": 1000},
        "agents": [
            {"id": "worker", "kind": "character", "brain": "rule", "goals": ["work"]},
        ],
    }


async def test_build_society_kernel_config_has_no_wake_all_characters_key():
    cfg = _scen()
    llm = FakeLLM(fn=lambda p, s=None: '{"action": "noop", "params": {}}')
    kernel = await build_society(cfg, llm=llm, embed_fn=afake_embed, event_log=EventLog(None))
    assert "wake_all_characters" not in kernel.config


# ----------------------------------------------------------------------
# remember_hint: a decision-time cue that fires once an agent has piled up
# `_remember_hint_threshold` remember-worthy events (its own say/act_on/
# broadcast + received dialogue) since its last `remember`. Empirical fix
# for agents never choosing the discretionary `remember` action on their
# own (the static skill-doc guidance alone never fired it in live sims).
# ----------------------------------------------------------------------

class _FakeSharedMem:
    def __init__(self):
        self.calls = []

    async def remember(self, owner, text, tick):
        self.calls.append((owner, text, tick))
        return {"id": "m1"}


def _build_with_mem(agents, mem, config=None):
    envs = [a.id for a in agents if a.kind == "environment"]
    return Kernel({a.id: a for a in agents}, WorldMap(envs, default_distance=4),
                  EventLog(None), shared_memory=mem, config=config)


def test_remember_hint_strings_mention_remember_and_cue():
    for s in (Kernel._REMEMBER_HINT_ZH, Kernel._REMEMBER_HINT_EN):
        assert "remember" in s
    assert "记忆提示" in Kernel._REMEMBER_HINT_ZH
    assert "Memory cue" in Kernel._REMEMBER_HINT_EN


def test_remember_hint_absent_below_threshold_present_at_threshold():
    a = char("a", "hall")
    k = build([a, env("hall")])  # default threshold == 2
    assert "remember_hint" not in k._build_agent_view(a)
    k._unremembered[a.id] = 1
    assert "remember_hint" not in k._build_agent_view(a)
    k._unremembered[a.id] = 2
    assert "remember_hint" in k._build_agent_view(a)


def test_remember_hint_respects_config_threshold_and_language():
    a = char("a", "hall")
    k = build([a, env("hall")], config={"remember_hint_threshold": 3, "language": "en"})
    k._unremembered[a.id] = 2
    assert "remember_hint" not in k._build_agent_view(a)
    k._unremembered[a.id] = 3
    view = k._build_agent_view(a)
    assert view["remember_hint"] == Kernel._REMEMBER_HINT_EN


async def test_say_increments_counter_for_speaker_and_receiver():
    a = char("a", "hall")
    b = char("b", "hall")
    k = build([a, b, env("hall")])
    await k._apply(a, Action("say", {"targets": ["b"], "content": "曹操十万大军将至"}), None)
    # speaker's own say counts immediately
    assert k._unremembered.get("a") == 1
    # receiver only counts once the message is actually delivered
    assert k._unremembered.get("b", 0) == 0
    k.deliver_pending()
    assert k._unremembered.get("b") == 1


async def test_remember_resets_counter():
    mem = _FakeSharedMem()
    a = char("a", "hall")
    k = _build_with_mem([a, env("hall")], mem)
    k._unremembered[a.id] = 5
    await k._apply(a, Action("remember", {"text": "刘备决意南撤江陵"}), None)
    assert mem.calls  # remember actually executed
    assert k._unremembered[a.id] == 0


async def test_failed_say_does_not_increment_counter():
    # target not co-located -> say is rejected -> not a real event
    a = char("a", "hall")
    b = char("b", "garden")
    k = build([a, b, env("hall"), env("garden")])
    await k._apply(a, Action("say", {"targets": ["b"], "content": "x"}), None)
    assert k._unremembered.get("a", 0) == 0
