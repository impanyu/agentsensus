"""Tests for `prime_initial_state()` on the two baseline backends whose
higher-level mechanism (G-Memory distillation, Generative Agents
importance-scoring + reflection) needs to run once, CONCURRENTLY, over a
fast-`restore()`-loaded sediment -- instead of the 6000+ sequential
`remember_atomic` awaits that would otherwise replay it (measured at 2.5+
hours). See `society/scenario.py`'s `build_society` for the call site
(`await shared.restore(entries)` then, if defined, `await
shared.prime_initial_state()`).

`CollaborativeMemory` and `society.ltm.SharedMemory` (consensus) do NOT
define `prime_initial_state` -- covered by scenario-level tests already,
not repeated here.
"""

import asyncio

from society.baselines import GenerativeAgentsMemory, GMemory
from society.gmemory_graph import INSIGHT, INTERACTION
from tests.helpers import FakeLLM, afake_embed

INSIGHT_TEXT = "刘关张三人情谊深厚，屡建战功"


def _gmemory_dump(n: int) -> list[dict]:
    """n interaction-tier entries, single-owner, in story order, no stored
    embedding (so restore() must compute one via embed_fn -- matches a real
    holographic dump's shape)."""
    return [
        {
            "id": f"row-{i}",
            "text": f"事件 {i}：关羽在第 {i} 回合巡视荆州",
            "owners": [f"agent-{i % 3}"],
            "affiliated": [],
            "meta": {
                "created_at": "2024-01-01T00:00:00+00:00",
                "source": "history",
                "tick": i,
                "tier": INTERACTION,
                "story_order": i,
            },
        }
        for i in range(n)
    ]


# ==========================================================================
# GMemory.prime_initial_state
# ==========================================================================


async def test_gmemory_prime_distills_restored_interactions_into_insights():
    entries = _gmemory_dump(5)  # distill_every=2 -> batches of 2,2,1 -> 3 insights
    llm = FakeLLM(responses=[INSIGHT_TEXT] * 3)
    m = GMemory(afake_embed, llm=llm, distill_every=2)

    await m.restore(entries)
    assert len([e for e in m.all_entries() if e["meta"]["tier"] == INSIGHT]) == 0

    await m.prime_initial_state()

    all_e = m.all_entries()
    insight_rows = [e for e in all_e if e["meta"]["tier"] == INSIGHT]
    interaction_rows = [e for e in all_e if e["meta"]["tier"] == INTERACTION]
    assert len(interaction_rows) == 5
    # ceil(5 / 2) == 3
    assert len(insight_rows) == 3

    # Every insight links (via derived_from) to its batch's source
    # interactions, and every interaction row id is covered by exactly one
    # insight's source set (batches partition the restored rows).
    covered = set()
    for row in insight_rows:
        sources = m._graph.neighbors(row["id"], "derived_from")
        assert sources, "insight must have derived_from edges to its sources"
        covered.update(sources)
    assert covered == {r["id"] for r in interaction_rows}


async def test_gmemory_prime_batches_by_story_order():
    entries = _gmemory_dump(4)
    # shuffle dump order so restore() writes rows out of story order --
    # prime must still batch by story_order, not insertion order.
    entries = [entries[2], entries[0], entries[3], entries[1]]
    llm = FakeLLM(responses=[INSIGHT_TEXT, INSIGHT_TEXT])
    m = GMemory(afake_embed, llm=llm, distill_every=2)
    await m.restore(entries)
    await m.prime_initial_state()

    # First batch (story_order 0,1) -> row-0, row-1; second batch (2,3) -> row-2, row-3.
    insight_rows = [e for e in m.all_entries() if e["meta"]["tier"] == INSIGHT]
    assert len(insight_rows) == 2
    source_sets = [set(m._graph.neighbors(r["id"], "derived_from")) for r in insight_rows]
    assert {"row-0", "row-1"} in source_sets
    assert {"row-2", "row-3"} in source_sets


