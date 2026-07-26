# Faithful, Chroma-unified baselines + per-method sedimentation — Design

Date: 2026-07-25
Status: approved (brainstorming)
Repo: agentsensus

## Problem

The three baseline memory backends we compare Agentsensus (consensus) against are
not a fair, faithful basis for the paper as currently built:

1. **Substrate asymmetry.** `society.ltm.SharedMemory` (consensus, ours) stores
   entries in **ChromaDB** (indexed vector DB, owner-filtered metadata queries),
   while the baselines in `society/baselines.py` store rows in a plain in-memory
   **Python dict** with brute-force pure-Python cosine. The engine is not any
   paper's contribution, but a reviewer will ask why our method uses a real
   vector DB and the baselines don't.

2. **Incomplete mechanisms.** The baselines reproduce only part of each paper:
   - Generative Agents (Park 2023): has the retrieval score (recency +
     importance + relevance) but **not the reflection tree**.
   - G-Memory (Zhang 2025): only a flat "interaction" tier with a tier tag —
     **no graph structure, no insight/query tiers, no distillation**. This is the
     weakest reproduction and the one most likely to be dismissed as "too weak a
     baseline."
   - Collaborative (2025): ACL-gated fragments — essentially faithful.

3. **Sediment base is unfairly merged.** The initial ~6051-memory sediment is
   produced once by the consensus pipeline (atomize → assign owners → consensus
   equivalence-merge) and then `restore()`d into every backend. Restoring the
   **already-merged** consensus dump hands g_memory/collaborative consensus's
   cross-chunk equivalence-merge for free; only generative_agents' `restore`
   faithfully re-expands per owner. So the baselines' starting memory is not
   organized by their own method. We also therefore do **not** currently know how
   many raw deposits collapsed into 6051 — i.e. consensus's true equivalence-merge
   compression is unmeasured.

## Goals

- All four backends store their entries on the **same substrate (ChromaDB)** so
  footprint is measured identically and the engine is neutral.
- Each baseline reproduces its paper's **full core mechanism** (Generative Agents
  reflection tree; G-Memory three-tier graph + distillation; Collaborative ACL).
- Each backend's **sediment base is built by its own method** from an identical
  pre-merge deposit stream — and this yields the measurement of consensus's real
  equivalence-merge compression.
- All re-runs (re-sediment + the 4-backend × N-scenario sim matrix) use
  **deepseek-v4-flash with thinking disabled**.

## Non-goals

- No change to `society.ltm.SharedMemory` (consensus) semantics or to the kernel's
  action set. The kernel interface is the fixed contract the baselines must meet.
- No unrelated refactoring of the sedimentation LLM prompts (atomize/assign logic
  stays as-is; we only add deposit-stream logging and re-run on the new model).

## Decisions (locked in brainstorming)

| topic | decision |
|---|---|
| G-Memory fidelity | **Full** — interaction + insight + query graph, graph-traversal retrieval, post-task distillation |
| Generative Agents | **Add the reflection tree** (full fidelity), keep existing 3-term retrieval |
| Storage substrate | **ChromaDB for all four backends** |
| Sediment | **Rebuilt per-method** from a captured pre-merge deposit stream |
| Model for re-runs | **deepseek-v4-flash + `thinking:{type:disabled}`** (config `extra_body`) |
| Sequencing | 1) Chroma unify + per-method sediment → fair 三国 table; 2) G-Memory Full; 3) GA reflection; 4) other 3 scenarios |

## Architecture

### Workstream 1 — Chroma-unified baseline substrate

Each baseline becomes a thin store over its **own ChromaDB collection**
(`collection_name` per backend/run), replacing `self._rows` + `_cosine`:

- **Entry storage:** one Chroma record per stored row = `{id, document=text,
  embedding, metadata}`. Method-specific fields live in metadata:
  - GenerativeAgents: `owner` (single), `importance`, `last_access`, `affiliated`.
  - GMemory: `owners` (JSON list), `tier` ∈ {interaction, insight, query},
    `affiliated`; graph adjacency kept in a small side index (see WS2).
  - Collaborative: `acl` (JSON list), `affiliated`.
- **Retrieval:** Chroma vector `query()` for candidate relevance, then
  method-specific re-ranking / filtering:
  - GenerativeAgents: pull candidates, compute recency + importance + relevance,
    min-max normalize per component, weighted sum (unchanged scoring math, now
    fed by Chroma relevance instead of pure-Python cosine).
  - GMemory: `where` filter by tier for retrieval scope; graph traversal over the
    side adjacency index (WS2); default cross-agent (shared) retrieval.
  - Collaborative: `where` ACL-membership filter before ranking.
- **Footprint:** measured uniformly from each collection — entry count and
  `text_bytes` (and, if reported, vector bytes = dim × entries) — identical
  method to consensus. `stats()` keeps `total`/`shared`/`ratio`.
- **Interface parity:** keep the full duck-typed contract the kernel calls:
  `remember`, `remember_atomic`, `recall`, `recall_of`, `forget`, `revise`,
  `add_/remove_/get_affiliations`, `all_entries`, `export`, `restore`, `stats`.
  (These already exist post-13057ce; they get re-implemented over Chroma.)

A shared helper module (e.g. `society/baseline_store.py`) holds the common Chroma
plumbing (collection create/insert/query/export/restore, cosine-free) so each
baseline class stays focused on its own organization rule.

### Workstream 2 — Full mechanisms

**G-Memory (Full) — three-tier hierarchical graph.**
- **Nodes** live as Chroma records tagged by `tier`:
  - `interaction`: raw deposits (from `remember`/`remember_atomic`).
  - `insight`: LLM-distilled generalizations produced by the distillation pass.
  - `query`: a task/query node linking a query to the trajectory (interaction
    nodes) that served it.
