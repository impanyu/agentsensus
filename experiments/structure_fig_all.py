"""One figure for the structural claim: consensus sharing and linking in all
four worlds, side by side.

Replaces the per-scenario footprint/structure panels -- entry counts now live
in Table 1, and the baselines are 0% on both measures everywhere, so the only
thing left to plot is how the consensus store's structure varies by world.

Run: venv/bin/python -m experiments.structure_fig_all
"""
import json
import os
import sys

os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); sys.path.insert(0, ".")
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from PIL import Image

WORLDS = [("三国演义\n80 rounds", "paper_stats_g80"),
          ("红楼梦\n80 rounds", "paper_stats_rc80"),
          ("Russia–Ukraine\n40 rounds", "paper_stats_ru40"),
          ("Hamlet\n30 rounds", "paper_stats_hl30")]
OUT = "runs/paper_figs_all"
os.makedirs(OUT, exist_ok=True)

plt.rcParams["font.sans-serif"] = ["Heiti TC", "Songti SC", "Arial Unicode MS", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

shared, linked, labels = [], [], []
for label, stats in WORLDS:
    c = json.load(open(f"runs/{stats}.json", encoding="utf-8"))["consensus"]
    labels.append(label)
    shared.append(c["sh_pct"])
    linked.append(c["aff_pct"])

x = np.arange(len(labels))
w = 0.36
fig, ax = plt.subplots(figsize=(7.2, 3.4))
b1 = ax.bar(x - w / 2, shared, w, label="shared (multi-owner)", color="#2563eb")
b2 = ax.bar(x + w / 2, linked, w, label="linked (affiliated)", color="#7c9ff5")
for bars in (b1, b2):
    for b in bars:
        ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 2,
                f"{b.get_height():.0f}%", ha="center", fontsize=9)
ax.set_xticks(x)
ax.set_xticklabels(labels, fontsize=9)
ax.set_ylabel("% of consensus sim memories")
ax.set_ylim(0, 132)
ax.legend(fontsize=9, loc="upper center", ncols=2, frameon=False,
          bbox_to_anchor=(0.5, 1.02))
ax.text(0.5, 0.86, "every baseline, both measures: 0% in all four worlds",
        transform=ax.transAxes, fontsize=9, color="#5b6472", ha="center")
plt.tight_layout()
plt.savefig(f"{OUT}/structure_all.png", dpi=140)
plt.close()
Image.open(f"{OUT}/structure_all.png").convert("RGB").quantize(colors=128).save(
    f"{OUT}/structure_all_q.png", optimize=True)
print(f"{OUT}/structure_all.png", dict(zip(labels, zip(shared, linked))))
