"""Task 9: importance accumulator + reflection trigger for
`GenerativeAgentsMemory`. `_reflect` itself stays a no-op placeholder in this
task (Task 10 fills in the actual synthesis) -- these tests only verify the
trigger: it fires exactly once per crossing of `reflection_threshold`, resets
the accumulator afterward, and a single multi-owner `remember_atomic` call
feeds the accumulator once (not once per owner row).

Task 10 adds tests for the actual reflection synthesis (`_reflect`'s real
body + `_store_reflection`): questions -> evidence -> synthesized reflection
rows tagged `kind`/`source` == "reflection" whose `affiliated` matches the
evidence they were built from, retrievable via a later `recall`, and never
feeding back into the importance accumulator.
"""

from society.baselines import GenerativeAgentsMemory
from tests.helpers import FakeLLM, afake_embed


def _ga_llm_fn(prompt, system=None):
    """FakeLLM `fn` for GenerativeAgentsMemory reflection tests: branches on
    prompt content since importance-scoring, question-generation, and
    synthesis calls all share one FakeLLM instance (bucket isn't visible to
    `fn`)."""
    if "On a scale of 1 to 10" in prompt:
        return "5"
    if "most salient high-level questions" in prompt:
        return "Why does everyone trust Guan Yu?\nWhat unites the sworn brothers?"
    if prompt.startswith("You are synthesizing"):
        for line in prompt.splitlines():
            if line.startswith("Question:"):
                return f"Reflection: {line[len('Question:'):].strip()}"
        return ""
    return ""


def _ga_llm_fn_empty_synthesis(prompt, system=None):
    if "On a scale of 1 to 10" in prompt:
        return "5"
    if "most salient high-level questions" in prompt:
        return "Why does everyone trust Guan Yu?"
    if prompt.startswith("You are synthesizing"):
        return "   "  # whitespace-only -> must be treated as empty
    return ""


def _ga_llm_fn_no_questions(prompt, system=None):
    if "On a scale of 1 to 10" in prompt:
        return "5"
    if "most salient high-level questions" in prompt:
        return ""  # no questions parsed at all
    return ""


class EvidenceSpyGenerativeAgentsMemory(GenerativeAgentsMemory):
    """Records every `_store_reflection` call's arguments so tests can check
    the affiliated ids a reflection row was actually built from."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.stored_reflections = []  # list of (text, owners, evidence_ids)

    async def _store_reflection(self, text, owners, evidence_ids):
        self.stored_reflections.append((text, list(owners), list(evidence_ids)))
        return await super()._store_reflection(text, owners, evidence_ids)


class SpyGenerativeAgentsMemory(GenerativeAgentsMemory):
    """Counts `_reflect` invocations without changing its (no-op) behavior."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.reflect_calls = 0

    async def _reflect(self):
        self.reflect_calls += 1
        return await super()._reflect()


async def test_ga_reflection_does_not_trigger_below_threshold():
    m = SpyGenerativeAgentsMemory(afake_embed, llm=None, reflection_threshold=10)
    # _DEFAULT_IMPORTANCE is 5 (llm=None); one deposit = 5 < 10.
    await m.remember("guanyu", "memory one")
    assert m.reflect_calls == 0
    assert m._importance_since_reflection == 5.0


async def test_ga_reflection_triggers_once_on_crossing_then_resets():
    m = SpyGenerativeAgentsMemory(afake_embed, llm=None, reflection_threshold=10)
    await m.remember("guanyu", "memory one")  # 5 -> accumulator 5
    assert m.reflect_calls == 0
    await m.remember("guanyu", "memory two")  # 5 -> accumulator 10, crosses threshold
    assert m.reflect_calls == 1
    assert m._importance_since_reflection == 0.0


async def test_ga_reflection_multi_owner_deposit_counts_once():
    m = SpyGenerativeAgentsMemory(afake_embed, llm=None, reflection_threshold=1000)
    await m.remember_atomic(["a", "b", "c"], "shared scene")
    # Importance (5, default) must be added ONCE, not once per owner row
    # (which would be 15).
    assert m._importance_since_reflection == 5.0
    ents = m.all_entries()
    assert len(ents) == 3  # sanity: the fan-out itself still happened


