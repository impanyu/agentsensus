"""Quantities the review asked for, computed from runs already on disk.

No simulation and no LLM calls: everything here is arithmetic over the event
logs and the final stores, so it can be recomputed at any time without paying
for a rerun. Four things the paper previously asserted without a number:

  expansion   what a recall actually returns once one-hop affiliation
              expansion has run, split into semantic hits and expanded rows
              via the `via_affiliated` flag the store already writes
  keeptext    how much text the keep-the-shorter merge rule discards, and
              whether surviving text shrinks as merge depth grows
  affdegree   how many affiliated siblings a row carries, by merge depth --
              i.e. whether write-side compression costs read-side payload
  headroom    how far the quality metrics sit from their ceiling, and how
              much they spread across cells, which is what decides whether
              "no backend separates" is a ceiling artefact

Run: venv/bin/python -m experiments.review_stats   -> runs/review_stats.json
"""
import ast
import json
import os
import statistics as st
import sys

os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); sys.path.insert(0, ".")

WORLDS = [("three_kingdoms", "Three Kingdoms", "g80full_consensus", "results_g80"),
          ("red_chamber", "Red Chamber", "rc80full_consensus", "results_rc80"),
          ("russia_ukraine", "Russia--Ukraine", "ru40full_consensus", "results_ru40"),
          ("hamlet", "Hamlet", "hl40full_consensus", "results_hl40")]
BASE_TOP_K = 5          # society/ltm.py recall_of default
SCALES = {"grnd": (0, 1), "traj": (0, 1), "narr": (1, 5), "goal": (0, 1)}


def _listlen(v):
    """owners/affiliated round-trip through the store as repr'd lists."""
    if isinstance(v, str):
        try:
            return len(ast.literal_eval(v))
        except (ValueError, SyntaxError):
            return 0
    return len(v or [])


def _events(run):
    p = f"runs/{run}/events.jsonl"
    if not os.path.exists(p):
        return
    for line in open(p, encoding="utf-8"):
        yield json.loads(line)


def expansion(run):
    """What recall returns, semantic hits vs rows pulled in by expansion.

    `read` goes through the same recall_of, so it is counted separately rather
    than folded in -- the expansion is not specific to the recall action."""
    out = {}
    for name in ("recall", "read"):
        base, exp, tot, chars, q_base, q_exp, n_base, n_exp = [], [], [], [], 0, 0, 0, 0
        for e in _events(run):
            a = e.get("action") or {}
            if a.get("name") != name:
                continue
            d = (e.get("result") or {}).get("data")
            if not isinstance(d, list) or not d or not isinstance(d[0], dict):
                continue
            if "n_affiliated" not in d[0]:
                continue                       # not a recall-shaped result
            ex = [r for r in d if r.get("via_affiliated")]
            bs = [r for r in d if not r.get("via_affiliated")]
            base.append(len(bs)); exp.append(len(ex)); tot.append(len(d))
            chars.append(sum(len(r.get("text", "")) for r in d))
            # crude relevance proxy: does the returned text contain the query
            # string? Only meaningful where queries are short names, so it is
            # reported per world and never aggregated.
            q = ((a.get("params") or {}).get("query") or "").strip().lower()
            if len(q) >= 2:
                n_base += len(bs); n_exp += len(ex)
                q_base += sum(1 for r in bs if q in r.get("text", "").lower())
                q_exp += sum(1 for r in ex if q in r.get("text", "").lower())
        if not tot:
            continue
        out[name] = {
            "n": len(tot),
            "median_base": st.median(base), "median_expanded": st.median(exp),
            "median_total": st.median(tot), "median_chars": st.median(chars),
            "amplification": round(sum(tot) / max(1, sum(base)), 1),
            "pct_with_expansion": round(sum(1 for x in exp if x) / len(exp) * 100),
            "q_in_base_pct": round(q_base / n_base * 100) if n_base else None,
            "q_in_expanded_pct": round(q_exp / n_exp * 100) if n_exp else None,
        }
    return out


def keeptext(run):
    """The keep-the-shorter rule, as far as the log can see it.

    A merge only reveals both texts when the surviving text CHANGED, i.e. the
    incoming atom was the shorter one; merges into a row whose text was
    already shorter leave the discarded text unlogged. So this is a lower
    bound on discarded characters, over an observable subset."""
    seen, merges, deltas = {}, 0, []
    for e in _events(run):
        a = e.get("action") or {}
        if a.get("name") != "remember":
            continue
        d = (e.get("result") or {}).get("data")
        if not isinstance(d, list):
            continue
        for r in d:
            if not isinstance(r, dict) or not r.get("merged"):
                continue
            merges += 1
            rid, txt = r.get("id"), r.get("text", "")
            if rid in seen and seen[rid] != txt:
                deltas.append(len(seen[rid]) - len(txt))
            seen[rid] = txt
    shrink = [x for x in deltas if x > 0]
    return {"merges": merges, "observable_rewrites": len(deltas),
            "median_chars_dropped": st.median(shrink) if shrink else 0,
            "total_chars_dropped": sum(shrink)}


def store_shape(run):
    """Row count, text length and affiliation degree, bucketed by merge depth."""
    f = f"runs/{run}/ltm_final.json"
    if not os.path.exists(f):
        return {}
    rows = json.load(open(f, encoding="utf-8"))
    by = {}
    for r in rows:
        k = min(_listlen(r.get("owners")), 4)
        by.setdefault(k, {"len": [], "aff": []})
        by[k]["len"].append(len(r.get("text", "")))
        by[k]["aff"].append(_listlen(r.get("affiliated")))
    depth = {("4plus" if k == 4 else str(k)):
             {"rows": len(v["len"]),
              "median_len": st.median(v["len"]),
              "median_aff": st.median(v["aff"]),
              "p90_aff": sorted(v["aff"])[int(len(v["aff"]) * 0.9)]}
             for k, v in sorted(by.items())}
    return {"rows": len(rows), "by_depth": depth}


def headroom(results):
    """How much room each metric has left, and how far it spreads across the
    four backends -- a metric pinned at its ceiling cannot separate anything,
    one that spreads a full point plainly can."""
    f = f"runs/{results}.json"
    if not os.path.exists(f):
        return {}
    R = json.load(open(f, encoding="utf-8"))
    out = {}
    for k, (lo, hi) in SCALES.items():
        vals = [v["agg"][k]["mean"] for v in R.values()
                if isinstance(v, dict) and "agg" in v and v["agg"].get(k)]
        if not vals:
            continue
        out[k] = {"min": round(min(vals), 2), "max": round(max(vals), 2),
                  "spread": round(max(vals) - min(vals), 2),
                  "headroom_pct": round((hi - max(vals)) / (hi - lo) * 100)}
    return out


def main():
    out = {"base_top_k": BASE_TOP_K, "worlds": {}}
    for key, title, run, results in WORLDS:
        out["worlds"][key] = {
            "title": title,
            "expansion": expansion(run),
            "keeptext": keeptext(run),
            "store": store_shape(run),
            "headroom": headroom(results),
        }
    os.makedirs("runs", exist_ok=True)
    json.dump(out, open("runs/review_stats.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("wrote runs/review_stats.json")
    for key, w in out["worlds"].items():
        r = (w["expansion"] or {}).get("recall")
        if r:
            print(f"  {w['title']:<16} recall n={r['n']:<4} "
                  f"{r['median_base']:.0f}+{r['median_expanded']:.0f} rows, "
                  f"{r['amplification']}x, query-in-text "
                  f"{r['q_in_base_pct']}% -> {r['q_in_expanded_pct']}%")


if __name__ == "__main__":
    main()
