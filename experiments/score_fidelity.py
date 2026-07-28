"""Offline continuation-fidelity scoring for the 三国 4-backend runs.

For each completed run (runs/<PREFIX>_<backend>/), scores the simulated "sequel"
against the held-out reference span (三国 ch41-60), using society.evaluation.
All three metrics are read off the sim TRANSCRIPT (behavior), not the raw store:

  - grounding rate: extract the sim's OWN events and judge each for canon
    consistency (the reverse of the retired forward event-hit, which collapsed
    to ~0 because the sim diverges from the ch41-60 plot). This is what
    shared-memory quality actually moves. See experiments/score_grounding.py.
  - trajectory consistency: did characters follow their reference arcs?
  - narrative quality: LLM-judged coherence/distinctiveness/drama/fidelity.

QA was REMOVED: it retrieved method-agnostically over the WHOLE final store
(all_entries), measuring only raw compression retention and blind to the
per-agent (owner-scoped / affiliated) retrieval that is the actual mechanism.

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
# FIDELITY_REPEAT>1 scores each backend N times (reusing the same gold) and
# reports mean±std per metric -- the LLM answer/judge steps are nondeterministic
# so a single run cannot rank backends (see the grounding variance finding).
REPEAT = int(os.environ.get("FIDELITY_REPEAT", "1"))


def _mean_std(xs):
    n = len(xs)
    if n == 0:
        return 0.0, 0.0
    m = sum(xs) / n
    return m, (sum((x - m) ** 2 for x in xs) / n) ** 0.5


def _source_chapters():
    a = open(f"{SRC}/three_kingdoms_ch01-10.txt", encoding="utf-8").read()
    b = open(f"{SRC}/three_kingdoms_ch11-60.txt", encoding="utf-8").read()
    return _split_by_chapters(a + "\n" + b)


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


async def main():
    which = sys.argv[1:] or BACKENDS
    llm, _embed = _build_llm_and_embed("config_flash.json")

    ref = reference_span()
    print(f"reference ch41-60: {len(ref)} chars", flush=True)

    # -- shared gold (computed once; identical for every backend) --
    # NOTE 1: the forward event-hit metric is retired (the sim diverges from the
    # ch41-60 plot -> collapses to ~0 for everyone). Replaced by the REVERSE
    # grounding metric (grounding_rate): extract the sim's OWN events, judge each
    # for canon consistency.
    # NOTE 2: QA is removed -- it retrieves method-agnostically over the WHOLE
    # final store (all_entries), so it measures only raw compression retention
    # and is blind to per-agent (owner-scoped / affiliated) retrieval, which is
    # the mechanism we care about. Grounding/trajectory/narrative (all off the
    # sim transcript, i.e. behavior) are what remain.
    gold_arcs = await ev.extract_arcs(ref, ARC_CHARS, llm)
    print(f"gold: {len(gold_arcs)} arcs", flush=True)

    async def score_once(transcript):
        gr = await grounding_rate(transcript, llm)
        tj = await ev.trajectory_consistency(gold_arcs, transcript, llm)
        nq = await ev.narrative_quality(transcript, llm)
        return {"grnd": gr["rate"], "grnd_n": gr["n"],
                "traj": tj["mean"], "narr": nq["overall"]}

    results = {}
    for kind in which:
        rd = f"runs/{PREFIX}_{kind}"
        entries = json.load(open(f"{rd}/ltm_final.json", encoding="utf-8"))
        transcript = sim_transcript(rd)

        runs = [await score_once(transcript) for _ in range(REPEAT)]
        agg = {}
        for key in ("grnd", "traj", "narr"):
            m, sd = _mean_std([r[key] for r in runs])
            agg[key] = {"mean": m, "std": sd}
        agg["grnd_n"] = sum(r["grnd_n"] for r in runs) / len(runs)
        results[kind] = {"entries": len(entries), "repeat": REPEAT, "agg": agg, "runs": runs}
        print(f"{kind}: grounding {agg['grnd']['mean']:.2f}±{agg['grnd']['std']:.2f} "
              f"(n≈{agg['grnd_n']:.0f}) | traj {agg['traj']['mean']:.2f}±{agg['traj']['std']:.2f} | "
              f"narr {agg['narr']['mean']:.2f}±{agg['narr']['std']:.2f}", flush=True)

    json.dump(results, open("runs/fidelity_results.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(f"\n=== FIDELITY TABLE (mean±std over {REPEAT} run{'s' if REPEAT>1 else ''}) ===")
    print(f"{'backend':<20}{'entries':>8}{'grnd':>13}{'traj':>13}{'narr':>13}")
    for k in which:
        if k in results:
            a = results[k]["agg"]
            def c(key):
                return f"{a[key]['mean']:.2f}±{a[key]['std']:.2f}"
            print(f"{k:<20}{results[k]['entries']:>8}{c('grnd'):>13}"
                  f"{c('traj'):>13}{c('narr'):>13}")


if __name__ == "__main__":
    asyncio.run(main())
