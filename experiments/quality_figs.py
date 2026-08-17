"""Continuation-quality bar figures, one per world, from the score_all results.

Same panels and style for every world, so the four figures can be read
side by side: grounding (0-1), trajectory (0-1), narrative (1-5), four backends,
bars are means over the repeated scorings with +-1 std whiskers.

Outputs runs/paper_figs_<tag>/quality.png and a 128-color _q copy (the paper
embeds the quantized one).

Run: venv/bin/python -m experiments.quality_figs [world ...]
"""
import json
import os
import sys

os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); sys.path.insert(0, ".")
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from PIL import Image

WORLDS = {"three_kingdoms": ("runs/results_g80.json", "runs/paper_figs_g80"),
          "red_chamber": ("runs/results_rc80.json", "runs/paper_figs_rc80"),
          "russia_ukraine": ("runs/results_ru40.json", "runs/paper_figs_ru40"),
          "hamlet": ("runs/results_hl40.json", "runs/paper_figs_hl40")}
KINDS = ["consensus", "generative_agents", "g_memory", "collaborative"]
LBL = {"consensus": "Consensus", "generative_agents": "Gen.Agents",
       "g_memory": "G-Memory", "collaborative": "Collab."}
COL = {"consensus": "#2563eb", "generative_agents": "#10b981",
       "g_memory": "#f59e0b", "collaborative": "#ef4444"}
PANELS = [("grnd", "grounding (0-1)", 1.18), ("traj", "trajectory (0-1)", 1.18),
          ("narr", "narrative (1-5)", 5.9), ("goal", "goal pursuit (0-1)", 1.18)]


def draw(world):
    src, outdir = WORLDS[world]
    Q = json.load(open(src, encoding="utf-8"))
    os.makedirs(outdir, exist_ok=True)
    panels = [p for p in PANELS if p[0] in next(iter(Q.values()))["agg"]]
    fig, axes = plt.subplots(1, len(panels), figsize=(3.5 * len(panels), 3.1))
    for ax, (key, title, ymax) in zip(axes, panels):
        for i, k in enumerate(KINDS):
            a = Q[k]["agg"][key]
            ax.bar(i, a["mean"], 0.62, yerr=a["std"], capsize=4, color=COL[k],
                   error_kw={"ecolor": "#374151", "lw": 1.2})
            ax.text(i, a["mean"] + a["std"] + ymax * 0.035, f"{a['mean']:.2f}",
                    ha="center", fontsize=9)
        ax.set_xticks(range(4))
        ax.set_xticklabels([LBL[k] for k in KINDS], rotation=15, fontsize=8)
        ax.set_title(title, fontsize=10)
        ax.set_ylim(0, ymax)
    plt.tight_layout()
    out = f"{outdir}/quality.png"
    plt.savefig(out, dpi=140); plt.close()
    Image.open(out).convert("RGB").quantize(colors=128).save(
        out.replace(".png", "_q.png"), optimize=True)
    print("wrote", out)


if __name__ == "__main__":
    for w in (sys.argv[1:] or list(WORLDS)):
        draw(w)
