"""Export a stratified sample for a human to label, to calibrate the adjudicator.

The adjudicator is a stronger model from the same vendor family as the
production judge, so agreement between them is not ground truth. This writes a
small blind sample -- the adjudicator's verdict is withheld -- that a person
can label in a few minutes; comparing the two afterwards says how far the
model-vs-model number can be trusted.

Run: venv/bin/python -m experiments.judge_human_sample [n]
     -> runs/judge_human_sample.md   (fill in the VERDICT lines)
     then: venv/bin/python -m experiments.judge_human_sample --score
"""
import json
import os
import random
import re
import sys

os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); sys.path.insert(0, ".")

OUT = "runs/judge_human_sample.md"
SEED = 20260904


def export(n):
    R = json.load(open("runs/judge_validation.json", encoding="utf-8"))["results"]
    rng = random.Random(SEED)
    # stratify so the sample is not swamped by whichever set is larger, and
    # so both of the adjudicator's verdicts are represented
    buckets = {}
    for r in R:
        if r["verdict"]:
            buckets.setdefault((r["set"], r["verdict"]), []).append(r)
    per = max(1, n // max(1, len(buckets)))
    picked = []
    for k, v in sorted(buckets.items()):
        picked += rng.sample(v, min(per, len(v)))
    rng.shuffle(picked)

    lines = ["# Blind sample for human labelling", "",
             "For each pair, write SAME or DIFFERENT after `VERDICT:`.",
             "SAME means the two record the same fact or event; a rewording is",
             "SAME, a different target or a later stage of the same process is",
             "DIFFERENT. The model's own verdict is not shown.", ""]
    for i, r in enumerate(picked, 1):
        lines += [f"## {i}  (pid {r['pid']}, {r['world']})",
                  f"- A: {r['a']}", f"- B: {r['b']}", "", "VERDICT: ", ""]
    open(OUT, "w", encoding="utf-8").write("\n".join(lines))
    print(f"wrote {OUT}  ({len(picked)} pairs, verdicts hidden)")


def score():
    text = open(OUT, encoding="utf-8").read()
    got = {}
    for m in re.finditer(r"## \d+\s+\(pid (\d+),[^)]*\)(.*?)(?=\n## |\Z)", text, re.S):
        v = re.search(r"VERDICT:\s*(SAME|DIFFERENT)", m.group(2), re.I)
        if v:
            got[int(m.group(1))] = v.group(1).upper()
    if not got:
        print("no verdicts filled in yet"); return
    R = {r["pid"]: r for r in
         json.load(open("runs/judge_validation.json", encoding="utf-8"))["results"]}
    agree = sum(1 for pid, v in got.items() if R[pid]["verdict"] == v)
    print(f"human-labelled {len(got)} pairs; adjudicator agrees on {agree} "
          f"({agree / len(got) * 100:.0f}%)")
    for pid, v in got.items():
        if R[pid]["verdict"] != v:
            r = R[pid]
            print(f"\n  disagree pid {pid} [{r['world']}/{r['set']}] "
                  f"human={v} model={r['verdict']}")
            print(f"    A: {r['a'][:80]}\n    B: {r['b'][:80]}")


if __name__ == "__main__":
    if "--score" in sys.argv:
        score()
    else:
        export(int(next((a for a in sys.argv[1:] if a.isdigit()), 40)))
