"""Tests for the G-Memory (Full) graph scaffolding: tier constants + the
`GraphIndex` adjacency side-index, and their wiring into `GMemory`.

See `.superpowers/sdd/task-6-brief.md`/`task-7-brief.md` and the
"Workstream 2 -- Full mechanisms -> G-Memory (Full)" section of
`docs/superpowers/specs/2026-07-25-faithful-chroma-baselines-design.md`.
This file also covers Task 7's post-task distillation (`GMemory.maybe_distill`):
periodically summarizing recent `interaction` nodes into `insight` nodes
linked back to their sources via `derived_from` provenance edges. Bi-level
retrieval at query time is a separate task.
"""

from society.baselines import GMemory
from society.gmemory_graph import INSIGHT, INTERACTION, QUERY, GraphIndex
from tests.helpers import FakeLLM, afake_embed

TEXT_A = "关羽千里走单骑"
TEXT_B = "刘备三顾茅庐"
TEXT_C = "张飞喝断当阳桥"


# ========================================================================
# Tier constants
# ========================================================================


def test_tier_constants_values():
    assert INTERACTION == "interaction"
    assert INSIGHT == "insight"
    assert QUERY == "query"


# ========================================================================
# GMemory tier tagging
# ========================================================================


async def test_gmemory_remember_creates_interaction_tier_row():
    m = GMemory(afake_embed)
    await m.remember("guanyu", TEXT_A)
    entries = m.all_entries()
    assert len(entries) == 1
    assert entries[0]["meta"]["tier"] == INTERACTION


async def test_gmemory_remember_atomic_creates_interaction_tier_row():
    # remember_atomic fans a multi-owner deposit out into one row per
    # owner (society.baselines.GMemory.remember_atomic) -- both rows still
    # land in the "interaction" tier.
    m = GMemory(afake_embed)
    await m.remember_atomic(["guanyu", "liubei"], TEXT_A)
    entries = m.all_entries()
    assert len(entries) == 2
    assert {e["owners"][0] for e in entries} == {"guanyu", "liubei"}
    assert all(e["meta"]["tier"] == INTERACTION for e in entries)


async def test_gmemory_owns_a_graph_index():
    m = GMemory(afake_embed)
    assert isinstance(m._graph, GraphIndex)


# ========================================================================
# GraphIndex basics
# ========================================================================


def test_graph_index_add_edge_and_neighbors_roundtrip():
    g = GraphIndex()
    g.add_edge("a", "b", "agent")
    g.add_edge("a", "c", "team")
    assert g.neighbors("a") == ["b", "c"]


def test_graph_index_neighbors_filters_by_etype():
    g = GraphIndex()
    g.add_edge("a", "b", "agent")
    g.add_edge("a", "c", "team")
    g.add_edge("a", "d", "agent")
    assert g.neighbors("a", etype="agent") == ["b", "d"]
    assert g.neighbors("a", etype="team") == ["c"]
    assert g.neighbors("a", etype="task") == []


def test_graph_index_neighbors_deterministic_order():
    g = GraphIndex()
    for dst in ["z", "m", "a", "q"]:
        g.add_edge("src", dst, "agent")
    assert g.neighbors("src") == ["a", "m", "q", "z"]


def test_graph_index_neighbors_unknown_node_returns_empty():
    g = GraphIndex()
    assert g.neighbors("nope") == []


def test_graph_index_add_edge_dedups():
    g = GraphIndex()
    g.add_edge("a", "b", "agent")
    g.add_edge("a", "b", "agent")
    assert g.neighbors("a") == ["b"]


def test_graph_index_remove_node_drops_outgoing_and_incoming_edges():
    g = GraphIndex()
    g.add_edge("a", "b", "agent")
    g.add_edge("b", "c", "team")
    g.add_edge("c", "b", "task")
    g.remove_node("b")
    assert g.neighbors("a") == []
    assert g.neighbors("b") == []
    assert g.neighbors("c") == []


def test_graph_index_remove_node_missing_is_noop():
    g = GraphIndex()
    g.add_edge("a", "b", "agent")
    g.remove_node("nope")
    assert g.neighbors("a") == ["b"]


# ========================================================================
# GraphIndex export/restore
# ========================================================================


