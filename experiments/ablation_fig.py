"""The ablation figure: what each knob does to the store (三国, 40 rounds).

Two panels over the four one-factor-at-a-time cells:
  left   store size -- the whole store and the simulation-written part,
         which is where turning the merge off is visible (3x)
  right  the two structural properties, sharing and linking, which is
         where they come apart: merge off zeroes sharing and leaves
         linking untouched

Run: venv/bin/python -m experiments.ablation_fig
"""
import json
import os
import sys

os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); sys.path.insert(0, ".")
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from PIL import Image

CELLS = [("on_fifo", "merge on\nfifo"), ("on_relevance", "merge on\nrelevance"),
         ("on_hybrid", "merge on\nhybrid"), ("off_fifo", "merge OFF\nfifo")]
COL = {"on_fifo": "#2563eb", "on_relevance": "#0891b2",
       "on_hybrid": "#0d9488", "off_fifo": "#ef4444"}
OUT = "runs/paper_figs_ablation"

A = json.load(open("runs/ablation_results.json", encoding="utf-8"))
FP = {c: json.load(open(f"runs/abl_{c}/result.json", encoding="utf-8"))["footprint"]
      for c, _ in CELLS}

os.makedirs(OUT, exist_ok=True)
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10.5, 3.4))

x = range(len(CELLS))
whole = [FP[c]["entries"] for c, _ in CELLS]
sim = [A[c]["sim_new"] for c, _ in CELLS]
ax1.bar([i - 0.19 for i in x], whole, 0.36, color=[COL[c] for c, _ in CELLS],
        label="whole store")
ax1.bar([i + 0.19 for i in x], sim, 0.36, color=[COL[c] for c, _ in CELLS],
        alpha=0.45, label="written during simulation")
for i, (w, s) in enumerate(zip(whole, sim)):
    ax1.text(i - 0.19, w + 400, f"{w:,}", ha="center", fontsize=8)
    ax1.text(i + 0.19, s + 400, f"{s}", ha="center", fontsize=8)
ax1.set_ylim(0, max(whole) * 1.18)
ax1.set_title("entries in the store", fontsize=10)
ax1.legend(fontsize=8, frameon=False, loc="upper left")

sh = [A[c]["sh_pct"] for c, _ in CELLS]
af = [A[c]["aff_pct"] for c, _ in CELLS]
ax2.bar([i - 0.19 for i in x], sh, 0.36, color=[COL[c] for c, _ in CELLS],
        label="shared (multi-owner)")
ax2.bar([i + 0.19 for i in x], af, 0.36, color=[COL[c] for c, _ in CELLS],
        alpha=0.45, label="linked (affiliated)")
for i, (s, a) in enumerate(zip(sh, af)):
    ax2.text(i - 0.19, s + 2.5, f"{s}%", ha="center", fontsize=8)
    ax2.text(i + 0.19, a + 2.5, f"{a}%", ha="center", fontsize=8)
ax2.set_ylim(0, 118)
ax2.set_title("structure of the simulation-written entries", fontsize=10)
ax2.legend(fontsize=8, frameon=False, loc="upper left")

for ax in (ax1, ax2):
    ax.set_xticks(list(x))
    ax.set_xticklabels([l for _, l in CELLS], fontsize=8)

plt.tight_layout()
path = f"{OUT}/ablation.png"
plt.savefig(path, dpi=140); plt.close()
Image.open(path).convert("RGB").quantize(colors=128).save(
    path.replace(".png", "_q.png"), optimize=True)
print("wrote", path)
