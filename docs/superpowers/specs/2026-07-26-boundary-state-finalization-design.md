# Boundary-state finalization (agent placement + aliveness) — Design

Date: 2026-07-26
Status: approved (brainstorming)
Repo: agentsensus
Scope: **Effort A** of a two-part fix. Effort B (messaging-layer redesign: inbox→kernel,
per-pair conversation threads, local-instant/remote-delayed comms) is designed separately.

## Problem

The simulation's initial agent placement and aliveness are wrong, which produces
canonically-implausible events that confound the continuation-fidelity ("grounding")
metric — independent of the memory backend.

Evidence (三国 sim.yaml, ch1-40 sediment):
- **河东 is a dumping bucket of 14 unrelated characters** — Wei generals (夏侯渊/张辽/
  于禁/乐进/许褚) + Han-court figures who died in ch2-3 (何进/张让) + 衣带诏 conspirators
  (王子服/吴硕) + 吕布 subordinates (侯成/宋宪) + 糜竺. They are not canonically
  co-located, so the sim forces cross-faction "河东密议" scenes.
- **Dead characters are active agents**: 何进/张让 died in ch2-3 (十常侍之乱) but appear
  as living, schedulable agents — the aliveness tracking missed their deaths.

Root cause: initial `status.location` and aliveness come from an LLM's per-fragment
`state_updates` emitted during atomization (`society/history_extract.py:745` —
`entry["location"]=loc`, `entry["alive"]=...`). This running state is unreliable: many
characters' terminal location is unresolved and falls into a bucket, and some deaths are
never recorded.

## Goal

A **reusable sedimentation-pipeline step** — not a one-off patch of one sim.yaml — that,
for every scenario (三国/红楼/俄乌/Hamlet), determines each cast character's
`{alive, location}` at the sediment boundary reliably, by reading the scenario's OWN
sedimented memories first and only falling back to the model's canon knowledge (anchored
to the boundary) when the memories don't determine it.

## Non-goals

- Effort B (messaging redesign) — separate spec.
- Changing the atomize/assign LLM logic, or the per-fragment `state_updates` tracking
  itself (it may still serve other purposes; this step supersedes it for the specific
  purpose of INITIAL sim placement/aliveness).
- Worldmap connectivity/geography redesign — this step only assigns each character an
  initial location that is a valid scenario environment id.

## Decisions (locked in brainstorming)

