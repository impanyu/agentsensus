"""Consolidate the judge evaluation set: pairs + the metadata the judge never saw + gold.

The production judge is shown text only. The store knows two more things about
every row -- who owns it and which tick it was written at -- and a merge across
two agents at two different ticks is a different proposition from a merge of one
agent's own restatement. This builds the set needed to test whether handing the
judge those two fields changes anything, so it carries them alongside each pair.

Gold labels come from the gpt-5.5 adjudication already on disk
(runs/judge_validation.json and runs/judge_complement.json). No LLM calls here.

Run: venv/bin/python -m experiments.judge_evalset   -> runs/judge_evalset.json
"""
import ast
import json
import os
import sys

os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); sys.path.insert(0, ".")

WORLDS = [("three_kingdoms", "g80full_consensus"), ("red_chamber", "rc80full_consensus"),
          ("russia_ukraine", "ru40full_consensus"), ("hamlet", "hl40full_consensus")]


def _lst(v):
    if isinstance(v, str):
        try:
            return ast.literal_eval(v)
        except (ValueError, SyntaxError):
            return []
    return v or []


def accepted_with_meta():
    """Real merges, carrying the depositing agent, the tick, and the owners the
    surviving row already had. `agent` is the incoming side's owner; the
    existing side's owners are the merged set minus that agent, which is exact
    unless the agent already owned the row."""
    out = []
    for world, run in WORLDS:
        p = f"runs/{run}/events.jsonl"
        if not os.path.exists(p):
            continue
        seen = {}
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
                owners = _lst(r.get("owners"))
                agent = e.get("agent")
                prev = seen.get(rid)
                if prev and prev["text"] != txt and prev["text"] and txt:
                    out.append({
                        "world": world, "set": "accepted", "src": "rewrite",
                        "a": prev["text"], "b": txt,
                        "a_owners": prev["owners"], "b_owners": [agent] if agent else [],
                        "a_tick": prev["tick"], "b_tick": e.get("tick"),
                    })
                # a single-atom deposit reveals the incoming text directly, which
                # covers the merges where the surviving text did NOT change
                if len(d) == 1:
                    inc = (a.get("params") or {}).get("text", "")
                    if inc and txt and inc != txt and not (prev and prev["text"] != txt):
                        out.append({
                            "world": world, "set": "accepted", "src": "single_atom",
                            "a": txt, "b": inc,
                            "a_owners": [o for o in owners if o != agent],
                            "b_owners": [agent] if agent else [],
                            "a_tick": (prev or {}).get("tick"), "b_tick": e.get("tick"),
                        })
                seen[rid] = {"text": txt, "owners": owners, "tick": e.get("tick")}
    return out


def gold_index():
    """text-pair -> gold verdict, from the two adjudication files."""
    g = {}
    V = json.load(open("runs/judge_validation.json", encoding="utf-8"))
    for r in V["results"]:
        if r["verdict"]:
            g[frozenset((r["a"], r["b"]))] = r["verdict"]
    f = "runs/judge_complement.json"
    if os.path.exists(f):
        C = json.load(open(f, encoding="utf-8"))
        for i, p in enumerate(C["pairs"]):
            v = C["verdicts"].get(str(i))
            if v:
                g[frozenset((p["a"], p["b"]))] = v
    return g


def unmerged_with_meta():
    """The already-sampled unmerged pairs, re-attached to their store rows so
    they carry owners and tick like the accepted ones do."""
    V = json.load(open("runs/judge_validation.json", encoding="utf-8"))
    want = {r["world"]: {} for r in V["results"]}
    for r in V["results"]:
        if r["set"] == "unmerged":
            want[r["world"]][r["a"]] = r
            want[r["world"]][r["b"]] = r
    meta = {}
    for world, run in WORLDS:
        f = f"runs/{run}/ltm_final.json"
        if not os.path.exists(f) or world not in want:
            continue
        for row in json.load(open(f, encoding="utf-8")):
            t = row.get("text")
            if t in want[world]:
                m = row.get("meta")
                m = ast.literal_eval(m) if isinstance(m, str) else (m or {})
                meta[(world, t)] = (_lst(row.get("owners")), m.get("tick"))
    out = []
    for r in V["results"]:
        if r["set"] != "unmerged":
            continue
        ao, at = meta.get((r["world"], r["a"]), ([], None))
        bo, bt = meta.get((r["world"], r["b"]), ([], None))
        out.append({"world": r["world"], "set": "unmerged", "src": "store",
                    "a": r["a"], "b": r["b"], "a_owners": ao, "b_owners": bo,
                    "a_tick": at, "b_tick": bt, "sim": r.get("sim")})
    return out


def main():
    gold = gold_index()
    pairs = accepted_with_meta() + unmerged_with_meta()
    kept, dropped = [], 0
    for p in pairs:
        g = gold.get(frozenset((p["a"], p["b"])))
        if not g:
            dropped += 1
            continue
        p["gold"] = g
        kept.append(p)
    for i, p in enumerate(kept):
        p["pid"] = i
    acc = [p for p in kept if p["set"] == "accepted"]
    unm = [p for p in kept if p["set"] == "unmerged"]
    withmeta = sum(1 for p in acc if p["a_owners"] and p["b_owners"])
    json.dump({"pairs": kept}, open("runs/judge_evalset.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(f"accepted {len(acc)}  (gold SAME {sum(p['gold']=='SAME' for p in acc)}), "
          f"owners known on both sides for {withmeta}")
    print(f"unmerged {len(unm)}  (gold SAME {sum(p['gold']=='SAME' for p in unm)})")
    print(f"dropped {dropped} pairs with no gold label")
    print("wrote runs/judge_evalset.json")


if __name__ == "__main__":
    main()
