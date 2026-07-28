import pytest

from society.actions import Action
from society.agent import Agent
from society.brains.rule_brain import RuleBrain
from society.events import EventLog
from society.kernel import Kernel
from society.ltm import SharedMemory
from society.baselines import (
    GenerativeAgentsMemory,
    GMemory,
    CollaborativeMemory,
    make_memory,
)
from society.gmemory_graph import INTERACTION
from society.stm import STM
from society.worldmap import WorldMap
from tests.helpers import FakeLLM, afake_embed


# ----------------------------------------------------------------------
# generic helpers
# ----------------------------------------------------------------------

TEXT_A = "关羽千里走单骑"
TEXT_B = "刘备三顾茅庐"


def _stats_shape_ok(stats):
    assert set(stats.keys()) == {"total", "shared", "ratio"}
    assert isinstance(stats["total"], int)
    assert isinstance(stats["shared"], int)
    assert isinstance(stats["ratio"], float)


# ========================================================================
# GenerativeAgentsMemory
# ========================================================================


async def test_ga_remember_then_recall_returns_text():
    m = GenerativeAgentsMemory(afake_embed)
    await m.remember("guanyu", TEXT_A)
    results = await m.recall("guanyu", TEXT_A, top_k=5)
    assert any(r["text"] == TEXT_A for r in results)
    assert set(results[0].keys()) == {"id", "text"}


async def test_ga_recall_ranks_by_relevance():
    m = GenerativeAgentsMemory(afake_embed)
    # Neutralize the recency term (DECAY=0 -> exp(0)=1 for every row
    # regardless of ticks-since-access) so recency and importance (both
    # default, tied) cannot decide the ranking -- only relevance can. TEXT_B
    # is remembered *first* (so a stable sort over an all-tied score would
    # put it on top), TEXT_A second; the query is TEXT_A, so only a
    # genuinely-working relevance term can push TEXT_A above TEXT_B.
    m.DECAY = 0.0
    await m.remember("guanyu", TEXT_B)
    await m.remember("guanyu", TEXT_A)
    results = await m.recall("guanyu", TEXT_A, top_k=2)
    assert results[0]["text"] == TEXT_A


async def test_ga_export_restore_roundtrip():
    m = GenerativeAgentsMemory(afake_embed)
    await m.remember("guanyu", TEXT_A)
    exported = m.export()
    assert len(exported) == 1
    assert exported[0]["embedding"] is not None
    assert exported[0]["text"] == TEXT_A
    assert exported[0]["owners"] == ["guanyu"]

    m2 = GenerativeAgentsMemory(afake_embed)
    await m2.restore(exported)
    entries = m2.all_entries()
    assert len(entries) == 1
    assert entries[0]["id"] == exported[0]["id"]
    assert entries[0]["text"] == TEXT_A
    assert entries[0]["owners"] == ["guanyu"]


async def test_ga_stats_shape():
    m = GenerativeAgentsMemory(afake_embed)
    await m.remember("guanyu", TEXT_A)
    _stats_shape_ok(m.stats())


async def test_ga_forget_removes_row():
    m = GenerativeAgentsMemory(afake_embed)
    results = await m.remember("guanyu", TEXT_A)
    memory_id = results[0]["id"]
    assert m.forget("guanyu", memory_id) is True
    assert m.all_entries() == []
    # forgetting again (already gone) returns False
    assert m.forget("guanyu", memory_id) is False


async def test_ga_duplication_across_owners_and_private_recall():
    m = GenerativeAgentsMemory(afake_embed)
    await m.remember("guanyu", TEXT_A)
    await m.remember("liubei", TEXT_A)

    entries = m.all_entries()
    assert len(entries) == 2  # duplicated, one row per owner -- no dedup

    guanyu_results = await m.recall("guanyu", TEXT_A, top_k=5)
    assert len(guanyu_results) == 1
    assert all(r["text"] == TEXT_A for r in guanyu_results)

    liubei_results = await m.recall("liubei", TEXT_A, top_k=5)
    assert len(liubei_results) == 1


async def test_ga_importance_uses_llm_when_available():
    llm = FakeLLM(responses=["8"])
    m = GenerativeAgentsMemory(afake_embed, llm=llm)
    await m.remember("guanyu", TEXT_A)
    entries = m.all_entries()
    assert entries[0]["meta"]["importance"] == 8


