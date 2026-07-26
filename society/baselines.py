"""Faithful baseline memory backends for comparison against `society.ltm.SharedMemory`.

Each class here is a drop-in, duck-typed replacement for `SharedMemory`: same
constructor keyword shape, same `remember`/`recall`/`forget`/`revise`/
`all_entries`/`export`/`restore`/`stats` methods and return shapes. None of
them get our normalize gate or consensus merge -- that machinery is the
contribution under test, so giving it to a baseline would invalidate the
comparison. Each baseline stores its rows in its own ChromaDB collection
(via the `ChromaRows` helper in `society/baseline_store.py`), keeping the
organization rule that distinguishes it (per-owner duplication, a single
shared graph, or ACL-gated fragments -- see each class's docstring);
ranking is cosine similarity computed by Chroma's HNSW index over the
embeddings returned by `embed_fn` (`GenerativeAgentsMemory` additionally
re-ranks the retrieved candidates with its recency+importance+relevance
score).

`make_memory(kind, embed_fn, llm=None, **kw)` is the factory experiment
runners should call to select a backend by name.
"""

import asyncio
import math
import re
import uuid
from datetime import datetime, timezone

from society.baseline_store import ChromaRows, dumps_meta, loads_meta
from society.gmemory_graph import INSIGHT, INTERACTION, GraphIndex, distill_prompt
from society.ltm import SharedMemory

_DEFAULT_IMPORTANCE = 5

# Generative Agents (Park et al. 2023) reflection trigger: the paper fires a
# reflection pass once the SUM of importance scores of memories deposited
# since the last reflection crosses this threshold (paper: ~150 on the 1-10
# importance scale). Overridable per-instance via the `reflection_threshold`
# constructor kwarg (e.g. tests use a small value to exercise the trigger
# without depositing 150+ points of importance).
REFLECTION_THRESHOLD = 150

# Max number of reflections fired while PRIMING the sediment (a whole story's
# worth of memories at once would otherwise fire ~hundreds of sequential
# LLM-bearing reflections -- ~48 min on the 三国 sediment). Priming is a
# one-time init, so it is capped: the reflection tree is still built (the
# mechanism runs), just bounded to a reasonable size. Does NOT affect
# sim-time reflection, which is uncapped. Overridable via the
# `prime_reflection_budget` constructor kwarg.
PRIME_REFLECTION_BUDGET = 40

# How many of the most-recently-touched rows in the WHOLE store (across all
# owners -- `GenerativeAgentsMemory` is one shared instance whose rows are
# scoped per owner by metadata, not one instance per agent, so the
# reflection accumulator and this recency window are store-wide too) are
# handed to the LLM as "recent memories" context for question generation.
# Selection key: (tick, last_access) descending -- `tick` is the caller-
# supplied simulation step (coarse, matches the paper's narrative ordering)
# with `last_access` (the monotonic access-tick counter) as a tiebreaker for
# rows sharing a tick, since it strictly increases with every store write.
REFLECTION_RECENT_N = 30

# Max number of high-level questions the LLM is asked to generate per
# reflection pass (paper: "salient high-level questions... about the
# subjects"), and the number of candidate rows retrieved as evidence for
# each question.
REFLECTION_QUESTIONS = 3
REFLECTION_EVIDENCE_K = 5


def reflection_questions_prompt(recent_texts: list[str]) -> str:
    """Build the LLM prompt used by `GenerativeAgentsMemory._reflect` to ask
    for the top salient high-level questions given a batch of recent
    memory-stream texts (Park et al. 2023, reflection step 1)."""
    bullets = "\n".join(f"- {t}" for t in recent_texts)
    return (
        "Given only the statements below, what are the "
        f"{REFLECTION_QUESTIONS} most salient high-level questions we can "
        "answer about the subjects in the statements?\n\n"
        f"{bullets}\n\n"
        "Respond with one question per line, no numbering, no preamble."
    )


