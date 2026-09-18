"""Can the equivalence judge be fixed without changing the model?

The production judge fails at precision ~0.43. Three defects are visible by
inspection, and this separates them by running the SAME production model
(gpt-5-mini) under prompt variants that remove them one at a time, scored
against the gpt-5.5 gold labels already on disk:

  base        production wording, but asked about one pair instead of five
              candidates at once. Isolates the forced-choice effect.
  meta        base plus the two fields the store has and the judge never sees:
              who owns each side, and which tick each was written at.
  meta_guide  meta plus one line saying what counts as different -- a different
              target, a different stage of one process, a different speaker.

Reporting both sets matters: a variant can raise precision simply by refusing
everything, so the unmerged set is scored alongside to catch that.

Run: venv/bin/python -m experiments.judge_fix   -> runs/judge_fix.json
"""
import asyncio
import json
import os
import re
import sys

os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); sys.path.insert(0, ".")

from society.llm import LLMClient                                    # noqa: E402

MODEL = os.environ.get("FIX_MODEL", "gpt-5-mini")       # the production judge
CONCURRENCY = int(os.environ.get("CONCURRENCY", "12"))

CRITERION = ("Two statements are equivalent only if they record the same act by "
             "the same doer. A different target, a different stage of one process "
             "(proposed vs carried out), or the two halves of one exchange "
             "(asking vs answering) are NOT equivalent.")


def _who(owners):
    return ", ".join(owners) if owners else "unknown"


def build(variant, p):
    """Return (system, prompt). Wording tracks the production judge's own."""
    if variant == "base":
        body = (f"New memory: {p['b']}\n\nExisting memory: {p['a']}\n\n"
                "Is the existing memory semantically equivalent to the new "
                "memory? Reply YES or NO.")
        return None, body
    meta = (f"New memory (owner: {_who(p['b_owners'])}, tick {p['b_tick']}): "
            f"{p['b']}\n\n"
            f"Existing memory (owners: {_who(p['a_owners'])}, tick {p['a_tick']}): "
            f"{p['a']}\n\n")
    tail = ("Is the existing memory semantically equivalent to the new memory? "
            "Reply YES or NO.")
    if variant == "meta":
        return None, meta + tail
    return CRITERION, meta + tail


def parse(reply):
    if not reply:
        return None
    m = re.search(r"\b(YES|NO)\b", reply, re.I)
    return m.group(1).upper() if m else None


def score(rows, variant):
    """Predicted SAME = YES. Gold SAME is the positive class."""
    acc = [r for r in rows if r["set"] == "accepted" and r[variant]]
    unm = [r for r in rows if r["set"] == "unmerged" and r[variant]]
    allr = acc + unm
    tp = sum(1 for r in allr if r[variant] == "YES" and r["gold"] == "SAME")
    fp = sum(1 for r in allr if r[variant] == "YES" and r["gold"] == "DIFFERENT")
    fn = sum(1 for r in allr if r[variant] == "NO" and r["gold"] == "SAME")
    prec = tp / (tp + fp) if tp + fp else None
    rec = tp / (tp + fn) if tp + fn else None
    # of the merges production made that gold calls wrong, how many would this
    # variant have stopped
    bad = [r for r in acc if r["gold"] == "DIFFERENT"]
    caught = sum(1 for r in bad if r[variant] == "NO")
    good = [r for r in acc if r["gold"] == "SAME"]
    kept = sum(1 for r in good if r[variant] == "YES")
    return {"precision": round(prec, 3) if prec else None,
            "recall": round(rec, 3) if rec else None,
            "f1": round(2 * prec * rec / (prec + rec), 3) if prec and rec else None,
            "bad_merges_caught": f"{caught}/{len(bad)}",
            "good_merges_kept": f"{kept}/{len(good)}",
            "n": len(allr)}


async def main():
    rows = json.load(open("runs/judge_evalset.json", encoding="utf-8"))["pairs"]
    cfg = json.load(open("config_flash.json", encoding="utf-8"))
    llm = LLMClient(api_key=cfg["api_key"], base_url=cfg["base_url"],
                    chat_model=MODEL, max_concurrency=CONCURRENCY)
    variants = ["base", "meta", "meta_guide"]
    jobs = [(r, v) for v in variants for r in rows]
    print(f"model={MODEL}  pairs={len(rows)}  variants={len(variants)}  "
          f"calls={len(jobs)}")

    async def one(r, v):
        system, prompt = build(v, r)
        try:
            reply = await llm.chat(prompt, system=system, bucket=f"fix_{v}")
        except Exception as e:                                   # noqa: BLE001
            reply = f"ERROR {e}"
        r[v] = parse(reply)

    for i in range(0, len(jobs), 60):
        await asyncio.gather(*(one(r, v) for r, v in jobs[i:i + 60]))
        print(f"  {min(i + 60, len(jobs))}/{len(jobs)}", flush=True)

    out = {"model": MODEL, "gold": "gpt-5.5", "scores":
           {v: score(rows, v) for v in variants}, "rows": rows}
    json.dump(out, open("runs/judge_fix.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

    print(f"\nproduction judge, as run: precision 0.429 on the same accepted set\n")
    print(f"{'variant':<12}{'prec':>7}{'recall':>8}{'F1':>7}"
          f"{'bad merges caught':>20}{'good kept':>12}")
    for v in variants:
        s = out["scores"][v]
        print(f"{v:<12}{str(s['precision']):>7}{str(s['recall']):>8}"
              f"{str(s['f1']):>7}{s['bad_merges_caught']:>20}"
              f"{s['good_merges_kept']:>12}")
    print("\nwrote runs/judge_fix.json")


if __name__ == "__main__":
    asyncio.run(main())
