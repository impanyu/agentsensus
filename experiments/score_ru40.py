"""Score the 40-tick Russia-Ukraine runs: grounding / trajectory / narrative
over the FULL 40-tick run, judged from its rendered screenplay (ru10 + ru20 +
ru40 event logs), mirroring the 三国 protocol of score_g40.py.

Gold arcs come from the held-out timeline continuation (2024-05 onward: the
span after the sedimentation boundary). Grounding judges each sim event
against the real-world canon of the conflict.

Usage: RUN_REPEAT=3 venv/bin/python experiments/score_ru40.py
"""
import os, sys, json, asyncio
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); sys.path.insert(0, ".")
from society import evaluation as ev
from society.run import _build_llm_and_embed
from experiments.score_fidelity import _mean_std
from experiments.screenplay_for_scoring import screenplay_text

BACKENDS = ["consensus", "generative_agents", "g_memory", "collaborative"]
REPEAT = int(os.environ.get("RUN_REPEAT", "3"))
MAX_EVENTS = int(os.environ.get("GROUNDING_MAX_EVENTS", "80"))

ARC_CHARS = [
    "putin", "zelenskyy", "zaluzhnyi", "syrskyi", "budanov",
    "stoltenberg", "sobyanin", "yermak", "sbu", "black_sea_fleet",
]


def reference_span() -> str:
    """Held-out timeline: entries dated 2024-05-01 or later."""
    keep = []
    for line in open("scenarios/sources/russia_ukraine_timeline.txt", encoding="utf-8"):
        d = line[:10]
        if len(d) == 10 and d[4] == "-" and d >= "2024-05-01":
            keep.append(line.rstrip("\n"))
    return "\n".join(keep)


async def source_text(kind, llm):
    """Scoring source: the run's screenplay, rendered in the scenario language.

    Replaces the raw transcript (see experiments/screenplay_for_scoring.py):
    the event log is mixed-language and ~1.6M chars, which previously forced
    per-message truncation and line sampling; the screenplay is one language,
    scene-organized, and small enough to judge whole.
    """
    return await screenplay_text(
        [f"runs/ru10_{kind}", f"runs/ru20_{kind}", f"runs/ru40_{kind}"], llm
    )


async def _judge_one(et, judge):
    prompt = (
        "Below is an event taken from a SIMULATED continuation of the "
        "real-world Russia-Ukraine conflict (the simulation continues the "
        "timeline beyond its 2024-04 boundary). Judge whether this event is "
        "GROUNDED in the real conflict's world: the people, institutions and "
        "places are real, their roles/affiliations/allegiances match reality, "
        "and the event is plausible within the conflict's actual dynamics "
        "(NOT a contradiction of established facts, a wrong-side/wrong-role "
        "error, or an invention of non-existent people, institutions or "
        "capabilities). A plausible in-role action that did not literally "
        "happen still counts as GROUNDED; only reality-violating or "
        "fabricated events are NOT grounded.\n\n"
        f"Event: {et}\n\n"
        'Return STRICT JSON: {"grounded": true/false, "why": "<short>"}. '
        "Return ONLY the JSON."
    )
    reply = await judge.chat(prompt, system=None, bucket="eval_judge")
    parsed = ev._parse_json(reply, default={"grounded": False, "why": ""})
    if not isinstance(parsed, dict):
        parsed = {"grounded": False}
    return {"event": et, "grounded": bool(parsed.get("grounded", False)),
            "why": str(parsed.get("why", ""))}


async def grounding_rate(transcript, judge, max_events=MAX_EVENTS):
    sim_events = await ev.extract_events(transcript, judge, max_events=max_events)
    per = await asyncio.gather(*[_judge_one(e.get("event", ""), judge) for e in sim_events])
    hits = sum(1 for p in per if p["grounded"])
    n = len(per)
    return {"rate": hits / n if n else 0.0, "n": n, "per": per}


async def main():
    llm, _ = _build_llm_and_embed("config_flash.json")
    gold_arcs = await ev.extract_arcs(reference_span(), ARC_CHARS, llm)
    print(f"gold: {len(gold_arcs)} arcs | repeat={REPEAT}", flush=True)
    results = {}
    for k in BACKENDS:
        tr = await source_text(k, llm)
        entries = len(json.load(open(f"runs/ru40_{k}/ltm_final.json", encoding="utf-8")))
        runs = []
        for _ in range(REPEAT):
            gr = await grounding_rate(tr, llm, max_events=MAX_EVENTS)
            tj = await ev.trajectory_consistency(gold_arcs, tr, llm)
            nq = await ev.narrative_quality(tr, llm)
            runs.append({"grnd": gr["rate"], "grnd_n": gr["n"], "traj": tj["mean"], "narr": nq["overall"]})
        agg = {key: dict(zip(("mean", "std"), _mean_std([r[key] for r in runs]))) for key in ("grnd", "traj", "narr")}
        agg["grnd_n"] = sum(r["grnd_n"] for r in runs) / len(runs)
        results[k] = {"entries": entries, "agg": agg, "runs": runs}
        print(f"{k}: grounding {agg['grnd']['mean']:.2f}±{agg['grnd']['std']:.2f} (n≈{agg['grnd_n']:.0f}) | "
              f"traj {agg['traj']['mean']:.2f}±{agg['traj']['std']:.2f} | "
              f"narr {agg['narr']['mean']:.2f}±{agg['narr']['std']:.2f}", flush=True)
    json.dump(results, open("runs/results_ru40.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)

asyncio.run(main())
