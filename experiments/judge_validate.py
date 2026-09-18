"""Label the equivalence-judge validation set with an independent adjudicator.

The production judge is gpt-5-mini, asked to pick an equivalent candidate by
index out of five. Here a stronger model of a later generation answers a plain
binary question about one pair at a time, and its answer is treated as the
reference. Two things follow from that and are stated in the paper rather than
buried: the adjudicator is from the same vendor family, so this measures
agreement with a stronger model and not human ground truth; and it sees one
pair, not five candidates, so it is a cleaner question than the one the
production judge faces.

Controls: the order of the two statements is randomised per pair, and a subset
is asked a second time with the order flipped, which gives a self-consistency
rate to compare the disagreement rate against.

Run: ADJ_MODEL=gpt-5.5 venv/bin/python -m experiments.judge_validate
     -> runs/judge_validation.json
"""
import asyncio
import json
import os
import random
import re
import sys

os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); sys.path.insert(0, ".")

from society.llm import LLMClient                                    # noqa: E402

MODEL = os.environ.get("ADJ_MODEL", "gpt-5.5")
CONFIG = os.environ.get("CONFIG", "config_flash.json")
FLIP_N = int(os.environ.get("FLIP_N", "40"))       # order-swap consistency probe
CONCURRENCY = int(os.environ.get("CONCURRENCY", "8"))
SEED = 20260904

SYSTEM = ("You judge whether two short statements taken from a story-world "
          "memory store record the SAME fact or event. Be strict: two "
          "statements about the same people that differ in what was said, "
          "ordered, or done are DIFFERENT, and so are two stages of one "
          "process. Rewordings of one fact are SAME.")

TEMPLATE = ("Statement 1: {a}\nStatement 2: {b}\n\n"
            "Do these record the same fact or event?\n"
            "Answer on two lines exactly:\n"
            "VERDICT: SAME or DIFFERENT\n"
            "REASON: one short sentence")


def parse(reply):
    if not reply:
        return None, ""
    v = re.search(r"VERDICT:\s*(SAME|DIFFERENT)", reply, re.I)
    r = re.search(r"REASON:\s*(.+)", reply, re.I)
    if not v:                       # fall back to a bare mention
        low = reply.lower()
        if "different" in low:
            v_ = "DIFFERENT"
        elif "same" in low:
            v_ = "SAME"
        else:
            return None, reply.strip()[:200]
    else:
        v_ = v.group(1).upper()
    return v_, (r.group(1).strip()[:300] if r else "")


async def run():
    D = json.load(open("runs/judge_pairs.json", encoding="utf-8"))
    pairs = D["pairs"]
    rng = random.Random(SEED)
    for p in pairs:
        p["_swapped"] = rng.random() < 0.5
    flip = set(rng.sample([p["pid"] for p in pairs], min(FLIP_N, len(pairs))))

    cfg = json.load(open(CONFIG, encoding="utf-8"))
    llm = LLMClient(api_key=cfg["api_key"], base_url=cfg["base_url"],
                    chat_model=MODEL, max_concurrency=CONCURRENCY,
                    extra_body=cfg.get("extra_body") or None)

    jobs = [(p, p["_swapped"]) for p in pairs]
    jobs += [(p, not p["_swapped"]) for p in pairs if p["pid"] in flip]
    print(f"adjudicator={MODEL}  pairs={len(pairs)}  calls={len(jobs)}")

    sem = asyncio.Semaphore(CONCURRENCY)
    results = {}

    async def one(p, swapped):
        a, b = (p["b"], p["a"]) if swapped else (p["a"], p["b"])
        async with sem:
            try:
                reply = await llm.chat(TEMPLATE.format(a=a, b=b), system=SYSTEM,
                                       bucket="judge_validation")
            except Exception as e:                      # noqa: BLE001
                reply = f"ERROR {e}"
        verdict, reason = parse(reply)
        results.setdefault(p["pid"], []).append(
            {"swapped": swapped, "verdict": verdict, "reason": reason})

    done = 0
    for i in range(0, len(jobs), 40):
        await asyncio.gather(*(one(p, s) for p, s in jobs[i:i + 40]))
        done = min(i + 40, len(jobs))
        print(f"  {done}/{len(jobs)}", flush=True)

    out = []
    for p in pairs:
        rs = results.get(p["pid"], [])
        primary = next((r for r in rs if r["swapped"] == p["_swapped"]), None)
        flipped = next((r for r in rs if r["swapped"] != p["_swapped"]), None)
        out.append({k: p[k] for k in ("pid", "world", "set", "a", "b")
                    if k in p} |
                   {"sim": p.get("sim"),
                    "verdict": primary["verdict"] if primary else None,
                    "reason": primary["reason"] if primary else "",
                    "verdict_flipped": flipped["verdict"] if flipped else None})
    json.dump({"adjudicator": MODEL, "production_judge": "gpt-5-mini",
               "system": SYSTEM, "template": TEMPLATE, "seed": SEED,
               "results": out},
              open("runs/judge_validation.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("wrote runs/judge_validation.json")


if __name__ == "__main__":
    asyncio.run(run())
