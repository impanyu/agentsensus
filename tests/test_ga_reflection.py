"""Task 9: importance accumulator + reflection trigger for
`GenerativeAgentsMemory`. `_reflect` itself stays a no-op placeholder in this
task (Task 10 fills in the actual synthesis) -- these tests only verify the
trigger: it fires exactly once per crossing of `reflection_threshold`, resets
the accumulator afterward, and a single multi-owner `remember_atomic` call
feeds the accumulator once (not once per owner row).
"""

from society.baselines import GenerativeAgentsMemory
from tests.helpers import afake_embed


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