def reflection_synthesis_prompt(question: str, evidence_texts: list[str]) -> str:
    """Build the LLM prompt used by `GenerativeAgentsMemory._reflect` to
    synthesize ONE reflection statement answering `question` from its
    retrieved evidence memories (Park et al. 2023, reflection step 2)."""
    bullets = "\n".join(f"- {t}" for t in evidence_texts)
    return (
        "You are synthesizing a higher-level reflection for an agent's "
        "memory stream.\n\n"
        f"Question: {question}\n\n"
        "Relevant memories:\n"
        f"{bullets}\n\n"
        "Write ONE concise sentence that answers the question with the "
        "insight or conclusion drawn from these memories. Respond with "
        "only that sentence, no preamble."
    )


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
    Reflection tree: implemented -- an importance accumulator
    (`_deposit_importance`/`_maybe_reflect`) triggers `_reflect` once
    deposited importance crosses `_reflection_threshold`, which asks the LLM
    for salient high-level questions over recent memories, retrieves
    per-question evidence, and stores each synthesized reflection
    (`_store_reflection`) as a new stream entry linked back to its evidence.

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

    def __init__(
        self,
        embed_fn,
        llm=None,
        *,
        top_k: int = 5,
        collection_name=None,
        reflection_threshold: int | None = None,
        prime_reflection_budget: int | None = None,
        **kwargs,
    ):
        self._embed_fn = embed_fn
        self._llm = llm
        self._store = ChromaRows(embed_fn, collection_name=collection_name)
        self._clock = 0  # monotonic access-tick counter
        self._prime_reflection_budget = (
            PRIME_REFLECTION_BUDGET
            if prime_reflection_budget is None
            else prime_reflection_budget
        )
        # Reflection trigger state (Task 9). `_importance_since_reflection`
        # accumulates one deposit's worth of importance per logical
        # `remember`/`remember_atomic` call (NOT once per per-owner row --
        # see `_deposit_importance`). `_reflect` itself is a placeholder
        # here; Task 10 fills in the actual reflection synthesis.
        self._importance_since_reflection = 0.0
        self._reflection_threshold = (
            REFLECTION_THRESHOLD if reflection_threshold is None else reflection_threshold
        )

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

    async def _deposit_importance(self, importance: float) -> None:
        """Feed one logical deposit's importance into the reflection
        accumulator and check the trigger.

        Called exactly ONCE per public `remember`/`remember_atomic` call --
        even when that call fans out into several per-owner rows -- so a
        3-owner memory contributes its importance once, not 3x. Internal
        reflection-storage paths (added in Task 10's `_store_reflection`)
        must NOT call this, to avoid a reflection's own deposit re-feeding
        (and recursively re-triggering) the accumulator.
        """
        self._importance_since_reflection += importance
        await self._maybe_reflect()

    async def _maybe_reflect(self) -> None:
        """If the accumulator has crossed the threshold, reset it and run a
        reflection pass. Resetting BEFORE calling `_reflect` (rather than
        after) means `_reflect`'s own memory deposits -- if it made any
        through the public path -- would start a fresh accumulation instead
        of being folded into the crossing that triggered them; combined with
        `_reflect` not being called from `_deposit_importance`, this keeps
        one crossing -> one `_reflect` call, with no re-trigger loop.
        """
        if self._importance_since_reflection >= self._reflection_threshold:
            self._importance_since_reflection = 0.0
            await self._reflect()

    async def _reflect(self) -> None:
        """Generative Agents (Park et al. 2023) reflection synthesis.

        Runs once per crossing of `_reflection_threshold` (called by
        `_maybe_reflect`, which has already reset the accumulator):

        1. Pull the `REFLECTION_RECENT_N` most-recently-touched rows across
           the WHOLE store (see `REFLECTION_RECENT_N`'s docstring on why
           this is store-wide, not per-owner) as "recent memories" context.
        2. Ask the LLM for up to `REFLECTION_QUESTIONS` salient high-level
           questions given those recent memories.
        3. For each question, retrieve `REFLECTION_EVIDENCE_K` candidate
           rows from the store as evidence (a plain relevance query over
           the whole store -- reflection evidence is not owner-scoped
           either, since the "recent memories" it questions weren't).
        4. Ask the LLM to synthesize ONE reflection sentence answering the
           question from that evidence, then store it via
           `_store_reflection` (which fans the row out per evidence owner
           and does NOT feed the importance accumulator).

        No-ops (never raises) when: there is no LLM configured, the store
        is empty, the LLM returns no parseable questions for a given pass,
        a question's evidence query comes back empty, no evidence row
        carries an owner, or a question's synthesized reflection text is
        empty/whitespace -- that question is simply skipped, the rest of
        the pass proceeds.
        """
        if self._llm is None:
            return

        rows = self._store.all_rows()
        if not rows:
            return

        def _recency_key(row):
            meta = row["metadata"]
            return (
                int(meta.get("tick", 0) or 0),
                int(meta.get("last_access", 0) or 0),
            )

        recent_rows = sorted(rows, key=_recency_key, reverse=True)[:REFLECTION_RECENT_N]
        recent_texts = [r["text"] for r in recent_rows]

        raw_questions = await self._llm.chat(
            reflection_questions_prompt(recent_texts), bucket="reflection_questions"
        )
        questions = [q.strip(" \t-") for q in (raw_questions or "").splitlines()]
        questions = [q for q in questions if q][:REFLECTION_QUESTIONS]
        if not questions:
            return

        for question in questions:
            evidence = await self._store.query(question, REFLECTION_EVIDENCE_K)
            if not evidence:
                continue
            evidence_ids = [cand["id"] for cand in evidence]
            evidence_texts = [cand["text"] for cand in evidence]
            owners = sorted(
                {
                    cand["metadata"].get("owner")
                    for cand in evidence
                    if cand["metadata"].get("owner")
                }
            )
            if not owners:
                continue

            reflection_text = await self._llm.chat(
                reflection_synthesis_prompt(question, evidence_texts),
                bucket="reflection_synthesis",
            )
            reflection_text = (reflection_text or "").strip()
            if not reflection_text:
                continue

            await self._store_reflection(reflection_text, owners, evidence_ids)

    async def _store_reflection(self, text: str, owners: list[str], evidence_ids: list[str]) -> None:
        """Store one synthesized reflection as new memory-stream row(s).

        Mirrors `remember_atomic`'s per-owner fan-out (ONE row per owner in
        `owners`), so `recall_of(owner_id, ...)` -- which scopes candidates
        to `owner == owner_id` -- surfaces the reflection for every agent
        whose evidence contributed to it, matching the paper's model of
        reflections as higher-level entries living in the same per-agent
        stream as everything else. `owners` here is the union of the
        evidence rows' owners (passed in by `_reflect`), not the reflecting
        agent's own id -- there is no single "reflecting agent" in this
        shared-instance store (see `REFLECTION_RECENT_N`'s docstring).

        CRUCIAL: unlike `remember`/`remember_atomic`, this does NOT call
        `_deposit_importance`. `_deposit_importance` is the only path that
        feeds `_importance_since_reflection` (see its docstring) and is
        called exclusively from the public remember* methods; a reflection
        is produced internally by `_reflect` itself; feeding a reflection's
        importance back into the accumulator would let a reflection pass
        re-trigger (or partially fund) the next one, an unbounded internal
        feedback loop the paper's mechanism does not have. Skipping it here
        is what keeps "one threshold crossing -> one `_reflect` call" true.
        """
        text = (text or "").strip()
        if not text or not owners:
            return

        embedding = (await self._embed_fn([text]))[0]
        importance = await self._score_importance(text)
        affiliated = dumps_meta(sorted(set(evidence_ids)))
        for owner in owners:
            row_id = uuid.uuid4().hex
            self._clock += 1
            metadata = {
                "owner": owner,
                "affiliated": affiliated,
                "created_at": _now_iso(),
                "source": "reflection",
                "kind": "reflection",
                "tick": 0,
                "importance": importance,
                "last_access": self._clock,
            }
            await self._store.add(row_id, text, embedding, metadata)

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
        # One logical deposit -> one accumulator update, regardless of how
        # many per-owner rows were written above.
        await self._deposit_importance(importance)
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
        # One logical deposit -> one accumulator update, regardless of how
        # many per-owner rows were written above (avoids tripling the
        # accumulator for a 3-owner memory).
        await self._deposit_importance(importance)
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

    async def prime_initial_state(self) -> None:
        """Fire this backend's own higher-level mechanism (importance
        scoring + reflection) over rows a fast `restore()` just loaded from
        a holographic sediment dump -- called once by
        `society.scenario.build_society` right after `restore()`, kept out
        of `restore()` itself because doing this inline/sequentially over
        thousands of entries is prohibitively slow (measured 2.5+ hours for
        a full sediment via one `remember_atomic` await per entry).

        No-op if no LLM is configured (some tests construct instances
        without one; `restore()` still works for those, just without a
        higher-level mechanism to prime).

        1. Importance scoring: `_score_importance` is a pure function of
           TEXT (see its docstring), and a multi-owner event is stored as
           several per-owner rows sharing identical text (this backend's
           per-owner duplication, see the class docstring) -- so every
           UNIQUE text is scored exactly once, concurrently
           (`asyncio.gather`, self-limited by the LLM client's own
           semaphore -- see `society.llm.LLMClient`), rather than once per
           row (which would re-score, and re-pay LLM cost for, the same
           text N times for an N-owner event). Every row's `importance`
           metadata is then updated to its text's score.
        2. Reflection replay: the reflection trigger
           (`_deposit_importance`/`_maybe_reflect`) is inherently ORDERED
           (it is exactly the running accumulator `remember`/
           `remember_atomic` would have fed at runtime) and each `_reflect`
           it may trigger makes its own sequential LLM calls -- so this
           step is NOT concurrent, it replays the SAME accumulator path
           unchanged, in story order, ONCE PER LOGICAL EVENT (grouped by
           `meta.story_order`, not once per per-owner row -- exactly
           mirroring how `remember_atomic` deposits a multi-owner event's
           importance once, see `_deposit_importance`'s docstring).
           Reflections created along the way go through the same
           `_reflect`/`_store_reflection` as a live run, and (per
           `_store_reflection`'s contract) do not themselves feed the
           accumulator.
        """
        if self._llm is None:
            return

        rows = self._store.all_rows()
        if not rows:
            return

        # -- Step 1: importance, once per unique text, concurrently. --
        unique_texts = sorted({r["text"] for r in rows})
        scores = await asyncio.gather(*[self._score_importance(t) for t in unique_texts])
        score_by_text = dict(zip(unique_texts, scores))

        for row in rows:
            new_meta = dict(row["metadata"])
            new_meta["importance"] = score_by_text[row["text"]]
            self._store.update_metadata(row["id"], new_meta)

        # -- Step 2: reflection replay, once per logical event, in story
        # order. A logical event = all per-owner rows sharing the same text
        # (a k-owner sediment event is stored as k rows), so importance is
        # deposited ONCE per event, not once per owner row. Key by
        # story_order when present; fall back to the row TEXT (not the row
        # id) so multi-owner rows of a story_order-less event still collapse
        # to one event rather than double-counting importance per owner. --
        events: dict = {}  # story_order (or fallback: text) -> text
        for row in rows:
            so = row["metadata"].get("story_order")
            key = so if so is not None else row["text"]
            events.setdefault(key, row["text"])

        def _order_key(item):
            key, _text = item
            if isinstance(key, (int, float)):
                return (0, key, "")
            return (1, 0, str(key))

        # Priming a whole story's sediment at once would fire hundreds of
        # sequential (LLM-bearing) reflections. Cap it: keep depositing
        # importance in story order so reflections fire via the real path,
        # but stop once `_prime_reflection_budget` reflections have fired --
        # the reflection tree exists (mechanism ran), bounded to a sane size.
        # A reflection is detected by the accumulator resetting on a deposit.
        reflections_fired = 0
        for _key, text in sorted(events.items(), key=_order_key):
            importance = score_by_text.get(text, _DEFAULT_IMPORTANCE)
            before = self._importance_since_reflection
            await self._deposit_importance(importance)
            if self._importance_since_reflection != before + importance:
                # accumulator did not simply grow -> _maybe_reflect reset it,
                # i.e. a reflection fired this step
                reflections_fired += 1
                if reflections_fired >= self._prime_reflection_budget:
                    break
        # Note: the sub-threshold remainder in `_importance_since_reflection`
        # is intentionally left to carry into the sim (matches how a
        # continuous run would accumulate), same as the uncapped path.

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
    `remember` observations, "insight" for LLM-distilled summaries, "query"
    reserved but unused -- see below) mirroring the paper's
    insight/query/interaction hierarchy. Plain `remember`/`remember_atomic`
    populate only the "interaction" tier; the paper's higher tier is
    produced by a separate, implemented distillation pass (`maybe_distill`,
    triggered every `_distill_every` new interactions) that summarizes
    pending interactions into one LLM-synthesized "insight" row linked back
    to its source interactions via `derived_from` provenance edges, and
    `recall`/`recall_of` perform the paper's bi-level graph-aware retrieval
    over both tiers (see "Retrieval note" below). The "query" tier is a
    defined constant (`society.gmemory_graph.QUERY`) that is never written
    or read here -- bi-level retrieval seeds its graph traversal from
    insight/interaction hits, not from a query node. No dedup: the full
    observation text is stored verbatim, appended every call even if a
    prior call stored identical text.

    Per-owner storage (deliberate deviation from the paper for a fair
    baseline comparison): `remember_atomic(owners, text, ...)` writes ONE
    ROW PER OWNER (each single-owner), not one shared multi-owner row --
    since this baseline (like `CollaborativeMemory`) has no cross-agent
    equivalence merge of its own, faithfully letting every agent that knows
    an event keep its own record is what "as if that agent had simulated
    the story itself" requires; collapsing multiple owners onto one row
    would instead give this baseline a merge it never earns. `remember`
    (single owner) was already one row per call and is unaffected. The
    STORE (the Chroma collection) is still shared across every agent --
    `recall`'s default `owner_scope=False` reads across all owners' rows --
    only per-ENTRY ownership is now per-owner; that is the axis the paper's
    "single shared graph" design choice above is actually about.
    `maybe_distill`'s synthesized "insight" rows remain genuinely
    multi-owner (the union of their source interactions' owners), since
    they are not per-owner duplicated by this fan-out. `stats()`'s `shared`
    counts rows whose owner set has length >=2; under plain runtime
    `remember`/`remember_atomic` that is now ~0 (rows are single-owner),
    with any nonzero count coming from distilled insight rows -- that is the
    faithful, expected reading, not a bug.

    Storage note: rows live in a `ChromaRows` collection SHARED across every
    agent (one Chroma record per owner per `remember`/`remember_atomic`
    call). Chroma metadata values must be scalars, so each row's owner set
    is stored TWICE: once as a JSON-encoded `owners` list (`dumps_meta`/
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
        """ONE ROW PER OWNER -- per-owner duplication, mirroring
        `GenerativeAgentsMemory.remember_atomic`. None of the three
        baselines implement the consensus store's cross-agent equivalence
        merge, so faithfully modeling "each agent that knows an event keeps
        its own record" means every owner in `owners` gets its own
        single-owner row, embedded/tagged identically. Since rows are no
        longer multi-owner under normal writes, `stats().shared` stays ~0
        here too (see the class docstring)."""
        text = text.strip()
        if not text:
            return None
        if not owners:
            raise ValueError("remember_atomic requires at least one owner")

        embedding = (await self._embed_fn([text]))[0]
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
        seed_affiliated = sorted(set(affiliated or []))
        first_id = None
        for owner in owners:
            row_id = uuid.uuid4().hex
            if first_id is None:
                first_id = row_id
            row_affiliated = sorted(a for a in seed_affiliated if a != row_id)
            metadata = self._build_meta([owner], row_affiliated, meta)
            await self._store.add(row_id, text, embedding, metadata)
            await self._track_new_interaction(row_id)
        return {"id": first_id, "text": text, "merged": False, "owners": list(owners)}

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
            owners = entry.get("owners") or [None]
            affiliated = list(entry.get("affiliated", []))
            meta = dict(entry.get("meta", {}) or {})
            meta.setdefault("tier", INTERACTION)
            embedding = entry.get("embedding") or computed[i]

            # A multi-owner entry (e.g. a consensus-merged dump from
            # `society.ltm.SharedMemory`) restored into this PER-OWNER
            # backend becomes one owned row per owner -- mirrors
            # `GenerativeAgentsMemory.restore`'s fan-out. The first owner
            # keeps the entry's original id; additional owners get a fresh
            # row id since two rows can never share one id in this store.
            for idx, owner in enumerate(owners):
                row_id = entry["id"] if idx == 0 else uuid.uuid4().hex
                metadata = self._build_meta([owner], affiliated, meta)
                await self._store.add(row_id, entry["text"], list(embedding), metadata)

    async def prime_initial_state(self) -> None:
        """Fire this backend's own higher-level mechanism (post-task
        distillation into `insight` nodes + `derived_from` provenance
        edges) over the `interaction`-tier rows a fast `restore()` just
        loaded from a holographic sediment dump -- called once by
        `society.scenario.build_society` right after `restore()`, kept out
        of `restore()` itself because doing this inline/sequentially (one
        `remember`-triggered `maybe_distill` per `_distill_every`
        interactions, each a sequential `llm.chat` + `embed_fn` await) is
        prohibitively slow over thousands of entries (measured 2.5+ hours
        for a full sediment).

        No-op if no LLM is configured (mirrors `maybe_distill`).

        1. Collect the restored `interaction`-tier rows, ordered by
           `meta.story_order` (fallback: each row lacking `story_order`
           sorts after every row that has one, in a stable but otherwise
           unspecified relative order) -- restore() writes rows in
           whatever order the dump/`all_rows()` gives, not necessarily
           story order, so this re-establishes it before batching.
        2. Partition into consecutive batches of `_distill_every` (the same
           batch size `maybe_distill` would have accumulated to at
           sim-time; the last batch may be smaller).
        3. Ask the LLM for one insight per batch, CONCURRENTLY
           (`asyncio.gather`, self-limited by the LLM client's own
           semaphore) -- this is the 6000-sequential-awaits-vs-concurrent
           difference the priming step exists to fix. Batches whose
           insight text comes back empty/whitespace are skipped (mirrors
           `maybe_distill`).
        4. Batch-embed every surviving insight text in ONE `embed_fn` call
           (rather than one call per insight).
        5. For each surviving insight, write its `insight`-tier row +
           `derived_from` edges via `_store_insight` -- the exact same
           helper `maybe_distill` uses, so the two paths can never diverge
           on what an insight row/edge set looks like.
        6. Reset `_pending_interactions` so a subsequent sim-time
           `remember`-triggered `maybe_distill` starts counting cleanly
           from zero (restore() itself never appends to it, but this makes
           the post-condition explicit rather than relying on that).
        """
        if self._llm is None:
            return

        interaction_rows = [
            r for r in self._store.all_rows() if r["metadata"].get("tier") == INTERACTION
        ]
        if not interaction_rows:
            self._pending_interactions = []
            return

        def _order_key(item):
            idx, row = item
            so = row["metadata"].get("story_order")
            if isinstance(so, (int, float)):
                return (0, so, idx)
            return (1, 0, idx)

        ordered = [row for _, row in sorted(enumerate(interaction_rows), key=_order_key)]

        batch_size = self._distill_every
        batches = [ordered[i : i + batch_size] for i in range(0, len(ordered), batch_size)]

        raw_insights = await asyncio.gather(
            *[
                self._llm.chat(distill_prompt([row["text"] for row in batch]), bucket="distill")
                for batch in batches
            ]
        )

        surviving: list[tuple[str, set[str], list[str]]] = []
        for batch, raw in zip(batches, raw_insights):
            insight_text = (raw or "").strip()
            if not insight_text:
                continue
            owners_union: set[str] = set()
            source_ids: list[str] = []
            for row in batch:
                owners, _affiliated, _meta = self._split_meta(row["metadata"])
                owners_union.update(owners)
                source_ids.append(row["id"])
            surviving.append((insight_text, owners_union, source_ids))

        if surviving:
            embeddings = await self._embed_fn([text for text, _, _ in surviving])
            for (insight_text, owners_union, source_ids), embedding in zip(
                surviving, embeddings
            ):
                await self._store_insight(insight_text, list(embedding), owners_union, source_ids)

        self._pending_interactions = []

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
        return await self._store_insight(insight_text, embedding, owners_union, source_ids)

    async def _store_insight(
        self,
        insight_text: str,
        embedding: list[float],
        owners_union: set[str],
        source_ids: list[str],
    ) -> dict:
        """Write one distilled `insight`-tier row (owners = union of its
        source interactions' owners) and its `derived_from` provenance
        edges to each source interaction id -- the exact insight-creation +
        edge logic shared by `maybe_distill` (sim-time, one batch, one
        `embed_fn` call) and `prime_initial_state` (restore-time, many
        batches, embeddings computed in a shared batch call up front) so
        the two paths can never diverge on what an insight row/edge set
        looks like."""
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
    fragment text: two agents writing identical text produce separate
    fragments. `grant(memory_id, agent_id)` extends a fragment's ACL (the
    paper's sharing/delegation primitive) and is the only way `stats()`'s
    `shared` (ACL size >= 2) becomes nonzero -- under plain runtime
    `remember`/`remember_atomic` calls every fragment's ACL starts
    single-member, so `shared` ~0 until an explicit grant, which is
    documented as expected rather than a gap. `forget(agent_id, id)` mirrors
    `SharedMemory.forget`: it revokes read access for `agent_id` and deletes
    the fragment once its ACL is empty.

    Per-owner storage (deliberate deviation from the paper for a fair
    baseline comparison): `remember_atomic(owners, text, ...)` writes ONE
    FRAGMENT PER OWNER, each with a single-member ACL, not one fragment
    shared-ACL'd to every owner -- since this baseline (like `GMemory`) has
    no cross-agent equivalence merge of its own, faithfully letting every
    agent that knows an event keep its own readable copy is what "as if
    that agent had simulated the story itself" requires; collapsing
    multiple owners onto one shared-ACL fragment would instead give this
    baseline a merge it never earns. `remember` (single owner) was already
    one fragment per call and is unaffected. The pool remains a shared
    Chroma collection across every agent; only the per-fragment ACL granted
    at write time is now single-member, with `grant` still the sole way an
    ACL grows past one reader.

    Storage note: rows live in a `ChromaRows` collection SHARED across every
    agent (one Chroma record per owner per `remember`/`remember_atomic`
    call). Chroma metadata values must be scalars, so each row's ACL is
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
        """ONE FRAGMENT PER OWNER, each with a single-member ACL -- per-owner
        duplication, mirroring `GenerativeAgentsMemory.remember_atomic`.
        None of the three baselines implement the consensus store's
        cross-agent equivalence merge, so faithfully modeling "each agent
        that knows an event keeps its own record" means every owner in
        `owners` gets its own single-reader fragment, embedded/tagged
        identically. `grant` remains the only way a fragment's ACL grows
        past one member (see the class docstring), so `stats().shared`
        stays ~0 here under plain writes."""
        text = text.strip()
        if not text:
            return None
        if not owners:
            raise ValueError("remember_atomic requires at least one owner")

        embedding = (await self._embed_fn([text]))[0]
        meta = {
            "created_at": _now_iso(),
            "source": source,
            "tick": tick,
        }
        if story_order is not None:
            meta["story_order"] = story_order
        if story_time is not None:
            meta["story_time"] = story_time
        seed_affiliated = sorted(set(affiliated or []))
        first_id = None
        for owner in owners:
            row_id = uuid.uuid4().hex
            if first_id is None:
                first_id = row_id
            row_affiliated = sorted(a for a in seed_affiliated if a != row_id)
            metadata = self._build_meta([owner], row_affiliated, meta)
            await self._store.add(row_id, text, embedding, metadata)
        return {"id": first_id, "text": text, "merged": False, "owners": list(owners)}

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
            acl = entry.get("owners") or [None]
            affiliated = list(entry.get("affiliated", []))
            meta = dict(entry.get("meta", {}) or {})
            embedding = entry.get("embedding") or computed[i]

            # A multi-ACL entry (e.g. a consensus-merged dump from
            # `society.ltm.SharedMemory`) restored into this PER-OWNER
            # backend becomes one single-reader fragment per owner --
            # mirrors `GenerativeAgentsMemory.restore`'s fan-out. The first
            # owner keeps the entry's original id; additional owners get a
            # fresh row id since two rows can never share one id in this
            # store.
            for idx, owner in enumerate(acl):
                row_id = entry["id"] if idx == 0 else uuid.uuid4().hex
                metadata = self._build_meta([owner], affiliated, meta)
                await self._store.add(row_id, entry["text"], list(embedding), metadata)

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
