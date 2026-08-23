"""Memory-operation latency across the ablation cells (三国, 40 rounds).

Figure 5 of the paper reads this way for the four backends; this is the same
plot for the four one-factor-at-a-time cells, which answers what the merge
and the cache policy cost per call rather than what they cost in total. Every
cell here is instrumented live -- these runs were not replayed -- so there is
no replay/live divider.

Run: venv/bin/python -m experiments.ablation_latency_fig
"""
import json
import os
import sys
from collections import defaultdict

os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); sys.path.insert(0, ".")
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image

CELLS = [("on_fifo", "merge on, fifo", "#2563eb"),
         ("on_relevance", "merge on, relevance", "#0891b2"),
         ("on_hybrid", "merge on, hybrid", "#0d9488"),
         ("off_fifo", "merge OFF, fifo", "#ef4444")]
BIN = 5
OUT = "runs/paper_figs_ablation"


def ops(cell):
    p = f"runs/abl_{cell}/mem_ops.jsonl"
    return [json.loads(l) for l in open(p, encoding="utf-8")] if os.path.exists(p) else []


def main():
    os.makedirs(OUT, exist_ok=True)
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 3.3), sharex=True)
    summary = {}
    for ax, op, title in [(axes[0], "remember", "remember latency"),
                          (axes[1], "recall", "recall latency")]:
        for cell, label, colour in CELLS:
            buck = defaultdict(list)
            for r in ops(cell):
                if r["op"] == op:
                    buck[int(r["tick"]) // BIN].append(r["s"])
            xs = sorted(buck)
            if not xs:
                continue
            ax.plot([x * BIN + BIN / 2 for x in xs], [np.mean(buck[x]) for x in xs],
                    marker="o", ms=3, lw=1.6, label=label, color=colour)
            allv = [v for x in xs for v in buck[x]]
            summary.setdefault(cell, {})[op] = (float(np.mean(allv)), len(allv))
        ax.set_xlabel("round"); ax.set_title(title, fontsize=10)
    axes[0].set_ylabel(f"mean seconds per call ({BIN}-round bins)")
    axes[0].legend(fontsize=8)
    plt.tight_layout()
    path = f"{OUT}/ablation_latency.png"
    plt.savefig(path, dpi=140); plt.close()
    Image.open(path).convert("RGB").quantize(colors=128).save(
        path.replace(".png", "_q.png"), optimize=True)
    print("wrote", path)
    for cell, label, _ in CELLS:
        s = summary.get(cell, {})
        r = s.get("remember", (0, 0)); c = s.get("recall", (0, 0))
        print(f"  {label:22} remember {r[0]:6.1f}s (n={r[1]:3})   "
              f"recall {c[0]:5.2f}s (n={c[1]:3})")


if __name__ == "__main__":
    main()
