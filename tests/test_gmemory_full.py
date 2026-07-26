"""Tests for the G-Memory (Full) graph scaffolding: tier constants + the
`GraphIndex` adjacency side-index, and their wiring into `GMemory`.

See `.superpowers/sdd/task-6-brief.md` and the "Workstream 2 -- Full
mechanisms -> G-Memory (Full)" section of
`docs/superpowers/specs/2026-07-25-faithful-chroma-baselines-design.md`.
This task builds ONLY the tier constants + adjacency index + wiring;
distillation (insight nodes) and bi-level retrieval are separate tasks.
"""

from society.baselines import GMemory
from society.gmemory_graph import INSIGHT, INTERACTION, QUERY, GraphIndex
from tests.helpers import afake_embed

TEXT_A = "关羽千里走单骑"
TEXT_B = "刘备三顾茅庐"


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
    m = GMemory(afake_embed)
    await m.remember_atomic(["guanyu", "liubei"], TEXT_A)
    entries = m.all_entries()
    assert len(entries) == 1
    assert entries[0]["meta"]["tier"] == INTERACTION


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
    m = GMemory(afake_embed)
    r = await m.remember_atomic(["guanyu", "liubei"], TEXT_A)
    row_id = r["id"]
    m._graph.add_edge(row_id, "guanyu", "agent")

    # removing one of two owners does not delete the row -> edges survive
    assert m.forget("guanyu", row_id) is True
    assert m._graph.neighbors(row_id) == ["guanyu"]
