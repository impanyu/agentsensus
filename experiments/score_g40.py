"""Score the 40-tick 三国 runs (gpt-5-mini): grounding / trajectory / narrative
over the FULL 40-tick transcript (g20 ticks 0-20 + g40 ticks 20-40).

Usage: RUN_REPEAT=3 venv/bin/python experiments/score_g40.py
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
    lines = []
    for rd in (f"runs/g20_{kind}", f"runs/g40_{kind}"):
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
        entries = len(json.load(open(f"runs/g40_{k}/ltm_final.json", encoding="utf-8")))
        runs = []
        for _ in range(REPEAT):
            gr = await grounding_rate(tr, llm, max_events=80)
            tj = await ev.trajectory_consistency(gold_arcs, tr, llm)
            nq = await ev.narrative_quality(tr, llm)
            runs.append({"grnd": gr["rate"], "grnd_n": gr["n"], "traj": tj["mean"], "narr": nq["overall"]})
        agg = {key: dict(zip(("mean", "std"), _mean_std([r[key] for r in runs]))) for key in ("grnd", "traj", "narr")}
        agg["grnd_n"] = sum(r["grnd_n"] for r in runs) / len(runs)
        results[k] = {"entries": entries, "agg": agg, "runs": runs}
        print(f"{k}: grounding {agg['grnd']['mean']:.2f}±{agg['grnd']['std']:.2f} (n≈{agg['grnd_n']:.0f}) | "
              f"traj {agg['traj']['mean']:.2f}±{agg['traj']['std']:.2f} | "
              f"narr {agg['narr']['mean']:.2f}±{agg['narr']['std']:.2f}", flush=True)
    json.dump(results, open("runs/results_g40.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)

asyncio.run(main())