async def test_ga_importance_defaults_without_llm():
    m = GenerativeAgentsMemory(afake_embed, llm=None)
    await m.remember("guanyu", TEXT_A)
    entries = m.all_entries()
    assert entries[0]["meta"]["importance"] == 5


async def test_ga_restore_advances_clock_so_recall_does_not_overflow():
    # Regression test: a checkpoint exported from a long-running instance
    # can carry a very large `last_access` tick. Restoring it into a fresh
    # instance (whose internal clock starts at 0) must not leave `recall`
    # computing a huge negative `ticks_since` -- which would overflow
    # math.exp -- against the new, low clock.
    m = GenerativeAgentsMemory(afake_embed)
    await m.remember("guanyu", TEXT_A)
    exported = m.export()
    exported[0]["meta"]["last_access"] = 10_000_000

    m2 = GenerativeAgentsMemory(afake_embed)
    await m2.restore(exported)

    results = await m2.recall("guanyu", TEXT_A, top_k=5)  # must not raise
    assert any(r["text"] == TEXT_A for r in results)


async def test_ga_chroma_per_owner_fanout():
    m = GenerativeAgentsMemory(afake_embed, llm=None)
    await m.remember_atomic(["a", "b"], "shared scene")
    ents = m.all_entries()
    assert len(ents) == 2  # one row per owner
    assert {e["owners"][0] for e in ents} == {"a", "b"}


async def test_ga_chroma_recall_scoped_and_reflection_fields():
    m = GenerativeAgentsMemory(afake_embed, llm=None)
    await m.remember("a", "刘备在新野议事")
    assert await m.recall("a", "新野")  # owner a sees it
    assert (await m.recall("b", "新野")) == []  # owner b does not


# ========================================================================
# GMemory
# ========================================================================


async def test_gmemory_remember_then_recall_returns_text():
    m = GMemory(afake_embed)
    await m.remember("guanyu", TEXT_A)
    results = await m.recall("guanyu", TEXT_A, top_k=5)
    assert any(r["text"] == TEXT_A for r in results)
    assert set(results[0].keys()) == {"id", "text"}


async def test_gmemory_recall_ranks_by_relevance():
    m = GMemory(afake_embed)
    await m.remember("guanyu", TEXT_A)
    await m.remember("guanyu", TEXT_B)
    results = await m.recall("guanyu", TEXT_A, top_k=2)
    assert results[0]["text"] == TEXT_A


async def test_gmemory_export_restore_roundtrip():
    m = GMemory(afake_embed)
    await m.remember("guanyu", TEXT_A)
    exported = m.export()
    assert len(exported) == 1
    assert exported[0]["embedding"] is not None

    m2 = GMemory(afake_embed)
    await m2.restore(exported)
    entries = m2.all_entries()
    assert len(entries) == 1
    assert entries[0]["text"] == TEXT_A
    assert entries[0]["owners"] == ["guanyu"]


async def test_gmemory_stats_shape():
    m = GMemory(afake_embed)
    await m.remember("guanyu", TEXT_A)
    _stats_shape_ok(m.stats())


async def test_gmemory_forget_removes_ownership():
    m = GMemory(afake_embed)
    results = await m.remember("guanyu", TEXT_A)
    memory_id = results[0]["id"]
    assert m.forget("guanyu", memory_id) is True
    assert m.all_entries() == []


async def test_gmemory_recall_is_shared_across_agents():
    m = GMemory(afake_embed)
    await m.remember("guanyu", TEXT_A)
    # agent B never wrote anything but can retrieve A's shared entry
    results = await m.recall("liubei", TEXT_A, top_k=5)
    assert any(r["text"] == TEXT_A for r in results)


async def test_gmemory_no_dedup_on_duplicate_text():
    m = GMemory(afake_embed)
    await m.remember("guanyu", TEXT_A)
    await m.remember("liubei", TEXT_A)
    entries = m.all_entries()
    assert len(entries) == 2  # appended, no merge


