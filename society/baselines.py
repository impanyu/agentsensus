"""Faithful baseline memory backends for comparison against `society.ltm.SharedMemory`.

Each class here is a drop-in, duck-typed replacement for `SharedMemory`: same
constructor keyword shape, same `remember`/`recall`/`forget`/`revise`/
`all_entries`/`export`/`restore`/`stats` methods and return shapes. None of
them get our normalize gate or consensus merge -- that machinery is the
contribution under test, so giving it to a baseline would invalidate the
comparison. Every store here is a plain in-memory list of rows with
embeddings stored as plain Python lists (no numpy); ranking is real cosine
similarity, computed in pure Python, from vectors returned by `embed_fn`.

`make_memory(kind, embed_fn, llm=None, **kw)` is the factory experiment
runners should call to select a backend by name.
"""

import math
import re
import uuid
from datetime import datetime, timezone

from society.baseline_store import ChromaRows, dumps_meta, loads_meta
from society.gmemory_graph import INSIGHT, INTERACTION, GraphIndex, distill_prompt
from society.ltm import SharedMemory

_DEFAULT_IMPORTANCE = 5


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _cosine(a, b) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


# ==========================================================================
# 1) GenerativeAgentsMemory -- Park et al. 2023, "Generative Agents: Interactive
#    Simulacra of Human Behavior" (memory stream)
# ==========================================================================