def test_graph_index_export_shape_and_order():
    g = GraphIndex()
    g.add_edge("b", "x", "agent")
    g.add_edge("a", "y", "team")
    g.add_edge("a", "x", "agent")
    exported = g.export()
    assert exported == [
        {"src": "a", "dst": "x", "etype": "agent"},
        {"src": "a", "dst": "y", "etype": "team"},
        {"src": "b", "dst": "x", "etype": "agent"},
    ]


def test_graph_index_export_restore_roundtrip():
    g = GraphIndex()
    g.add_edge("a", "b", "agent")
    g.add_edge("a", "c", "team")
    g.add_edge("insight1", "interaction1", "provenance")
    exported = g.export()

    g2 = GraphIndex()
    g2.restore(exported)
    assert g2.export() == exported
    assert g2.neighbors("a") == ["b", "c"]
    assert g2.neighbors("insight1", etype="provenance") == ["interaction1"]


def test_graph_index_from_export_classmethod():
    g = GraphIndex()
    g.add_edge("a", "b", "agent")
    exported = g.export()

    g2 = GraphIndex.from_export(exported)
    assert g2.export() == exported


def test_graph_index_restore_replaces_existing_edges():
    g = GraphIndex()
    g.add_edge("a", "b", "agent")
    g.restore([{"src": "x", "dst": "y", "etype": "task"}])
    assert g.neighbors("a") == []
    assert g.neighbors("x") == ["y"]


# ========================================================================
# GMemory graph wiring: export_graph / restore_graph
# ========================================================================


async def test_gmemory_graph_survives_export_graph_restore_graph():
    m = GMemory(afake_embed)
    r = await m.remember("guanyu", TEXT_A)
    row_id = r[0]["id"]
    m._graph.add_edge(row_id, "guanyu", "agent")
    m._graph.add_edge(row_id, "task-1", "task")

    exported_edges = m.export_graph()
    assert exported_edges == m._graph.export()

    m2 = GMemory(afake_embed)
    m2.restore_graph(exported_edges)
    assert m2.export_graph() == exported_edges
    assert m2._graph.neighbors(row_id) == ["guanyu", "task-1"]


async def test_gmemory_export_entry_contract_unchanged_by_graph():
    """`export()`/`restore()` must stay a plain list[dict] of entries --
    other code (persistence.py, run_sim.py) depends on that shape -- the
    graph travels separately via export_graph/restore_graph."""
    m = GMemory(afake_embed)
    await m.remember("guanyu", TEXT_A)
    m._graph.add_edge("x", "y", "agent")
    exported = m.export()
    assert isinstance(exported, list)
    assert all(isinstance(e, dict) for e in exported)
    assert all("src" not in e and "dst" not in e for e in exported)


async def test_gmemory_forget_removes_node_edges_from_graph():
    m = GMemory(afake_embed)
    r = await m.remember("guanyu", TEXT_A)
    row_id = r[0]["id"]
    m._graph.add_edge(row_id, "guanyu", "agent")
    m._graph.add_edge("other", row_id, "provenance")

    assert m.forget("guanyu", row_id) is True

    assert m._graph.neighbors(row_id) == []
    assert m._graph.neighbors("other") == []


async def test_gmemory_forget_partial_owner_keeps_edges():
    # remember_atomic no longer produces a multi-owner row (it fans out one
    # single-owner row per owner -- see society.baselines.GMemory
    # .remember_atomic), so a genuinely multi-owner row to exercise
    # forget's partial-owner-removal path (row survives, edges survive)
    # now comes from distillation's insight rows instead, whose owners are
    # the union of their source interactions' owners.
    llm = FakeLLM(responses=[INSIGHT_TEXT])
    m = GMemory(afake_embed, llm=llm, distill_every=2)
    await m.remember("guanyu", TEXT_A)
    await m.remember("liubei", TEXT_B)

    insight_rows = [e for e in m.all_entries() if e["meta"]["tier"] == INSIGHT]
    assert len(insight_rows) == 1
    row_id = insight_rows[0]["id"]
    assert sorted(insight_rows[0]["owners"]) == ["guanyu", "liubei"]
    m._graph.add_edge(row_id, "guanyu", "agent")

    # removing one of two owners does not delete the row -> edges survive
    # (the insight row also carries its own derived_from provenance edges
    # to its source interactions, so filter to the "agent" edge added above)
    assert m.forget("guanyu", row_id) is True
    assert m._graph.neighbors(row_id, "agent") == ["guanyu"]

    remaining = next(e for e in m.all_entries() if e["id"] == row_id)
    assert remaining["owners"] == ["liubei"]