async def test_gmemory_chroma_per_owner_fanout():
    m = GMemory(afake_embed, llm=None)
    await m.remember_atomic(["a", "b"], "shared scene")
    ents = m.all_entries()
    assert len(ents) == 2  # one row per owner, no shared multi-owner row
    assert {e["owners"][0] for e in ents} == {"a", "b"}


async def test_gmemory_recall_of_owner_filter():
    m = GMemory(afake_embed, llm=None)
    await m.remember("a", "刘备在新野")
    assert (await m.recall_of("a", "新野"))
    assert (await m.recall_of("z", "新野")) == []


async def test_gmemory_forget_sole_owner_deletes_row_leaves_sibling_row():
    # With remember_atomic now fanning multi-owner deposits out into one
    # single-owner row per owner (see GMemory.remember_atomic), a 2-owner
    # call no longer produces one shared row to partially forget from --
    # forgetting a row's sole owner takes the whole-row-delete path, and
    # must leave the sibling row for the other owner (from the same
    # remember_atomic call) untouched. (Partial-owner forget on a row that
    # SURVIVES with owners remaining -- and the ChromaRows.update_metadata
    # merge-trap regression that guards -- is now covered against
    # distillation's genuinely multi-owner insight rows; see
    # tests/test_gmemory_full.py::test_gmemory_forget_partial_owner_keeps_edges.)
    m = GMemory(afake_embed, llm=None)
    await m.remember_atomic(["a", "b"], "shared scene")
    rows_by_owner = {e["owners"][0]: e["id"] for e in m.all_entries()}
    assert set(rows_by_owner) == {"a", "b"}

    assert m.forget("b", rows_by_owner["b"]) is True

    assert (await m.recall_of("b", "scene")) == []
    assert any(e["text"] == "shared scene" for e in await m.recall_of("a", "scene"))

    entries = m.all_entries()
    assert len(entries) == 1
    assert entries[0]["owners"] == ["a"]


# ========================================================================
# CollaborativeMemory
# ========================================================================


async def test_collab_remember_then_recall_returns_text():
    m = CollaborativeMemory(afake_embed)
    await m.remember("guanyu", TEXT_A)
    results = await m.recall("guanyu", TEXT_A, top_k=5)
    assert any(r["text"] == TEXT_A for r in results)
    assert set(results[0].keys()) == {"id", "text"}


async def test_collab_recall_ranks_by_relevance():
    m = CollaborativeMemory(afake_embed)
    await m.remember("guanyu", TEXT_A)
    await m.remember("guanyu", TEXT_B)
    results = await m.recall("guanyu", TEXT_A, top_k=2)
    assert results[0]["text"] == TEXT_A


async def test_collab_export_restore_roundtrip():
    m = CollaborativeMemory(afake_embed)
    await m.remember("guanyu", TEXT_A)
    exported = m.export()
    assert len(exported) == 1
    assert exported[0]["embedding"] is not None
    assert exported[0]["owners"] == ["guanyu"]

    m2 = CollaborativeMemory(afake_embed)
    await m2.restore(exported)
    entries = m2.all_entries()
    assert len(entries) == 1
    assert entries[0]["text"] == TEXT_A
    assert entries[0]["owners"] == ["guanyu"]


async def test_collab_stats_shape():
    m = CollaborativeMemory(afake_embed)
    await m.remember("guanyu", TEXT_A)
    _stats_shape_ok(m.stats())


async def test_collab_acl_gates_recall_then_grant_allows():
    m = CollaborativeMemory(afake_embed)
    results = await m.remember("guanyu", TEXT_A)
    memory_id = results[0]["id"]

    # B has no read access yet
    b_results = await m.recall("liubei", TEXT_A, top_k=5)
    assert b_results == []

    # grant read access to B
    assert m.grant(memory_id, "liubei") is True
    b_results = await m.recall("liubei", TEXT_A, top_k=5)
    assert any(r["text"] == TEXT_A for r in b_results)

    stats = m.stats()
    assert stats["shared"] == 1  # ACL now has 2 members