async def test_gmemory_prime_skips_empty_insight_batches():
    entries = _gmemory_dump(4)
    llm = FakeLLM(responses=["   ", INSIGHT_TEXT])  # first batch's insight is blank
    m = GMemory(afake_embed, llm=llm, distill_every=2)
    await m.restore(entries)
    await m.prime_initial_state()

    insight_rows = [e for e in m.all_entries() if e["meta"]["tier"] == INSIGHT]
    assert len(insight_rows) == 1
    assert m._graph.neighbors(insight_rows[0]["id"], "derived_from") == ["row-2", "row-3"]


async def test_gmemory_prime_resets_pending_counter_for_sim_time_distillation():
    entries = _gmemory_dump(4)  # distill_every=2 -> prime makes ceil(4/2) == 2 insights
    llm = FakeLLM(responses=[INSIGHT_TEXT, INSIGHT_TEXT])
    m = GMemory(afake_embed, llm=llm, distill_every=2)
    await m.restore(entries)
    await m.prime_initial_state()
    assert m._pending_interactions == []
    baseline_insights = len([e for e in m.all_entries() if e["meta"]["tier"] == INSIGHT])
    assert baseline_insights == 2

    # sim-time remember() must start counting cleanly from zero afterward:
    # one new remember() must NOT immediately trigger another distillation
    # (that would mean the pending counter carried over stale state from
    # priming instead of resetting), but a second one (crossing
    # distill_every==2 pending interactions) must.
    llm._responses.append("新的顿悟")
    await m.remember("guanyu", "新事件A")
    assert (
        len([e for e in m.all_entries() if e["meta"]["tier"] == INSIGHT]) == baseline_insights
    )
    await m.remember("liubei", "新事件B")
    assert (
        len([e for e in m.all_entries() if e["meta"]["tier"] == INSIGHT])
        == baseline_insights + 1
    )


async def test_gmemory_prime_noop_when_llm_is_none():
    entries = _gmemory_dump(4)
    m = GMemory(afake_embed, llm=None, distill_every=2)
    await m.restore(entries)
    await m.prime_initial_state()  # must not raise
    all_e = m.all_entries()
    assert len(all_e) == 4
    assert all(e["meta"]["tier"] == INTERACTION for e in all_e)


async def test_gmemory_prime_is_deterministic_across_two_fresh_instances():
    entries = _gmemory_dump(6)

    async def _run():
        llm = FakeLLM(responses=[INSIGHT_TEXT] * 3)
        m = GMemory(afake_embed, llm=llm, distill_every=2)
        await m.restore(entries)
        await m.prime_initial_state()
        insight_rows = sorted(
            (
                tuple(sorted(m._graph.neighbors(e["id"], "derived_from"))),
                e["text"],
                tuple(sorted(e["owners"])),
            )
            for e in m.all_entries()
            if e["meta"]["tier"] == INSIGHT
        )
        return insight_rows

    r1, r2 = await asyncio.gather(_run(), _run())
    assert r1 == r2
    assert len(r1) == 3


# ==========================================================================
# GenerativeAgentsMemory.prime_initial_state
# ==========================================================================


def _ga_dump(story_events: list[tuple[str, list[str]]]) -> list[dict]:
    """`story_events`: list of (text, owners) in story order -> a dump where
    each event becomes one multi-owner entry (as GenerativeAgentsMemory's
    own `restore()` fans a multi-owner entry into one row per owner)."""
    entries = []
    for i, (text, owners) in enumerate(story_events):
        entries.append(
            {
                "id": f"evt-{i}",
                "text": text,
                "owners": owners,
                "affiliated": [],
                "meta": {
                    "created_at": "2024-01-01T00:00:00+00:00",
                    "source": "history",
                    "tick": i,
                    "story_order": i,
                },
            }
        )
    return entries


async def test_ga_prime_updates_importance_for_every_row():
    entries = _ga_dump(
        [
            ("刘备三顾茅庐", ["guanyu", "liubei"]),
            ("张飞喝断当阳桥", ["zhangfei"]),
        ]
    )
    llm = FakeLLM(fn=lambda p, s=None: "8")
    m = GenerativeAgentsMemory(afake_embed, llm=llm, reflection_threshold=10_000)
    await m.restore(entries)
    await m.prime_initial_state()

    entries_after = m.all_entries()
    assert len(entries_after) == 3  # 2 owners for event 0 + 1 owner for event 1
    assert all(e["meta"]["importance"] == 8 for e in entries_after)