# ========================================================================
# Post-task distillation (Task 7): maybe_distill / insight nodes
# ========================================================================

INSIGHT_TEXT = "刘关张三人情谊深厚，屡建战功"


async def test_maybe_distill_triggers_after_distill_every_interactions():
    llm = FakeLLM(responses=[INSIGHT_TEXT])
    m = GMemory(afake_embed, llm=llm, distill_every=3)

    r1 = await m.remember("guanyu", TEXT_A)
    r2 = await m.remember("liubei", TEXT_B)
    r3 = await m.remember("zhangfei", TEXT_C)
    source_ids = sorted([r1[0]["id"], r2[0]["id"], r3[0]["id"]])

    entries = m.all_entries()
    insight_rows = [e for e in entries if e["meta"]["tier"] == INSIGHT]
    assert len(insight_rows) == 1
    assert insight_rows[0]["text"] == INSIGHT_TEXT

    insight_id = insight_rows[0]["id"]
    assert m._graph.neighbors(insight_id, "derived_from") == source_ids

    # counter reset: a 4th remember does not trigger a second distillation
    await m.remember("guanyu", "又一件事")
    entries = m.all_entries()
    assert len([e for e in entries if e["meta"]["tier"] == INSIGHT]) == 1


async def test_maybe_distill_insight_owners_are_union_of_source_owners():
    llm = FakeLLM(responses=[INSIGHT_TEXT])
    m = GMemory(afake_embed, llm=llm, distill_every=2)

    await m.remember("guanyu", TEXT_A)
    await m.remember("liubei", TEXT_B)

    insight_rows = [e for e in m.all_entries() if e["meta"]["tier"] == INSIGHT]
    assert len(insight_rows) == 1
    assert insight_rows[0]["owners"] == ["guanyu", "liubei"]


async def test_maybe_distill_insight_retrievable_via_recall_by_source_owner():
    llm = FakeLLM(responses=[INSIGHT_TEXT])
    m = GMemory(afake_embed, llm=llm, distill_every=2)

    await m.remember("guanyu", TEXT_A)
    await m.remember("liubei", TEXT_B)

    # recall by one of the source owners, querying with the insight's own
    # text -- the deterministic fake embedding makes this an exact-match
    # top hit, so the insight (owned jointly via the union) must surface.
    recalled = await m.recall_of("guanyu", INSIGHT_TEXT)
    assert any(r["text"] == INSIGHT_TEXT for r in recalled)


async def test_maybe_distill_noop_when_llm_is_none():
    m = GMemory(afake_embed, llm=None, distill_every=2)

    await m.remember("guanyu", TEXT_A)
    await m.remember("liubei", TEXT_B)  # crosses the threshold

    entries = m.all_entries()
    assert all(e["meta"]["tier"] != INSIGHT for e in entries)
    assert len(entries) == 2


async def test_maybe_distill_skips_insight_creation_on_empty_llm_output():
    llm = FakeLLM(responses=["   "])
    m = GMemory(afake_embed, llm=llm, distill_every=1)

    await m.remember("guanyu", TEXT_A)  # crosses the threshold immediately

    entries = m.all_entries()
    assert all(e["meta"]["tier"] != INSIGHT for e in entries)
    assert len(entries) == 1


async def test_maybe_distill_manual_call_is_noop_when_nothing_pending():
    llm = FakeLLM(responses=[INSIGHT_TEXT])
    m = GMemory(afake_embed, llm=llm, distill_every=100)

    result = await m.maybe_distill()
    assert result is None
    assert m.all_entries() == []


# ========================================================================
# Bi-level retrieval (Task 8): recall/recall_of are graph-aware
# ========================================================================