| topic | decision |
|---|---|
| Where it runs | A pipeline step AFTER owner-assignment (each agent's memories assigned), over the selected cast, feeding sim.yaml generation. Scenario-general. |
| Primary source | Read the character's OWN full memory timeline (all memories owned by them, sorted by `story_order` front→back) and LLM-EXTRACT `{alive, location}` from it. Data first. |
| Fallback | If the timeline doesn't determine it, fall back to the model's canon knowledge — but PROVIDE a "boundary world-state" summary as context so the model reasons about the RIGHT moment (not a vague "canonical" state). |
| Location domain | `location` must be one of the scenario's environment ids (the model chooses from the env list; an off-list answer is mapped to the nearest / flagged). |
| Dead handling | `alive=false` → `archived=true`: the character stays a registered agent that still OWNS its ch1-40 memories (recallable/readable by others) but is NEVER scheduled (`is_eligible` already excludes archived). NOT deleted. |
| Provenance | Each result records its source: `memory` or `canon@boundary`, for auditing. |

## Architecture

New module `society/boundary_state.py` (keeps the logic focused and testable), invoked by
the sim.yaml build step (after `select_cast`, before `place_carriers`).

### Inputs
- The sedimented memories (list of entries with `text`, `owners`, `meta.story_order`).
- The selected cast (character ids).
- The scenario's environment ids (valid locations) + optional display names.
- A short boundary label (e.g. "end of ch40") — descriptive only.

### Step 1 — boundary context = raw source tail (no summarization call)
Take the TAIL of the sediment SOURCE TEXT — the last few chapters/segments of the sediment
span (e.g. 三国 ~ch36-40; 俄乌 ~the events just before the 2024/04 boundary) — together with
its chapter/time markers, sliced ONCE from the source. This raw boundary text is reused
verbatim as the context for every fallback call. No separate summarization LLM call: it is
the actual canonical text at the boundary (most reliable), and the chapter/time markers
anchor the exact moment. Bound it (e.g. last 1-2 chapters, or a max-char cap) so the
context stays affordable; if the tail exceeds the cap, keep the closest-to-boundary
portion. Works for canons the model doesn't know well (俄乌, obscure works) because the
grounding is the scenario's own source text, not the model's memory.

### Step 2 — per-character finalization
`async def finalize_boundary_state(memories, cast, env_ids, *, llm, boundary_context,
env_names=None, max_mem_per_char=200) -> dict[str, dict]`
(`boundary_context` = the raw source-tail text from Step 1.)
returning `{char_id: {"alive": bool, "location": <env_id>|None, "source": "memory"|"canon@boundary"}}`.

For each `char_id` in `cast`:
1. Gather memories where `char_id in owners`, sorted by `meta.story_order` ascending
   (front→back). If more than `max_mem_per_char`, keep the LATEST `max_mem_per_char`
   (recent memories determine the "current" state; the tail is what matters).
2. **Primary (grounded) LLM call**: given this ordered timeline + the env list, extract
   STRICT JSON `{"alive": bool, "location": <env_id or "">, "determinable": bool}` —
   "based on what happens to this character in order, are they alive at the end and where
   are they; `determinable=false` if the memories don't say."
3. If `determinable` is false (or `location` empty / off-list for a living character),
   **Fallback LLM call**: provide `boundary_context` (the raw source-tail text with
   chapter/time markers) + the env list, ask the model to determine, AT THAT STORY POINT,
   `{"alive": bool, "location": <env_id>}`. Mark `source="canon@boundary"`.
4. Validate `location ∈ env_ids`; if off-list, map to the closest by name/id or leave
   `None` with a warning (a living character with no resolvable location keeps its
   pre-existing tracked location as a last resort — never crash).

Batch the per-character calls concurrently (`asyncio.gather`, bounded by the LLM client's
semaphore) so 71 characters finish in ~minutes, not sequentially.

### Step 3 — apply to sim.yaml build
- `alive=false` → mark the agent `archived: true` in the scenario (kept as an owner of its
  memories; excluded from the active roster / never eligible).
- `alive=true` → set `status.location` to the finalized `location`.
- Emit a report: per character `{alive, location, source}`, plus counts (n archived, n
  relocated, n canon-fallback).

## Data flow

```
sediment (atomize + assign owners; memories carry story_order)
        │
   select_cast (pick cast by memory threshold)
        │
   finalize_boundary_state  ← THIS STEP
     ├─ boundary context = raw source-tail text (sliced once, no LLM call)
     └─ per char: timeline → grounded extract {alive,location}
                   └─ if inconclusive → canon@boundary fallback (+ source-tail context)
        │  {char: {alive, location, source}}
        ▼
   apply: dead→archived, alive→status.location
        │
   place_carriers → sim.yaml
```

## Testing

- **Grounded extraction**: a character whose memory timeline ends in death (feed a small
  synthetic timeline ending "X 被杀") → `alive=false`, `source="memory"`. A timeline
  ending "X 在 <loc> 议事" → `alive=true, location=<loc>`.
- **Fallback**: a character with an inconclusive timeline (no death, no location) →
  `determinable=false` → fallback call fires and returns a location from the env list;
  `source="canon@boundary"`; the boundary source-tail context is present in the fallback prompt.
- **Location domain**: an off-list model answer is mapped to an env id or left None (never
  a non-env location); a living character never ends with an invalid location.
- **Apply**: `alive=false` → agent gets `archived: true` and is excluded by
  `Kernel.is_eligible` yet still returned by `shared_memory.all_entries()` as an owner;
  `alive=true` → `status.location` updated.
- **Real 三国 regression** (post-run check, not a unit test): after regenerating
  three_kingdoms.sim.yaml through this step, 何进/张让/董卓/吕布 (dead by ch40) are
  `archived`; the 河东 14-character bucket is dispersed (each placed at a plausible env);
  re-running the grounding score shows fewer canon-violation flags.
- Full suite green; the new module has its own unit tests with a FakeLLM.

## Risks / open points

- **Timeline length for principals**: 刘备/曹操 own hundreds of memories. `max_mem_per_char`
  bounds the prompt to the latest chunk; recent memories dominate "current" state, so this
  is a safe truncation (log when it triggers).
- **Extraction/fallback still LLM-judged** (flash): imperfect. Provenance + the report let
  a human spot-check key characters; a small manual override map for principals is a cheap
  future add if needed (out of scope now).
- **俄乌 / non-narrative scenarios**: "location" and "alive" may map awkwardly to a
  timeline of institutional events; the grounded-first design degrades gracefully
  (determinable=false → fallback with the boundary summary), and the env-list constraint
  keeps outputs valid.
