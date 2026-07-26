# Faithful, Chroma-unified Baselines Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the three baseline memory backends (Generative Agents, G-Memory, Collaborative) a fair, faithful comparison basis against Agentsensus (consensus) by putting all four on ChromaDB and completing G-Memory (full 3-tier graph + distillation) and Generative Agents (reflection tree).

**Architecture:** Each baseline becomes a thin store over its own ChromaDB collection (shared plumbing in `society/baseline_store.py`), keeping its distinguishing organization rule (per-owner private streams / shared graph / ACL fragments). Retrieval = Chroma vector query → method-specific re-rank. G-Memory gains an insight/query tier + adjacency side-index + LLM distillation + bi-level retrieval; Generative Agents gains an importance-triggered reflection pass. Sediment bases are built by each backend's own `restore()` from the existing consensus dump (no re-sediment).

**Tech Stack:** Python 3.14, chromadb (cosine HNSW), asyncio, pytest. LLM via `society.llm.LLMClient` (deepseek-v4-flash + thinking disabled for sim runs). Embeddings via `society.embeddings.EmbeddingClient`.

## Global Constraints

- Do NOT modify `society/ltm.py` (consensus `SharedMemory`) semantics or `society/kernel.py`'s action set — the kernel interface is the fixed contract.
- Every baseline MUST keep the full duck-typed interface the kernel calls: `remember`, `remember_atomic`, `recall`, `recall_of`, `forget`, `revise`, `add_affiliations`, `remove_affiliations`, `get_affiliations`, `all_entries`, `export`, `restore`, `stats` (same signatures/return shapes as `SharedMemory`).
- Chroma pattern (mirror `SharedMemory.__init__`): `chromadb.Client()` + `get_or_create_collection(name, metadata={"hnsw:space":"cosine"})`; default `collection_name=None` auto-generates a unique name `f"<backend>_{uuid4().hex[:8]}"`.
- Embeddings are provided by an injected async `embed_fn(list[str]) -> list[list[float]]`; never call an embedding API directly.
- Tests run under the venv only: `venv/bin/python -m pytest -q`. Baseline before this plan: **363 passed**.
- TDD: failing test → run (fail) → minimal impl → run (pass) → commit. One logical change per commit.
- Footprint math unchanged: `stats()` returns `{total, shared, ratio}`; `shared` = entries whose owner/acl set ≥ 2.

## File Structure

- Create `society/baseline_store.py` — shared Chroma plumbing: `ChromaRows` helper (create collection, add/get/query/update/delete/count, export/restore of `{id,text,owners,affiliated,meta,embedding}`), pure of any method-specific rule.
- Modify `society/baselines.py` — rewrite `GenerativeAgentsMemory`, `GMemory`, `CollaborativeMemory` over `ChromaRows`; keep `make_memory` factory and each class's organization rule.
- Create `society/gmemory_graph.py` — G-Memory adjacency side-index + tier constants + distillation prompt/logic (keeps `baselines.py` focused).
- Modify `tests/test_baselines.py` — extend for Chroma-backed behavior + new mechanisms.
- Create `tests/test_gmemory_full.py`, `tests/test_ga_reflection.py`.
- Modify `society/scenario.py` / `experiments/run_sim.py` only if needed to pass a unique `collection_name` per run (avoid cross-run collection contamination).

---

# PHASE 1 — Chroma-unified baseline substrate (fair footprint table)

Delivers a fair 三国 4-backend footprint+cost table using current retrieval mechanisms.

### Task 1: `ChromaRows` shared plumbing

**Files:**
- Create: `society/baseline_store.py`
- Test: `tests/test_baseline_store.py`

**Interfaces:**
- Produces: `class ChromaRows` with:
  - `__init__(self, embed_fn, *, collection_name: str | None = None)`
  - `async def add(self, row_id: str, text: str, embedding: list[float], metadata: dict) -> None`
  - `def get(self, row_id: str) -> dict | None` → `{id,text,metadata}` or None
  - `async def query(self, query: str, n: int, where: dict | None = None) -> list[dict]` → `[{id,text,metadata}]` ranked by cosine
  - `def update_metadata(self, row_id: str, metadata: dict) -> None`
  - `def delete(self, row_id: str) -> None`
  - `def count(self) -> int`
  - `def all_rows(self) -> list[dict]` → `[{id,text,metadata,embedding}]`
  - metadata values must be Chroma-scalar; store list fields (`owners`,`acl`,`affiliated`) as JSON strings via helpers `dumps_meta`/`loads_meta`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_baseline_store.py
import pytest
from society.baseline_store import ChromaRows
from tests.helpers import afake_embed