async def test_collab_forget_removes_acl_membership():
    m = CollaborativeMemory(afake_embed)
    results = await m.remember("guanyu", TEXT_A)
    memory_id = results[0]["id"]
    m.grant(memory_id, "liubei")

    assert m.forget("guanyu", memory_id) is True
    entries = m.all_entries()
    assert len(entries) == 1
    assert entries[0]["owners"] == ["liubei"]

    # removing the last reader deletes the fragment entirely
    assert m.forget("liubei", memory_id) is True
    assert m.all_entries() == []


async def test_collab_forget_unknown_agent_returns_false():
    m = CollaborativeMemory(afake_embed)
    results = await m.remember("guanyu", TEXT_A)
    memory_id = results[0]["id"]
    assert m.forget("liubei", memory_id) is False


async def test_collab_chroma_acl_gates_recall():
    m = CollaborativeMemory(afake_embed, llm=None)
    res = await m.remember("a", "密信内容")
    mid = res[0]["id"]
    assert (await m.recall("a", "密信"))
    assert (await m.recall("b", "密信")) == []
    assert m.grant(mid, "b") is True
    assert (await m.recall("b", "密信"))


async def test_collab_forget_partial_acl_then_recall():
    # Regression for the ChromaRows.update_metadata merge trap (see
    # GMemory.forget, fixed in 1eab70b): forgetting one reader out of a
    # multi-reader ACL must null out that reader's `acl_<id>` flag, not
    # just leave it stale on the stored metadata -- otherwise the revoked
    # agent keeps matching `where={f"acl_{id}": True}` and can still recall
    # the fragment even though it was removed from the ACL.
    m = CollaborativeMemory(afake_embed)
    results = await m.remember("a", TEXT_A)
    memory_id = results[0]["id"]
    assert m.grant(memory_id, "b") is True

    assert m.forget("a", memory_id) is True

    assert await m.recall("a", TEXT_A) == []
    b_results = await m.recall("b", TEXT_A)
    assert any(r["text"] == TEXT_A for r in b_results)

    entries = m.all_entries()
    assert len(entries) == 1
    assert entries[0]["owners"] == ["b"]


# ========================================================================
# factory
# ========================================================================


def test_make_memory_returns_correct_classes():
    assert isinstance(make_memory("consensus", afake_embed), SharedMemory)
    assert isinstance(
        make_memory("generative_agents", afake_embed), GenerativeAgentsMemory
    )
    assert isinstance(make_memory("g_memory", afake_embed), GMemory)
    assert isinstance(make_memory("collaborative", afake_embed), CollaborativeMemory)


def test_make_memory_unknown_kind_raises():
    with pytest.raises(ValueError):
        make_memory("nonexistent", afake_embed)


def test_make_memory_ignores_extra_kwargs():
    # existing call sites do SharedMemory(embed_fn, llm, max_chars=...) -- adapters
    # must accept and ignore kwargs they don't use.
    m = make_memory(
        "generative_agents", afake_embed, llm=None, max_chars=80, sim_threshold=0.86
    )
    assert isinstance(m, GenerativeAgentsMemory)


# ========================================================================
# remember_atomic / recall_of / affiliations -- kernel-required interface
#
# The kernel (society/kernel.py::_execute_act_on/_execute_read/
# _execute_affiliated_crud) calls remember_atomic, recall_of,
# add_affiliations, remove_affiliations and get_affiliations on whatever
# `shared_memory` it was built with. Only society.ltm.SharedMemory
# implemented these; running a live sim on any of the 3 baselines here
# crashed with AttributeError. These tests cover all 3 baselines against
# that same interface.
# ========================================================================

BASELINE_CLASSES = [GenerativeAgentsMemory, GMemory, CollaborativeMemory]


@pytest.mark.parametrize("cls", BASELINE_CLASSES)
async def test_remember_atomic_deposits_and_is_recallable(cls):
    m = cls(afake_embed)
    result = await m.remember_atomic(["env1"], TEXT_A)
    assert isinstance(result, dict)
    assert result["id"]

    recalled = await m.recall_of("env1", TEXT_A)
    assert any(r["text"] == TEXT_A for r in recalled)
    assert set(recalled[0].keys()) == {"id", "text"}


@pytest.mark.parametrize("cls", BASELINE_CLASSES)
async def test_remember_atomic_empty_owners_raises(cls):
    m = cls(afake_embed)
    with pytest.raises(ValueError):
        await m.remember_atomic([], "x")


