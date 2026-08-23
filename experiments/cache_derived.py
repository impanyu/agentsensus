"""Cache the tables that are computed by reading whole event logs.

Two appendix tables are counted straight out of the runs: the action census
(A1, every action every backend called) and the screenplay geometry (A5,
rounds/scenes/beats/speakers/places). Counting them means reading 52 MB of
event logs, which is more than a paper's repository should have to carry, so
the counts are cached here and the builder prefers the cache.

Regenerate after a rerun:  venv/bin/python -m experiments.cache_derived
"""
import json
import os
import sys

os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); sys.path.insert(0, ".")

OUT = "runs/derived_tables.json"
PREFIXES = ["g80", "rc80", "ru40", "hl40"]
BACKENDS = ["consensus", "generative_agents", "g_memory", "collaborative"]
WORLDS = ["three_kingdoms", "red_chamber", "russia_ukraine", "hamlet"]


def action_counts(pref):
    """{backend: {action: count}} over one world's final stage."""
    per = {}
    for b in BACKENDS:
        path = f"runs/{pref}_{b}/events.jsonl"
        if not os.path.exists(path):
            continue
        counts = {}
        with open(path, encoding="utf-8") as f:
            for line in f:
                e = json.loads(line)
                if e.get("kind") == "action":
                    n = (e.get("action") or {}).get("name")
                    counts[n] = counts.get(n, 0) + 1
        per[b] = counts
    return per


def main():
    from experiments.scene_grid_fig import stats
    cache = {"actions": {p: action_counts(p) for p in PREFIXES},
             "screenplay": {w: stats(w) for w in WORLDS}}
    json.dump(cache, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"wrote {OUT}: {sum(len(v) for v in cache['actions'].values())} action tables, "
          f"{len(cache['screenplay'])} screenplay stats")


if __name__ == "__main__":
    main()
