"""Graph scaffolding for the G-Memory (Full) baseline (2025).

The paper's G-Memory organizes memory as a three-tier hierarchical graph:

- ``interaction``: raw deposits (from ``remember``/``remember_atomic``).
- ``insight``: LLM-distilled generalizations produced by a distillation pass
  over accumulated interactions (Task 7 -- not built here).
- ``query``: a task/query node linking a query to the trajectory of
  interaction nodes that served it (Task 7/8 -- not built here).

This module owns the tier constants and a small side adjacency index,
``GraphIndex``, that records the graph topology (agent/team/task relations
and insight->interaction provenance edges) *alongside* the Chroma-backed row
store -- Chroma itself only stores node rows (text + metadata), it has no
notion of directed typed edges between rows, so the edges live in this
separate in-memory structure. `GMemory` (see `society/baselines.py`) owns one
`GraphIndex` instance and is responsible for keeping it in sync with the row
store (e.g. dropping edges that touch a node when its row is deleted).

Only the scaffolding lives here: tier tagging + adjacency bookkeeping.
Distillation (writing `insight` nodes and insight->interaction edges) and
bi-level retrieval (traversing the graph at query time) are separate tasks
layered on top of this.
"""

# ---------------------------------------------------------------------------
# Tier constants
# ---------------------------------------------------------------------------

INTERACTION = "interaction"
INSIGHT = "insight"
QUERY = "query"


class GraphIndex:
    """In-memory directed adjacency index: node id -> [(dst, etype), ...].

    Edges are typed (`etype`, e.g. "agent"/"team"/"task"/"provenance") and
    directed (`src` -> `dst`). No dedup guard beyond a plain set: adding the
    same `(src, dst, etype)` triple twice is a no-op, matching a graph
    edge-set semantics rather than a multigraph. Node identity here is
    implicit -- a node "exists" in the index only by appearing as an
    endpoint of at least one edge; there is no separate node registry, so
    `remove_node` on an id with no edges is a harmless no-op.
    """

    def __init__(self) -> None:
        # src -> set of (dst, etype) tuples
        self._edges: dict[str, set[tuple[str, str]]] = {}

    def add_edge(self, src: str, dst: str, etype: str) -> None:
        self._edges.setdefault(src, set()).add((dst, etype))

    def neighbors(self, node_id: str, etype: str | None = None) -> list[str]:
        """Outgoing neighbors of `node_id`, optionally filtered by edge
        type, returned de-duplicated and sorted for deterministic order."""
        edges = self._edges.get(node_id, ())
        dsts = {dst for dst, et in edges if etype is None or et == etype}
        return sorted(dsts)

    def remove_node(self, node_id: str) -> None:
        """Drop every edge touching `node_id`, as either source or
        destination -- called when the underlying row is deleted (e.g.
        `GMemory.forget` dropping the last owner) so edges never dangle."""
        self._edges.pop(node_id, None)
        for src in list(self._edges.keys()):
            remaining = {(dst, et) for dst, et in self._edges[src] if dst != node_id}
            if remaining:
                self._edges[src] = remaining
            else:
                del self._edges[src]

    def export(self) -> list[dict]:
        """Serialize all edges deterministically as
        `[{"src", "dst", "etype"}, ...]`, sorted by (src, dst, etype)."""
        rows = [
            {"src": src, "dst": dst, "etype": etype}
            for src, edges in self._edges.items()
            for dst, etype in edges
        ]
        rows.sort(key=lambda e: (e["src"], e["dst"], e["etype"]))
        return rows

    def restore(self, edges: list[dict]) -> None:
        """Replace the current adjacency with the given exported edges."""
        self._edges = {}
        for e in edges or []:
            self.add_edge(e["src"], e["dst"], e["etype"])

    @classmethod
    def from_export(cls, edges: list[dict]) -> "GraphIndex":
        graph = cls()
        graph.restore(edges)
        return graph


# ---------------------------------------------------------------------------
# Post-task distillation prompt (Task 7)
# ---------------------------------------------------------------------------


def distill_prompt(interaction_texts: list[str]) -> str:
    """Build the LLM prompt used by `GMemory.maybe_distill` to summarize a
    cluster of recent `interaction`-tier texts into ONE higher-level
    `insight` statement.

    Kept here (rather than inline in `society/baselines.py`) so the prompt
    text is unit-testable/tweakable independent of the distillation
    plumbing, mirroring how the tier constants and `GraphIndex` live in this
    module as the "graph memory" surface of the G-Memory (Full) baseline.
    """
    bullets = "\n".join(f"- {t}" for t in interaction_texts)
    return (
        "You are consolidating an agent's recent memories into a single, "
        "higher-level insight for a hierarchical memory graph.\n\n"
        "Below are recent interaction memories:\n"
        f"{bullets}\n\n"
        "Write ONE concise sentence that generalizes the pattern, lesson, or "
        "takeaway shared across these interactions. Respond with only that "
        "sentence, no preamble or bullet points."
    )
