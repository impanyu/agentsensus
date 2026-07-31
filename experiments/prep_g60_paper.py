"""Prepare all data/figures for the 60-tick paper build.

- merges g20+g40+g60 events into runs/g60full_consensus (+ g60 ltm copy)
- computes a stats JSON (runs/paper_stats_g60.json): per-backend structure,
  consensus relation means, auto-expand usage, merge examples, horizon growth
- generates summary figures (sim footprint / structure bars) and the NEW
  horizon-growth figure into runs/paper_figs_g60/

Run AFTER the g60 sims finish. Case-study figures are generated separately by
case_study{,_graphs,_trilayer}.py on runs/g60full_consensus.
"""
import os, sys, json, random, shutil
from collections import Counter, defaultdict

os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); sys.path.insert(0, ".")
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

random.seed(7)
KINDS = ["consensus", "generative_agents", "g_memory", "collaborative"]
STAGES = ["g20", "g40", "g60"]
SIM_SRC = {"runtime", "act_on"}

# ---- merged run dir for case study ----
os.makedirs("runs/g60full_consensus", exist_ok=True)
with open("runs/g60full_consensus/events.jsonl", "w", encoding="utf-8") as out:
    for st in STAGES:
        p = f"runs/{st}_consensus/events.jsonl"
        if os.path.exists(p):
            out.write(open(p, encoding="utf-8").read())
shutil.copy("runs/g60_consensus/ltm_final.json", "runs/g60full_consensus/ltm_final.json")

stats = {}

# ---- per-backend structure at 60 ticks ----
for k in KINDS:
    d = json.load(open(f"runs/g60_{k}/ltm_final.json", encoding="utf-8"))
    sn = [e for e in d if (e.get("meta") or {}).get("source") in SIM_SRC]
    sh = [e for e in sn if len(e.get("owners", [])) >= 2]
    aff = sum(1 for e in sn if e.get("affiliated"))
    stats[k] = {"sim_new": len(sn), "multi_owner": len(sh),
                "sh_pct": round(100 * len(sh) / max(len(sn), 1)),
                "aff_pct": round(100 * aff / max(len(sn), 1))}
    if k == "consensus":
        big = sorted([e for e in sh if len(e["owners"]) >= 3], key=lambda e: -len(e["owners"]))
        stats["merge_examples"] = [
            {"owners": e["owners"], "text": e["text"][:60]} for e in big[:3]
        ] + [{"owners": e["owners"], "text": e["text"][:60]} for e in sh[:2]]
        stats["max_owners"] = max((len(e["owners"]) for e in sh), default=1)
        stats["n_3plus"] = len(big)

# ---- consensus horizon growth (20/40/60) ----
growth = {"ticks": [20, 40, 60], "sim_new": [], "multi_owner": [], "aff_edges": []}
for st in STAGES:
    d = json.load(open(f"runs/{st}_consensus/ltm_final.json", encoding="utf-8"))
    sn = [e for e in d if (e.get("meta") or {}).get("source") in SIM_SRC]
    ids = {e["id"] for e in sn}
    edges = 0
    for e in sn:
        for a in (e.get("affiliated") or []):
            if a in ids and a > e["id"]:
                edges += 1
    growth["sim_new"].append(len(sn))
    growth["multi_owner"].append(sum(1 for e in sn if len(e.get("owners", [])) >= 2))
    growth["aff_edges"].append(edges)
stats["growth"] = growth

# ---- relations + auto-expand on the merged 60-tick consensus run ----
d = json.load(open("runs/g60full_consensus/ltm_final.json", encoding="utf-8"))
sn = [e for e in d if (e.get("meta") or {}).get("source") in SIM_SRC]
byid = {e["id"]: e for e in sn}
owners = {e["id"]: set(e["owners"]) for e in sn}
say = Counter()
va = tot = exp_items = 0
for line in open("runs/g60full_consensus/events.jsonl", encoding="utf-8"):
    e = json.loads(line)
    if e.get("kind") == "message" and e["message"].get("kind") == "say":
        m = e["message"]
        for r in m.get("recipients", []):
            if r != m["sender"]:
                say[tuple(sorted((m["sender"], r)))] += 1
    elif e.get("kind") == "action" and (e.get("action") or {}).get("name") == "recall":
        tot += 1
        data = (e.get("result") or {}).get("data") or []
        n = sum(1 for x in data if isinstance(x, dict) and x.get("via_affiliated"))
        if n:
            va += 1
        exp_items += n
stats["auto_expand"] = {"recalls": tot, "with_expansion": va, "items": exp_items}

mem_of = defaultdict(set)
for mid, ow in owners.items():
    for o in ow:
        mem_of[o].add(mid)
agents = sorted(mem_of)
talk = set(say)
def jac(a, b):
    u = a | b
    return len(a & b) / len(u) if u else 0.0