async def test_recall_after_distillation_returns_insight_and_its_interactions():
    """A query semantically near the insight (here: an exact-text query,
    matching the deterministic fake embedding's only notion of
    "semantically near") must surface both the insight row and at least one
    of its `derived_from` source interactions -- bi-level retrieval, not
    just a flat vector hit on the insight alone."""
    llm = FakeLLM(responses=[INSIGHT_TEXT])
    m = GMemory(afake_embed, llm=llm, distill_every=2)

    r1 = await m.remember("guanyu", TEXT_A)
    r2 = await m.remember("liubei", TEXT_B)
    source_ids = {r1[0]["id"], r2[0]["id"]}

    insight_rows = [e for e in m.all_entries() if e["meta"]["tier"] == INSIGHT]
    assert len(insight_rows) == 1
    insight_id = insight_rows[0]["id"]

    recalled = await m.recall("guanyu", INSIGHT_TEXT, top_k=5)
    recalled_ids = {r["id"] for r in recalled}

    assert insight_id in recalled_ids
    assert recalled_ids & source_ids, "expected at least one derived interaction id"


async def test_recall_owner_scope_excludes_insight_asker_does_not_own():
    """An insight distilled from another agent's interactions (asker not
    among its owners) must not surface for that asker under owner_scope."""
    llm = FakeLLM(responses=[INSIGHT_TEXT])
    m = GMemory(afake_embed, llm=llm, distill_every=2)

    await m.remember("guanyu", TEXT_A)
    await m.remember("liubei", TEXT_B)

    insight_rows = [e for e in m.all_entries() if e["meta"]["tier"] == INSIGHT]
    insight_id = insight_rows[0]["id"]

    # zhangfei is not an owner of the insight (owners = union of guanyu/liubei)
    recalled = await m.recall_of("zhangfei", INSIGHT_TEXT, top_k=5)
    recalled_ids = {r["id"] for r in recalled}
    assert insight_id not in recalled_ids


async def test_recall_owner_scope_excludes_non_owned_derived_interaction():
    """Even when the asker DOES own the insight (part of the owner union),
    a specific derived interaction owned by a *different* agent must not
    leak into that asker's owner-scoped recall."""
    llm = FakeLLM(responses=[INSIGHT_TEXT])
    m = GMemory(afake_embed, llm=llm, distill_every=2)

    r1 = await m.remember("guanyu", TEXT_A)
    r2 = await m.remember("liubei", TEXT_B)
    guanyu_interaction_id = r1[0]["id"]
    liubei_interaction_id = r2[0]["id"]

    recalled = await m.recall_of("guanyu", INSIGHT_TEXT, top_k=5)
    recalled_ids = {r["id"] for r in recalled}

    assert guanyu_interaction_id in recalled_ids  # guanyu owns this one
    assert liubei_interaction_id not in recalled_ids


async def test_recall_pre_distillation_matches_plain_vector_query():
    """Backward-compat: with no insight nodes yet, `recall` must reduce to
    plain interaction-tier vector retrieval -- same ids/order a bare
    `ChromaRows.query` over the (all-interaction) store would give."""
    m = GMemory(afake_embed)  # no llm -> distillation never fires
    await m.remember("guanyu", TEXT_A)
    await m.remember("liubei", TEXT_B)
    await m.remember("zhangfei", TEXT_C)

    recalled = await m.recall("guanyu", TEXT_B, top_k=2)
    direct_hits = await m._store.query(TEXT_B, 2, where={"tier": INTERACTION})

    assert [r["id"] for r in recalled] == [h["id"] for h in direct_hits]
    assert [r["text"] for r in recalled] == [h["text"] for h in direct_hits]


async def test_recall_pre_distillation_owner_scope_matches_plain_query():
    m = GMemory(afake_embed)
    await m.remember("guanyu", TEXT_A)
    await m.remember("liubei", TEXT_B)

    recalled = await m.recall_of("guanyu", TEXT_A, top_k=5)
    assert recalled and recalled[0]["text"] == TEXT_A

    # explicit ownership check: liubei's row must not appear for guanyu's owner scope
    liubei_only = await m.remember("liubei", "只有刘备知道的秘密")
    recalled2 = await m.recall_of("guanyu", "只有刘备知道的秘密", top_k=5)
    assert liubei_only[0]["id"] not in {r["id"] for r in recalled2}
