"""Turn the adjudicated pairs into the numbers the paper quotes.

Precision is the quantity the review asked for and the one this can actually
supply: of the merges the production judge made, how many does a stronger
adjudicator agree were the same fact. The unmerged set is reported alongside
but is deliberately NOT called recall -- a pair that co-exists in the store may
never have been put to the judge at all, so it bounds missed compression rather
than measuring the judge's misses.

Run: venv/bin/python -m experiments.judge_report   -> runs/judge_report.json
"""
import collections
import json
import os
import sys

os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); sys.path.insert(0, ".")


def main():
    D = json.load(open("runs/judge_validation.json", encoding="utf-8"))
    R = D["results"]

    acc = [r for r in R if r["set"] == "accepted" and r["verdict"]]
    unm = [r for r in R if r["set"] == "unmerged" and r["verdict"]]
    fp = [r for r in acc if r["verdict"] == "DIFFERENT"]
    missed = [r for r in unm if r["verdict"] == "SAME"]

    flipped = [r for r in R if r.get("verdict_flipped") and r["verdict"]]
    unstable = [r for r in flipped if r["verdict"] != r["verdict_flipped"]]

    out = {
        "adjudicator": D["adjudicator"], "production_judge": D["production_judge"],
        "accepted_n": len(acc), "accepted_agree": len(acc) - len(fp),
        "precision": round((len(acc) - len(fp)) / len(acc), 3) if acc else None,
        "unmerged_n": len(unm), "unmerged_same": len(missed),
        "unmerged_same_pct": round(len(missed) / len(unm) * 100) if unm else None,
        "consistency_n": len(flipped),
        "order_flips": len(unstable),
        "consistency": round(1 - len(unstable) / len(flipped), 3) if flipped else None,
        "by_world": {},
        "false_positive_examples": [
            {"world": r["world"], "a": r["a"], "b": r["b"], "reason": r["reason"]}
            for r in fp[:12]],
    }
    for w in sorted({r["world"] for r in R}):
        a = [r for r in acc if r["world"] == w]
        u = [r for r in unm if r["world"] == w]
        out["by_world"][w] = {
            "accepted_n": len(a),
            "precision": round(sum(r["verdict"] == "SAME" for r in a) / len(a), 3) if a else None,
            "unmerged_n": len(u),
            "unmerged_same_pct": round(sum(r["verdict"] == "SAME" for r in u) / len(u) * 100) if u else None,
        }

    # where the false positives sit: the judge sees text only, so pairs that
    # differ in a named target or a stage of one process are the failure mode
    # the paper predicts. Report the count, not a taxonomy we cannot support.
    json.dump(out, open("runs/judge_report.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

    print(f"adjudicator {out['adjudicator']} vs production {out['production_judge']}\n")
    print(f"PRECISION on real merges : {out['accepted_agree']}/{out['accepted_n']}"
          f" = {out['precision']}")
    print(f"unmerged pairs judged SAME: {out['unmerged_same']}/{out['unmerged_n']}"
          f" = {out['unmerged_same_pct']}%   (missed compression, not recall)")
    print(f"order-swap consistency    : {out['consistency']} "
          f"({out['order_flips']}/{out['consistency_n']} flipped)\n")
    for w, v in out["by_world"].items():
        print(f"  {w:<16} precision {v['precision']} (n={v['accepted_n']:<3}) "
              f" unmerged-SAME {v['unmerged_same_pct']}% (n={v['unmerged_n']})")
    if out["false_positive_examples"]:
        print("\n误合并样例:")
        for e in out["false_positive_examples"][:4]:
            print(f"  [{e['world']}] {e['a'][:56]}")
            print(f"           vs {e['b'][:56]}")
            print(f"           -> {e['reason'][:90]}")


if __name__ == "__main__":
    main()
