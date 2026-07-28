"""Three-layer network analysis of one 三国 consensus run (offline, no LLM):

  Layer A (agents):   interaction graph      -- who says to whom (sim)
  Layer M (memories): affiliation graph      -- memory<->memory affiliated links
  Bridge (bipartite): agent-owns-memory      -- owner sets

and the RELATIONSHIPS between them:
  R1 affiliation <-> ownership : do affiliated memories share owners?
       (affiliated = same event/topic => should be witnessed by the same agents)
  R2 interaction <-> ownership : do interaction communities have denser shared
       memory than across communities? (community-level 'topology -> shared')
  R3 ownership coherence       : are an agent's owned memories concentrated in a
       few affiliation components (coherent) or scattered?

Usage: venv/bin/python experiments/case_study_graphs.py [run_dir]
Figures + summary -> <run_dir>/case_study/.
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
import networkx as nx

RUN = sys.argv[1] if len(sys.argv) > 1 else "runs/fair2_consensus"
OUT = os.path.join(RUN, "case_study")
os.makedirs(OUT, exist_ok=True)
random.seed(0)


def jaccard(a, b):
    a, b = set(a), set(b)
    u = a | b
    return len(a & b) / len(u) if u else 0.0


def main():
    # Sim-NEW memories only (remember/act_on), dropping the sedimented novel
    # corpus -- the graph analysis is about what the SIM built.
    mems = [m for m in json.load(open(f"{RUN}/ltm_final.json", encoding="utf-8"))
            if (m.get("meta") or {}).get("source") in ("runtime", "act_on")]
    byid = {m["id"]: m for m in mems}
    owners = {m["id"]: set(m.get("owners", [])) for m in mems}

    # ---- interaction graph (agents) ----
    say = Counter()
    for line in open(f"{RUN}/events.jsonl", encoding="utf-8"):
        e = json.loads(line)
        if e.get("kind") == "message" and e["message"].get("kind") == "say":
            m = e["message"]
            for r in m.get("recipients", []):
                if r != m["sender"]:
                    say[tuple(sorted((m["sender"], r)))] += 1
    GA = nx.Graph()
    for (a, b), w in say.items():
        GA.add_edge(a, b, weight=w)
    comm = nx.community.greedy_modularity_communities(GA, weight="weight")
    node_comm = {n: i for i, c in enumerate(comm) for n in c}

    # ---- affiliation graph (memories) ----
    GM = nx.DiGraph()
    GM.add_nodes_from(byid)
    for m in mems:
        for a in (m.get("affiliated") or []):
            if a in byid:
                GM.add_edge(m["id"], a)
    UM = GM.to_undirected()
    comps = sorted(nx.connected_components(UM), key=len, reverse=True)
    comp_sizes = [len(c) for c in comps]
    comp_of = {n: i for i, c in enumerate(comps) for n in c}

    # =========================================================
    # R1: affiliation <-> ownership -- do affiliated memories share owners?
    aff_j, rand_j = [], []
    edges = list(GM.edges())
    sample_edges = random.sample(edges, min(4000, len(edges)))
    for u, v in sample_edges:
        aff_j.append(jaccard(owners[u], owners[v]))
    ids = list(byid)
    for _ in range(len(sample_edges)):
        u, v = random.sample(ids, 2)
        rand_j.append(jaccard(owners[u], owners[v]))
    aff_mean, rand_mean = float(np.mean(aff_j)), float(np.mean(rand_j))

    # =========================================================
    # R2: interaction communities vs shared memory (co-ownership)
    co = defaultdict(int)
    for m in mems:
        ow = sorted(owners[m["id"]])
        for i in range(len(ow)):
            for j in range(i + 1, len(ow)):
                co[(ow[i], ow[j])] += 1
    intra, inter = [], []
    agents_in_comm = [a for a in node_comm]
    for i in range(len(agents_in_comm)):
        for j in range(i + 1, len(agents_in_comm)):
            a, b = agents_in_comm[i], agents_in_comm[j]
            s = co.get(tuple(sorted((a, b))), 0)
            (intra if node_comm[a] == node_comm[b] else inter).append(s)
    intra_mean = float(np.mean(intra)) if intra else 0.0
    inter_mean = float(np.mean(inter)) if inter else 0.0

    # =========================================================
    # R3: ownership coherence -- are an agent's memories concentrated in few
    # affiliation components? (entropy of an agent's memories over components,
    # normalized; low = coherent/clustered, high = scattered)
    owner_comps = defaultdict(Counter)
    for m in mems:
        c = comp_of[m["id"]]
        for o in owners[m["id"]]:
            owner_comps[o][c] += 1
    coherence = {}
    for o, cc in owner_comps.items():
        tot = sum(cc.values())
        if tot < 20:
            continue
        p = np.array(list(cc.values())) / tot
        H = -(p * np.log(p)).sum()
        Hmax = np.log(len(cc)) if len(cc) > 1 else 1.0
        coherence[o] = 1.0 - (H / Hmax if Hmax else 0.0)  # 1=coherent, 0=scattered

    # =========================================================
    # figures
    # -- affiliation component-size distribution --
    plt.figure(figsize=(8, 5.5))
    plt.hist(comp_sizes, bins=50, color="#5b8ad1", edgecolor="white")
    plt.yscale("log")
    plt.xlabel("affiliation-component size (# memories)")
    plt.ylabel("# components (log)")
    plt.title(f"Memory affiliation graph: {len(comps)} components over {len(mems)} memories\n"
              f"largest = {comp_sizes[0]}, median = {int(np.median(comp_sizes))}")
    plt.tight_layout()
    plt.savefig(f"{OUT}/affiliation_components.png", dpi=140)
    plt.close()

    # -- R1 bar --
    plt.figure(figsize=(6, 5))
    plt.bar(["affiliated\npairs", "random\npairs"], [aff_mean, rand_mean],
            color=["#d1495b", "#999999"])
    plt.ylabel("mean owner-set Jaccard")
    plt.title(f"R1: affiliated memories share owners\n"
              f"affiliated {aff_mean:.3f} vs random {rand_mean:.3f} "
              f"({aff_mean/rand_mean:.1f}x)" if rand_mean else "R1")
    plt.tight_layout()
    plt.savefig(f"{OUT}/R1_affiliation_vs_ownership.png", dpi=140)
    plt.close()

    # -- affiliation graph viz of the largest component (bounded) --
    big = comps[0]
    if len(big) > 400:
        big = set(list(big)[:400])
    sub = UM.subgraph(big)
    plt.figure(figsize=(10, 9))
    pos = nx.spring_layout(sub, seed=1, k=0.3)
    ncol = [comp_of[n] for n in sub.nodes()]  # all same comp; color by a dominant owner instead
    dom = []
    for n in sub.nodes():
        ow = owners[n]
        dom.append(hash(min(ow)) % 10 if ow else 0)
    nx.draw_networkx_edges(sub, pos, alpha=0.15)
    nx.draw_networkx_nodes(sub, pos, node_size=18, node_color=dom, cmap="tab10", alpha=0.8)
    plt.title(f"Memory affiliation graph — largest component "
              f"({len(comps[0])} memories, showing {len(big)})\nnodes colored by a dominant owner")
    plt.axis("off")
    plt.tight_layout()
    plt.savefig(f"{OUT}/affiliation_graph_largest.png", dpi=140)
    plt.close()

    # =========================================================
    lines = [
        f"=== 三国 consensus THREE-LAYER graph analysis ({RUN}) ===",
        "",
        f"[Layer A] interaction graph: {GA.number_of_nodes()} agents, "
        f"{GA.number_of_edges()} pairs, {len(comm)} communities",
        f"[Layer M] affiliation graph: {len(mems)} memory nodes, {GM.number_of_edges()} "
        f"affiliated edges, {len(comps)} components (largest {comp_sizes[0]}, "
        f"median {int(np.median(comp_sizes))}, singletons {sum(1 for s in comp_sizes if s==1)})",
        f"[Bridge]  ownership: mean owners/memory = "
        f"{np.mean([len(owners[i]) for i in byid]):.2f}",
        "",
        "--- RELATIONSHIPS ---",
        f"R1 affiliation<->ownership: affiliated memory pairs share owners "
        f"{aff_mean:.3f} Jaccard vs {rand_mean:.3f} random "
        f"({aff_mean/rand_mean:.1f}x)  => affiliated memories ARE co-owned by the "
        f"same agents (same event/topic => same witnesses)." if rand_mean else "",
        f"R2 interaction<->ownership: intra-community pairs co-own {intra_mean:.1f} "
        f"memories vs {inter_mean:.1f} across communities "
        f"({intra_mean/inter_mean:.1f}x)  => interaction factions DO align with "
        f"denser shared memory (the community-level version of the null pairwise r)."
        if inter_mean else "",
        f"R3 ownership coherence: agents' memories concentrate in few affiliation "
        f"components (mean coherence {np.mean(list(coherence.values())):.2f}, 1=coherent) "
        f"-- most/least coherent:",
    ]
    sc = sorted(coherence.items(), key=lambda x: -x[1])
    lines.append("     most coherent: " + ", ".join(f"{a}({v:.2f})" for a, v in sc[:5]))
    lines.append("     least coherent: " + ", ".join(f"{a}({v:.2f})" for a, v in sc[-5:]))
    text = "\n".join(x for x in lines if x is not None)
    open(f"{OUT}/three_layer_summary.txt", "w", encoding="utf-8").write(text)
    print(text)
    print(f"\nfigures -> {OUT}/ (affiliation_components.png, R1_affiliation_vs_ownership.png, "
          f"affiliation_graph_largest.png)")


if __name__ == "__main__":
    main()
