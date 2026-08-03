"""Render runs/paper_figs_ru40/quality.png (+ 128-color _q copy) from
runs/results_ru40.json, same style as the 三国 quality figure.

Run: venv/bin/python -m experiments.quality_fig_ru40
"""
import os, sys, json

os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); sys.path.insert(0, ".")
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from PIL import Image

KINDS = ["consensus", "generative_agents", "g_memory", "collaborative"]
LBL = {"consensus": "Consensus", "generative_agents": "Gen.Agents",
       "g_memory": "G-Memory", "collaborative": "Collab."}
COL = {"consensus": "#2563eb", "generative_agents": "#10b981",
       "g_memory": "#f59e0b", "collaborative": "#ef4444"}

Q = json.load(open("runs/results_ru40.json", encoding="utf-8"))
PANELS = [("grnd", "grounding (0-1)", 1.18), ("traj", "trajectory (0-1)", 1.18),
          ("narr", "narrative (1-5)", 5.9)]

fig, axes = plt.subplots(1, 3, figsize=(10.5, 3.1))
for ax, (key, title, ymax) in zip(axes, PANELS):
    for i, k in enumerate(KINDS):
        a = Q[k]["agg"][key]
        ax.bar(i, a["mean"], 0.62, yerr=a["std"], capsize=4, color=COL[k],
               error_kw={"ecolor": "#374151", "lw": 1.2})
        ax.text(i, a["mean"] + ymax * 0.035, f"{a['mean']:.2f}", ha="center", fontsize=9)
    ax.set_xticks(range(4))
    ax.set_xticklabels([LBL[k] for k in KINDS], rotation=15, fontsize=8)
    ax.set_title(title, fontsize=10)
    ax.set_ylim(0, ymax)
plt.tight_layout()
out = "runs/paper_figs_ru40/quality.png"
plt.savefig(out, dpi=140); plt.close()
Image.open(out).convert("RGB").quantize(colors=128).save(out.replace(".png", "_q.png"), optimize=True)
print("wrote", out)
