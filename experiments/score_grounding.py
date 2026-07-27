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


def sim_transcript(run_dir):
    lines = []
    for line in open(f"{run_dir}/events.jsonl", encoding="utf-8"):
        e = json.loads(line)
        if e.get("kind") == "message" and e["message"].get("kind") in ("say", "gesture", "broadcast"):
            m = e["message"]
            lines.append(f"[t{e['tick']}] {m['sender']}: {m['content']}")
    return "\n".join(lines)


async def grounding_rate(transcript, judge):
    """Extract the sim's own events, then judge each for canonical grounding."""
    sim_events = await ev.extract_events(transcript, judge, max_events=40)
    hits = 0
    per = []
    for e in sim_events:
        et = e.get("event", "")
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
        g = bool(parsed.get("grounded", False))
        hits += g
        per.append({"event": et, "grounded": g, "why": str(parsed.get("why", ""))})
    n = len(sim_events)
    return {"rate": (hits / n) if n else 0.0, "hits": hits, "n": n, "per": per}


async def main():
    which = sys.argv[1:] or BACKENDS
    llm, _ = _build_llm_and_embed("config_flash.json")
    out = {}
    for k in which:
        r = await grounding_rate(sim_transcript(f"runs/{PREFIX}_{k}"), llm)
        out[k] = r
        print(f"{k:<20} grounding {r['rate']:.2f}  ({r['hits']}/{r['n']} sim events grounded)", flush=True)
    json.dump(out, open("runs/grounding_results.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)


if __name__ == "__main__":
    asyncio.run(main())
