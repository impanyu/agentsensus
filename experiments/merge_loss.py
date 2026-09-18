"""What the keep-the-shorter merge rule discards.

When the consensus store merges two memory items it keeps whichever text is
shorter. Under the equivalence criterion the system actually uses -- two items
are the same if they describe the same event -- that rule is not neutral,
because among descriptions of one event the shorter one is systematically the
one that omits the principal: "X ordered Y to do Z" is always longer than
"Y did Z". This measures how often the surviving text loses a named character,
and how often the lost character is the one who ordered the act.

Characters are resolved through the scenario registry so that aliases of one
person (Liu Xie / Emperor Xian) collapse to a single id and do not count as a
loss.

Population: the merges whose two input texts can both be recovered from the
event log; the log records the surviving text, so the discarded side is only
observable for merges that rewrote a row or deposited a single atom. That is a
minority of all merges and the fraction is reported alongside.

No LLM calls and no simulation: arithmetic over runs already on disk.

Run: venv/bin/python -m experiments.merge_loss   -> runs/merge_loss.json
"""
import json
import os
import re
import statistics as st
import sys

os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); sys.path.insert(0, ".")

WORLDS = [("three_kingdoms", "Three Kingdoms", "g80full_consensus",
           "scenarios/three_kingdoms.yaml.registry.json"),
          ("red_chamber", "Red Chamber", "rc80full_consensus",
           "scenarios/red_chamber.yaml.registry.json"),
          ("russia_ukraine", "Russia--Ukraine", "ru40full_consensus",
           "scenarios/russia_ukraine.yaml.registry.json"),
          ("hamlet", "Hamlet", "hl40full_consensus",
           "scenarios/hamlet.yaml.registry.json")]

# verbs that put the named party above the act rather than performing it
ORDER = ("命|令|下令|命令|指示|吩咐|交代|授权|准许|批准|差|遣|派|安排|建议|"
         r"嘱|叮嘱|委托|请|ordered|order|authoriz|authoris|instruct|direct|"
         "command|requested|request|urged|approved|told|sent|asked")
ORDER_RE = re.compile(ORDER, re.I)
NEAR = 14          # chars between the name and the verb to call it a command


def surface_to_id(reg_path):
    """Every written form of a character -> one canonical id."""
    m = {}
    if not os.path.exists(reg_path):
        return m
    reg = json.load(open(reg_path, encoding="utf-8"))
    for c in reg.get("characters", []):
        cid = c.get("id") or c.get("name")
        for s in [c.get("name")] + list(c.get("aliases") or []):
            if s and len(s) >= 2:
                m[s] = cid
    return m


def people(text, s2id):
    return {cid for s, cid in s2id.items() if s in text}


def commands(text, s2id, cid):
    """True if `cid` appears in `text` immediately before a command verb."""
    for s, i in s2id.items():
        if i != cid or s not in text:
            continue
        for mt in re.finditer(re.escape(s), text):
            if ORDER_RE.search(text[mt.end():mt.end() + NEAR]):
                return True
    return False


def total_merges(run):
    p = f"runs/{run}/events.jsonl"
    if not os.path.exists(p):
        return 0
    n = 0
    for line in open(p, encoding="utf-8"):
        e = json.loads(line)
        if ((e.get("action") or {}).get("name")) != "remember":
            continue
        d = (e.get("result") or {}).get("data")
        if isinstance(d, list):
            n += sum(1 for r in d if isinstance(r, dict) and r.get("merged"))
    return n


def main():
    pairs = json.load(open("runs/judge_evalset.json", encoding="utf-8"))["pairs"]
    acc = [p for p in pairs if p["set"] == "accepted"]
    maps = {w: surface_to_id(reg) for w, _, _, reg in WORLDS}
    titles = {w: t for w, t, _, _ in WORLDS}

    out, rows = {}, []
    for w, title, run, _ in WORLDS:
        s2id = maps[w]
        mine = [p for p in acc if p["world"] == w]
        if not mine:
            continue
        deltas, lost, princ = [], 0, 0
        for p in mine:
            a, b = p["a"], p["b"]
            keep, drop = (a, b) if len(a) <= len(b) else (b, a)
            deltas.append(len(drop) - len(keep))
            gone = people(drop, s2id) - people(keep, s2id)
            if gone:
                lost += 1
                if any(commands(drop, s2id, c) for c in gone):
                    princ += 1
                rows.append({"world": w, "lost": sorted(gone),
                             "kept": keep, "discarded": drop})
        n = len(mine)
        tot = total_merges(run)
        out[w] = {"title": title, "merges_total": tot, "pairs_recovered": n,
                  "coverage_pct": round(n / tot * 100) if tot else None,
                  "chars_median": st.median(deltas),
                  "chars_mean": round(sum(deltas) / n, 1),
                  "chars_max": max(deltas),
                  "lost_person": lost, "lost_person_pct": round(lost / n * 100),
                  "lost_principal": princ,
                  "lost_principal_pct": round(princ / n * 100)}

    n = len(acc)
    tot = sum(v["merges_total"] for v in out.values())
    L = sum(v["lost_person"] for v in out.values())
    P = sum(v["lost_principal"] for v in out.values())
    alld = []
    for w, _, _, _ in WORLDS:
        for p in acc:
            if p["world"] == w:
                alld.append(abs(len(p["a"]) - len(p["b"])))
    overall = {"merges_total": tot, "pairs_recovered": n,
               "coverage_pct": round(n / tot * 100),
               "chars_median": st.median(alld),
               "chars_mean": round(sum(alld) / n, 1), "chars_max": max(alld),
               "lost_person": L, "lost_person_pct": round(L / n * 100),
               "lost_principal": P, "lost_principal_pct": round(P / n * 100)}

    json.dump({"overall": overall, "worlds": out, "examples": rows},
              open("runs/merge_loss.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

    print(f"{'world':<16}{'merges':>8}{'recov':>7}{'cov%':>6}"
          f"{'chars med':>11}{'lost person':>13}{'of which principal':>20}")
    for w, v in out.items():
        print(f"{titles[w]:<16}{v['merges_total']:>8}{v['pairs_recovered']:>7}"
              f"{v['coverage_pct']:>6}{v['chars_median']:>11}"
              f"{v['lost_person']:>6} ({v['lost_person_pct']:>2}%)"
              f"{v['lost_principal']:>12} ({v['lost_principal_pct']:>2}%)")
    o = overall
    print(f"{'ALL':<16}{o['merges_total']:>8}{o['pairs_recovered']:>7}"
          f"{o['coverage_pct']:>6}{o['chars_median']:>11}"
          f"{o['lost_person']:>6} ({o['lost_person_pct']:>2}%)"
          f"{o['lost_principal']:>12} ({o['lost_principal_pct']:>2}%)")
    print("\nwrote runs/merge_loss.json")


if __name__ == "__main__":
    main()