async def test_add_get_query_roundtrip():
    r = ChromaRows(afake_embed)
    emb = (await afake_embed(["刘备在新野"]))[0]
    await r.add("m1", "刘备在新野", emb, {"owners": '["liubei"]'})
    got = r.get("m1")
    assert got["text"] == "刘备在新野" and got["metadata"]["owners"] == '["liubei"]'
    assert r.count() == 1
    hits = await r.query("新野", 5)
    assert hits and hits[0]["id"] == "m1"
```

- [ ] **Step 2: Run to verify fail** — `venv/bin/python -m pytest tests/test_baseline_store.py -q` → FAIL (no module).

- [ ] **Step 3: Implement `ChromaRows`** mirroring `SharedMemory`'s chroma usage:

```python
# society/baseline_store.py
import json, uuid
import chromadb

def dumps_meta(v): return json.dumps(v)
def loads_meta(s): return json.loads(s or "[]")

class ChromaRows:
    def __init__(self, embed_fn, *, collection_name=None):
        self._embed_fn = embed_fn
        if collection_name is None:
            collection_name = f"baseline_{uuid.uuid4().hex[:8]}"
        self._client = chromadb.Client()
        self._collection = self._client.get_or_create_collection(
            name=collection_name, metadata={"hnsw:space": "cosine"})

    async def add(self, row_id, text, embedding, metadata):
        self._collection.add(ids=[row_id], documents=[text],
                             embeddings=[list(embedding)], metadatas=[dict(metadata)])

    def get(self, row_id):
        got = self._collection.get(ids=[row_id], include=["documents", "metadatas"])
        if not got["ids"]:
            return None
        return {"id": row_id, "text": got["documents"][0], "metadata": got["metadatas"][0]}

    async def query(self, query, n, where=None):
        if self._collection.count() == 0:
            return []
        emb = (await self._embed_fn([query]))[0]
        res = self._collection.query(
            query_embeddings=[emb], n_results=min(n, self._collection.count()),
            where=where, include=["documents", "metadatas"])
        return [{"id": i, "text": d, "metadata": m}
                for i, d, m in zip(res["ids"][0], res["documents"][0], res["metadatas"][0])]

    def update_metadata(self, row_id, metadata):
        self._collection.update(ids=[row_id], metadatas=[dict(metadata)])

    def delete(self, row_id):
        self._collection.delete(ids=[row_id])

    def count(self):
        return self._collection.count()

    def all_rows(self):
        if self._collection.count() == 0:
            return []
        got = self._collection.get(include=["documents", "metadatas", "embeddings"])
        return [{"id": i, "text": d, "metadata": m, "embedding": list(e)}
                for i, d, m, e in zip(got["ids"], got["documents"], got["metadatas"], got["embeddings"])]
```

- [ ] **Step 4: Run to verify pass.**
- [ ] **Step 5: Commit** — `feat(baselines): ChromaRows shared plumbing for baseline stores`.

### Task 2: Port `GenerativeAgentsMemory` to Chroma

**Files:**
- Modify: `society/baselines.py` (class `GenerativeAgentsMemory`)
- Test: `tests/test_baselines.py` (extend)

**Interfaces:**
- Consumes: `ChromaRows` from Task 1.
- Produces: `GenerativeAgentsMemory(embed_fn, llm=None, *, top_k=5, collection_name=None)` with the full interface; per-owner rows (one Chroma record per owner); metadata `{owner, importance, last_access, affiliated(JSON), source, tick, created_at, story_order?}`; retrieval = recency+importance+relevance min-max normalized, weighted sum (weights 1.0), fed by `ChromaRows.query` candidates (fetch e.g. `max(4*top_k, 50)` candidates then re-rank).

- [ ] **Step 1: Write failing tests** (behavior must match pre-Chroma semantics — reuse existing test intents):

```python
async def test_ga_chroma_per_owner_fanout():
    m = GenerativeAgentsMemory(afake_embed, llm=None)
    await m.remember_atomic(["a", "b"], "shared scene")
    ents = m.all_entries()
    assert len(ents) == 2                      # one row per owner
    assert {e["owners"][0] for e in ents} == {"a", "b"}

async def test_ga_chroma_recall_scoped_and_reflection_fields():
    m = GenerativeAgentsMemory(afake_embed, llm=None)
    await m.remember("a", "刘备在新野议事")
    assert (await m.recall("a", "新野"))          # owner a sees it
    assert (await m.recall("b", "新野")) == []    # owner b does not