async def test_ga_reflection_triggers_twice_with_reset_between():
    m = SpyGenerativeAgentsMemory(afake_embed, llm=None, reflection_threshold=10)
    await m.remember("guanyu", "memory one")  # 5
    await m.remember("guanyu", "memory two")  # 10 -> trigger #1, reset to 0
    assert m.reflect_calls == 1
    await m.remember("guanyu", "memory three")  # 5
    assert m.reflect_calls == 1
    await m.remember("guanyu", "memory four")  # 10 -> trigger #2, reset to 0
    assert m.reflect_calls == 2
    assert m._importance_since_reflection == 0.0


async def test_ga_reflection_threshold_defaults_to_module_constant():
    from society.baselines import REFLECTION_THRESHOLD

    m = GenerativeAgentsMemory(afake_embed, llm=None)
    assert m._reflection_threshold == REFLECTION_THRESHOLD == 150


# ==========================================================================
# Task 10: reflection synthesis + evidence links
# ==========================================================================


async def test_ga_reflection_stores_rows_matching_evidence_and_is_recallable():
    llm = FakeLLM(fn=_ga_llm_fn)
    m = EvidenceSpyGenerativeAgentsMemory(afake_embed, llm=llm, reflection_threshold=9)
    await m.remember("guanyu", "刘备在新野议事")  # importance 5 -> accumulator 5
    await m.remember("guanyu", "关羽镇守荆州")  # importance 5 -> accumulator 10, crosses 9

    assert m.stored_reflections, "reflection pass should have fired and stored something"

    entries = m.all_entries()
    reflection_entries = [e for e in entries if e["meta"].get("kind") == "reflection"]
    assert reflection_entries
    for e in reflection_entries:
        assert e["meta"]["source"] == "reflection"

    # Each stored reflection row's `affiliated` ids match the evidence ids
    # `_store_reflection` was actually called with for that text.
    evidence_by_text = {text: sorted(set(ids)) for text, _owners, ids in m.stored_reflections}
    for e in reflection_entries:
        assert e["affiliated"] == evidence_by_text[e["text"]]
        assert e["affiliated"]  # non-empty: real evidence backs every reflection

    # A subsequent recall by an evidence owner surfaces the reflection
    # (semantic match on the reflection text itself).
    results = await m.recall("guanyu", "刘备在新野议事")
    assert any(r["text"].startswith("Reflection:") for r in results)


async def test_store_reflection_does_not_feed_importance_accumulator():
    m = GenerativeAgentsMemory(afake_embed, llm=None, reflection_threshold=1000)
    await m.remember("guanyu", "some memory")  # accumulator -> 5 (default importance)
    before = m._importance_since_reflection
    await m._store_reflection("a synthesized reflection", ["guanyu"], ["evidence-id-1"])
    assert m._importance_since_reflection == before

    # The reflection row was still written (so the seam isn't just skipping
    # storage entirely, only the accumulator feed).
    entries = m.all_entries()
    assert any(e["meta"].get("kind") == "reflection" for e in entries)


async def test_ga_reflection_llm_none_crossing_threshold_creates_no_reflection():
    m = GenerativeAgentsMemory(afake_embed, llm=None, reflection_threshold=10)
    await m.remember("guanyu", "memory one")  # 5
    await m.remember("guanyu", "memory two")  # 10 -> crosses threshold, llm is None
    entries = m.all_entries()
    assert len(entries) == 2
    assert all(e["meta"].get("kind") != "reflection" for e in entries)


async def test_ga_reflection_empty_synthesis_skips_that_question():
    llm = FakeLLM(fn=_ga_llm_fn_empty_synthesis)
    m = GenerativeAgentsMemory(afake_embed, llm=llm, reflection_threshold=9)
    await m.remember("guanyu", "memory one")
    await m.remember("guanyu", "memory two")  # crosses threshold; synthesis is whitespace-only
    entries = m.all_entries()
    assert len(entries) == 2  # only the two originals -- no reflection row stored
    assert all(e["meta"].get("kind") != "reflection" for e in entries)


async def test_ga_reflection_no_questions_parsed_is_noop():
    llm = FakeLLM(fn=_ga_llm_fn_no_questions)
    m = GenerativeAgentsMemory(afake_embed, llm=llm, reflection_threshold=9)
    await m.remember("guanyu", "memory one")
    await m.remember("guanyu", "memory two")  # crosses threshold; no questions parsed
    entries = m.all_entries()
    assert len(entries) == 2
    assert all(e["meta"].get("kind") != "reflection" for e in entries)
