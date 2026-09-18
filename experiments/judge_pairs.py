"""Build the validation set for the equivalence judge. No LLM calls here.

Two sets, because they answer different questions:

  accepted  pairs the production judge merged. Recovered from the event log:
            a merge only reveals both texts when the surviving text changed,
            so these are merges where the incoming atom was the shorter one.
            Labelling these gives precision on real merges.

  unmerged  pairs that co-exist in the final store above the same cosine
            pre-filter the judge uses. Both survived, so neither was merged
            into the other -- either the judge declined, or the pre-filter
            never surfaced the pair. Labelling these bounds the compression
            left on the table; it is NOT judge recall, and must not be
            reported as such.

Run: venv/bin/python -m experiments.judge_pairs   -> runs/judge_pairs.json
"""
import ast
import json
import os
import random
import sys

os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); sys.path.insert(0, ".")

WORLDS = [("three_kingdoms", "g80full_consensus"), ("red_chamber", "rc80full_consensus"),
          ("russia_ukraine", "ru40full_consensus"), ("hamlet", "hl40full_consensus")]
SIM_THRESHOLD = 0.70        # society/ltm.py SharedMemory default
TOP_K = 5                   # candidates the judge is shown
PER_WORLD_UNMERGED = 60
SEED = 20260904


def accepted_pairs(world, run):
    """Merges where the log shows both texts."""
    seen, out = {}, []
    p = f"runs/{run}/events.jsonl"
    if not os.path.exists(p):
        return out
    for line in open(p, encoding="utf-8"):
        e = json.loads(line)
        a = e.get("action") or {}
        if a.get("name") != "remember":
            continue
        d = (e.get("result") or {}).get("data")
        if not isinstance(d, list):
            continue
        for r in d:
            if not isinstance(r, dict) or not r.get("merged"):
                continue
            rid, txt = r.get("id"), r.get("text", "")
            if rid in seen and seen[rid] != txt and seen[rid] and txt:
                out.append({"world": world, "set": "accepted", "tick": e.get("tick"),
                            "a": seen[rid], "b": txt})
            seen[rid] = txt
    return out


def unmerged_pairs(world, run, rng):
    """Nearest neighbours above the pre-filter that both survived."""
    f = f"runs/{run}/ltm_final.json"
    if not os.path.exists(f):
        return []
    rows = json.load(open(f, encoding="utf-8"))
    rows = [r for r in rows if r.get("embedding") and r.get("text")]
    if len(rows) < 50:
        return []
    try:
        import numpy as np
    except ImportError:
        print("  numpy missing; skipping unmerged set", file=sys.stderr)
        return []
    M = np.asarray([r["embedding"] for r in rows], dtype="float32")
    M /= (np.linalg.norm(M, axis=1, keepdims=True) + 1e-9)
    idx = rng.sample(range(len(rows)), min(400, len(rows)))
    out, used = [], set()
    for i in idx:
        sims = M @ M[i]
        sims[i] = -1
        top = sims.argsort()[-TOP_K:][::-1]
        for j in top:
            if sims[j] < SIM_THRESHOLD:
                continue
            key = (min(i, int(j)), max(i, int(j)))
            if key in used:
                continue
            used.add(key)
            out.append({"world": world, "set": "unmerged",
                        "sim": round(float(sims[j]), 3),
                        "a": rows[i]["text"], "b": rows[int(j)]["text"]})
            break                       # one pair per sampled row, top neighbour
        if len(out) >= PER_WORLD_UNMERGED:
            break
    return out


def main():
    rng = random.Random(SEED)
    pairs = []
    for world, run in WORLDS:
        acc = accepted_pairs(world, run)
        unm = unmerged_pairs(world, run, rng)
        pairs += acc + unm
        print(f"{world:<16} accepted={len(acc):<4} unmerged={len(unm)}")
    for n, p in enumerate(pairs):
        p["pid"] = n
    json.dump({"sim_threshold": SIM_THRESHOLD, "top_k": TOP_K, "seed": SEED,
               "pairs": pairs},
              open("runs/judge_pairs.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(f"\nwrote runs/judge_pairs.json  ({len(pairs)} pairs total)")


if __name__ == "__main__":
    main()
