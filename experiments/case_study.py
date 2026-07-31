"""Case-study analyses for one 三国 consensus run (offline, no LLM):

  1. Pairwise shared-memory heatmap   (co-ownership of memories)
  2. Agent interaction graph          (say-frequency network + communities)
  3. Interaction topology vs shared   (does more interaction => more shared memory?)
  4. Affiliated-memory structure      (chain stats + an example recall trajectory)

Usage: venv/bin/python experiments/case_study.py [run_dir]
  default run_dir = runs/fair2_consensus
Figures + text go to <run_dir>/case_study/.
"""

import os
import sys
import json
from collections import Counter, defaultdict

os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ".")

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import networkx as nx
from scipy.stats import pearsonr

RUN = sys.argv[1] if len(sys.argv) > 1 else "runs/fair2_consensus"
OUT = os.path.join(RUN, "case_study")
os.makedirs(OUT, exist_ok=True)


# Sim-NEW memories only: keep entries the SIM produced (remember -> "runtime",
# act_on -> "act_on"), dropping the sedimented novel corpus ("history"/
# "document"). The case study is about the memory structure the SIM built.
SIM_SOURCES = {"runtime", "act_on"}


def _sim_new(mems):
    return [m for m in mems if (m.get("meta") or {}).get("source") in SIM_SOURCES]


def load():
    mems = _sim_new(json.load(open(f"{RUN}/ltm_final.json", encoding="utf-8")))
    say = Counter()
    for line in open(f"{RUN}/events.jsonl", encoding="utf-8"):
        e = json.loads(line)
        if e.get("kind") == "message" and e["message"].get("kind") == "say":
            m = e["message"]
            for r in m.get("recipients", []):
                if r != m["sender"]:
                    say[(m["sender"], r)] += 1
    return mems, say


def roster():
    """FULL active-character roster from the run's checkpoint, so figures show
    every agent -- including ones that never spoke or never wrote a memory.
    Falls back to [] (figures then cover only observed agents)."""
    p = f"{RUN}/checkpoints/ckpt_final.json"
    if not os.path.exists(p):
        return []
    ck = json.load(open(p, encoding="utf-8"))
    kinds = {a["id"]: a.get("kind") for a in ck.get("scenario", {}).get("agents", [])}
    state = ck.get("agents", {})
    return sorted(aid for aid, kind in kinds.items()
                  if kind == "character" and not state.get(aid, {}).get("archived"))


def build_matrices(mems, say):
    inter = defaultdict(int)  # undirected interaction weight
    for (a, b), w in say.items():
        inter[tuple(sorted((a, b)))] += w
    co = defaultdict(int)     # undirected co-ownership count
    own_total = Counter()
    for m in mems:
        ow = sorted(set(m.get("owners", [])))
        for o in ow:
            own_total[o] += 1
        for i in range(len(ow)):
            for j in range(i + 1, len(ow)):
                co[(ow[i], ow[j])] += 1
    return inter, co, own_total


def interaction_graph(inter, full_roster=()):
    G = nx.Graph()
    G.add_nodes_from(full_roster)          # every active character, even silent
    for (a, b), w in inter.items():
        G.add_edge(a, b, weight=w)
    connected = [n for n in G.nodes() if G.degree(n) > 0]
    comm = nx.community.greedy_modularity_communities(G.subgraph(connected), weight="weight")
    node_comm = {n: i for i, c in enumerate(comm) for n in c}
    return G, comm, node_comm


def fig_interaction_graph(G, node_comm):
    deg = dict(G.degree(weight="weight"))
    pos = nx.spring_layout(G, seed=1, weight="weight", k=0.5)
    # isolated (never-spoke) agents: park on a bottom row so they're visible
    isolated = sorted(n for n in G.nodes() if G.degree(n) == 0)
    if isolated:
        xs = np.linspace(-1.1, 1.1, len(isolated))
        ymin = min(y for _, y in pos.values()) if len(pos) > len(isolated) else 0
        for x, n in zip(xs, isolated):
            pos[n] = (x, ymin - 0.35)
    ncolors = [node_comm.get(n, -1) for n in G.nodes()]
    sizes = [60 + 6 * deg.get(n, 0) ** 0.6 for n in G.nodes()]
    ew = [0.2 + 0.15 * G[u][v]["weight"] for u, v in G.edges()]
    plt.figure(figsize=(11, 9.5))
    nx.draw_networkx_edges(G, pos, width=ew, alpha=0.25)
    nx.draw_networkx_nodes(G, pos, node_size=sizes, node_color=ncolors,
                           cmap="tab10", alpha=0.9)
    # label EVERY agent (complete cast)
    nx.draw_networkx_labels(G, pos, labels={n: n for n in G.nodes()}, font_size=7)
    n_talk = sum(1 for n in G.nodes() if G.degree(n) > 0)
    plt.title(f"Agent interaction graph (say frequency) — {len(G)} active characters "
              f"({n_talk} conversing, {len(G) - n_talk} silent, bottom row), "
              f"{G.number_of_edges()} pairs, {len(set(node_comm.values()))} communities")
    plt.axis("off")
    plt.tight_layout()
    plt.savefig(f"{OUT}/interaction_graph.png", dpi=140)
    plt.close()