@pytest.mark.parametrize("cls", BASELINE_CLASSES)
async def test_remember_atomic_blank_text_returns_none(cls):
    m = cls(afake_embed)
    assert await m.remember_atomic(["a"], "  ") is None
    assert m.all_entries() == []


@pytest.mark.parametrize("cls", BASELINE_CLASSES)
async def test_recall_of_scopes_to_owner(cls):
    m = cls(afake_embed)
    await m.remember_atomic(["a"], TEXT_A)
    await m.remember_atomic(["b"], TEXT_B)

    a_results = await m.recall_of("a", TEXT_A, top_k=5)
    assert all(r["text"] != TEXT_B for r in a_results)
    assert any(r["text"] == TEXT_A for r in a_results)

    stranger_results = await m.recall_of("nobody", TEXT_A, top_k=5)
    assert stranger_results == []


async def test_ga_remember_atomic_creates_one_row_per_owner():
    m = GenerativeAgentsMemory(afake_embed)
    result = await m.remember_atomic(["guanyu", "liubei"], "共享场景")
    entries = m.all_entries()
    assert len(entries) == 2  # per-owner duplication, the whole point of GA
    assert {e["owners"][0] for e in entries} == {"guanyu", "liubei"}
    assert result["merged"] is False
    assert set(result["owners"]) == {"guanyu", "liubei"}

    guanyu_results = await m.recall_of("guanyu", "共享场景")
    assert any(r["text"] == "共享场景" for r in guanyu_results)
    liubei_results = await m.recall_of("liubei", "共享场景")
    assert any(r["text"] == "共享场景" for r in liubei_results)


async def test_gmemory_remember_atomic_creates_one_row_per_owner():
    m = GMemory(afake_embed)
    result = await m.remember_atomic(["guanyu", "liubei"], "共享场景")
    entries = m.all_entries()
    assert len(entries) == 2  # per-owner duplication, no shared multi-owner row
    assert {e["owners"][0] for e in entries} == {"guanyu", "liubei"}
    assert result["merged"] is False
    assert set(result["owners"]) == {"guanyu", "liubei"}

    for owner in ("guanyu", "liubei"):
        results = await m.recall_of(owner, "共享场景")
        assert any(r["text"] == "共享场景" for r in results)


async def test_collab_remember_atomic_creates_one_fragment_per_owner():
    m = CollaborativeMemory(afake_embed)
    result = await m.remember_atomic(["guanyu", "liubei"], "共享场景")
    entries = m.all_entries()
    assert len(entries) == 2  # per-owner duplication, no shared ACL fragment
    assert {e["owners"][0] for e in entries} == {"guanyu", "liubei"}
    assert result["merged"] is False
    assert set(result["owners"]) == {"guanyu", "liubei"}

    for owner in ("guanyu", "liubei"):
        results = await m.recall_of(owner, "共享场景")
        assert any(r["text"] == "共享场景" for r in results)


async def test_gmemory_restore_fans_multi_owner_entry_into_one_row_per_owner():
    # Mirrors GenerativeAgentsMemory.restore's fan-out contract: a
    # multi-owner dump entry (e.g. a consensus-merged export) becomes one
    # single-owner row per owner, first owner keeping the entry's original
    # id, extra owners getting a fresh id.
    dump = [
        {
            "id": "shared-e1",
            "text": "共享场景",
            "owners": ["guanyu", "liubei"],
            "affiliated": [],
            "meta": {"source": "test", "tier": INTERACTION},
            "embedding": None,
        }
    ]
    m = GMemory(afake_embed)
    await m.restore(dump)

    entries = m.all_entries()
    assert len(entries) == 2
    assert {e["owners"][0] for e in entries} == {"guanyu", "liubei"}

    by_owner = {e["owners"][0]: e for e in entries}
    assert by_owner["guanyu"]["id"] == "shared-e1"  # first owner keeps entry id
    assert by_owner["liubei"]["id"] != "shared-e1"  # extra owner gets a fresh id

    for owner in ("guanyu", "liubei"):
        results = await m.recall_of(owner, "共享场景")
        assert any(r["text"] == "共享场景" for r in results)