async def test_ga_prime_scores_importance_once_per_unique_text_not_per_row():
    entries = _ga_dump([("三人共守荆州", ["guanyu", "liubei", "zhangfei"])])
    llm = FakeLLM(fn=lambda p, s=None: "8")
    m = GenerativeAgentsMemory(afake_embed, llm=llm, reflection_threshold=10_000)
    await m.restore(entries)
    await m.prime_initial_state()

    importance_calls = [c for c in llm.calls if c[0] == "importance"]
    assert len(importance_calls) == 1  # one unique text -> one score call, not 3


async def test_ga_prime_triggers_reflection_and_counts_event_once():
    # threshold 9: two events of importance 8 each cross it on the second
    # event -- if a 2-owner event wrongly deposited its importance twice,
    # the FIRST event alone (owners=2) would already cross the threshold.
    entries = _ga_dump(
        [
            ("刘备在新野议事", ["guanyu", "liubei"]),  # 2 owners, 1 logical event
            ("关羽镇守荆州", ["guanyu"]),
        ]
    )

    def _fn(prompt, system=None):
        if "On a scale of 1 to 10" in prompt:
            return "8"
        if "most salient high-level questions" in prompt:
            return "谁最受信任？"
        if prompt.startswith("You are synthesizing"):
            return "Reflection: 刘关张情谊深厚"
        return ""

    llm = FakeLLM(fn=_fn)
    m = GenerativeAgentsMemory(afake_embed, llm=llm, reflection_threshold=9)
    await m.restore(entries)
    await m.prime_initial_state()

    entries_after = m.all_entries()
    reflection_rows = [e for e in entries_after if e["meta"].get("source") == "reflection"]
    assert reflection_rows, "second event alone should cross the threshold and fire a reflection"
    assert all(e["meta"].get("kind") == "reflection" for e in reflection_rows)

    # accumulator was reset by the crossing, not left dangling
    assert m._importance_since_reflection == 0.0


async def test_ga_prime_does_not_trigger_reflection_if_first_event_alone_would_wrongly_cross():
    # A single 2-owner event of importance 8: if the accumulator were fed
    # once PER ROW (8+8=16) it would wrongly cross a threshold of 10; fed
    # once per logical event (8) it must not.
    entries = _ga_dump([("刘备在新野议事", ["guanyu", "liubei"])])
    llm = FakeLLM(fn=lambda p, s=None: "8")
    m = GenerativeAgentsMemory(afake_embed, llm=llm, reflection_threshold=10)
    await m.restore(entries)
    await m.prime_initial_state()
    assert m._importance_since_reflection == 8.0
    assert all(e["meta"].get("source") != "reflection" for e in m.all_entries())


async def test_ga_prime_noop_when_llm_is_none():
    entries = _ga_dump([("刘备三顾茅庐", ["guanyu", "liubei"])])
    m = GenerativeAgentsMemory(afake_embed, llm=None, reflection_threshold=10)
    await m.restore(entries)
    before = [dict(e["meta"]) for e in m.all_entries()]
    await m.prime_initial_state()  # must not raise
    after = [dict(e["meta"]) for e in m.all_entries()]
    assert before == after


async def test_ga_prime_is_deterministic_across_two_fresh_instances():
    entries = _ga_dump(
        [
            ("刘备三顾茅庐", ["guanyu", "liubei"]),
            ("张飞喝断当阳桥", ["zhangfei"]),
            ("三人共守荆州", ["guanyu", "liubei", "zhangfei"]),
        ]
    )

    def _fn(prompt, system=None):
        if "On a scale of 1 to 10" in prompt:
            # vary by content so the mapping is checkable, not just constant
            return "9" if "三顾茅庐" in prompt else "6"
        return ""

    async def _run():
        llm = FakeLLM(fn=_fn)
        m = GenerativeAgentsMemory(afake_embed, llm=llm, reflection_threshold=10_000)
        await m.restore(entries)
        await m.prime_initial_state()
        return sorted((e["text"], e["meta"]["importance"]) for e in m.all_entries())

    r1, r2 = await asyncio.gather(_run(), _run())
    assert r1 == r2
    assert dict(r1)["刘备三顾茅庐"] == 9
    assert dict(r1)["张飞喝断当阳桥"] == 6