tj, nj = [], []
for i, a in enumerate(agents):
    for b in agents[i + 1:]:
        p = tuple(sorted((a, b)))
        (tj if p in talk else nj).append(jac(mem_of[a], mem_of[b]))
aff_edges = []
for e in sn:
    for a in (e.get("affiliated") or []):
        if a in byid and a > e["id"]:
            aff_edges.append((e["id"], a))
edge = {tuple(sorted(x)) for x in aff_edges}
ids = list(byid)
aj = [jac(owners[u], owners[v]) for u, v in aff_edges]
nj2 = []
seen = 0
allp = [(ids[i], ids[j]) for i in range(len(ids)) for j in range(i + 1, len(ids))]
random.shuffle(allp)
for p in allp:
    if tuple(sorted(p)) in edge:
        continue
    nj2.append(jac(owners[p[0]], owners[p[1]]))
    seen += 1
    if seen >= 20000:
        break
te, ne = [], []
for i, a in enumerate(agents):
    for b in agents[i + 1:]:
        p = tuple(sorted((a, b)))
        n_e = sum(1 for u, v in aff_edges
                  if (u in mem_of[a] and v in mem_of[b]) or (u in mem_of[b] and v in mem_of[a]))
        (te if p in talk else ne).append(n_e)
m = lambda x: sum(x) / max(len(x), 1)
stats["relations"] = {
    "AO": {"talk_n": len(tj), "talk_mean": round(m(tj), 4), "non_n": len(nj), "non_mean": round(m(nj), 4)},
    "MO": {"link_n": len(aj), "link_mean": round(m(aj), 3), "non_mean": round(m(nj2), 3)},
    "AM": {"talk_mean": round(m(te), 2), "non_mean": round(m(ne), 3)},
}

json.dump(stats, open("runs/paper_stats_g60.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(json.dumps({k: v for k, v in stats.items() if k != "merge_examples"}, ensure_ascii=False))

# ---- figures ----
os.makedirs("runs/paper_figs_g60", exist_ok=True)
LBL = {"consensus": "Consensus", "generative_agents": "Gen.Agents", "g_memory": "G-Memory", "collaborative": "Collab."}
cols = ["#2563eb", "#9ca3af", "#9ca3af", "#9ca3af"]

fig, ax = plt.subplots(figsize=(5, 3.0))
ys = [stats[k]["sim_new"] for k in KINDS]
ax.bar([LBL[k] for k in KINDS], ys, color=cols)
for i, y in enumerate(ys):
    ax.text(i, y + 15, str(y), ha="center", fontsize=9)
ax.set_ylabel("sim-generated memory entries")
ax.set_title("Sim-memory footprint, 60 ticks (uniform atomization)")
ax.set_ylim(0, max(ys) * 1.22)
plt.tight_layout(); plt.savefig("runs/paper_figs_g60/sim_footprint.png", dpi=140); plt.close()

fig, ax = plt.subplots(figsize=(5.6, 3.0))
x = np.arange(4); w = 0.38
sh = [stats[k]["sh_pct"] for k in KINDS]; af = [stats[k]["aff_pct"] for k in KINDS]
b1 = ax.bar(x - w / 2, sh, w, label="multi-owner (shared)", color="#2563eb")
b2 = ax.bar(x + w / 2, af, w, label="with affiliated links", color="#7c9ff5")
for b in list(b1) + list(b2):
    if b.get_height() > 0:
        ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 1.4, f"{b.get_height():.0f}%", ha="center", fontsize=8)
ax.set_xticks(x); ax.set_xticklabels([LBL[k] for k in KINDS])
ax.set_ylabel("% of sim memories"); ax.set_title("Memory structure in the sim (shared + graph)")
ax.legend(fontsize=8); ax.set_ylim(0, 112)
plt.tight_layout(); plt.savefig("runs/paper_figs_g60/structure.png", dpi=140); plt.close()

g = stats["growth"]
fig, axes = plt.subplots(1, 3, figsize=(10.5, 2.9))
for axp, key, title, color in [
        (axes[0], "sim_new", "sim memories", "#2563eb"),
        (axes[1], "multi_owner", "shared (multi-owner) memories", "#d63b3b"),
        (axes[2], "aff_edges", "affiliated edges", "#10b981")]:
    axp.plot(g["ticks"], g[key], marker="o", color=color, lw=2)
    for xx, yy in zip(g["ticks"], g[key]):
        axp.annotate(str(yy), (xx, yy), textcoords="offset points", xytext=(0, 7), ha="center", fontsize=8)
    axp.set_xticks(g["ticks"]); axp.set_xlabel("tick"); axp.set_title(title, fontsize=9.5)
    axp.set_ylim(0, max(g[key]) * 1.25)
plt.tight_layout(); plt.savefig("runs/paper_figs_g60/growth.png", dpi=140); plt.close()
print("figs -> runs/paper_figs_g60/ (sim_footprint, structure, growth)")
