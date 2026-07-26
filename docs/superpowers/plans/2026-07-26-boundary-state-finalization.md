# Boundary-state Finalization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A reusable sedimentation-pipeline step that determines each cast character's `{alive, location}` at the sediment boundary — grounded first in the character's own memory timeline, falling back to the model's canon knowledge anchored to the raw boundary source-tail — then places living characters at valid scenario environments and archives the dead.

**Architecture:** A pure, LLM-driven module `society/boundary_state.py` computes `{alive, location, source}` per character (concurrent, self-limited by the LLM client's semaphore). `experiments/select_cast.py` calls it during `.sim.yaml` generation: it slices the raw boundary source-tail as context, passes the kept cast + kept env ids, then applies results (set `status.location`; add `archived: true` for the dead). The scenario loader already honors an `archived` bool and `Kernel.is_eligible` already excludes archived agents.

**Tech Stack:** Python 3.14, asyncio, `society.llm.LLMClient` (deepseek-v4-flash), `society.evaluation._parse_json` (strict-JSON parser), pytest, PyYAML. Tests use `tests.helpers.FakeLLM`.

## Global Constraints

- Do NOT modify `society/ltm.py`, `society/kernel.py`, or the atomize/assign logic in `society/history_extract.py`. This step SUPERSEDES the per-fragment `state_updates` tracking only for INITIAL sim placement/aliveness.
- `location` for a living character MUST be one of the scenario's environment ids; an off-list / unresolvable location becomes `None` (never a non-env string) and the caller keeps the character's pre-existing tracked location as a last resort.
- Dead (`alive=false`) → agent gets `archived: true` in the sim.yaml (kept as a memory owner, never scheduled) — NOT deleted from the agent list.
- Grounded-first: read the character's own memory timeline sorted by `meta.story_order` ascending; only fall back to canon when the timeline is inconclusive.
- Fallback context is the RAW boundary source-tail text (chapters/segments near the boundary + their markers), sliced once and reused verbatim — NOT a generated summary.
- Per-character LLM calls run concurrently via `asyncio.gather` (the client bounds concurrency); never a sequential 71-await loop.
- `max_mem_per_char = 200` (keep the LATEST 200 timeline memories when a character owns more).
- Tests run under the venv: `venv/bin/python -m pytest -q`. `chromadb` imports only under the venv.
- TDD; one logical change per commit.

## File Structure

- Create `society/boundary_state.py` — the finalization logic: timeline gather, grounded extraction, canon fallback, location validation, concurrent orchestration. One responsibility, no I/O, LLM injected.
- Create `tests/test_boundary_state.py` — unit tests with `FakeLLM`.
- Modify `experiments/select_cast.py` — slice the boundary source-tail (per scenario), call `finalize_boundary_state`, apply `status.location` + `archived` into the emitted `.sim.yaml`.

---

### Task 1: `boundary_state.py` — finalization module

**Files:**
- Create: `society/boundary_state.py`
- Test: `tests/test_boundary_state.py`

**Interfaces:**
- Consumes: `society.evaluation._parse_json(text, default)` (strict-JSON parse, returns `default` on failure); an injected `llm` with `async chat(prompt, system=None, bucket=...) -> str`.
- Produces:
  - `gather_timeline(memories: list[dict], char_id: str, max_mem: int = 200) -> list[str]`
  - `async finalize_boundary_state(memories: list[dict], cast: list[str], env_ids, *, llm, boundary_context: str, max_mem_per_char: int = 200) -> dict[str, dict]` returning `{char_id: {"alive": bool, "location": str|None, "source": "memory"|"canon@boundary"}}`.

- [ ] **Step 1: Write the failing test for `gather_timeline`**

```python
# tests/test_boundary_state.py
import pytest
from society.boundary_state import gather_timeline, finalize_boundary_state
from tests.helpers import FakeLLM


def _mem(text, owners, so):
    return {"text": text, "owners": owners, "meta": {"story_order": so}}


def test_gather_timeline_owned_sorted_and_capped():
    mems = [
        _mem("b", ["x"], 20), _mem("a", ["x"], 10),
        _mem("other", ["y"], 5), _mem("c", ["x", "z"], 30),
    ]
    assert gather_timeline(mems, "x") == ["a", "b", "c"]        # owned by x, story order
    assert gather_timeline(mems, "y") == ["other"]
    # cap keeps the LATEST max_mem
    big = [_mem(str(i), ["x"], i) for i in range(300)]
    tl = gather_timeline(big, "x", max_mem=200)
    assert len(tl) == 200 and tl[0] == "100" and tl[-1] == "299"
```

- [ ] **Step 2: Run to verify fail** — `venv/bin/python -m pytest tests/test_boundary_state.py -q` → FAIL (module/func missing).

- [ ] **Step 3: Implement `gather_timeline` + module skeleton**

```python
# society/boundary_state.py
"""Boundary-state finalization: for each cast character, determine {alive,
location} at the sediment boundary -- grounded first in the character's own
memory timeline, falling back to the model's canon knowledge anchored to the
raw boundary source-tail. Pure logic; the LLM is injected. See
docs/superpowers/specs/2026-07-26-boundary-state-finalization-design.md."""

import asyncio

from society.evaluation import _parse_json


def gather_timeline(memories, char_id, max_mem=200):
    """Texts of the memories owned by `char_id`, ascending by story_order.
    If more than `max_mem`, keep the LATEST `max_mem` (recent memories set the
    'current' boundary state)."""
    owned = [m for m in memories if char_id in (m.get("owners") or [])]
    owned.sort(key=lambda m: (m.get("meta", {}) or {}).get("story_order", 0))
    texts = [m["text"] for m in owned]
    if len(texts) > max_mem:
        texts = texts[-max_mem:]
    return texts


async def _extract_grounded(char_id, timeline, env_ids, llm):
    joined = "\n".join(f"- {t}" for t in timeline)
    prompt = (
        f"Below are the memories about the character '{char_id}', in narrative "
        "order (earliest first). Based ONLY on what happens to this character in "
        "these memories, determine, as of the LAST memory: is the character "
        "alive, and at which location are they?\n\n"
        f"Memories:\n{joined}\n\n"
        f"Choose location from this list of valid location ids (or \"\" if the "
        f"memories don't say): {sorted(env_ids)}\n\n"
        'Return STRICT JSON: {"alive": true/false, "location": "<location id or '
        'empty string>", "determinable": true/false}. Set determinable=false if '
        "the memories do not make the alive/location state clear. Return ONLY the JSON."
    )
    reply = await llm.chat(prompt, system=None, bucket="boundary_extract")
    return _parse_json(reply, default={"alive": True, "location": "", "determinable": False})


async def _fallback_canon(char_id, boundary_context, env_ids, llm):
    prompt = (
        "The following is the source text at the current point of a story "
        "(near the boundary of what has been narrated so far), including its "
        "chapter/time markers:\n\n"
        f"{boundary_context}\n\n"
        f"At THIS point in the story, is the character '{char_id}' alive, and at "
        "which location are they? Use your knowledge of this work anchored to "
        "the moment shown above.\n\n"
        f"Choose location from this list of valid location ids: {sorted(env_ids)}\n\n"
        'Return STRICT JSON: {"alive": true/false, "location": "<location id>"}. '
        "Return ONLY the JSON."
    )
    reply = await llm.chat(prompt, system=None, bucket="boundary_fallback")
    return _parse_json(reply, default={"alive": True, "location": ""})


async def _finalize_one(char_id, memories, env_ids, llm, boundary_context, max_mem):
    timeline = gather_timeline(memories, char_id, max_mem)
    source = "memory"
    if timeline:
        res = await _extract_grounded(char_id, timeline, env_ids, llm)
    else:
        res = {"alive": True, "location": "", "determinable": False}
    alive = bool(res.get("alive", True))
    location = res.get("location") or ""
    determinable = bool(res.get("determinable", False))
    # fall back when the timeline is inconclusive, or a living character has no
    # valid on-list location
    if (not determinable) or (alive and location not in env_ids):
        fb = await _fallback_canon(char_id, boundary_context, env_ids, llm)
        alive = bool(fb.get("alive", alive))
        location = fb.get("location") or location
        source = "canon@boundary"
    if location not in env_ids:
        location = None  # unresolved -> caller keeps prior tracked location
    return {"alive": alive, "location": location, "source": source}


async def finalize_boundary_state(memories, cast, env_ids, *, llm,
                                  boundary_context, max_mem_per_char=200):
    """For each character id in `cast`, return
    {char_id: {"alive": bool, "location": <env id>|None, "source": str}}.
    Per-character LLM work runs concurrently (the client bounds concurrency)."""
    env_ids = set(env_ids)
    results = await asyncio.gather(*[
        _finalize_one(c, memories, env_ids, llm, boundary_context, max_mem_per_char)
        for c in cast
    ])
    return dict(zip(cast, results))
```

- [ ] **Step 4: Run to verify `gather_timeline` passes** — `venv/bin/python -m pytest tests/test_boundary_state.py::test_gather_timeline_owned_sorted_and_capped -q` → PASS.

- [ ] **Step 5: Write failing tests for grounded / fallback / validation paths**

```python
# tests/test_boundary_state.py (append)

async def test_grounded_death_from_timeline():
    mems = [_mem("何进入宫", ["hejin"], 1), _mem("何进被十常侍所杀", ["hejin"], 2)]
    llm = FakeLLM(fn=lambda p, s=None: '{"alive": false, "location": "", "determinable": true}')
    out = await finalize_boundary_state(mems, ["hejin"], {"luoyang"}, llm=llm, boundary_context="ctx")
    assert out["hejin"]["alive"] is False and out["hejin"]["source"] == "memory"


async def test_grounded_location_from_timeline():
    mems = [_mem("曹操在许昌议事", ["caocao"], 5)]
    llm = FakeLLM(fn=lambda p, s=None: '{"alive": true, "location": "xuchang", "determinable": true}')
    out = await finalize_boundary_state(mems, ["caocao"], {"xuchang", "luoyang"}, llm=llm, boundary_context="ctx")
    assert out["caocao"] == {"alive": True, "location": "xuchang", "source": "memory"}


async def test_inconclusive_timeline_triggers_canon_fallback():
    mems = [_mem("某无关记忆", ["liubei"], 1)]
    def fn(prompt, system=None):
        if "determinable" in prompt:               # grounded call
            return '{"alive": true, "location": "", "determinable": false}'
        return '{"alive": true, "location": "xinye"}'  # fallback call
    out = await finalize_boundary_state(mems, ["liubei"], {"xinye"}, llm=FakeLLM(fn=fn), boundary_context="第40回 …")
    assert out["liubei"] == {"alive": True, "location": "xinye", "source": "canon@boundary"}


async def test_off_list_location_becomes_none():
    mems = [_mem("x", ["a"], 1)]
    def fn(prompt, system=None):
        if "determinable" in prompt:
            return '{"alive": true, "location": "nowhere", "determinable": true}'
        return '{"alive": true, "location": "stillnowhere"}'   # fallback also off-list
    out = await finalize_boundary_state(mems, ["a"], {"xuchang"}, llm=FakeLLM(fn=fn), boundary_context="ctx")
    assert out["a"]["location"] is None and out["a"]["alive"] is True


async def test_no_timeline_goes_straight_to_fallback():
    def fn(prompt, system=None):
        return '{"alive": true, "location": "jiangdong"}'
    out = await finalize_boundary_state([], ["sunquan"], {"jiangdong"}, llm=FakeLLM(fn=fn), boundary_context="ctx")
    assert out["sunquan"]["source"] == "canon@boundary" and out["sunquan"]["location"] == "jiangdong"
```

- [ ] **Step 6: Run to verify all pass** — `venv/bin/python -m pytest tests/test_boundary_state.py -q` → PASS (all). (The implementation from Step 3 already covers these paths.)

- [ ] **Step 7: Commit**

```bash
git add society/boundary_state.py tests/test_boundary_state.py
git commit -m "feat(boundary): finalize {alive,location} from memory timeline + canon fallback"
```

---

### Task 2: Integrate into `select_cast` (place living, archive dead)

**Files:**
- Modify: `experiments/select_cast.py`
- Test: `tests/test_boundary_state.py` (add an integration test of the apply logic)

**Interfaces:**
- Consumes: `finalize_boundary_state(...)` from Task 1; `society.history_extract._split_by_chapters(text) -> list[str]`; `society.run._build_llm_and_embed(config_path) -> (llm, embed_fn)`.
- Produces: `apply_boundary_state(agents: list[dict], keep_char: set[str], finalized: dict[str, dict]) -> dict` (mutates agent dicts in place: sets `status.location` for living, `archived=True` for dead; returns counts). Plus a `boundary_source_tail(name) -> str` helper in `select_cast`.

- [ ] **Step 1: Write the failing test for `apply_boundary_state`**

```python
# tests/test_boundary_state.py (append)
from experiments.select_cast import apply_boundary_state


def test_apply_sets_location_and_archives_dead():
    agents = [
        {"id": "caocao", "kind": "character", "status": {"location": "hedong"}},
        {"id": "hejin", "kind": "character", "status": {"location": "hedong"}},
        {"id": "liubei", "kind": "character", "status": {"location": "xinye"}},
        {"id": "xuchang", "kind": "environment"},
    ]
    finalized = {
        "caocao": {"alive": True, "location": "xuchang", "source": "memory"},
        "hejin": {"alive": False, "location": None, "source": "memory"},
        "liubei": {"alive": True, "location": None, "source": "canon@boundary"},  # unresolved -> keep prior
    }
    counts = apply_boundary_state(agents, {"caocao", "hejin", "liubei"}, finalized)
    byid = {a["id"]: a for a in agents}
    assert byid["caocao"]["status"]["location"] == "xuchang"      # relocated
    assert byid["hejin"].get("archived") is True                 # dead archived
    assert byid["liubei"]["status"]["location"] == "xinye"       # unresolved -> unchanged
    assert counts["archived"] == 1 and counts["relocated"] == 1
```

- [ ] **Step 2: Run to verify fail** — `venv/bin/python -m pytest tests/test_boundary_state.py::test_apply_sets_location_and_archives_dead -q` → FAIL (func missing).

- [ ] **Step 3: Implement `apply_boundary_state` + `boundary_source_tail` + wire into `curate`**

Add to `experiments/select_cast.py` (imports at top: `from society.boundary_state import finalize_boundary_state`, `from society.history_extract import _split_by_chapters`):

```python
# how many trailing chapters/segments of the sediment span form the boundary
# context, and the sediment chapter count per scenario (mirrors sediment_all.py)
_SEDIMENT_CHAPTERS = {"three_kingdoms": 40, "red_chamber": 40}
_BOUNDARY_TAIL_CHAPTERS = 2
_SOURCE_FILES = {
    "three_kingdoms": ["three_kingdoms_ch01-10.txt", "three_kingdoms_ch11-60.txt"],
    "red_chamber": ["red_chamber.txt"],
}


def boundary_source_tail(name):
    """Raw source text of the last `_BOUNDARY_TAIL_CHAPTERS` chapters of the
    sediment span (with their chapter markers), reused as fallback context.
    Returns "" for scenarios whose source isn't chapter-sliceable here (callers
    then rely on the grounded path + an empty context)."""
    files = _SOURCE_FILES.get(name)
    n = _SEDIMENT_CHAPTERS.get(name)
    if not files or n is None:
        return ""
    src_dir = os.path.join(BASE, "scenarios", "sources")
    text = "\n".join(open(os.path.join(src_dir, f), encoding="utf-8").read() for f in files)
    chs = _split_by_chapters(text)
    if not chs:
        return ""
    tail = chs[max(0, n - _BOUNDARY_TAIL_CHAPTERS):n]
    return "".join(tail)


def apply_boundary_state(agents, keep_char, finalized):
    """Mutate agent dicts: living -> status.location (when resolved); dead ->
    archived=True. Returns {"archived": int, "relocated": int, "canon": int}."""
    counts = {"archived": 0, "relocated": 0, "canon": 0}
    for a in agents:
        if a.get("kind") != "character" or a["id"] not in keep_char:
            continue
        fin = finalized.get(a["id"])
        if not fin:
            continue
        if fin.get("source") == "canon@boundary":
            counts["canon"] += 1
        if not fin.get("alive", True):
            a["archived"] = True
            counts["archived"] += 1
            continue
        loc = fin.get("location")
        if loc:  # resolved on-list location; otherwise keep the pre-existing one
            st = a.setdefault("status", {})
            if st.get("location") != loc:
                counts["relocated"] += 1
            st["location"] = loc
    return counts
```

Then in `curate(name, T)`, AFTER `keep_char` is computed and BEFORE the env-trim block (`active_locations` must reflect the corrected locations), insert:

```python
    # Boundary-state finalization: place living cast at canonical boundary
    # locations, archive characters dead by the boundary. Grounded in each
    # character's memory timeline; canon fallback anchored to the source tail.
    import asyncio
    from society.run import _build_llm_and_embed
    llm, _embed = _build_llm_and_embed(os.path.join(BASE, "config_flash.json"))
    finalized = asyncio.run(finalize_boundary_state(
        ltm, sorted(keep_char), env_ids,
        llm=llm, boundary_context=boundary_source_tail(name),
    ))
    bcounts = apply_boundary_state(agents, keep_char, finalized)
    # a character archived as dead should not count as active cast
    keep_char = {c for c in keep_char
                 if not any(a["id"] == c and a.get("archived") for a in agents)}
```

(`env_ids` is already computed above as `{a["id"] for a in agents if a.get("kind")=="environment"}`; ensure that line runs before this block — it currently does.)

Add `bcounts` to the returned dict: `"archived": bcounts["archived"], "relocated": bcounts["relocated"], "canon_fallback": bcounts["canon"]`.

- [ ] **Step 4: Run the apply test** — `venv/bin/python -m pytest tests/test_boundary_state.py -q` → PASS.

- [ ] **Step 5: Run full suite** — `venv/bin/python -m pytest -q` → all green.

- [ ] **Step 6: Commit**

```bash
git add experiments/select_cast.py tests/test_boundary_state.py
git commit -m "feat(select_cast): finalize boundary state -> place living, archive dead"
```

---

### Task 3: Regenerate 三国 sim.yaml + verify (execution, no unit test)

**Files:** none (runs the pipeline; regenerates `scenarios/three_kingdoms.sim.yaml`).

- [ ] **Step 1: Regenerate** — `venv/bin/python -m experiments.select_cast three_kingdoms` (uses `config_flash.json`). Expect the printed JSON to include nonzero `archived` and `relocated`.
- [ ] **Step 2: Verify archived dead** — confirm 何进/张让/董卓/吕布 (dead by ch40) now have `archived: true` in `scenarios/three_kingdoms.sim.yaml`:
  `venv/bin/python -c "import yaml;d=yaml.safe_load(open('scenarios/three_kingdoms.sim.yaml'));print([a['id'] for a in d['agents'] if a.get('archived')])"`
- [ ] **Step 3: Verify 河东 dispersed** — the `hedong` bucket should no longer hold 14 unrelated living characters; print per-location active counts and confirm cross-faction dumping is gone.
- [ ] **Step 4 (optional, run):** re-run `experiments/score_grounding.py` on a fresh 三国 consensus sim built from the corrected sim.yaml and confirm fewer canon-violation flags than the pre-fix 0.72. (Requires re-running the sim first — coordinate with the matrix runs; not part of this plan's code.)

---

## Self-Review

- **Spec coverage:** pipeline step after cast selection → Task 2 (`curate`); grounded-first timeline extraction → Task 1 `_extract_grounded`; canon fallback with raw source-tail → Task 1 `_fallback_canon` + Task 2 `boundary_source_tail`; location ∈ env ids / off-list → None → Task 1 validation + tests; dead → archived (kept owner) → Task 2 `apply_boundary_state` + loader already honors `archived`; concurrency → `asyncio.gather` in `finalize_boundary_state`; `max_mem_per_char=200` → `gather_timeline`; provenance `memory`/`canon@boundary` → returned per char; 三国 regression → Task 3. Covered.
- **Placeholders:** none — every code step is complete; Task 3 is execution with exact commands.
- **Type consistency:** `finalize_boundary_state` returns `{char: {"alive","location","source"}}` consumed unchanged by `apply_boundary_state`; `gather_timeline` returns `list[str]` used by `_extract_grounded`; `boundary_context` is a `str` throughout; `env_ids` a set of str.
- **Scope:** Effort A only (Effort B / messaging redesign is a separate spec). Other scenarios (红楼/俄乌/Hamlet) get correct behavior via the same module; `boundary_source_tail` currently slices 三国/红楼 by chapter and returns "" (grounded-only) for non-chapter sources — extending it to 俄乌/Hamlet source formats is a follow-up, out of this plan's 三国-first scope.