- **Edges (graph topology):** a side adjacency index (id → neighbor ids with edge
  type) captures agent/team/task relations and insight→interaction provenance.
  Persisted in `export()`/`restore()` alongside the Chroma collection.
- **Bi-level retrieval:** given a query, (1) retrieve relevant `insight` nodes;
  (2) from those + the query node, traverse the interaction sub-graph (bounded
  hops) to gather supporting interactions; return the combined, ranked set.
- **Post-task distillation:** on a distillation trigger (e.g. end of a task/scene
  or every K new interactions), an LLM pass summarizes a cluster of recent
  interactions into one or more `insight` nodes, adds insight→interaction edges,
  and links a `query` node. Runtime LLM cost is accepted.

**Generative Agents — reflection tree.**
- Maintain a running sum of the importance of memories added since the last
  reflection. When it crosses a threshold (paper: ~150 on a 1–10 importance
  scale; make it a config constant), run a reflection:
  1. Ask the LLM for the N most salient high-level questions given the recent
     memories.
  2. For each question, `recall` relevant memories.
  3. LLM-synthesize a **reflection** statement; store it as a new stream entry
     (`tier`/`kind = reflection`) with `affiliated` = the evidence memory ids.
- Reflections are themselves retrievable and can feed later reflections (tree).

**Collaborative — unchanged mechanism, ported to Chroma.** Keep the immutable
ACL-gated fragments and `grant()`.

### Workstream 3 — Per-method sedimentation

- **Capture the deposit stream.** Instrument the sediment pipeline
  (`society/history_extract.py`, which calls `shared.remember_atomic(owners, text,
  …)`) so every deposit is appended once to a JSONL:
  `{owners, text, affiliated, story_order}` (order = call order). Implement via a
  thin recording wrapper around the shared-memory object passed to the pipeline
  (no change to the atomize/assign logic), so the stream is exactly the fragments
  fed to consensus.
- **Re-run 三国 sediment on flash**, producing (a) the consensus store as today and
  (b) `three_kingdoms.deposit_stream.jsonl`.
- **Build each backend's base by replaying the identical stream** through that
  backend's `remember_atomic` (+ `link_group`/affiliations where applicable):
  consensus merges → ~6051; generative → per-owner expansion; g_memory → shared
  interaction nodes, no equivalence-merge; collaborative → one fragment per
  deposit with ACL. This produces four faithful sediment bases from one stream.
- **Report** raw-deposit count `D` vs consensus `6051` = consensus's real
  equivalence-merge compression (previously unknown), plus per-backend base
  footprints.

### Model

`config_flash.json` already sets `chat_model=deepseek-v4-flash`,
`extra_body={"thinking":{"type":"disabled"}}`, `max_concurrency=32`, threaded via
the new `LLMClient(extra_body=…)` passthrough (llm.py / run.py). Re-sediment and
all sim runs use it. The already-completed v4-pro consensus 三国 sim is re-run on
flash so the whole matrix shares one model.

## Data flow (three国, end to end)

```
source text ──atomize+assign(flash)──▶ deposit stream JSONL ──replay──▶ 4 bases
                     │                        (owners,text,affiliated)      │
                     └──consensus store (6051, ChromaDB)                    ▼
                                                              consensus / GA / G-Mem / Collab
                                                              (each ChromaDB, own rule)
                                                                            │
                         per backend: restore base ──▶ 50-tick sim (flash) ─┘
                                                                            │
                                                                            ▼
                                            footprint + cost + new_memories per backend
```

## Testing

- **Chroma substrate (each backend):** remember/remember_atomic round-trip;
  recall/recall_of owner/ACL scoping; export→restore fidelity; footprint counts.
- **GA reflection:** crossing the importance threshold triggers a reflection;
  the reflection is stored with evidence `affiliated` ids; it is retrievable.
- **G-Memory Full:** distillation adds `insight` nodes and insight→interaction
  edges; bi-level retrieval returns insights + traversed interactions; tier
  `where`-filtering works; graph survives export/restore.
- **Sediment replay:** replaying the same deposit stream twice into a backend
  yields identical bases (determinism); consensus base count ≤ deposit count;
  generative base = sum of owner-set sizes; g_memory/collab base = deposit count.
- **Kernel integration:** `act_on`/`read`/affiliations drive each Chroma-backed
  baseline without error (extends the existing 13057ce integration test).
- Full suite green.

## Risks / open points

- **Re-sediment quality on flash.** The sediment is the foundation; atomize/assign
  on flash may differ from v4-pro. Mitigation: spot-check the new 三国 sediment
  memories for quality before committing to the base; the user accepted flash for
  re-sediment.
- **Runtime LLM cost of Full mechanisms.** G-Memory distillation and GA reflection
  add per-sim LLM calls (extra cost/latency) — accepted for fidelity.
- **Small equivalence-merge compression.** If narrative deposits are mostly unique
  across chunks, `D ≈ 6051` and consensus shows little sediment-level advantage
  over g_memory/collaborative. That is an honest empirical outcome; report it as
  measured. (Generative's per-owner 3.3× inflation is independent of this.)

## Sequencing

1. **Chroma unification + per-method sediment replay** → produces a *fair* 三国
   4-backend footprint table quickly (uses current mechanism level).
2. **G-Memory Full graph.**
3. **Generative Agents reflection tree.**
4. **Generalize to red_chamber / russia_ukraine / hamlet** (re-sediment each,
   run the 4-backend matrix).
