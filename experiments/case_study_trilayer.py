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


def main():
    mems, say = load()
    byid = {m["id"]: m for m in mems}
    owners = {m["id"]: sorted(set(m.get("owners", []))) for m in mems}

    # agents = those owning sim memories or talking
    agents = sorted({o for ow in owners.values() for o in ow} |
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

    # affiliation arcs below the memory row; cross-owner ones highlighted
    for u, v in aff_edges:
        cross = set(owners[u]) != set(owners[v])
        arc(ax, mem_pos[u], mem_pos[v], YM - 0.05,
            0.10 + 0.45 * abs(mem_pos[u] - mem_pos[v]) / len(order),
            "#d63b3b" if cross else "#10b981",
            1.6 if cross else 0.7, 0.9 if cross else 0.35, up=False)

    # nodes
    for a, x in ax_pos.items():
        ax.scatter([x], [YA], s=170, color="#2563eb", zorder=3, edgecolors="white", linewidths=1.2)
        ax.text(x, YA + 0.045, a, rotation=55, ha="left", va="bottom", fontsize=7.5)
    for mid, x in mem_pos.items():
        multi = len(owners[mid]) >= 2
        ax.scatter([x], [YM], s=64 if multi else 26,
                   color="#d63b3b" if multi else "#8fa3c8",
                   marker="*" if multi else "o", zorder=3,
                   edgecolors="white", linewidths=0.6)

    # legend
    from matplotlib.lines import Line2D
    handles = [
        Line2D([], [], color="#2563eb", lw=2, label="interaction (say) — agents"),
        Line2D([], [], color="#c3c9d4", lw=1, label="ownership"),
        Line2D([], [], color="#d63b3b", lw=1.6, label="shared memory (multi-owner) / cross-owner link"),
        Line2D([], [], color="#10b981", lw=1.4, label="affiliation — memories"),
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
                 "cross-owner affiliation (red arcs) bridges conversing agents",
                 fontsize=10)
    plt.tight_layout()
    plt.savefig(f"{OUT}/tri_layer.png", dpi=150)
    plt.close()

    # ---------------- relationship panels ----------------
    def jac(a, b):
        A, B = set(a), set(b)
        u = A | B
        return len(A & B) / len(u) if u else 0.0

    fig, axes = plt.subplots(1, 3, figsize=(12, 3.6))

    # per-agent sim-memory sets
    mem_of = defaultdict(set)
    for mid, ow in owners.items():
        for o in ow:
            mem_of[o].add(mid)
    talk_pairs = set(say)
    all_pairs = [tuple(sorted((a, b))) for i, a in enumerate(order) for b in order[i + 1:]]

    # P(A-O): two-color histogram -- owned-memory-set Jaccard for TALKING vs
    # NON-TALKING agent pairs.
    axp = axes[0]
    talk_j, non_j = [], []
    for p in all_pairs:
        a, b = p
        if not mem_of[a] or not mem_of[b]:
            continue
        (talk_j if p in talk_pairs else non_j).append(jac(mem_of[a], mem_of[b]))
    bins = np.linspace(0, max(talk_j + non_j + [0.05]) * 1.05, 16)
    axp.hist(non_j, bins=bins, density=True, alpha=0.55, color="#9ca3af",
             label=f"non-talking pairs (n={len(non_j)}, mean {np.mean(non_j):.3f})")
    axp.hist(talk_j, bins=bins, density=True, alpha=0.65, color="#2563eb",
             label=f"talking pairs (n={len(talk_j)}, mean {np.mean(talk_j):.3f})")
    axp.set_yscale("log")
    axp.set_xlabel("Jaccard of the pair's owned-memory sets")
    axp.set_ylabel("density (log)")
    axp.legend(fontsize=7.2)
    axp.set_title("A↔O  memory overlap: talking vs non-talking pairs", fontsize=9.5)

    # P(M-O): two-color histogram -- owner-set Jaccard for memory pairs WITH an
    # affiliated edge vs memory pairs WITHOUT one (all non-edge pairs, exact).
    edge_set = {tuple(sorted(e)) for e in aff_edges}
    ids = list(byid)
    aj, nj = [], []
    for i in range(len(ids)):
        for j2 in range(i + 1, len(ids)):
            pair = tuple(sorted((ids[i], ids[j2])))
            (aj if pair in edge_set else nj).append(jac(owners[pair[0]], owners[pair[1]]))
    axp = axes[1]
    bins = np.linspace(0, 1, 21)
    axp.hist(nj, bins=bins, density=True, alpha=0.55, color="#9ca3af",
             label=f"no affiliated edge (n={len(nj)}, mean {np.mean(nj):.2f})")
    axp.hist(aj, bins=bins, density=True, alpha=0.65, color="#10b981",
             label=f"affiliated edge (n={len(aj)}, mean {np.mean(aj):.2f})")
    axp.set_yscale("log")
    axp.set_xlabel("owner-set Jaccard of the memory pair"); axp.set_ylabel("density (log)")
    axp.legend(fontsize=7.2)
    axp.set_title("M↔O  owner overlap: linked vs unlinked memory pairs", fontsize=9.5)

    # P(A-M): two-color histogram -- # affiliated edges between the pair's
    # memory sets, for TALKING vs NON-TALKING agent pairs. (An edge counts when
    # one endpoint is in a's set and the other in b's.)
    axp = axes[2]
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
    bins = np.arange(-0.5, mx + 1.5, 1)
    axp.hist(non_e, bins=bins, density=True, alpha=0.55, color="#9ca3af",
             label=f"non-talking pairs (n={len(non_e)}, mean {np.mean(non_e):.2f})")
    axp.hist(talk_e, bins=bins, density=True, alpha=0.65, color="#d63b3b",
             label=f"talking pairs (n={len(talk_e)}, mean {np.mean(talk_e):.2f})")
    axp.set_yscale("log")
    axp.set_xlabel("affiliated edges between the pair's memory sets")
    axp.set_ylabel("density (log)")
    axp.legend(fontsize=7.2)
    axp.set_title("A↔M  cross-set links: talking vs non-talking", fontsize=9.5)

    plt.tight_layout()
    plt.savefig(f"{OUT}/relationship_panels.png", dpi=150)
    plt.close()
    print(f"figures -> {OUT}/ (tri_layer.png, relationship_panels.png)")


if __name__ == "__main__":
    main()