async def test_collab_restore_fans_multi_owner_entry_into_one_fragment_per_owner():
    dump = [
        {
            "id": "shared-e1",
            "text": "共享场景",
            "owners": ["guanyu", "liubei"],
            "affiliated": [],
            "meta": {"source": "test"},
            "embedding": None,
        }
    ]
    m = CollaborativeMemory(afake_embed)
    await m.restore(dump)

    entries = m.all_entries()
    assert len(entries) == 2
    assert {e["owners"][0] for e in entries} == {"guanyu", "liubei"}

    by_owner = {e["owners"][0]: e for e in entries}
    assert by_owner["guanyu"]["id"] == "shared-e1"  # first owner keeps entry id
    assert by_owner["liubei"]["id"] != "shared-e1"  # extra owner gets a fresh id

    for owner in ("guanyu", "liubei"):
        results = await m.recall_of(owner, "共享场景")
        assert any(r["text"] == "共享场景" for r in results)


@pytest.mark.parametrize("cls", BASELINE_CLASSES)
async def test_affiliations_roundtrip(cls):
    m = cls(afake_embed)
    result = await m.remember_atomic(["a"], TEXT_A)
    memory_id = result["id"]
    other = (await m.remember_atomic(["a"], TEXT_B))["id"]

    assert m.get_affiliations(memory_id) == []

    assert m.add_affiliations(memory_id, [other]) is True
    assert m.get_affiliations(memory_id) == [other]

    # self-id is excluded even if passed explicitly
    assert m.add_affiliations(memory_id, [memory_id]) is True
    assert m.get_affiliations(memory_id) == [other]

    assert m.remove_affiliations(memory_id, [other]) is True
    assert m.get_affiliations(memory_id) == []


@pytest.mark.parametrize("cls", BASELINE_CLASSES)
async def test_affiliations_on_missing_id(cls):
    m = cls(afake_embed)
    assert m.get_affiliations("nope") == []
    assert m.add_affiliations("nope", ["x"]) is False
    assert m.remove_affiliations("nope", ["x"]) is False


@pytest.mark.parametrize("cls", BASELINE_CLASSES)
async def test_affiliated_field_present_in_all_entries_and_export(cls):
    m = cls(afake_embed)
    result = await m.remember_atomic(["a"], TEXT_A)
    other = (await m.remember_atomic(["a"], TEXT_B))["id"]
    m.add_affiliations(result["id"], [other])

    entry = next(e for e in m.all_entries() if e["id"] == result["id"])
    assert entry["affiliated"] == [other]

    exported = next(e for e in m.export() if e["id"] == result["id"])
    assert exported["affiliated"] == [other]


@pytest.mark.parametrize("cls", BASELINE_CLASSES)
async def test_affiliated_roundtrips_through_export_restore(cls):
    m = cls(afake_embed)
    result = await m.remember_atomic(["a"], TEXT_A)
    other = (await m.remember_atomic(["a"], TEXT_B))["id"]
    m.add_affiliations(result["id"], [other])

    exported = m.export()
    m2 = cls(afake_embed)
    await m2.restore(exported)

    entry = next(e for e in m2.all_entries() if e["id"] == result["id"])
    assert entry["affiliated"] == [other]


# ========================================================================
# kernel integration -- the exact path that crashed with AttributeError
# before these baselines implemented remember_atomic/recall_of/
# add_affiliations/remove_affiliations/get_affiliations.
# ========================================================================


def _build_kernel(shared):
    envs = ["hall"]
    agents = {
        "a": Agent("a", "character", RuleBrain(), STM(status={"location": "hall"})),
        "hall": Agent("hall", "environment", RuleBrain(), STM()),
    }
    return Kernel(agents, WorldMap(envs, edges=[], default_distance=4),
                  EventLog(None), shared_memory=shared)


