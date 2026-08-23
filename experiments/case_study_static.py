"""Static renders of the case-study graphs, for the PDF paper.

The HTML paper's interaction graph, ownership heatmap and three-layer figure
are interactive canvases; a PDF cannot carry them, so this draws the same
graphs.json with matplotlib -- same layout coordinates, same data -- one
three-panel figure per world.

Run: venv/bin/python -m experiments.case_study_static
"""
import json
import os
import sys

os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); sys.path.insert(0, ".")
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

WORLDS = [("three_kingdoms", "g80full_consensus"), ("red_chamber", "rc80full_consensus"),
          ("russia_ukraine", "ru40full_consensus"), ("hamlet", "hl40full_consensus")]
COMM = ["#2563eb", "#0f9d6b", "#c07a12", "#d63b3b", "#7c3aed", "#0891b2",
        "#be185d", "#4d7c0f", "#64748b", "#0d9488"]


def draw(world, case):
    G = json.load(open(f"runs/{case}/case_study/graphs.json", encoding="utf-8"))
    tpath = f"runs/{case}/case_study/translations.json"
    names = (json.load(open(tpath, encoding="utf-8")).get("agents", {})
             if os.path.exists(tpath) else {})
    nm = lambda i: names.get(i, i)

    fig, (a1, a2, a3) = plt.subplots(1, 3, figsize=(15, 4.6),
                                     gridspec_kw={"width_ratios": [1.1, 1, 1.3]})

    # --- interaction graph, at the layout the page computed
    I = G["interaction"]; pos = {n["id"]: (n["x"], n["y"]) for n in I["nodes"]}
    wmax = max(e["w"] for e in I["edges"]) or 1
    for e in I["edges"]:
        (x1, y1), (x2, y2) = pos[e["s"]], pos[e["t"]]
        a1.plot([x1, x2], [y1, y2], color="#94a3b8",
                lw=0.5 + 2.5 * e["w"] / wmax, alpha=0.55, zorder=1)
    dmax = max(n["deg"] for n in I["nodes"]) or 1
    for n in I["nodes"]:
        a1.scatter(*pos[n["id"]], s=60 + 340 * n["deg"] / dmax,
                   color=COMM[n.get("comm", 0) % len(COMM)],
                   edgecolors="white", lw=0.8, zorder=2)
    for n in sorted(I["nodes"], key=lambda n: -n["deg"])[:10]:
        a1.annotate(nm(n["id"]), pos[n["id"]], fontsize=6.5,
                    xytext=(0, 6), textcoords="offset points", ha="center")
    a1.set_title("interaction graph", fontsize=10); a1.axis("off")

    # --- ownership heatmap
    H = G["heatmap"]; M = np.array(H["matrix"], dtype=float)
    im = a2.imshow(np.log1p(M), cmap="Blues", aspect="auto")
    labs = [nm(o) for o in H["order"]]
    a2.set_xticks(range(len(labs))); a2.set_yticks(range(len(labs)))
    fs = 6 if len(labs) <= 20 else 4
    a2.set_xticklabels(labs, rotation=90, fontsize=fs)
    a2.set_yticklabels(labs, fontsize=fs)
    a2.set_title("shared-ownership heatmap (log)", fontsize=10)

    # --- three layers: agents above, memories below
    T = G["trilayer"]
    ax_pos = {a["id"]: a["x"] for a in T["agents"]}
    mx = {m["id"]: m["x"] for m in T["mems"]}
    xs = list(ax_pos.values()) + list(mx.values())
    lo, hi = min(xs), max(xs) or 1
    sc = lambda x: (x - lo) / (hi - lo or 1)
    for e in T["aff"]:
        s, t = (e["s"], e["t"]) if isinstance(e, dict) else (e[0], e[1])
        if s in mx and t in mx:
            a3.plot([sc(mx[s]), sc(mx[t])], [0, 0], color="#c7d2fe", lw=0.4,
                    alpha=0.35, zorder=1)
    for e in T["own"]:
        ag, m = e["a"], e["m"]
        if ag in ax_pos and m in mx:
            a3.plot([sc(ax_pos[ag]), sc(mx[m])], [1, 0], color="#94a3b8",
                    lw=0.25, alpha=0.3, zorder=1)
    for e in T["say"]:
        s, t = (e["s"], e["t"]) if isinstance(e, dict) else (e[0], e[1])
        if s in ax_pos and t in ax_pos:
            a3.plot([sc(ax_pos[s]), sc(ax_pos[t])], [1, 1], color="#2563eb",
                    lw=1.0, alpha=0.6, zorder=2)
    a3.scatter([sc(x) for x in mx.values()], [0] * len(mx), s=8,
               color="#6366f1", alpha=0.8, zorder=3)
    a3.scatter([sc(x) for x in ax_pos.values()], [1] * len(ax_pos), s=42,
               color="#0f9d6b", zorder=3)
    for a, x in ax_pos.items():
        a3.annotate(nm(a), (sc(x), 1), fontsize=5, rotation=45,
                    xytext=(0, 8), textcoords="offset points", ha="left")
    a3.set_ylim(-0.25, 1.45); a3.set_yticks([0, 1])
    a3.set_yticklabels(["memories", "agents"], fontsize=8)
    a3.set_xticks([]); [s.set_visible(False) for s in a3.spines.values()]
    a3.set_title("agents / memories / ownership", fontsize=10)

    plt.tight_layout()
    out = f"paper/figures/case_{world}.png"
    plt.savefig(out, dpi=150); plt.close()
    print("wrote", out)


if __name__ == "__main__":
    for w, c in WORLDS:
        draw(w, c)