class GenerativeAgentsMemory:
    """Per-agent private memory stream (Park et al. 2023).

    Fidelity note: faithful to the paper's core mechanism -- every agent has
    its own private stream, and `remember` stores a SEPARATE row for each
    owner in the call's owner set (a runtime `remember(agent_id, ...)` call
    has owner set {agent_id}); there is no consensus/dedup step, so the same
    shared scene recorded by N agents produces N independent rows, which is
    exactly the footprint-inflation behavior this baseline is meant to
    exhibit. Retrieval uses the paper's three-term score
    (recency + importance + relevance), min-max normalized per component
    then weighted-summed with weights RECENCY_W/IMPORTANCE_W/RELEVANCE_W
    (default 1.0 each, matching the paper's un-tuned equal weighting).
    Importance is scored once at insert time via a single `llm.chat` call
    (paper: "poignancy" 1-10 rating) and cached on the row; recency uses an
    exponential decay over a synthetic access-tick counter that advances on
    every `recall` (paper uses wall-clock hours since last retrieval -- we
    substitute a monotonic tick counter since the simulator has no wall
    clock, which is the charitable, deterministic reading for testing).
    Simplification left out: the paper's separate "reflection" tree
    (higher-level synthesized memories) is not implemented -- reflections
    would themselves be additional stream entries produced via an LLM
    summarization pass, which is orthogonal to the retrieval-scoring
    mechanism this adapter is faithful to and is not needed to compare
    against consensus-compressed storage.

    Storage note: rows live in a `ChromaRows` collection (one Chroma record
    PER OWNER, matching the per-owner-duplication behavior above) instead of
    an in-memory dict. Chroma metadata values must be scalars, so the
    per-row `affiliated` id list is JSON-encoded (`dumps_meta`/`loads_meta`)
    before being written and decoded after being read back. `recall_of`
    narrows candidates server-side via `ChromaRows.query(..., where={"owner":
    owner_id}, return_query_embedding=True)` (fetching `max(4*top_k, 50)`
    candidates), then applies the unchanged three-term score in Python using
    each candidate's stored embedding (returned inline by `query`) and the
    query embedding `query` already computed internally -- no extra
    `embed_fn` calls beyond the one `query` makes for the query text itself.
    """

    RECENCY_W = 1.0
    IMPORTANCE_W = 1.0
    RELEVANCE_W = 1.0
    DECAY = 0.1

    def __init__(self, embed_fn, llm=None, *, top_k: int = 5, collection_name=None, **kwargs):
        self._embed_fn = embed_fn
        self._llm = llm
        self._store = ChromaRows(embed_fn, collection_name=collection_name)
        self._clock = 0  # monotonic access-tick counter

    async def _score_importance(self, text: str) -> int:
        if self._llm is None:
            return _DEFAULT_IMPORTANCE
        prompt = (
            "On a scale of 1 to 10, where 1 is mundane and 10 is extremely "
            "important/poignant, rate the importance of this memory. Reply "
            f"with only the integer.\n\nMemory: {text}"
        )
        reply = await self._llm.chat(prompt, system=None, bucket="importance")
        match = re.search(r"-?\d+", reply or "")
        if not match:
            return _DEFAULT_IMPORTANCE
        try:
            val = int(match.group())
            return max(1, min(10, val))
        except (ValueError, TypeError):
            return _DEFAULT_IMPORTANCE

    @staticmethod
    def _split_meta(metadata: dict) -> tuple[str, list[str], dict]:
        """Split a raw Chroma metadata dict into (owner, affiliated ids, the
        remaining `meta` sub-dict used by `all_entries`/`export`)."""
        owner = metadata.get("owner")
        affiliated = sorted(loads_meta(metadata.get("affiliated")))
        meta = {k: v for k, v in metadata.items() if k not in ("owner", "affiliated")}
        return owner, affiliated, meta

    async def remember(
        self,
        agent_id: str,
        text: str,
        tick: int = 0,
        source: str = "runtime",
        story_order=None,
        story_time=None,
    ) -> list[dict]:
        owners = [agent_id]
        embedding = (await self._embed_fn([text]))[0]
        importance = await self._score_importance(text)
        results = []
        for owner in owners:
            row_id = uuid.uuid4().hex
            self._clock += 1
            metadata = {
                "owner": owner,
                "affiliated": dumps_meta([]),
                "created_at": _now_iso(),
                "source": source,
                "tick": tick,
                "importance": importance,
                "last_access": self._clock,
            }
            if story_order is not None:
                metadata["story_order"] = story_order
            if story_time is not None:
                metadata["story_time"] = story_time
            await self._store.add(row_id, text, embedding, metadata)
            results.append({"id": row_id, "text": text, "merged": False, "owners": [owner]})
        return results

    async def remember_atomic(
        self,
        owners: list[str],
        text: str,
        tick: int = 0,
        source: str = "sediment",
        story_order=None,
        story_time=None,
        affiliated: list[str] | None = None,
    ) -> dict | None:
        """Mirror `remember`, but loop over the given `owners` list (not
        `[agent_id]`) -- ONE separate row per owner, since per-owner
        duplication is this baseline's whole point. Embeds once and scores
        importance once, reused across every owner's row."""
        text = text.strip()
        if not text:
            return None
        if not owners:
            raise ValueError("remember_atomic requires at least one owner")

        embedding = (await self._embed_fn([text]))[0]
        importance = await self._score_importance(text)
        seed_affiliated = sorted(set(affiliated or []))
        first_id = None
        for owner in owners:
            row_id = uuid.uuid4().hex
            if first_id is None:
                first_id = row_id
            self._clock += 1
            metadata = {
                "owner": owner,
                "affiliated": dumps_meta(sorted(a for a in seed_affiliated if a != row_id)),
                "created_at": _now_iso(),
                "source": source,
                "tick": tick,
                "importance": importance,
                "last_access": self._clock,
            }
            if story_order is not None:
                metadata["story_order"] = story_order
            if story_time is not None:
                metadata["story_time"] = story_time
            await self._store.add(row_id, text, embedding, metadata)
        return {"id": first_id, "text": text, "merged": False, "owners": list(owners)}

    async def recall(self, agent_id: str, query: str, top_k: int = 5) -> list[dict]:
        """`recall_of` already scopes candidates to `owner == owner_id`, so
        a caller retrieving its own stream is just `recall_of` under its own
        id."""
        return await self.recall_of(agent_id, query, top_k)

    async def recall_of(self, owner_id: str, query: str, top_k: int = 5) -> list[dict]:
        candidate_k = max(4 * top_k, 50)
        candidates, q_emb = await self._store.query(
            query, candidate_k, where={"owner": owner_id}, return_query_embedding=True
        )
        if not candidates:
            return []

        self._clock += 1  # one "current time" tick shared by all candidates
        now = self._clock
        raw = []
        for cand in candidates:
            emb = cand["embedding"]
            meta = cand["metadata"]
            ticks_since = now - int(meta.get("last_access", now))
            recency = math.exp(-self.DECAY * ticks_since)
            importance = float(meta.get("importance", _DEFAULT_IMPORTANCE)) / 10.0
            relevance = _cosine(q_emb, emb)
            raw.append((cand, recency, importance, relevance))

        def _norm(vals):
            lo, hi = min(vals), max(vals)
            if hi - lo < 1e-12:
                return [1.0 for _ in vals]
            return [(v - lo) / (hi - lo) for v in vals]

        recencies = _norm([r[1] for r in raw])
        importances = _norm([r[2] for r in raw])
        relevances = _norm([r[3] for r in raw])

        scored = []
        for (cand, _, _, _), rec_n, imp_n, rel_n in zip(raw, recencies, importances, relevances):
            score = (
                self.RECENCY_W * rec_n
                + self.IMPORTANCE_W * imp_n
                + self.RELEVANCE_W * rel_n
            )
            scored.append((score, cand))

        scored.sort(key=lambda pair: pair[0], reverse=True)
        top = scored[:top_k]
        for _, cand in top:
            new_meta = dict(cand["metadata"])
            new_meta["last_access"] = now
            self._store.update_metadata(cand["id"], new_meta)
        return [{"id": cand["id"], "text": cand["text"]} for _, cand in top]

    def forget(self, agent_id: str, memory_id: str) -> bool:
        row = self._store.get(memory_id)
        if row is None or row["metadata"].get("owner") != agent_id:
            return False
        self._store.delete(memory_id)
        return True

    async def revise(self, agent_id: str, memory_id: str, new_text: str, tick: int = 0) -> list[dict]:
        self.forget(agent_id, memory_id)
        return await self.remember(agent_id, new_text, tick=tick)

    def add_affiliations(self, memory_id: str, other_ids: list[str]) -> bool:
        row = self._store.get(memory_id)
        if row is None:
            return False
        current = set(loads_meta(row["metadata"].get("affiliated")))
        updated = sorted((current | set(other_ids)) - {memory_id})
        new_meta = dict(row["metadata"])
        new_meta["affiliated"] = dumps_meta(updated)
        self._store.update_metadata(memory_id, new_meta)
        return True

    def remove_affiliations(self, memory_id: str, other_ids: list[str]) -> bool:
        row = self._store.get(memory_id)
        if row is None:
            return False
        current = set(loads_meta(row["metadata"].get("affiliated")))
        updated = sorted(current - set(other_ids))
        new_meta = dict(row["metadata"])
        new_meta["affiliated"] = dumps_meta(updated)
        self._store.update_metadata(memory_id, new_meta)
        return True

    def get_affiliations(self, memory_id: str) -> list[str]:
        row = self._store.get(memory_id)
        if row is None:
            return []
        return sorted(loads_meta(row["metadata"].get("affiliated")))

    def all_entries(self) -> list[dict]:
        entries = []
        for r in self._store.all_rows():
            owner, affiliated, meta = self._split_meta(r["metadata"])
            entries.append(
                {
                    "id": r["id"],
                    "text": r["text"],
                    "owners": [owner],
                    "affiliated": affiliated,
                    "meta": meta,
                }
            )
        return entries

    def export(self) -> list[dict]:
        exported = []
        for r in self._store.all_rows():
            owner, affiliated, meta = self._split_meta(r["metadata"])
            exported.append(
                {
                    "id": r["id"],
                    "text": r["text"],
                    "owners": [owner],
                    "affiliated": affiliated,
                    "meta": meta,
                    "embedding": list(r["embedding"]),
                }
            )
        return exported

    async def restore(self, entries: list[dict]) -> None:
        if not entries:
            return
        missing_idx = [i for i, e in enumerate(entries) if not e.get("embedding")]
        computed = {}
        if missing_idx:
            texts = [entries[i]["text"] for i in missing_idx]
            vectors = await self._embed_fn(texts)
            for i, vec in zip(missing_idx, vectors):
                computed[i] = list(vec)

        # Advance the monotonic access-tick clock past the highest
        # `last_access` being restored so a subsequent `recall` never
        # computes a large-negative `ticks_since` (which would overflow
        # `math.exp`) against a fresh instance's clock starting at 0.
        self._clock = max(
            [self._clock]
            + [int(e.get("meta", {}).get("last_access", 0) or 0) for e in entries]
        )

        for i, entry in enumerate(entries):
            owners = entry.get("owners") or [None]
            embedding = entry.get("embedding") or computed[i]
            base_meta = dict(entry.get("meta", {}) or {})
            base_meta.setdefault("importance", _DEFAULT_IMPORTANCE)
            base_meta.setdefault("last_access", self._clock)

            # A multi-owner entry (e.g. a consensus-merged dump from
            # `society.ltm.SharedMemory`) restored into this PER-OWNER
            # backend must become one owned row per owner -- that
            # duplication (each owner keeps its own private copy) is
            # exactly the fidelity difference this baseline is meant to
            # exhibit, not something to collapse away. The first owner
            # keeps the entry's original id (so the common single-owner
            # case round-trips id-for-id, as before); any additional
            # owners get a fresh row id since two rows can never share one
            # id in this store.
            affiliated = list(entry.get("affiliated", []))
            for idx, owner in enumerate(owners):
                row_id = entry["id"] if idx == 0 else uuid.uuid4().hex
                metadata = dict(base_meta)
                metadata["owner"] = owner
                metadata["affiliated"] = dumps_meta(affiliated)
                await self._store.add(row_id, entry["text"], list(embedding), metadata)

    def stats(self) -> dict:
        entries = self.all_entries()
        total = len(entries)
        shared = sum(1 for e in entries if len(e["owners"]) >= 2)
        ratio = (shared / total) if total else 0.0
        return {"total": total, "shared": shared, "ratio": ratio}


