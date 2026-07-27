"""Reverse event-hit / grounding score: extract events FROM each backend's sim
continuation, then judge each against the canonical 三国 (does it 'hit' the
original story -- right characters/relationships, plausible in-canon, not a
contradiction or invention). Better-preserved memory -> more grounded events.

Usage: venv/bin/python experiments/score_grounding.py [backend ...]
"""

import os
import sys
import json
import asyncio

os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ".")

from society import evaluation as ev
from society.run import _build_llm_and_embed

BACKENDS = ["consensus", "generative_agents", "g_memory", "collaborative"]


PREFIX = os.environ.get("RUN_PREFIX", "fair2")
MAX_EVENTS = int(os.environ.get("GROUNDING_MAX_EVENTS", "40"))
REPEAT = int(os.environ.get("GROUNDING_REPEAT", "1"))


def sim_transcript(run_dir):
    lines = []
    for line in open(f"{run_dir}/events.jsonl", encoding="utf-8"):
        e = json.loads(line)
        if e.get("kind") == "message" and e["message"].get("kind") in ("say", "gesture", "broadcast"):
            m = e["message"]
            lines.append(f"[t{e['tick']}] {m['sender']}: {m['content']}")
    return "\n".join(lines)


async def _judge_one(et, judge):
    prompt = (
        "Below is an event taken from a SIMULATED continuation of 三国演义 "
        "(Romance of the Three Kingdoms). Judge whether this event is "
        "GROUNDED in the canonical story world: the characters exist and "
        "their identities/relationships/allegiances match the canon, and "
        "the event is plausible within 三国演义 (NOT a contradiction of "
        "canon, an anachronism, a wrong-faction/wrong-relationship error, "
        "or an invention of non-canonical people/facts). A plausible "
        "in-character action that simply isn't a literal book event still "
        "counts as GROUNDED; only canon-violating or fabricated events are "
        "NOT grounded.\n\n"
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
    """Extract the sim's own events, then judge each for canonical grounding.

    Judge calls are issued concurrently (the client semaphore bounds real
    parallelism) -- with a larger max_events the old sequential loop was the
    bottleneck.
    """
    sim_events = await ev.extract_events(transcript, judge, max_events=max_events)
    per = await asyncio.gather(*[_judge_one(e.get("event", ""), judge) for e in sim_events])
    hits = sum(1 for p in per if p["grounded"])
    n = len(per)
    return {"rate": (hits / n) if n else 0.0, "hits": hits, "n": n, "per": per}


def _mean_std(xs):
    n = len(xs)
    if n == 0:
        return 0.0, 0.0
    m = sum(xs) / n
    var = sum((x - m) ** 2 for x in xs) / n  # population std over the repeats
    return m, var ** 0.5


async def main():
    which = sys.argv[1:] or BACKENDS
    llm, _ = _build_llm_and_embed("config_flash.json")
    print(f"prefix={PREFIX} max_events={MAX_EVENTS} repeat={REPEAT}", flush=True)

    # For each backend, run REPEAT independent scorings of the SAME transcript
    # (LLM extract/judge nondeterminism is what we're quantifying). All
    # backend*repeat scorings are dispatched together; the client semaphore
    # bounds real concurrency.
    transcripts = {k: sim_transcript(f"runs/{PREFIX}_{k}") for k in which}
    tasks = {k: [grounding_rate(transcripts[k], llm) for _ in range(REPEAT)] for k in which}
    out = {}
    for k in which:
        runs = await asyncio.gather(*tasks[k])
        rates = [r["rate"] for r in runs]
        ns = [r["n"] for r in runs]
        m, sd = _mean_std(rates)
        out[k] = {"mean": m, "std": sd, "rates": rates, "ns": ns,
                  "n_mean": sum(ns) / len(ns), "runs": runs}
        detail = ", ".join(f"{x:.2f}" for x in rates)
        print(f"{k:<20} grounding {m:.3f} ± {sd:.3f}  (n≈{sum(ns)/len(ns):.0f}; "
              f"{REPEAT} runs: {detail})", flush=True)
    json.dump(out, open("runs/grounding_results.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("\n=== GROUNDING (mean ± std over runs) ===")
    print(f"{'backend':<20}{'mean':>8}{'std':>8}{'n':>6}")
    for k in which:
        r = out[k]
        print(f"{k:<20}{r['mean']:>8.3f}{r['std']:>8.3f}{r['n_mean']:>6.0f}")


if __name__ == "__main__":
    asyncio.run(main())