```

- [ ] **Step 2: Run → fail.**
- [ ] **Step 3: Reimplement** class over `ChromaRows`: `remember`/`remember_atomic` write per-owner rows with importance (`_score_importance`) + `last_access` from a monotonic `self._clock`; `recall_of` fetches candidates via `ChromaRows.query(query, n=candidate_k, where={"owner": owner_id})`, then computes the 3-term score in Python (unchanged math) and updates `last_access` via `update_metadata`. `forget`/`affiliations`/`all_entries`/`export`/`restore`/`stats` operate over `ChromaRows`. Keep `restore` fanning multi-owner entries into per-owner rows.
- [ ] **Step 4: Run → pass** (plus existing GA tests still green).
- [ ] **Step 5: Commit** — `feat(baselines): GenerativeAgentsMemory on ChromaDB (per-owner streams)`.

### Task 3: Port `GMemory` to Chroma

**Files:** Modify `society/baselines.py` (class `GMemory`); Test `tests/test_baselines.py`.

**Interfaces:**
- Produces: `GMemory(embed_fn, llm=None, *, top_k=5, collection_name=None)`; shared rows with metadata `{owners(JSON), tier, affiliated(JSON), source, tick, ...}`; `recall` default cross-agent, `recall(..., owner_scope=True)`/`recall_of` filter `owner_id in owners`; `tier` defaults `"interaction"`.

- [ ] **Step 1: Failing tests**

```python
async def test_gmemory_chroma_shared_single_row():
    m = GMemory(afake_embed, llm=None)
    await m.remember_atomic(["a", "b"], "shared scene")
    ents = m.all_entries()
    assert len(ents) == 1 and sorted(ents[0]["owners"]) == ["a", "b"]

async def test_gmemory_recall_of_owner_filter():
    m = GMemory(afake_embed, llm=None)
    await m.remember("a", "刘备在新野")
    assert (await m.recall_of("a", "新野"))
    assert (await m.recall_of("z", "新野")) == []
```

- [ ] **Step 2: Run → fail.**
- [ ] **Step 3: Reimplement** over `ChromaRows`; `recall_of` uses `where={"$contains"...}` is NOT supported for JSON list — instead store per-owner boolean metadata keys `owner_<id>=True` (mirror `SharedMemory`'s owner-filter approach) so `where={f"owner_{owner_id}": True}` works, and keep `owners` JSON for `all_entries`. Document this dual storage in a comment.
- [ ] **Step 4: Run → pass.**
- [ ] **Step 5: Commit** — `feat(baselines): GMemory on ChromaDB (shared store, tiered)`.

### Task 4: Port `CollaborativeMemory` to Chroma

**Files:** Modify `society/baselines.py` (class `CollaborativeMemory`); Test `tests/test_baselines.py`.

**Interfaces:**
- Produces: `CollaborativeMemory(...)`; one row per fragment; ACL as per-member boolean metadata `acl_<id>=True` (+ `acl` JSON for `all_entries`/export); `recall`/`recall_of` filter `where={f"acl_{agent_id}": True}`; `grant(memory_id, agent_id)`; `forget` revokes then deletes when ACL empty; affiliations.

- [ ] **Step 1: Failing tests**

```python
async def test_collab_chroma_acl_gates_recall():
    m = CollaborativeMemory(afake_embed, llm=None)
    res = await m.remember("a", "密信内容")
    mid = res[0]["id"]
    assert (await m.recall("a", "密信"))
    assert (await m.recall("b", "密信")) == []
    assert m.grant(mid, "b") is True
    assert (await m.recall("b", "密信"))