# ==========================================================================
# 2) GMemory -- Zhang et al. 2025 hierarchical graph memory
# ==========================================================================

# Post-task distillation trigger: run a distillation pass every this-many
# NEW interaction-tier rows added since the last distillation (paper's
# "post-task" summarization, approximated here as a periodic trigger since
# this codebase has no explicit task/scene boundary at the memory layer).
# Overridable per-instance via `GMemory(..., distill_every=...)`, primarily
# so tests can use a small value instead of waiting for 20 `remember` calls.
DISTILL_EVERY = 20

# Default `derived_from`-hop bound for bi-level retrieval (Task 8), see
# `GMemory.__init__`/`GMemory.recall`.
GMEMORY_MAX_HOPS = 2


class GMemory:
    """Single shared store with a hierarchical tier tag (G-Memory, 2025).

    Fidelity note: faithful to the paper's central design choice that memory
    is a SHARED graph rather than private per-agent streams -- every
    `remember` call appends a row visible to any agent's `recall` (default
    `owner_scope=False`, i.e. cross-agent retrieval; pass `owner_scope=True`
    to `recall` to restrict to the calling agent's own writes, exposed for
    completeness but not the default since G-Memory's whole point is shared
    retrieval). Each row carries a `tier` tag ("interaction" for raw
    `remember` observations, "insight"/"query" reserved for LLM-distilled
    tiers) mirroring the paper's insight/query/interaction hierarchy, but
    only the "interaction" tier is populated by plain `remember` -- the
    paper's higher tiers are produced by a separate distillation pass over
    accumulated interactions, which is out of scope for a like-for-like
    comparison of the raw-storage mechanism. No atomic splitting and no
    dedup: the full observation text is stored as one row, owner={agent_id},
    appended every call even if a prior call stored identical text.
    `stats()`'s `shared` counts rows whose owner set has length >=2; since
    there is no cross-insert owner merge, `shared` stays ~0 under normal
    runtime use (this baseline shares the STORE across agents, not the
    per-entry OWNER SET) -- that is the faithful, expected reading, not a
    bug.

    Storage note: rows live in a `ChromaRows` collection SHARED across every
    agent (one Chroma record per `remember`/`remember_atomic` call, never
    per-owner-duplicated), matching the paper's single-graph design above.
    Chroma metadata values must be scalars, so each row's owner set is
    stored TWICE: once as a JSON-encoded `owners` list (`dumps_meta`/
    `loads_meta`) for `all_entries`/`export`, and once as a per-owner
    boolean flag `owner_<id>=True` for every owner -- Chroma's `where` can't
    test membership inside a JSON string, so the boolean flags are what let
    `recall(..., owner_scope=True)`/`recall_of` filter server-side with
    `where={f"owner_{owner_id}": True}` (mirroring
    `society.ltm.SharedMemory`'s identical dual-storage trick). `affiliated`
    is JSON-encoded the same way as `owners`.

    Retrieval note (Task 8, bi-level retrieval): `recall`/`recall_of` query
    the `insight` tier, walk `derived_from` provenance edges from the
    retrieved insights to pull in their supporting `interaction` rows, and
    also run a direct `interaction`-tier vector query so interactions with
    no insight yet are not missed -- the three sources are merged
    (de-duplicated by id) and ranked by plain cosine similarity (no
    recency/importance rerank like `GenerativeAgentsMemory`) before being
    truncated to `top_k`. Before any distillation has produced `insight`
    rows this reduces to the old single interaction-tier vector query.
    """

    def __init__(
        self,
        embed_fn,
        llm=None,
        *,
        top_k: int = 5,
        collection_name=None,
        distill_every: int | None = None,
        **kwargs,
    ):
        self._embed_fn = embed_fn
        self._llm = llm
        self._store = ChromaRows(embed_fn, collection_name=collection_name)
        # Side adjacency index for the paper's graph topology (agent/team/
        # task relations and insight->interaction provenance edges). Chroma
        # only stores node rows; edges live here (see
        # `society/gmemory_graph.py`). Populated by the distillation pass
        # (Task 7) and bi-level retrieval (Task 8); this task only wires the
        # scaffolding + keeps it in sync with row deletion (`forget`).
        self._graph = GraphIndex()
        # Post-task distillation (Task 7): `_distill_every` new interaction
        # rows trigger `maybe_distill`; `_pending_interactions` tracks the
        # ids of interaction rows added since the last distillation pass (or
        # since construction/restore, for a freshly built instance).
        self._distill_every = distill_every if distill_every is not None else DISTILL_EVERY
        self._pending_interactions: list[str] = []
        # Bi-level retrieval (Task 8): bound on how many `derived_from` hops
        # `recall`/`recall_of` walk out from a retrieved insight to collect
        # supporting interactions. Today only insight->interaction
        # `derived_from` edges exist (Task 7), so this resolves in a single
        # hop in practice; kept at 2 so a future edge type chaining further
        # (e.g. interaction->interaction) is picked up without code changes.
        self._max_hops = GMEMORY_MAX_HOPS

    @staticmethod
    def _split_meta(metadata: dict) -> tuple[list[str], list[str], dict]:
        """Split a raw Chroma metadata dict into (owners, affiliated ids,
        the remaining `meta` sub-dict used by `all_entries`/`export`),
        stripping both JSON list fields and the per-owner `owner_<id>`
        boolean flags (which are a derived index, not real entry data)."""
        owners = sorted(loads_meta(metadata.get("owners")))
        affiliated = sorted(loads_meta(metadata.get("affiliated")))
        meta = {
            k: v
            for k, v in metadata.items()
            if k not in ("owners", "affiliated") and not k.startswith("owner_")
        }
        return owners, affiliated, meta

    @staticmethod
    def _build_meta(owners: list[str], affiliated: list[str], meta: dict) -> dict:
        """Inverse of `_split_meta`: rebuild a full Chroma metadata dict
        (JSON-encoded `owners`/`affiliated` plus fresh per-owner boolean
        flags) from the given owner set, affiliated set, and extra fields.

        Note: `ChromaRows.update_metadata` -> `collection.update(metadatas=
        ...)` MERGES the given dict into the existing stored metadata
        key-by-key (it does NOT replace it wholesale); a key omitted here is
        simply left untouched on the stored row. That's harmless for every
        key this method writes, since `owners`/`affiliated` and every
        `owner_<id>=True` flag for an owner still in the set are always
        present with a fresh, correct value. It is NOT harmless for a flag
        whose owner was just REMOVED from `owners`: that stale
        `owner_<id>=True` key is absent from this dict's output (since the
        id is gone from `owners`), so a plain merge would leave it in place
        forever. Callers that remove an owner (see `forget`) must explicitly
        set `owner_<removed_id>: None` in the update they send -- chromadb
        treats `None` as "delete this key" -- in addition to what this
        method builds."""
        metadata = dict(meta)
        metadata["owners"] = dumps_meta(sorted(set(owners)))
        metadata["affiliated"] = dumps_meta(sorted(set(affiliated)))
        for o in owners:
            metadata[f"owner_{o}"] = True
        return metadata

    async def remember(
        self,
        agent_id: str,
        text: str,
        tick: int = 0,
        source: str = "runtime",
        story_order=None,
        story_time=None,
    ) -> list[dict]:
        embedding = (await self._embed_fn([text]))[0]
        row_id = uuid.uuid4().hex
        meta = {
            "created_at": _now_iso(),
            "source": source,
            "tick": tick,
            "tier": INTERACTION,
        }
        if story_order is not None:
            meta["story_order"] = story_order
        if story_time is not None:
            meta["story_time"] = story_time
        metadata = self._build_meta([agent_id], [], meta)
        await self._store.add(row_id, text, embedding, metadata)
        await self._track_new_interaction(row_id)
        return [{"id": row_id, "text": text, "merged": False, "owners": [agent_id]}]

    async def remember_atomic(
        self,
        owners: list[str],
        text: str,
        tick: int = 0,
        source: str = "sediment",
        story_order=None,
        story_time=None,
        affiliated: list[str] | None = None,
    ) -> dict | None:
        """One shared row, owners=sorted(set(owners)) -- faithful to
        G-Memory's central design choice that memory is a single shared
        graph rather than private per-agent streams."""
        text = text.strip()
        if not text:
            return None
        if not owners:
            raise ValueError("remember_atomic requires at least one owner")

        embedding = (await self._embed_fn([text]))[0]
        row_id = uuid.uuid4().hex
        meta = {
            "created_at": _now_iso(),
            "source": source,
            "tick": tick,
            "tier": INTERACTION,
        }
        if story_order is not None:
            meta["story_order"] = story_order
        if story_time is not None:
            meta["story_time"] = story_time
        new_owners = sorted(set(owners))
        seed_affiliated = sorted(a for a in set(affiliated or []) if a != row_id)
        metadata = self._build_meta(new_owners, seed_affiliated, meta)
        await self._store.add(row_id, text, embedding, metadata)
        await self._track_new_interaction(row_id)
        return {"id": row_id, "text": text, "merged": False, "owners": new_owners}

    async def recall(
        self, agent_id: str, query: str, top_k: int = 5, owner_scope: bool = False
    ) -> list[dict]:
        """Bi-level retrieval (Task 8): the paper's G-Memory ranks a query
        against the `insight` tier, then walks `derived_from` provenance
        edges from the relevant insights to pull in the raw interactions
        that support them, alongside a direct `interaction`-tier vector hit
        so relevant interactions with no insight yet are not missed. All
        three sources -- insight hits, their graph-linked interactions, and
        direct interaction hits -- are merged (de-duplicated by id), ranked
        by cosine similarity to the query embedding, and truncated to
        `top_k`.

        Backward-compat: before any distillation has run there are no
        `insight` rows, so the insight-tier query and the graph traversal it
        seeds both contribute nothing, and this reduces to exactly the old
        single interaction-tier vector query.
        """
        owner_where = {f"owner_{agent_id}": True} if owner_scope else None

        def _tier_where(tier: str) -> dict:
            tier_clause = {"tier": tier}
            return tier_clause if owner_where is None else {"$and": [tier_clause, owner_where]}

        insight_hits, q_emb = await self._store.query(
            query, top_k, where=_tier_where(INSIGHT), return_query_embedding=True
        )
        interaction_hits = await self._store.query(query, top_k, where=_tier_where(INTERACTION))

        candidates: dict[str, dict] = {}
        for hit in insight_hits + interaction_hits:
            candidates.setdefault(hit["id"], hit)

        # Graph traversal: from the retrieved insights, walk `derived_from`
        # edges up to `_max_hops` deep to gather supporting interactions
        # that the direct interaction-tier query above may not have
        # surfaced. `_store.get` bypasses the tier queries' `where` clause,
        # so owner scoping must be re-applied by hand here.
        frontier = [hit["id"] for hit in insight_hits]
        seen = set(frontier)
        for _ in range(self._max_hops):
            if not frontier:
                break
            next_frontier = []
            for node_id in frontier:
                for dst in self._graph.neighbors(node_id, "derived_from"):
                    if dst in seen:
                        continue
                    seen.add(dst)
                    next_frontier.append(dst)
                    if dst in candidates:
                        continue
                    row = self._store.get(dst)
                    if row is None:
                        continue  # node was forgotten/deleted since the edge was added
                    if owner_scope:
                        owners, _affiliated, _meta = self._split_meta(row["metadata"])
                        if agent_id not in owners:
                            continue
                    candidates[dst] = {
                        "id": dst,
                        "text": row["text"],
                        "embedding": row["embedding"],
                    }
            frontier = next_frontier

        ranked = sorted(
            candidates.values(), key=lambda c: _cosine(q_emb, c["embedding"]), reverse=True
        )
        return [{"id": c["id"], "text": c["text"]} for c in ranked[:top_k]]

    async def recall_of(self, owner_id: str, query: str, top_k: int = 5) -> list[dict]:
        """Entries where owner_id is in row["owners"], ranked by cosine --
        i.e. `recall` restricted to the owner's own scope."""
        return await self.recall(owner_id, query, top_k, owner_scope=True)

    def forget(self, agent_id: str, memory_id: str) -> bool:
        row = self._store.get(memory_id)
        if row is None:
            return False
        owners, affiliated, meta = self._split_meta(row["metadata"])
        if agent_id not in owners:
            return False
        owners = [o for o in owners if o != agent_id]
        if not owners:
            self._store.delete(memory_id)
            # Row is gone -- drop any graph edges touching it (both as
            # source, e.g. insight->interaction provenance, and as
            # destination, e.g. agent/team/task edges) so the adjacency
            # index never references a deleted node.
            self._graph.remove_node(memory_id)
        else:
            new_meta = self._build_meta(owners, affiliated, meta)
            # `ChromaRows.update_metadata` -> `collection.update(metadatas=...)`
            # MERGES key-by-key rather than replacing the metadata dict, and
            # chromadb treats a `None` value as "delete this key" -- so the
            # removed owner's `owner_<agent_id>` boolean flag (still present
            # in the stored metadata, and NOT re-written by `_build_meta`
            # since `agent_id` is no longer in `owners`) must be explicitly
            # nulled out here, or it would keep matching
            # `where={f"owner_{agent_id}": True}` in `recall`/`recall_of`
            # forever. Mirrors `society.ltm.SharedMemory.forget`.
            new_meta[f"owner_{agent_id}"] = None
            self._store.update_metadata(memory_id, new_meta)
        return True

    async def revise(self, agent_id: str, memory_id: str, new_text: str, tick: int = 0) -> list[dict]:
        self.forget(agent_id, memory_id)
        return await self.remember(agent_id, new_text, tick=tick)

    def add_affiliations(self, memory_id: str, other_ids: list[str]) -> bool:
        row = self._store.get(memory_id)
        if row is None:
            return False
        owners, affiliated, meta = self._split_meta(row["metadata"])
        updated = sorted((set(affiliated) | set(other_ids)) - {memory_id})
        self._store.update_metadata(memory_id, self._build_meta(owners, updated, meta))
        return True

    def remove_affiliations(self, memory_id: str, other_ids: list[str]) -> bool:
        row = self._store.get(memory_id)
        if row is None:
            return False
        owners, affiliated, meta = self._split_meta(row["metadata"])
        updated = sorted(set(affiliated) - set(other_ids))
        self._store.update_metadata(memory_id, self._build_meta(owners, updated, meta))
        return True

    def get_affiliations(self, memory_id: str) -> list[str]:
        row = self._store.get(memory_id)
        if row is None:
            return []
        _, affiliated, _ = self._split_meta(row["metadata"])
        return affiliated

    def all_entries(self) -> list[dict]:
        entries = []
        for r in self._store.all_rows():
            owners, affiliated, meta = self._split_meta(r["metadata"])
            entries.append(
                {
                    "id": r["id"],
                    "text": r["text"],
                    "owners": owners,
                    "affiliated": affiliated,
                    "meta": meta,
                }
            )
        return entries

    def export(self) -> list[dict]:
        exported = []
        for r in self._store.all_rows():
            owners, affiliated, meta = self._split_meta(r["metadata"])
            exported.append(
                {
                    "id": r["id"],
                    "text": r["text"],
                    "owners": owners,
                    "affiliated": affiliated,
                    "meta": meta,
                    "embedding": list(r["embedding"]),
                }
            )
        return exported

    async def restore(self, entries: list[dict]) -> None:
        if not entries:
            return
        missing_idx = [i for i, e in enumerate(entries) if not e.get("embedding")]
        computed = {}
        if missing_idx:
            texts = [entries[i]["text"] for i in missing_idx]
            vectors = await self._embed_fn(texts)
            for i, vec in zip(missing_idx, vectors):
                computed[i] = list(vec)

        for i, entry in enumerate(entries):
            owners = list(entry.get("owners", []))
            affiliated = list(entry.get("affiliated", []))
            meta = dict(entry.get("meta", {}) or {})
            meta.setdefault("tier", INTERACTION)
            embedding = entry.get("embedding") or computed[i]
            metadata = self._build_meta(owners, affiliated, meta)
            await self._store.add(entry["id"], entry["text"], list(embedding), metadata)

    def stats(self) -> dict:
        entries = self.all_entries()
        total = len(entries)
        shared = sum(1 for e in entries if len(e["owners"]) >= 2)
        ratio = (shared / total) if total else 0.0
        return {"total": total, "shared": shared, "ratio": ratio}

    async def _track_new_interaction(self, row_id: str) -> None:
        """Record a freshly-added `interaction`-tier row id and, once
        `_distill_every` of them have accumulated since the last
        distillation pass, run one (Task 7 post-task distillation)."""
        self._pending_interactions.append(row_id)
        if len(self._pending_interactions) >= self._distill_every:
            await self.maybe_distill()

    async def maybe_distill(self) -> dict | None:
        """Summarize the interaction rows pending since the last
        distillation into ONE new `insight`-tier row, linked back to its
        source interactions via `insight -> interaction` (`derived_from`)
        provenance edges in `self._graph`.

        Called automatically by `_track_new_interaction` once
        `_distill_every` new interactions have accumulated, and safe to call
        directly (e.g. from tests) -- it processes whatever is pending,
        regardless of whether that count reached the trigger threshold, and
        is a no-op if nothing is pending.

        Gracefully skips (no-op, never raises) when there is no LLM
        configured (`self._llm is None`, the common case in tests that don't
        exercise distillation) or when the LLM's summary is empty/whitespace
        -- either way the pending id list is still cleared, so a skipped
        distillation does not re-trigger on every subsequent `remember`.
        """
        ids = self._pending_interactions
        self._pending_interactions = []
        if not ids or self._llm is None:
            return None

        texts: list[str] = []
        owners_union: set[str] = set()
        source_ids: list[str] = []
        for row_id in ids:
            row = self._store.get(row_id)
            if row is None:
                continue  # row was forgotten/deleted since being queued
            owners, _affiliated, _meta = self._split_meta(row["metadata"])
            texts.append(row["text"])
            owners_union.update(owners)
            source_ids.append(row_id)
        if not source_ids:
            return None

        insight_text = await self._llm.chat(distill_prompt(texts), bucket="distill")
        insight_text = (insight_text or "").strip()
        if not insight_text:
            return None

        embedding = (await self._embed_fn([insight_text]))[0]
        insight_id = uuid.uuid4().hex
        meta = {
            "created_at": _now_iso(),
            "source": "distilled",
            "tick": 0,
            "tier": INSIGHT,
        }
        metadata = self._build_meta(sorted(owners_union), [], meta)
        await self._store.add(insight_id, insight_text, embedding, metadata)
        for row_id in source_ids:
            self._graph.add_edge(insight_id, row_id, "derived_from")

        return {
            "id": insight_id,
            "text": insight_text,
            "owners": sorted(owners_union),
            "source_ids": source_ids,
        }

    def export_graph(self) -> list[dict]:
        """Serialize the graph adjacency index (agent/team/task relations
        and insight->interaction provenance edges) as
        `[{"src", "dst", "etype"}, ...]`, deterministic order. Kept
        SEPARATE from `export()` (which stays a plain list[dict] of row
        entries, per the existing contract relied on by
        `society/persistence.py`, `society/run.py`, `experiments/run_sim.py`
        and `society/scenario.py`) -- callers that want the full G-Memory
        state must call both `export()`/`export_graph()` and
        `restore()`/`restore_graph()`."""
        return self._graph.export()

    def restore_graph(self, edges: list[dict]) -> None:
        """Inverse of `export_graph`: replace the current graph adjacency
        with the given exported edges."""
        self._graph.restore(edges)


