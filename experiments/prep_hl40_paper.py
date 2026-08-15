"""Prepare all data/figures for the Hamlet 40-round paper section.

- computes runs/paper_stats_hl40.json (same schema as paper_stats_hl40.json)
- generates runs/paper_figs_hl40/{sim_footprint,structure,growth,latency}.png
  (+ 128-color quantized copies)

Single-stage pilot: no event-stream merging needed; the case study runs
on the merged runs/hl40full_consensus (export_graph_json.py + case_study_trilayer.py).
"""
import os, sys, json, random, shutil
from collections import Counter, defaultdict

os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); sys.path.insert(0, ".")
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from PIL import Image

random.seed(7)
KINDS = ["consensus", "generative_agents", "g_memory", "collaborative"]
LBL = {"consensus": "Consensus", "generative_agents": "Gen.Agents",
       "g_memory": "G-Memory", "collaborative": "Collab."}
COL = {"consensus": "#2563eb", "generative_agents": "#10b981",
       "g_memory": "#f59e0b", "collaborative": "#ef4444"}
SIM_SRC = {"runtime", "act_on"}
T = 40
OUT = "runs/paper_figs_hl40"
os.makedirs(OUT, exist_ok=True)


def quantize(p):
    im = Image.open(p).convert("RGB").quantize(colors=128)
    im.save(p.replace(".png", "_q.png"), optimize=True)


# ---- merged consensus run dir for the case study ----
os.makedirs("runs/hl40full_consensus", exist_ok=True)
with open("runs/hl40full_consensus/events.jsonl", "w", encoding="utf-8") as out:
    for st in ("hl20", "hl30", "hl40"):
        out.write(open(f"runs/{st}_consensus/events.jsonl", encoding="utf-8").read())
shutil.copy("runs/hl40_consensus/ltm_final.json", "runs/hl40full_consensus/ltm_final.json")

stats = {}

# ---- per-backend structure at 20 ticks ----
for k in KINDS:
    d = json.load(open(f"runs/hl40_{k}/ltm_final.json", encoding="utf-8"))
    sn = [e for e in d if (e.get("meta") or {}).get("source") in SIM_SRC]
    sh = [e for e in sn if len(e.get("owners", [])) >= 2]
    aff = sum(1 for e in sn if e.get("affiliated"))
    stats[k] = {"sim_new": len(sn), "multi_owner": len(sh),
                "sh_pct": round(100 * len(sh) / max(len(sn), 1)),
                "aff_pct": round(100 * aff / max(len(sn), 1))}
    if k == "consensus":
        big = sorted([e for e in sh if len(e["owners"]) >= 3], key=lambda e: -len(e["owners"]))
        stats["merge_examples"] = [
            {"owners": e["owners"], "text": e["text"][:200]} for e in (big + sh)[:5]
        ]
        stats["max_owners"] = max((len(e["owners"]) for e in sh), default=1)
        stats["n_3plus"] = len(big)

# ---- relations + auto-expand on the merged consensus run ----
d = json.load(open("runs/hl40full_consensus/ltm_final.json", encoding="utf-8"))
sn = [e for e in d if (e.get("meta") or {}).get("source") in SIM_SRC]
byid = {e["id"]: e for e in sn}
owners = {e["id"]: set(e["owners"]) for e in sn}
say = Counter()
va = tot = exp_items = 0
for line in open("runs/hl40full_consensus/events.jsonl", encoding="utf-8"):
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