```

- [ ] **Step 2: Run → fail.**  **Step 3: Reimplement over `ChromaRows`.**  **Step 4: Run → pass.**
- [ ] **Step 5: Commit** — `feat(baselines): CollaborativeMemory on ChromaDB (ACL fragments)`.

### Task 5: Per-run collection isolation + fair 三国 table

**Files:** Modify `society/scenario.py` (pass `collection_name` into `make_memory` per run, e.g. `f"{scenario}_{memory_kind}_{seed}"`); verify `experiments/run_sim.py` writes footprint from `stats()`/`export()`.
- Test: `tests/test_baselines.py::test_kernel_act_on_and_read_do_not_crash_on_baseline_memory` (already exists) must still pass over Chroma-backed baselines.

- [ ] **Step 1** Confirm the existing kernel-integration test passes over the Chroma-backed backends; add a `restore`→footprint assertion per backend (generative expands 3.3×; g_memory/collab == consensus count).
- [ ] **Step 2** Run full suite `venv/bin/python -m pytest -q` → all green.
- [ ] **Step 3: Commit** — `feat(baselines): per-run Chroma collection isolation`.
- [ ] **Step 4 (run, not code):** launch the 三国 4-backend 50-tick sims on `config_flash.json`, in parallel; collect footprint+cost+new_memories into a table. (Execution step — no commit.)

---

# PHASE 2 — G-Memory Full (3-tier graph + distillation + bi-level retrieval)

Tasks 6–8 raise G-Memory from flat-interaction to the paper's hierarchy. Each task is TDD (failing test with the asserts below → minimal impl → pass → commit); the executing subagent writes the concrete code following these specs and the spec doc §"Workstream 2 — G-Memory".

### Task 6: Tiers + adjacency side-index

**Files:** Create `society/gmemory_graph.py` (tier constants `INTERACTION/INSIGHT/QUERY`; `class GraphIndex` with `add_edge(src, dst, etype)`, `neighbors(node_id, etype=None) -> list[str]`, `export()/restore()` as an adjacency dict); Modify `GMemory` to own a `GraphIndex`, tag each stored row's `tier`, and include the graph in `export()/restore()`.
- Test `tests/test_gmemory_full.py`:
  - a raw `remember` creates an `interaction`-tier node;
  - `add_edge`/`neighbors` round-trip; graph survives `export`→new instance `restore`.

### Task 7: Post-task distillation → insight nodes

**Files:** `society/gmemory_graph.py` (distillation prompt + `async def distill(cluster: list[dict], llm) -> list[str]`); `GMemory.maybe_distill(trigger)` invoked every K new interactions (K = config, default 20) — clusters recent interaction nodes, calls `llm` to summarize into 1+ `insight` nodes (new Chroma rows, tier=insight), and adds `insight→interaction` provenance edges.
- Test: with a FakeLLM returning a canned insight, crossing K interactions creates an `insight` node linked (via `GraphIndex`) to its source interactions; insight text is retrievable.

### Task 8: Bi-level retrieval

**Files:** `GMemory.recall`/`recall_of` gain graph-aware retrieval: (1) query `insight`-tier for relevant insights; (2) from those insights + top interaction hits, traverse `GraphIndex` (≤2 hops) to gather supporting interactions; merge+rank; return `[{id,text}]`. Preserve `owner_scope`.
- Test: after distillation, a query semantically near an insight returns both the insight and its linked interactions; `owner_scope=True` still restricts to the owner's interactions.

---

# PHASE 3 — Generative Agents reflection tree

### Task 9: Importance accumulator + reflection trigger

**Files:** `GenerativeAgentsMemory` tracks `self._importance_since_reflection`; each `remember`/`remember_atomic` adds the scored importance; when it crosses `REFLECTION_THRESHOLD` (config, default 150) a reflection is triggered and the accumulator resets.
- Test: feeding enough high-importance memories crosses the threshold exactly once and calls the reflection routine (spy/FakeLLM); low-importance memories don't trigger.

### Task 10: Reflection synthesis + evidence links

**Files:** `GenerativeAgentsMemory.async def _reflect(self)`: (1) ask `llm` for N salient high-level questions given recent memories; (2) `recall` per question; (3) `llm`-synthesize a reflection statement; (4) store it as a new row with `meta.kind="reflection"` and `affiliated` = evidence ids. Reflections are retrievable and can feed later reflections.
- Test: with a FakeLLM returning fixed questions+reflection, `_reflect` stores a `reflection` row whose `affiliated` equals the retrieved evidence ids; the reflection is returned by a subsequent `recall`.

---

# PHASE 4 — Generalize (separate execution, no new code)

Run the 4-backend × {red_chamber, russia_ukraine, hamlet} matrix on flash, reusing each existing sediment dump; assemble the full footprint/cost/fidelity tables.

---

## Self-Review

- **Spec coverage:** WS1 (Chroma) → Tasks 1–5; WS2 (G-Mem Full) → Tasks 6–8; WS2 (GA reflection) → Tasks 9–10; WS3 (per-method base via restore) → Task 5 assertions + each class's `restore`; model (flash) → Task 5 Step 4 / Phase 4; Collaborative faithful → Task 4. Covered.
- **Placeholders:** Phases 2–3 tasks specify files, interfaces, and exact test assertions but defer concrete code to the executing subagent (each is still TDD with a named failing test) — acceptable given each is a self-contained mechanism; Phase 1 is fully bite-sized.
- **Type consistency:** `ChromaRows` methods and the per-class metadata keys (`owner`/`owners`/`acl`/`owner_<id>`/`acl_<id>`, `tier`, `affiliated`) are used consistently across tasks; `make_memory`/kernel interface unchanged.