def fig_shared_heatmap(co, node_comm, deg, full_roster=()):
    # complete cast: every active character (community-ordered, silent last)
    pool = sorted(set(deg) | set(full_roster),
                  key=lambda n: (node_comm.get(n, 99), -deg.get(n, 0), n))
    order = pool
    n = len(order)
    M = np.zeros((n, n))
    for i, a in enumerate(order):
        for j, b in enumerate(order):
            if i != j:
                M[i, j] = co.get(tuple(sorted((a, b))), 0)
    plt.figure(figsize=(10, 8.5))
    im = plt.imshow(M, cmap="magma")
    plt.colorbar(im, label="# memories co-owned")
    plt.xticks(range(n), order, rotation=90, fontsize=7)
    plt.yticks(range(n), order, fontsize=7)
    plt.title("Pairwise shared-memory heatmap (consensus co-ownership)\n"
              "agents ordered by interaction community")
    plt.tight_layout()
    plt.savefig(f"{OUT}/shared_memory_heatmap.png", dpi=140)
    plt.close()
    return order


def fig_topology_vs_shared(inter, co, node_comm):
    xs, ys, intra = [], [], []
    for (a, b), w in inter.items():
        s = co.get(tuple(sorted((a, b))), 0)
        xs.append(w)
        ys.append(s)
        intra.append(node_comm.get(a) == node_comm.get(b))
    xs, ys, intra = np.array(xs), np.array(ys), np.array(intra)
    r, p = pearsonr(xs, ys)
    # log-log-ish scatter, colored by intra/inter community
    plt.figure(figsize=(8, 6.5))
    plt.scatter(xs[intra], ys[intra], s=28, alpha=0.7, label="intra-community pair", color="#d1495b")
    plt.scatter(xs[~intra], ys[~intra], s=28, alpha=0.7, label="inter-community pair", color="#5b8ad1")
    plt.xlabel("interaction frequency (# say messages between the pair)")
    plt.ylabel("# memories co-owned (shared memory)")
    plt.title(f"Interaction topology vs shared memory\nPearson r = {r:.3f} (p = {p:.1e}), "
              f"n = {len(xs)} interacting pairs")
    plt.legend()
    plt.tight_layout()
    plt.savefig(f"{OUT}/topology_vs_shared.png", dpi=140)
    plt.close()
    intra_share = ys[intra].mean() if intra.any() else 0
    inter_share = ys[~intra].mean() if (~intra).any() else 0
    return r, p, intra_share, inter_share


def affiliated_analysis(mems):
    byid = {m["id"]: m for m in mems}
    sizes = Counter(len(m.get("affiliated", []) or []) for m in mems)
    with_aff = sum(1 for m in mems if m.get("affiliated"))
    # directed affiliated graph -> find a long chain (carrier doc / event group)
    adj = {m["id"]: [a for a in (m.get("affiliated") or []) if a in byid] for m in mems}

    def longest_from(start, seen):
        best = [start]
        for nxt in adj.get(start, []):
            if nxt in seen:
                continue
            path = [start] + longest_from(nxt, seen | {start})
            if len(path) > len(best):
                best = path
        return best

    # greedily find the longest chain (bounded search over heads with affiliated)
    best_chain = []
    sys.setrecursionlimit(10000)
    heads = [m["id"] for m in mems if m.get("affiliated")]
    for h in heads[:4000]:
        try:
            c = longest_from(h, set())
        except RecursionError:
            continue
        if len(c) > len(best_chain):
            best_chain = c
        if len(best_chain) >= 8:
            break

    lines = []
    lines.append(f"memories: {len(mems)} | with affiliated links: {with_aff} "
                 f"({100*with_aff/len(mems):.0f}%)")
    lines.append(f"affiliated-set size distribution: {dict(sorted(sizes.items()))}")
    lines.append("")
    lines.append(f"=== Example affiliated recall trajectory (constructed; agents used "
                 f"get_affiliated/read 0 times live) ===")
    lines.append(f"Starting from one recalled memory, following its affiliated chain "
                 f"reconstructs {len(best_chain)} linked memories:")
    for i, mid in enumerate(best_chain):
        lines.append(f"  {i+1}. {byid[mid]['text']}")
    return "\n".join(lines)


def main():
    mems, say = load()
    full = roster()
    inter, co, own_total = build_matrices(mems, say)
    G, comm, node_comm = interaction_graph(inter, full_roster=full)
    deg = dict(G.degree(weight="weight"))

    fig_interaction_graph(G, node_comm)
    fig_shared_heatmap(co, node_comm, deg, full_roster=full)
    r, p, intra_share, inter_share = fig_topology_vs_shared(inter, co, node_comm)
    aff_text = affiliated_analysis(mems)

    summary = [
        f"=== 三国 consensus case study ({RUN}) ===",
        f"agents interacting: {len(G)} | interacting pairs: {G.number_of_edges()} | "
        f"communities: {len(comm)}",
        f"co-owned memory pairs: {len(co)} | say messages: {sum(say.values())}",
        "",
        f"[Topology -> shared memory] Pearson r = {r:.3f} (p={p:.1e})",
        f"  mean shared memory: intra-community pair = {intra_share:.1f}, "
        f"inter-community pair = {inter_share:.1f}  "
        f"(ratio {intra_share/inter_share:.1f}x)" if inter_share else "",
        "",
        aff_text,
    ]
    text = "\n".join(x for x in summary if x is not None)
    open(f"{OUT}/summary.txt", "w", encoding="utf-8").write(text)
    print(text)
    print(f"\nfigures -> {OUT}/ (interaction_graph.png, shared_memory_heatmap.png, "
          f"topology_vs_shared.png)")


if __name__ == "__main__":
    main()
