"""Tri-layer visualization of the case study's three graphs and their three
pairwise relationships, for ONE consensus run's sim-generated memories.

Outputs (to <run>/case_study/):
  tri_layer.png           -- agents row + memories row; interaction arcs (top),
                             ownership lines (middle), affiliation arcs (bottom).
                             All three relations visible in one picture: shared
                             (multi-owner) memories sit between talking agents;
                             cross-owner affiliation arcs bridge blocks whose
                             agents converse.
  relationship_panels.png -- 3 panels, one per pairwise relation:
                             A-O talking vs non-talking pairs (strip, co-owned)
                             M-O Jaccard distributions (affiliated vs random)
                             A-M cross-owner affiliated edges: % owners talked

Usage: venv/bin/python experiments/case_study_trilayer.py [run_dir]
"""

import os
import sys
import json
import random
from collections import Counter, defaultdict

os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ".")

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.path import Path
from matplotlib.patches import PathPatch
import networkx as nx

random.seed(7)
RUN = sys.argv[1] if len(sys.argv) > 1 else "runs/t10_consensus"
OUT = os.path.join(RUN, "case_study")
os.makedirs(OUT, exist_ok=True)

SIM_SOURCES = {"runtime", "act_on"}


def load():
    mems = [m for m in json.load(open(f"{RUN}/ltm_final.json", encoding="utf-8"))
            if (m.get("meta") or {}).get("source") in SIM_SOURCES]
    say = Counter()
    for line in open(f"{RUN}/events.jsonl", encoding="utf-8"):
        e = json.loads(line)
        if e.get("kind") == "message" and e["message"].get("kind") == "say":
            m = e["message"]
            for r in m.get("recipients", []):
                if r != m["sender"]:
                    say[tuple(sorted((m["sender"], r)))] += 1
    return mems, say


def arc(ax, x1, x2, y, height, color, lw, alpha, up=True):
    """Quadratic bezier arc between (x1,y) and (x2,y)."""
    xm = (x1 + x2) / 2
    yc = y + height if up else y - height
    path = Path([(x1, y), (xm, yc), (x2, y)],
                [Path.MOVETO, Path.CURVE3, Path.CURVE3])
    ax.add_patch(PathPatch(path, facecolor="none", edgecolor=color, lw=lw, alpha=alpha))


def roster_and_kinds():
    """(active-character roster, id->kind map) from the run's checkpoint;
    ([], {}) when absent."""
    p = f"{RUN}/checkpoints/ckpt_final.json"
    if not os.path.exists(p):
        return [], {}
    ck = json.load(open(p, encoding="utf-8"))
    kinds = {a["id"]: a.get("kind") for a in ck.get("scenario", {}).get("agents", [])}
    state = ck.get("agents", {})
    ros = sorted(aid for aid, kind in kinds.items()
                 if kind == "character" and not state.get(aid, {}).get("archived"))
    return ros, kinds