# ==========================================================================
# 3) CollaborativeMemory -- access-controlled shared fragments (2025)
# ==========================================================================


class CollaborativeMemory:
    """Shared fragment store gated by a per-fragment read ACL (2025).

    Fidelity note: faithful to the paper's core mechanism -- a shared pool
    of immutable fragments, each carrying an access-control list of agents
    permitted to READ it (initialized to the writer, {agent_id}), plus
    provenance (source, tick, created_at). This is the axis that
    distinguishes the baseline from our consensus store: we deduplicate
    COPIES across agents, this baseline instead gates READS on a single
    copy -- `recall` filters candidates to fragments whose ACL contains
    `agent_id` *before* ranking by cosine relevance, so an agent with no
    grant sees nothing regardless of relevance. No merge/dedup of duplicate
    fragment text: two agents writing identical text produce two fragments.
    `grant(memory_id, agent_id)` extends a fragment's ACL (the paper's
    sharing/delegation primitive) and is the only way `stats()`'s `shared`
    (ACL size >= 2) becomes nonzero -- under plain runtime `remember` calls
    ACLs start single-owner, so `shared` ~0 until an explicit grant, which
    is documented as expected rather than a gap. `forget(agent_id, id)`
    mirrors `SharedMemory.forget`: it revokes read access for `agent_id`
    and deletes the fragment once its ACL is empty.

    Storage note: rows live in a `ChromaRows` collection SHARED across every
    agent (one Chroma record per `remember`/`remember_atomic` call, one
    fragment, never duplicated per-reader), matching the shared-pool design
    above. Chroma metadata values must be scalars, so each row's ACL is
    stored TWICE, mirroring `GMemory`'s (and `society.ltm.SharedMemory`'s)
    identical dual-storage trick: once as a JSON-encoded `acl` list
    (`dumps_meta`/`loads_meta`) for `all_entries`/`export`, and once as a
    per-member boolean flag `acl_<id>=True` for every reader -- Chroma's
    `where` can't test membership inside a JSON string, so the boolean
    flags are what let `recall`/`recall_of` filter server-side with
    `where={f"acl_{agent_id}": True}` *before* Chroma ranks the (already
    ACL-filtered) candidates by cosine similarity. `affiliated` is
    JSON-encoded the same way as `acl`.
    """

    def __init__(self, embed_fn, llm=None, *, top_k: int = 5, collection_name=None, **kwargs):
        self._embed_fn = embed_fn
        self._llm = llm
        self._store = ChromaRows(embed_fn, collection_name=collection_name)

    @staticmethod
    def _split_meta(metadata: dict) -> tuple[list[str], list[str], dict]:
        """Split a raw Chroma metadata dict into (acl, affiliated ids, the
        remaining `meta` sub-dict used by `all_entries`/`export`), stripping
        both JSON list fields and the per-member `acl_<id>` boolean flags
        (which are a derived index, not real entry data)."""
        acl = sorted(loads_meta(metadata.get("acl")))
        affiliated = sorted(loads_meta(metadata.get("affiliated")))
        meta = {
            k: v
            for k, v in metadata.items()
            if k not in ("acl", "affiliated") and not k.startswith("acl_")
        }
        return acl, affiliated, meta

    @staticmethod
    def _build_meta(acl: list[str], affiliated: list[str], meta: dict) -> dict:
        """Inverse of `_split_meta`: rebuild a full Chroma metadata dict
        (JSON-encoded `acl`/`affiliated` plus fresh per-member boolean
        flags) from the given ACL, affiliated set, and extra fields.

        Note: `ChromaRows.update_metadata` -> `collection.update(metadatas=
        ...)` MERGES the given dict into the existing stored metadata
        key-by-key (it does NOT replace it wholesale); a key omitted here is
        simply left untouched on the stored row. That's harmless for every
        key this method writes, since `acl`/`affiliated` and every
        `acl_<id>=True` flag for a member still in the ACL are always
        present with a fresh, correct value. It is NOT harmless for a flag
        whose member was just REVOKED from `acl`: that stale `acl_<id>=True`
        key is absent from this dict's output (since the id is gone from
        `acl`), so a plain merge would leave it in place forever -- the
        revoked agent would keep matching `where={f"acl_{id}": True}` and
        could still `recall` the fragment. Callers that revoke a member (see
        `forget`) must explicitly set `acl_<revoked_id>: None` in the update
        they send -- chromadb treats `None` as "delete this key" -- in
        addition to what this method builds. `grant` only ever ADDS a
        member, so a plain merge is safe there."""
        metadata = dict(meta)
        metadata["acl"] = dumps_meta(sorted(set(acl)))
        metadata["affiliated"] = dumps_meta(sorted(set(affiliated)))
        for a in acl:
            metadata[f"acl_{a}"] = True
        return metadata

    async def remember(
        self,
        agent_id: str,
        text: str,
        tick: int = 0,
        source: str = "runtime",
        story_order=None,
        story_time=None,
    ) -> list[dict]:
        embedding = (await self._embed_fn([text]))[0]
        row_id = uuid.uuid4().hex
        meta = {
            "created_at": _now_iso(),
            "source": source,
            "tick": tick,
        }
        if story_order is not None:
            meta["story_order"] = story_order
        if story_time is not None:
            meta["story_time"] = story_time
        metadata = self._build_meta([agent_id], [], meta)
        await self._store.add(row_id, text, embedding, metadata)
        return [{"id": row_id, "text": text, "merged": False, "owners": [agent_id]}]

    async def remember_atomic(
        self,
        owners: list[str],
        text: str,
        tick: int = 0,
        source: str = "sediment",
        story_order=None,
        story_time=None,
        affiliated: list[str] | None = None,
    ) -> dict | None:
        """One row whose ACL is `set(owners)` -- faithful to this baseline's
        access-controlled-fragment model, where a fragment's ACL is the set
        of agents permitted to read it."""
        text = text.strip()
        if not text:
            return None
        if not owners:
            raise ValueError("remember_atomic requires at least one owner")

        embedding = (await self._embed_fn([text]))[0]
        row_id = uuid.uuid4().hex
        meta = {
            "created_at": _now_iso(),
            "source": source,
            "tick": tick,
        }
        if story_order is not None:
            meta["story_order"] = story_order
        if story_time is not None:
            meta["story_time"] = story_time
        new_acl = sorted(set(owners))
        seed_affiliated = sorted(a for a in set(affiliated or []) if a != row_id)
        metadata = self._build_meta(new_acl, seed_affiliated, meta)
        await self._store.add(row_id, text, embedding, metadata)
        return {"id": row_id, "text": text, "merged": False, "owners": new_acl}

    async def recall(self, agent_id: str, query: str, top_k: int = 5) -> list[dict]:
        """Filters candidates to fragments whose ACL contains `agent_id`
        server-side via `where={f"acl_{agent_id}": True}` BEFORE Chroma
        ranks by cosine relevance -- an agent with no grant sees nothing
        regardless of relevance."""
        hits = await self._store.query(query, top_k, where={f"acl_{agent_id}": True})
        return [{"id": h["id"], "text": h["text"]} for h in hits]

    async def recall_of(self, owner_id: str, query: str, top_k: int = 5) -> list[dict]:
        """`recall` already filters candidates to fragments whose ACL
        contains `agent_id`, so retrieving on behalf of another owner is
        just `recall` under that owner's id."""
        return await self.recall(owner_id, query, top_k)

    def grant(self, memory_id: str, agent_id: str) -> bool:
        """Extend a fragment's read ACL to include `agent_id`. Returns False
        if the fragment doesn't exist."""
        row = self._store.get(memory_id)
        if row is None:
            return False
        acl, affiliated, meta = self._split_meta(row["metadata"])
        updated_acl = sorted(set(acl) | {agent_id})
        self._store.update_metadata(memory_id, self._build_meta(updated_acl, affiliated, meta))
        return True

    def forget(self, agent_id: str, memory_id: str) -> bool:
        """Revoke agent_id's read access; delete the fragment once its ACL
        is empty. Returns False if the fragment doesn't exist or agent_id
        was never a reader."""
        row = self._store.get(memory_id)
        if row is None:
            return False
        acl, affiliated, meta = self._split_meta(row["metadata"])
        if agent_id not in acl:
            return False
        acl = [a for a in acl if a != agent_id]
        if not acl:
            self._store.delete(memory_id)
        else:
            new_meta = self._build_meta(acl, affiliated, meta)
            # `ChromaRows.update_metadata` -> `collection.update(metadatas=...)`
            # MERGES key-by-key rather than replacing the metadata dict, and
            # chromadb treats a `None` value as "delete this key" -- so the
            # revoked agent's `acl_<agent_id>` boolean flag (still present in
            # the stored metadata, and NOT re-written by `_build_meta` since
            # `agent_id` is no longer in `acl`) must be explicitly nulled out
            # here, or it would keep matching `where={f"acl_{agent_id}":
            # True}` in `recall`/`recall_of` forever. Mirrors
            # `GMemory.forget`/`society.ltm.SharedMemory.forget`.
            new_meta[f"acl_{agent_id}"] = None
            self._store.update_metadata(memory_id, new_meta)
        return True

    async def revise(self, agent_id: str, memory_id: str, new_text: str, tick: int = 0) -> list[dict]:
        self.forget(agent_id, memory_id)
        return await self.remember(agent_id, new_text, tick=tick)

    def add_affiliations(self, memory_id: str, other_ids: list[str]) -> bool:
        row = self._store.get(memory_id)
        if row is None:
            return False
        acl, affiliated, meta = self._split_meta(row["metadata"])
        updated = sorted((set(affiliated) | set(other_ids)) - {memory_id})
        self._store.update_metadata(memory_id, self._build_meta(acl, updated, meta))
        return True

    def remove_affiliations(self, memory_id: str, other_ids: list[str]) -> bool:
        row = self._store.get(memory_id)
        if row is None:
            return False
        acl, affiliated, meta = self._split_meta(row["metadata"])
        updated = sorted(set(affiliated) - set(other_ids))
        self._store.update_metadata(memory_id, self._build_meta(acl, updated, meta))
        return True

    def get_affiliations(self, memory_id: str) -> list[str]:
        row = self._store.get(memory_id)
        if row is None:
            return []
        _, affiliated, _ = self._split_meta(row["metadata"])
        return affiliated

    def all_entries(self) -> list[dict]:
        entries = []
        for r in self._store.all_rows():
            acl, affiliated, meta = self._split_meta(r["metadata"])
            entries.append(
                {
                    "id": r["id"],
                    "text": r["text"],
                    "owners": acl,
                    "affiliated": affiliated,
                    "meta": meta,
                }
            )
        return entries

    def export(self) -> list[dict]:
        exported = []
        for r in self._store.all_rows():
            acl, affiliated, meta = self._split_meta(r["metadata"])
            exported.append(
                {
                    "id": r["id"],
                    "text": r["text"],
                    "owners": acl,
                    "affiliated": affiliated,
                    "meta": meta,
                    "embedding": list(r["embedding"]),
                }
            )
        return exported

    async def restore(self, entries: list[dict]) -> None:
        if not entries:
            return
        missing_idx = [i for i, e in enumerate(entries) if not e.get("embedding")]
        computed = {}
        if missing_idx:
            texts = [entries[i]["text"] for i in missing_idx]
            vectors = await self._embed_fn(texts)
            for i, vec in zip(missing_idx, vectors):
                computed[i] = list(vec)

        for i, entry in enumerate(entries):
            acl = list(entry.get("owners", []))
            affiliated = list(entry.get("affiliated", []))
            meta = dict(entry.get("meta", {}) or {})
            embedding = entry.get("embedding") or computed[i]
            metadata = self._build_meta(acl, affiliated, meta)
            await self._store.add(entry["id"], entry["text"], list(embedding), metadata)

    def stats(self) -> dict:
        entries = self.all_entries()
        total = len(entries)
        shared = sum(1 for e in entries if len(e["owners"]) >= 2)
        ratio = (shared / total) if total else 0.0
        return {"total": total, "shared": shared, "ratio": ratio}


# ==========================================================================
# factory
# ==========================================================================

_REGISTRY = {
    "consensus": SharedMemory,
    "generative_agents": GenerativeAgentsMemory,
    "g_memory": GMemory,
    "collaborative": CollaborativeMemory,
}


def make_memory(kind: str, embed_fn, llm=None, **kw):
    """Return an instance of the memory backend named by `kind`.

    kind in {"consensus", "generative_agents", "g_memory", "collaborative"}.
    Raises ValueError for an unknown kind.
    """
    try:
        cls = _REGISTRY[kind]
    except KeyError:
        raise ValueError(
            f"unknown memory kind {kind!r}; expected one of {sorted(_REGISTRY)}"
        )
    return cls(embed_fn, llm=llm, **kw)
