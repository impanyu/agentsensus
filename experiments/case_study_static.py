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


import textwrap


def draw(world, case):
    G = json.load(open(f"runs/{case}/case_study/graphs.json", encoding="utf-8"))
    tpath = f"runs/{case}/case_study/translations.json"
    tr = json.load(open(tpath, encoding="utf-8")) if os.path.exists(tpath) else {}
    names, texts = tr.get("agents", {}), tr.get("texts", {})
    nm = lambda i: names.get(i, i)
    en = lambda t: texts.get(t, t)

    # four quadrants at one proportion: every panel is boxed 4:3, so the
    # grid reads as a grid rather than a jumble of aspect ratios
    fig, ((a1, a4), (a2, a3)) = plt.subplots(2, 2, figsize=(13.2, 10.6))
    for _ax in (a1, a2, a3, a4):
        _ax.set_box_aspect(0.75)

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
    a1.set_title("(a) interaction graph", fontsize=10); a1.axis("off")

    # --- memory-affiliation graph, annotated: a few nodes from different
    # clusters circled, with the memory's English text and owner set
    A = G["affiliation"]
    apos = {n["id"]: (n["x"], n["y"]) for n in A["nodes"]}
    from collections import Counter
    csize = Counter(n["comp"] for n in A["nodes"])
    top = [c for c, _ in csize.most_common(8)]
    ccol = {c: COMM[i % len(COMM)] for i, c in enumerate(top)}
    for e in A["edges"]:
        if e["s"] in apos and e["t"] in apos:
            (x1, y1), (x2, y2) = apos[e["s"]], apos[e["t"]]
            a4.plot([x1, x2], [y1, y2], color="#cbd5e1", lw=0.4, alpha=0.5, zorder=1)
    for n in A["nodes"]:
        a4.scatter(n["x"], n["y"], s=26 if n.get("shared") else 12,
                   color=ccol.get(n["comp"], "#cbd5e1"),
                   edgecolors="white", lw=0.4, zorder=2)
    # pick one shared node from each of the three largest clusters, shortest
    # English text first so the callout stays readable
    is_en = lambda t: all(ord(ch) < 0x2E80 for ch in t)   # callouts must render
    picks = []
    for c in top[:3]:
        pool = [n for n in A["nodes"] if n["comp"] == c and is_en(en(n["text"]))]
        cand = [n for n in pool if n.get("shared")] or pool
        cand.sort(key=lambda n: len(en(n["text"])))
        if cand:
            picks.append(cand[0])
    spots = [(0.01, 0.99, "left", "top"), (0.99, 0.01, "right", "bottom"),
             (0.99, 0.99, "right", "top")]
    # assign each pick the spot nearest it (best of all permutations), so the
    # leader lines never cross
    xs_ = [n["x"] for n in A["nodes"]]; ys_ = [n["y"] for n in A["nodes"]]
    xr = (min(xs_), max(xs_)); yr = (min(ys_), max(ys_))
    frac = lambda n: ((n["x"] - xr[0]) / (xr[1] - xr[0] or 1),
                      (n["y"] - yr[0]) / (yr[1] - yr[0] or 1))
    import itertools
    best = min(itertools.permutations(range(len(spots))),
               key=lambda perm: sum(
                   (frac(n)[0] - spots[j][0]) ** 2 + (frac(n)[1] - spots[j][1]) ** 2
                   for n, j in zip(picks, perm)))
    ordered = [spots[j] for j in best]
    for n, (fx, fy, ha, va) in zip(picks, ordered):
        a4.scatter(n["x"], n["y"], s=210, facecolors="none",
                   edgecolors="#111827", lw=1.4, zorder=3)
        owners = n["owners"][:5] + (["\u2026"] if len(n["owners"]) > 5 else [])
        blurb = "\n".join(textwrap.wrap(en(n["text"]), 44)[:3])
        blurb += "\nowners = [" + ", ".join(owners) + "]"
        a4.annotate(blurb, xy=(n["x"], n["y"]), xycoords="data",
                    xytext=(fx, fy), textcoords="axes fraction",
                    ha=ha, va=va, fontsize=5.6, zorder=4,
                    bbox=dict(boxstyle="round,pad=0.35", fc="#fffbeb",
                              ec="#d1d5db", lw=0.6),
                    arrowprops=dict(arrowstyle="-", color="#6b7280", lw=0.7))
    a4.set_title("(b) memory-affiliation graph, coloured by cluster", fontsize=10)
    a4.axis("off")

    # --- ownership heatmap
    H = G["heatmap"]; M = np.array(H["matrix"], dtype=float)
    im = a2.imshow(np.log1p(M), cmap="Blues", aspect="auto")
    labs = [nm(o) for o in H["order"]]
    a2.set_xticks(range(len(labs))); a2.set_yticks(range(len(labs)))
    fs = 6 if len(labs) <= 20 else 4
    a2.set_xticklabels(labs, rotation=90, fontsize=fs)
    a2.set_yticklabels(labs, fontsize=fs)
    a2.set_title("(c) shared-ownership heatmap (log)", fontsize=10)

    # --- (d) a didactic subset of the three layers: a few conversing agents,
    # the memories they own (shared ones emphasized), affiliation arcs among
    # those memories, and a couple of memories labelled with their text
    T = G["trilayer"]
    say = sorted((e for e in T["say"]), key=lambda e: -e.get("w", 1))
    ag = []
    for e in say:
        for a in (e["s"], e["t"]):
            if a not in ag:
                ag.append(a)
        if len(ag) >= 7:
            break
    ag = ag[:7]
    own_by = {}
    for e in T["own"]:
        if e["a"] in ag:
            own_by.setdefault(e["m"], set()).add(e["a"])
    mem_info = {m["id"]: m for m in T["mems"]}
    # shared-among-chosen first, then affiliated partners of those
    chosen = sorted((m for m in own_by if len(own_by[m]) >= 2),
                    key=lambda m: -len(own_by[m]))[:6]
    aff_pairs = [(e["s"], e["t"]) for e in T["aff"]]
    for a_, b_ in aff_pairs:
        if len(chosen) >= 18:
            break
        if a_ in chosen and b_ in own_by and b_ not in chosen:
            chosen.append(b_)
        elif b_ in chosen and a_ in own_by and a_ not in chosen:
            chosen.append(a_)
    for m in sorted(own_by, key=lambda m: -len(own_by[m])):
        if len(chosen) >= 18:
            break
        if m not in chosen:
            chosen.append(m)
    ax_pos = {a: i / max(len(ag) - 1, 1) for i, a in enumerate(ag)}
    # place each memory under the centre of its owners, so ownership lines run
    # near-vertical instead of criss-crossing the panel
    key = lambda m: sum(ag.index(a) for a in own_by[m]) / len(own_by[m])
    chosen.sort(key=lambda m: (key(m), m))
    mx = {}
    for i, m in enumerate(chosen):
        target = key(m) / max(len(ag) - 1, 1)
        slot = (i + 0.5) / len(chosen)
        mx[m] = 0.75 * target + 0.25 * slot   # grouped, but never overlapping
    for e in say:                                    # conversation edges, weighted
        if e["s"] in ax_pos and e["t"] in ax_pos:
            a3.plot([ax_pos[e["s"]], ax_pos[e["t"]]], [1, 1], color="#2563eb",
                    lw=0.8 + 2.2 * e.get("w", 1) / (say[0].get("w", 1) or 1),
                    alpha=0.75, zorder=2)
    for m in chosen:                                 # ownership lines
        for a in own_by[m]:
            shared = len(own_by[m]) >= 2
            a3.plot([ax_pos[a], mx[m]], [1, 0], color="#111827" if shared else "#cbd5e1",
                    lw=1.1 if shared else 0.6, alpha=0.85 if shared else 0.6, zorder=1)
    import numpy as _np
    for a_, b_ in aff_pairs:                         # affiliation arcs below
        if a_ in mx and b_ in mx:
            x1, x2 = sorted((mx[a_], mx[b_]))
            t = _np.linspace(0, _np.pi, 24)
            a3.plot((x1 + x2) / 2 + (x2 - x1) / 2 * _np.cos(t),
                    -0.16 * _np.sin(t) * min(1, 3 * (x2 - x1)) - 0.02,
                    color="#7c3aed", lw=0.9, alpha=0.8, zorder=1)
    for m in chosen:
        shared = len(own_by[m]) >= 2
        a3.scatter(mx[m], 0, s=120 if shared else 55,
                   color="#6366f1" if shared else "#c7d2fe",
                   edgecolors="white", lw=0.8, zorder=3)
    a3.scatter(list(ax_pos.values()), [1] * len(ax_pos), s=260, color="#0f9d6b",
               edgecolors="white", lw=1, zorder=3)
    for a, x in ax_pos.items():
        a3.annotate(nm(a), (x, 1), fontsize=7.5, ha="center",
                    xytext=(0, 12), textcoords="offset points")
    # label a few memories with their text
    is_en2 = lambda t: all(ord(ch) < 0x2E80 for ch in t)
    labelled = [m for m in chosen if len(own_by[m]) >= 2 and is_en2(en(mem_info[m]["text"]))]
    labelled.sort(key=lambda m: len(en(mem_info[m]["text"])))
    spots3 = [(0.01, -0.42, "left"), (0.99, -0.42, "right"), (0.5, -0.72, "center")]
    for m, (fx, fy, ha) in zip(labelled[:3], spots3):
        blurb = "\n".join(textwrap.wrap(en(mem_info[m]["text"]), 46)[:2])
        blurb += "\nowners = [" + ", ".join(sorted(own_by[m])) + "]"
        a3.annotate(blurb, xy=(mx[m], -0.05), xytext=(fx, fy),
                    textcoords="data", ha=ha, va="top", fontsize=6, zorder=4,
                    bbox=dict(boxstyle="round,pad=0.35", fc="#f0fdf4",
                              ec="#d1d5db", lw=0.6),
                    arrowprops=dict(arrowstyle="-", color="#6b7280", lw=0.7))
    a3.set_xlim(-0.06, 1.06); a3.set_ylim(-1.12, 1.32)
    a3.set_yticks([0, 1]); a3.set_yticklabels(["memories", "agents"], fontsize=8)
    a3.set_xticks([]); [sp.set_visible(False) for sp in a3.spines.values()]
    a3.set_title("(d) shared memories, conversations, affiliation --- a subset",
                 fontsize=10)

    plt.tight_layout()
    out = f"paper/figures/case_{world}.png"
    plt.savefig(out, dpi=150); plt.close()
    print("wrote", out)


if __name__ == "__main__":
    for w, c in WORLDS:
        draw(w, c)