def main():
    mems, say = load()
    byid = {m["id"]: m for m in mems}
    owners = {m["id"]: sorted(set(m.get("owners", []))) for m in mems}

    # agents = FULL active-character roster, plus any other memory owner
    # (environments/info-carriers own memories via act_on) or speaker.
    ros, kinds = roster_and_kinds()
    agents = sorted(set(ros) |
                    {o for ow in owners.values() for o in ow} |
                    {a for p in say for a in p})
    # order agents by interaction communities to keep arcs short
    GA = nx.Graph()
    GA.add_nodes_from(agents)
    for (a, b), w in say.items():
        GA.add_edge(a, b, weight=w)
    comms = list(nx.community.greedy_modularity_communities(GA, weight="weight"))
    order = [a for c in sorted(comms, key=len, reverse=True) for a in sorted(c)]
    order += [a for a in agents if a not in order]
    ax_pos = {a: i for i, a in enumerate(order)}

    # memory x: mean of owner positions (multi-owner sits BETWEEN its owners);
    # stable jitter for stacking
    groups = defaultdict(list)
    for mid, ow in owners.items():
        xm = np.mean([ax_pos[o] for o in ow])
        groups[round(xm, 3)].append(mid)
    mem_pos = {}
    for xm, mids in groups.items():
        # spread memories sharing an x slot
        span = min(0.8, 0.16 * (len(mids) - 1))
        for i, mid in enumerate(sorted(mids)):
            off = -span / 2 + (span * i / max(len(mids) - 1, 1)) if len(mids) > 1 else 0
            mem_pos[mid] = xm + off

    # affiliation edges among sim memories
    aff_edges = []
    for m in mems:
        for a in (m.get("affiliated") or []):
            if a in byid and a > m["id"]:
                aff_edges.append((m["id"], a))

    YA, YM = 1.0, 0.0
    fig, ax = plt.subplots(figsize=(12, 6.2))

    # ownership lines (agent -> memory)
    for mid, ow in owners.items():
        multi = len(ow) >= 2
        for o in ow:
            ax.plot([ax_pos[o], mem_pos[mid]], [YA - 0.03, YM + 0.045],
                    color="#d63b3b" if multi else "#c3c9d4",
                    lw=1.6 if multi else 0.6, alpha=0.9 if multi else 0.45, zorder=1)

    # interaction arcs above the agent row
    wmax = max(say.values()) if say else 1
    for (a, b), w in say.items():
        arc(ax, ax_pos[a], ax_pos[b], YA + 0.05, 0.12 + 0.5 * abs(ax_pos[a] - ax_pos[b]) / len(order),
            "#2563eb", 0.7 + 2.4 * w / wmax, 0.5, up=True)

    # affiliation arcs below the memory row: GREEN when the two memories'
    # owner sets intersect (same/overlapping witnesses -- the normal case,
    # including merge-ripple edges like {A}-{A,B}), GRAY when fully disjoint.
    for u, v in aff_edges:
        overlap = bool(set(owners[u]) & set(owners[v]))
        arc(ax, mem_pos[u], mem_pos[v], YM - 0.05,
            0.10 + 0.45 * abs(mem_pos[u] - mem_pos[v]) / len(order),
            "#10b981" if overlap else "#9ca3af",
            0.7 if overlap else 1.4, 0.35 if overlap else 0.85, up=False)

    # nodes: characters as circles; passive owners (environments/info
    # carriers, which own memories via act_on) as squares
    for a, x in ax_pos.items():
        is_char = kinds.get(a, "character") == "character"
        ax.scatter([x], [YA], s=170 if is_char else 130,
                   color="#2563eb" if is_char else "#7c9ff5",
                   marker="o" if is_char else "s",
                   zorder=3, edgecolors="white", linewidths=1.2)
        ax.text(x, YA + 0.045, a, rotation=55, ha="left", va="bottom", fontsize=7)
    for mid, x in mem_pos.items():
        multi = len(owners[mid]) >= 2
        ax.scatter([x], [YM], s=64 if multi else 26,
                   color="#d63b3b" if multi else "#8fa3c8",
                   marker="*" if multi else "o", zorder=3,
                   edgecolors="white", linewidths=0.6)

    # legend
    from matplotlib.lines import Line2D
    handles = [
        Line2D([], [], marker="o", color="#2563eb", lw=0, markersize=9, label="character"),
        Line2D([], [], marker="s", color="#7c9ff5", lw=0, markersize=8, label="environment / info-carrier (memory owner)"),
        Line2D([], [], color="#2563eb", lw=2, label="interaction (say) — agents"),
        Line2D([], [], color="#c3c9d4", lw=1, label="ownership"),
        Line2D([], [], color="#d63b3b", lw=1.6, label="shared-memory ownership (multi-owner)"),
        Line2D([], [], color="#10b981", lw=1.4, label="affiliation — owners overlap"),
        Line2D([], [], color="#9ca3af", lw=1.4, label="affiliation — owners disjoint"),
        Line2D([], [], marker="*", color="#d63b3b", lw=0, markersize=11, label="merged (multi-owner) memory"),
    ]
    ax.legend(handles=handles, loc="lower left", fontsize=7.5, framealpha=0.9)
    ax.text(-0.6, YA, "agents", fontsize=9, ha="right", va="center", fontweight="bold")
    ax.text(-0.6, YM, "memories", fontsize=9, ha="right", va="center", fontweight="bold")
    ax.set_xlim(-1.4, len(order))
    ax.set_ylim(-0.75, 1.85)
    ax.axis("off")
    ax.set_title("Three layers in one view: conversations (top), ownership (middle), memory affiliation (bottom)\n"
                 "merged memories (★) hang between the talking agents that share them; "
                 "affiliation arcs are green when the linked memories share a witness",
                 fontsize=10)
    plt.tight_layout()
    plt.savefig(f"{OUT}/tri_layer.png", dpi=150)
    plt.close()

    # ---------------- relationship panels ----------------
    def jac(a, b):
        A, B = set(a), set(b)
        u = A | B
        return len(A & B) / len(u) if u else 0.0

    # 2x3 grid: one COLUMN per relation, with-relation group on the TOP row and
    # without-relation group on the BOTTOM row (columns share x for comparison).
    fig, axes = plt.subplots(2, 3, figsize=(12, 5.6), sharex="col", sharey="col")

    # per-agent sim-memory sets
    mem_of = defaultdict(set)
    for mid, ow in owners.items():
        for o in ow:
            mem_of[o].add(mid)
    talk_pairs = set(say)
    all_pairs = [tuple(sorted((a, b))) for i, a in enumerate(order) for b in order[i + 1:]]

    def split_hist(col, top_vals, bot_vals, bins, top_color, top_label, bot_label,
                   xlabel, title, label_side=("right", "right")):
        for row, (vals, color, label) in enumerate(
                [(top_vals, top_color, top_label), (bot_vals, "#9ca3af", bot_label)]):
            lx, ha = (0.98, "right") if label_side[row] == "right" else (0.02, "left")
            axp = axes[row][col]
            axp.hist(vals, bins=bins, density=True, color=color, edgecolor="white")
            axp.set_yscale("log")
            axp.text(lx, 0.86, f"{label}\nn={len(vals)}, mean {np.mean(vals):.3f}",
                     transform=axp.transAxes, ha=ha, fontsize=8, color=color)
            if row == 0:
                axp.set_title(title, fontsize=9.5)
            else:
                axp.set_xlabel(xlabel)
            if col == 0:
                axp.set_ylabel("density (log)")

    # P(A-O): owned-memory-set Jaccard, talking (top) vs non-talking (bottom)
    talk_j, non_j = [], []
    for p in all_pairs:
        a, b = p
        if not mem_of[a] or not mem_of[b]:
            continue
        (talk_j if p in talk_pairs else non_j).append(jac(mem_of[a], mem_of[b]))
    bins = np.linspace(0, max(talk_j + non_j + [0.05]) * 1.05, 16)
    split_hist(0, talk_j, non_j, bins, "#2563eb", "talking pairs", "non-talking pairs",
               "Jaccard of the pair's owned-memory sets",
               "A↔O  memory overlap between agents")

    # P(M-O): owner-set Jaccard, memory pairs with (top) vs without (bottom) an
    # affiliated edge (all non-edge pairs, exact).
    edge_set = {tuple(sorted(e)) for e in aff_edges}
    ids = list(byid)
    aj, nj = [], []
    for i in range(len(ids)):
        for j2 in range(i + 1, len(ids)):
            pair = tuple(sorted((ids[i], ids[j2])))
            (aj if pair in edge_set else nj).append(jac(owners[pair[0]], owners[pair[1]]))
    split_hist(1, aj, nj, np.linspace(0, 1, 21), "#10b981",
               "affiliated (linked) pairs", "unlinked pairs",
               "owner-set Jaccard of the memory pair",
               "M↔O  owner overlap between memories", label_side=("left", "right"))

    # P(A-M): cross-set affiliated edge counts, talking (top) vs non-talking
    # (bottom) agent pairs.
    talk_e, non_e = [], []
    for p in all_pairs:
        a, b = p
        if not mem_of[a] or not mem_of[b]:
            continue
        n_edges = 0
        for u, v in aff_edges:
            if (u in mem_of[a] and v in mem_of[b]) or (u in mem_of[b] and v in mem_of[a]):
                n_edges += 1
        (talk_e if p in talk_pairs else non_e).append(n_edges)
    mx = max(talk_e + non_e + [1])
    # adaptive bin width: integer bins up to ~25 bars, else widen (a width-1
    # bin over a 0..200+ range renders sub-pixel bars that look like an empty
    # panel).
    step = max(1, int(np.ceil((mx + 1) / 25)))
    split_hist(2, talk_e, non_e, np.arange(-0.5, mx + step + 0.5, step), "#d63b3b",
               "talking pairs", "non-talking pairs",
               "affiliated edges between the pair's memory sets",
               "A↔M  memory links between agents")

    plt.tight_layout()
    plt.savefig(f"{OUT}/relationship_panels.png", dpi=150)
    plt.close()
    print(f"figures -> {OUT}/ (tri_layer.png, relationship_panels.png)")


if __name__ == "__main__":
    main()