json.dump(stats, open("runs/paper_stats_hl40.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print(json.dumps({k: v for k, v in stats.items() if k != "merge_examples"}, ensure_ascii=False))

# ---- fig: sim footprint ----
fig, ax = plt.subplots(figsize=(5, 3.0))
ys = [stats[k]["sim_new"] for k in KINDS]
ax.bar([LBL[k] for k in KINDS], ys, color=["#2563eb", "#9ca3af", "#9ca3af", "#9ca3af"])
for i, y in enumerate(ys):
    ax.text(i, y + max(ys) * 0.02, str(y), ha="center", fontsize=9)
ax.set_ylabel("sim-generated memory entries")
ax.set_title("Sim-memory footprint, 40 rounds (uniform atomization)")
ax.set_ylim(0, max(ys) * 1.22)
plt.tight_layout(); plt.savefig(f"{OUT}/sim_footprint.png", dpi=140); plt.close()
quantize(f"{OUT}/sim_footprint.png")

# ---- fig: structure ----
fig, ax = plt.subplots(figsize=(5.6, 3.0))
x = np.arange(4); w = 0.38
sh = [stats[k]["sh_pct"] for k in KINDS]; af = [stats[k]["aff_pct"] for k in KINDS]
b1 = ax.bar(x - w / 2, sh, w, label="multi-owner (shared)", color="#2563eb")
b2 = ax.bar(x + w / 2, af, w, label="with affiliated links", color="#7c9ff5")
for b in list(b1) + list(b2):
    if b.get_height() > 0:
        ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 1.4,
                f"{b.get_height():.0f}%", ha="center", fontsize=8)
ax.set_xticks(x); ax.set_xticklabels([LBL[k] for k in KINDS])
ax.set_ylabel("% of sim memories"); ax.set_title("Memory structure in the sim (shared + graph)")
ax.legend(fontsize=8); ax.set_ylim(0, 112)
plt.tight_layout(); plt.savefig(f"{OUT}/structure.png", dpi=140); plt.close()
quantize(f"{OUT}/structure.png")

# ---- fig: growth (system + per-agent, two panels) ----
fig, axes = plt.subplots(1, 2, figsize=(10.5, 3.3))
ax = axes[0]
for k in KINDS:
    d = json.load(open(f"runs/hl40_{k}/ltm_final.json", encoding="utf-8"))
    curve = np.zeros(T + 1)
    for e in d:
        mm = e.get("meta") or {}
        if mm.get("source") in SIM_SRC:
            t = min(max(int(mm.get("tick", 0) or 0), 0), T)
            curve[t:] += 1
    ax.plot(range(T + 1), curve, label=LBL[k], color=COL[k], lw=1.8)
ax.set_xlabel("round"); ax.set_ylabel("cumulative sim-generated entries")
ax.set_title("System memory growth (sim-only)")
ax.legend(fontsize=8); ax.margins(x=0.01)

ax = axes[1]
d = json.load(open("runs/hl40full_consensus/ltm_final.json", encoding="utf-8"))
per = defaultdict(lambda: np.zeros(T + 1))
for e in d:
    mm = e.get("meta") or {}
    if mm.get("source") in SIM_SRC:
        t = min(max(int(mm.get("tick", 0) or 0), 0), T)
        for o in e.get("owners", []):
            per[o][t:] += 1
finals = sorted(per.items(), key=lambda kv: -kv[1][-1])
top = {k for k, _ in finals[:6]}
for aid, curve in finals:
    if aid in top:
        ax.plot(range(T + 1), curve, lw=1.7, label=aid)
    else:
        ax.plot(range(T + 1), curve, lw=0.6, color="#9ca3af", alpha=0.5)
ax.set_xlabel("round"); ax.set_ylabel("owned sim memories")
ax.set_title("Per-agent growth (consensus; top 6 labeled)")
ax.legend(fontsize=7, ncols=2); ax.margins(x=0.01)
plt.tight_layout(); plt.savefig(f"{OUT}/growth.png", dpi=140); plt.close()
quantize(f"{OUT}/growth.png")

# ---- fig: latency (remember / recall, 2-round bins, all live) ----
BIN = 2
fig, axes = plt.subplots(1, 2, figsize=(10.5, 3.1))
for ax, op, title in [(axes[0], "remember", "remember latency"),
                      (axes[1], "recall", "recall latency")]:
    for k in KINDS:
        acc = defaultdict(list)
        for st in ("hl20", "hl30", "hl40"):
            p = f"runs/{st}_{k}/mem_ops.jsonl"
            if not os.path.exists(p):
                continue
            for line in open(p, encoding="utf-8"):
                r = json.loads(line)
                if r.get("op") == op:
                    b = min(max(int(r.get("tick", 0) or 0), 1), T)
                    acc[(b - 1) // BIN].append(r["s"])
        xs = sorted(acc)
        ax.plot([b * BIN + BIN / 2 for b in xs], [np.mean(acc[b]) for b in xs],
                marker="o", ms=3.5, label=LBL[k], color=COL[k], lw=1.6)
    ax.set_xlabel("round"); ax.set_ylabel("mean seconds per call")
    ax.set_title(title, fontsize=10); ax.margins(x=0.02)
axes[0].legend(fontsize=8)
plt.tight_layout(); plt.savefig(f"{OUT}/latency.png", dpi=140); plt.close()
quantize(f"{OUT}/latency.png")
print(f"figs -> {OUT}/")
