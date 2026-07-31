"""Score the 80-tick 三国 runs: footprint (tk80 final memory) + grounding /
trajectory / narrative over the FULL 80-tick transcript (tk60 ticks 0-60 +
tk80 ticks 60-80 concatenated). QA removed (see score_fidelity).

Usage: RUN_REPEAT=3 venv/bin/python experiments/score_80tick.py
"""
import os, sys, json, asyncio
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); sys.path.insert(0, ".")
from society import evaluation as ev
from society.run import _build_llm_and_embed
from experiments.score_grounding import grounding_rate
from experiments.score_fidelity import reference_span, ARC_CHARS, _mean_std

BACKENDS = ["consensus", "generative_agents", "g_memory", "collaborative"]
REPEAT = int(os.environ.get("RUN_REPEAT", "3"))


def combined_transcript(kind):
    """tk60 (0-60) + tk80 (60-80) say/gesture stream = the full 80-tick sequel."""
    lines = []
    for rd in (f"runs/tk60_{kind}", f"runs/tk80_{kind}"):
        p = f"{rd}/events.jsonl"
        if not os.path.exists(p):
            continue
        for line in open(p, encoding="utf-8"):
            e = json.loads(line)
            if e.get("kind") == "message" and e["message"].get("kind") in ("say", "gesture", "broadcast"):
                m = e["message"]
                lines.append(f"[t{e['tick']}] {m['sender']}: {m['content']}")
    return "\n".join(lines)


async def main():
    llm, _ = _build_llm_and_embed("config_flash.json")
    gold_arcs = await ev.extract_arcs(reference_span(), ARC_CHARS, llm)
    print(f"gold: {len(gold_arcs)} arcs | repeat={REPEAT}", flush=True)
    results = {}
    for k in BACKENDS:
        tr = combined_transcript(k)
        entries = len(json.load(open(f"runs/tk80_{k}/ltm_final.json", encoding="utf-8")))
        runs = []
        for _ in range(REPEAT):
            gr = await grounding_rate(tr, llm, max_events=80)
            tj = await ev.trajectory_consistency(gold_arcs, tr, llm)
            nq = await ev.narrative_quality(tr, llm)
            runs.append({"grnd": gr["rate"], "grnd_n": gr["n"], "traj": tj["mean"], "narr": nq["overall"]})
        agg = {key: dict(zip(("mean", "std"), _mean_std([r[key] for r in runs]))) for key in ("grnd", "traj", "narr")}
        agg["grnd_n"] = sum(r["grnd_n"] for r in runs) / len(runs)
        results[k] = {"entries": entries, "agg": agg, "runs": runs}
        print(f"{k}: entries {entries} | grounding {agg['grnd']['mean']:.2f}±{agg['grnd']['std']:.2f} "
              f"(n≈{agg['grnd_n']:.0f}) | traj {agg['traj']['mean']:.2f}±{agg['traj']['std']:.2f} | "
              f"narr {agg['narr']['mean']:.2f}±{agg['narr']['std']:.2f}", flush=True)
    json.dump(results, open("runs/results_80tick.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("\n=== 80-TICK TABLE (mean±std) ===")
    print(f"{'backend':<20}{'entries':>8}{'grounding':>14}{'traj':>14}{'narr':>14}")
    for k in BACKENDS:
        a = results[k]["agg"]
        c = lambda key: f"{a[key]['mean']:.2f}±{a[key]['std']:.2f}"
        print(f"{k:<20}{results[k]['entries']:>8}{c('grnd'):>14}{c('traj'):>14}{c('narr'):>14}")

asyncio.run(main())
