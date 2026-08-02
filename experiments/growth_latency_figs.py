"""§5.1 curves for the paper (run after g80 + latency replays finish):

  growth_total.png   -- cumulative sim-generated memory entries vs tick, 4 backends
  growth_agents.png  -- per-agent owned sim-memory count vs tick (consensus run)
  latency.png        -- mean remember / recall latency vs tick, 4 backends
                        (ticks 1-60 replay-measured, 61-80 live-instrumented)

Outputs (128-color quantized copies too) into runs/paper_figs_g60/.
"""
import os, sys, json
from collections import defaultdict

os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); sys.path.insert(0, ".")
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from PIL import Image

KINDS = ["consensus", "generative_agents", "g_memory", "collaborative"]
LBL = {"consensus": "Consensus", "generative_agents": "Gen.Agents",
       "g_memory": "G-Memory", "collaborative": "Collab."}
COL = {"consensus": "#2563eb", "generative_agents": "#10b981",
       "g_memory": "#f59e0b", "collaborative": "#ef4444"}
STAGES = [("g20", 0, 20), ("g40", 20, 40), ("g60", 40, 60), ("g80", 60, 80)]
OUT = "runs/paper_figs_g60"


def quantize(p):
    im = Image.open(p).convert("RGB").quantize(colors=128)
    im.save(p.replace(".png", "_q.png"), optimize=True)


# ---------- 1) total sim-generated entries vs tick ----------
fig, ax = plt.subplots(figsize=(6.4, 3.2))
for k in KINDS:
    curve = []
    for st, a, b in STAGES:
        r = json.load(open(f"runs/{st}_{k}/result.json"))
        ptm = r["per_tick_memory"]
        sed = json.load(open(f"runs/g20_{k}/result.json"))["sediment_memories"]
        seg = ptm[a:b] if len(ptm) > (b - a) else ptm      # resumed stages backfill 0..b
        curve += [v - sed for v in seg]
    ax.plot(range(1, len(curve) + 1), curve, label=LBL[k], color=COL[k], lw=1.8)
ax.set_xlabel("tick"); ax.set_ylabel("cumulative sim-generated entries")
ax.set_title("System memory growth (sim-only), 80 ticks")
ax.legend(fontsize=8); ax.margins(x=0.01)
plt.tight_layout(); plt.savefig(f"{OUT}/growth_total.png", dpi=140); plt.close()
quantize(f"{OUT}/growth_total.png")

# ---------- 2) per-agent owned sim memories vs tick (consensus) ----------
d = json.load(open("runs/g80_consensus/ltm_final.json", encoding="utf-8"))
sim = [e for e in d if (e.get("meta") or {}).get("source") in ("runtime", "act_on")]
per = defaultdict(lambda: np.zeros(81))
for e in sim:
    t = int((e.get("meta") or {}).get("tick", 0) or 0)
    t = min(max(t, 0), 80)
    for o in e.get("owners", []):
        per[o][t:] += 1                       # owned from its creation tick onward
fig, ax = plt.subplots(figsize=(6.4, 3.6))
finals = sorted(per.items(), key=lambda kv: -kv[1][-1])
top = {k for k, _ in finals[:6]}
for aid, curve in finals:
    if aid in top:
        ax.plot(range(81), curve, lw=1.7, label=aid)
    else:
        ax.plot(range(81), curve, lw=0.6, color="#9ca3af", alpha=0.5)
ax.set_xlabel("tick"); ax.set_ylabel("owned sim memories")
ax.set_title("Per-agent memory growth (consensus run; top 6 labeled, others gray)")
ax.legend(fontsize=7.5, ncols=2); ax.margins(x=0.01)
plt.tight_layout(); plt.savefig(f"{OUT}/growth_agents.png", dpi=140); plt.close()
quantize(f"{OUT}/growth_agents.png")

# ---------- 3) remember / recall latency vs tick ----------
def load_ops(kind):
    ops = []
    for st, a, b in STAGES[:3]:
        p = f"runs/{st}_{kind}/mem_ops_replay.jsonl"
        if os.path.exists(p):
            ops += [json.loads(l) for l in open(p, encoding="utf-8")]
    p = f"runs/g80_{kind}/mem_ops.jsonl"
    if os.path.exists(p):
        ops += [json.loads(l) for l in open(p, encoding="utf-8")]
    return ops

fig, axes = plt.subplots(1, 2, figsize=(10.5, 3.3), sharex=True)
BIN = 5   # 5-tick bins: per-tick op counts are small, bin for stable means
for ax, op, title in [(axes[0], "remember", "remember latency"),
                      (axes[1], "recall", "recall latency")]:
    for k in KINDS:
        buck = defaultdict(list)
        for r in load_ops(k):
            if r["op"] == op:
                buck[min(int(r["tick"]) // BIN, 15)].append(r["s"])
        xs = sorted(buck)
        if not xs:
            continue
        ax.plot([x * BIN + BIN / 2 for x in xs], [np.mean(buck[x]) for x in xs],
                marker="o", ms=3, lw=1.6, label=LBL[k], color=COL[k])
    ax.axvline(60, color="#9ca3af", ls=":", lw=1)
    ax.text(60.5, ax.get_ylim()[1] * 0.92, "replay | live", fontsize=7, color="#9ca3af")
    ax.set_xlabel("tick"); ax.set_title(title, fontsize=10)
axes[0].set_ylabel(f"mean seconds per call ({BIN}-tick bins)")
axes[0].legend(fontsize=8)
plt.tight_layout(); plt.savefig(f"{OUT}/latency.png", dpi=140); plt.close()
quantize(f"{OUT}/latency.png")
print("figs -> growth_total / growth_agents / latency (+_q)")