@pytest.mark.parametrize("kind", ["generative_agents", "g_memory", "collaborative"])
async def test_kernel_act_on_and_read_do_not_crash_on_baseline_memory(kind):
    shared = make_memory(kind, afake_embed)
    k = _build_kernel(shared)
    agent = k.agents["a"]

    r = await k.execute(agent, Action("act_on", {"targets": ["hall"], "content": "大门"}))
    assert r.ok, r.error

    r2 = await k.execute(agent, Action("read", {"target": "hall", "query": "大门"}))
    assert r2.ok, r2.error
    assert any(d["text"] == "大门" for d in r2.data)

    r3 = await k.execute(
        agent,
        Action("act_on", {"targets": ["hall"], "content": "花瓶"}),
    )
    assert r3.ok, r3.error

    # affiliated CRUD via kernel needs the actor to be an owner; act_on
    # deposits memories owned by the environment, not the character, so
    # exercise add/remove/get_affiliations directly against the backend
    # (same objects the kernel calls through _execute_affiliated_crud).
    entries = shared.all_entries()
    ids = [e["id"] for e in entries if e["text"] in ("大门", "花瓶")]
    assert len(ids) == 2
    assert shared.add_affiliations(ids[0], [ids[1]]) is True
    assert shared.get_affiliations(ids[0]) == [ids[1]]
    assert shared.remove_affiliations(ids[0], [ids[1]]) is True
    assert shared.get_affiliations(ids[0]) == []


# ========================================================================
# Task 5: per-run Chroma collection isolation + footprint fairness
# ========================================================================


def _synthetic_dump():
    """A tiny holographic dump with 3 multi-owner entries -- owners
    [a,b,c], [a,b], [x] -- in `export()`/`restore()` format. `embedding` is
    left None so `restore()` computes it via `afake_embed`, exactly as the
    brief asks. This is the fixture used to lock in the core fairness
    property: GenerativeAgentsMemory, GMemory, and CollaborativeMemory all
    fan out one row per owner (none of them has the consensus backend's
    cross-agent equivalence merge, so each keeps its own per-owner copy),
    while only the consensus store keeps one row per entry."""
    return [
        {
            "id": "e1",
            "text": TEXT_A,
            "owners": ["a", "b", "c"],
            "affiliated": [],
            "meta": {"source": "test"},
            "embedding": None,
        },
        {
            "id": "e2",
            "text": TEXT_B,
            "owners": ["a", "b"],
            "affiliated": [],
            "meta": {"source": "test"},
            "embedding": None,
        },
        {
            "id": "e3",
            "text": "曹操煮酒论英雄",
            "owners": ["x"],
            "affiliated": [],
            "meta": {"source": "test"},
            "embedding": None,
        },
    ]


async def test_restore_footprint_per_method():
    dump = _synthetic_dump()

    consensus = SharedMemory(afake_embed)
    ga = make_memory("generative_agents", afake_embed)
    gm = make_memory("g_memory", afake_embed)
    collab = make_memory("collaborative", afake_embed)

    await consensus.restore(dump)
    await ga.restore(dump)
    await gm.restore(dump)
    await collab.restore(dump)

    consensus_total = consensus.stats()["total"]
    ga_total = ga.stats()["total"]
    gm_total = gm.stats()["total"]
    collab_total = collab.stats()["total"]

    # generative_agents / g_memory / collaborative: one row per (entry,
    # owner) pair -- 3 + 2 + 1 = 6. None of the three baselines has the
    # consensus backend's cross-agent equivalence merge, so each is
    # faithfully modeled as per-owner duplication (see the class
    # docstrings) -- every agent that knows an event keeps its own record.
    expected_fanout = sum(len(e["owners"]) for e in dump)
    assert expected_fanout == 6
    assert ga_total == expected_fanout
    assert gm_total == expected_fanout
    assert collab_total == expected_fanout

    # consensus is the only shared store: one row per entry regardless of
    # how many owners it has.
    assert consensus_total == len(dump) == 3

    # the fairness property this whole Chroma-unification effort exists to
    # lock in: every per-owner baseline's fanout inflates its footprint
    # relative to the consensus backend whenever any entry has >=2 owners
    # (true here for e1 and e2).
    assert ga_total > consensus_total
    assert gm_total > consensus_total
    assert collab_total > consensus_total


