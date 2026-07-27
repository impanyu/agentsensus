"""Offline continuation-fidelity scoring for the 三国 4-backend runs.

For each completed run (runs/fair2_<backend>/), scores the simulated "sequel"
against the held-out reference span (三国 ch41-60) and the sedimented source
(ch1-40), using society.evaluation:

  - QA accuracy: method-agnostic recall over the backend's FINAL stored memory
    (all_entries) -> did the method's compression/merge keep facts retrievable?
  - grounding rate: extract the sim's OWN events and judge each for canon
    consistency (the reverse of the retired forward event-hit, which collapsed
    to ~0 because the sim diverges from the ch41-60 plot). This is what
    shared-memory quality actually moves. See experiments/score_grounding.py.
  - trajectory consistency: did characters follow their reference arcs?
  - narrative quality: LLM-judged coherence/distinctiveness/drama/fidelity.

Usage: venv/bin/python experiments/score_fidelity.py [backend1 backend2 ...]
  (no args -> all 4 backends; useful to pass one backend for a cheap smoke.)
"""

import os
import sys
import json
import asyncio

os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ".")

from society import evaluation as ev
from society.history_extract import _split_by_chapters
from society.run import _build_llm_and_embed
from experiments.score_grounding import grounding_rate

SRC = "scenarios/sources"
# Main characters to score arcs for (keep it to the principals -- arc scoring
# is one judge call per character).
ARC_CHARS = [
    "liubei", "guanyu", "zhangfei", "zhugeliang", "zhaoyun",
    "caocao", "sunquan", "zhouyu", "simayi", "xiahoudun",
]
BACKENDS = ["consensus", "generative_agents", "g_memory", "collaborative"]
PREFIX = os.environ.get("RUN_PREFIX", "fair2")


def _source_chapters():
    a = open(f"{SRC}/three_kingdoms_ch01-10.txt", encoding="utf-8").read()
    b = open(f"{SRC}/three_kingdoms_ch11-60.txt", encoding="utf-8").read()
    return _split_by_chapters(a + "\n" + b)


def sediment_source() -> str:
    return "".join(_source_chapters()[:40])  # ch1-40 (what was sedimented)


def reference_span() -> str:
    return "".join(_source_chapters()[40:60])  # ch41-60 (held out)


def sim_transcript(run_dir: str) -> str:
    """Assemble the simulated 'sequel' screenplay from the say/gesture/broadcast
    stream in events.jsonl, in delivery order."""
    lines = []
    with open(f"{run_dir}/events.jsonl", encoding="utf-8") as f:
        for line in f:
            e = json.loads(line)
            if e.get("kind") != "message":
                continue
            m = e["message"]
            if m.get("kind") in ("say", "gesture", "broadcast"):
                lines.append(f"[t{e['tick']}] {m['sender']}: {m['content']}")
    return "\n".join(lines)


class _ShimBackend:
    """Minimal duck-type of the SharedMemory interface run_qa/footprint need:
    just all_entries()/stats() over a run's exported ltm_final.json."""

    def __init__(self, entries):
        self._entries = entries

    def all_entries(self):
        return self._entries

    def stats(self):
        total = len(self._entries)
        shared = sum(1 for e in self._entries if len(e.get("owners", [])) >= 2)
        return {"total": total, "shared": shared, "ratio": (shared / total) if total else 0.0}


def _batched(embed_fn, batch: int = 256):
    """run_qa embeds ALL of a backend's entry texts in one call; a 6.5k-20k
    entry store exceeds the OpenAI embeddings batch/token limit (-> 400). Wrap
    the embed fn to chunk large input lists into safe batches transparently."""
    async def _embed(texts):
        if len(texts) <= batch:
            return await embed_fn(texts)
        out = []
        for i in range(0, len(texts), batch):
            out.extend(await embed_fn(texts[i:i + batch]))
        return out
    return _embed


async def main():
    which = sys.argv[1:] or BACKENDS
    llm, embed = _build_llm_and_embed("config_flash.json")
    embed = _batched(embed)

    src = sediment_source()
    ref = reference_span()
    print(f"source ch1-40: {len(src)} chars | reference ch41-60: {len(ref)} chars", flush=True)

    # -- shared gold (computed once; identical for every backend) --
    # NOTE: the forward event-hit metric (extract gold beats from the reference
    # span, find them in each sim) is retired -- the sim freely diverges from
    # the ch41-60 plot, so event-hit collapses to ~0 for every backend and
    # carries no signal. It is replaced by the REVERSE grounding metric
    # (grounding_rate): extract the sim's OWN events and judge each for canon
    # consistency. That is what shared-memory quality actually moves.
    qa = await ev.generate_qa(src, llm, n=40)
    gold_arcs = await ev.extract_arcs(ref, ARC_CHARS, llm)
    print(f"gold: {len(qa)} QA, {len(gold_arcs)} arcs", flush=True)

    results = {}
    for kind in which:
        rd = f"runs/{PREFIX}_{kind}"
        entries = json.load(open(f"{rd}/ltm_final.json", encoding="utf-8"))
        backend = _ShimBackend(entries)
        transcript = sim_transcript(rd)

        qa_r = await ev.run_qa(backend, qa, llm, embed, llm, top_k=5)
        gr = await grounding_rate(transcript, llm)
        tj = await ev.trajectory_consistency(gold_arcs, transcript, llm)
        nq = await ev.narrative_quality(transcript, llm)

        results[kind] = {
            "entries": len(entries),
            "qa_accuracy": qa_r["accuracy"],
            "grounding_rate": gr["rate"],
            "grounding_n": gr["n"],
            "trajectory_mean": tj["mean"],
            "narrative_overall": nq["overall"],
            "narrative_fidelity": nq.get("fidelity"),
            "_raw": {"qa": qa_r, "grounding": gr, "trajectory": tj, "narrative": nq},
        }
        print(f"{kind}: QA {qa_r['accuracy']:.2f} | grounding {gr['rate']:.2f} "
              f"({gr['hits']}/{gr['n']}) | traj {tj['mean']:.2f} | "
              f"narrative {nq['overall']:.2f}", flush=True)

    json.dump(results, open("runs/fidelity_results.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("\n=== FIDELITY TABLE ===")
    print(f"{'backend':<20}{'entries':>8}{'QA':>7}{'grnd':>7}{'(n)':>6}{'traj':>7}{'narr':>7}")
    for k in which:
        if k not in results:
            continue
        r = results[k]
        print(f"{k:<20}{r['entries']:>8}{r['qa_accuracy']:>7.2f}"
              f"{r['grounding_rate']:>7.2f}{r['grounding_n']:>6}"
              f"{r['trajectory_mean']:>7.2f}{r['narrative_overall']:>7.2f}")


if __name__ == "__main__":
    asyncio.run(main())