@pytest.mark.parametrize("kind", ["generative_agents", "g_memory", "collaborative"])
async def test_make_memory_collection_name_isolation(kind):
    """Two `make_memory(..., collection_name=...)` calls with DIFFERENT
    names must not see each other's writes -- this is the property
    `build_society`'s per-run collection name (derived from
    `f"{scenario}_{memory_kind}_<uuid>"`) relies on so repeated/parallel
    runs of the same (scenario, backend) don't contaminate each other.
    Regression-guards against chromadb's `Client()` instances silently
    sharing an in-process store keyed by collection name (verified: two
    separate `chromadb.Client()` objects with the SAME collection name DO
    share data, so a unique name -- not just a fresh Client() -- is what
    actually isolates runs)."""
    m1 = make_memory(kind, afake_embed, collection_name=f"isolation_alpha_{kind}")
    m2 = make_memory(kind, afake_embed, collection_name=f"isolation_beta_{kind}")

    await m1.remember_atomic(["a"], TEXT_A, tick=0)

    assert len(m1.all_entries()) == 1
    assert len(m2.all_entries()) == 0


async def test_shared_memory_collection_name_isolation():
    """Same isolation property for the consensus backend
    (`society.ltm.SharedMemory`), which is not covered by
    `test_make_memory_collection_name_isolation`'s BASELINE_CLASSES-style
    parametrization since it's constructed directly rather than through
    `make_memory`'s registry in most tests."""
    m1 = SharedMemory(afake_embed, collection_name="isolation_alpha_consensus")
    m2 = SharedMemory(afake_embed, collection_name="isolation_beta_consensus")

    await m1.remember_atomic(["a"], TEXT_A, tick=0)

    assert len(m1.all_entries()) == 1
    assert len(m2.all_entries()) == 0


async def test_build_society_gives_each_call_a_distinct_collection():
    """Two `build_society(...)` calls for the same scenario/memory_kind must
    not contaminate each other's shared memory, even though both derive
    their collection name from the same `f"{scenario}_{memory_kind}"`
    prefix -- the uuid suffix in `build_society` must make each call's name
    unique."""
    from society.events import EventLog
    from society.scenario import build_society

    cfg = {
        "scenario": "isolation_test",
        "agents": [
            {"id": "a", "kind": "character", "brain": "rule",
             "status": {"location": "hall"}},
            {"id": "hall", "kind": "environment", "brain": "rule"},
        ],
        "map": {"environments": ["hall"], "edges": []},
    }

    k1 = await build_society(
        cfg, llm=None, embed_fn=afake_embed, event_log=EventLog(None),
        memory_kind="g_memory",
    )
    k2 = await build_society(
        cfg, llm=None, embed_fn=afake_embed, event_log=EventLog(None),
        memory_kind="g_memory",
    )

    await k1.shared_memory.remember_atomic(["a"], TEXT_A, tick=0)

    assert len(k1.shared_memory.all_entries()) == 1
    assert len(k2.shared_memory.all_entries()) == 0


# ----------------------------------------------------------------------
# Fairness: every backend (baselines + consensus) atomizes a compound memory
# at the SAME granularity, so a footprint comparison isolates the merge, not
# incidental row coarseness. Each atomic piece must be self-contained.
# ----------------------------------------------------------------------

import uuid
from society.baselines import make_memory as _make


@pytest.mark.parametrize("kind", ["generative_agents", "g_memory", "collaborative", "consensus"])
async def test_all_backends_split_compound_remember_identically(kind):
    llm = FakeLLM(responses=['["宝玉挨打", "贾政大发雷霆"]'])
    m = _make(kind, afake_embed, llm=llm, max_tokens=50, collection_name=f"t_{uuid.uuid4().hex[:6]}")
    out = await m.remember("alice", "宝玉挨打了，然后贾政大发雷霆。", tick=1)
    assert [r["text"] for r in out] == ["宝玉挨打", "贾政大发雷霆"]   # split into 2 atomic rows
    assert all(r["owners"] == ["alice"] for r in out)


@pytest.mark.parametrize("kind", ["generative_agents", "g_memory", "collaborative"])
async def test_baseline_short_memory_not_split(kind):
    # A short, already-atomic memory stays one row (no spurious splitting).
    m = _make(kind, afake_embed, llm=None, max_tokens=50, collection_name=f"t_{uuid.uuid4().hex[:6]}")
    out = await m.remember("alice", "黛玉葬花", tick=1)
    assert len(out) == 1 and out[0]["text"] == "黛玉葬花"
