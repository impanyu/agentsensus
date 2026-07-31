"""Export the case-study graphs as JSON (precomputed layouts) for the paper's
embedded interactive renderers.

Writes <run>/case_study/graphs.json with four datasets:
  interaction: {nodes:[{id,x,y,comm,deg,silent}], edges:[{s,t,w}]}
  affiliation: {nodes:[{id,x,y,comp,text,owners,shared}], edges:[{s,t}]}
  trilayer:    {agents:[{id,x,kind}], mems:[{id,x,text,owners,multi}],
                say:[{s,t,w}], own:[{a,m,multi}], aff:[{s,t,overlap}]}
  heatmap:     {order:[...], matrix:[[...]]}

Usage: venv/bin/python experiments/export_graph_json.py [run_dir]
"""
import os, sys, json
from collections import Counter, defaultdict

os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); sys.path.insert(0, ".")
import numpy as np
import networkx as nx

RUN = sys.argv[1] if len(sys.argv) > 1 else "runs/g60full_consensus"
OUT = os.path.join(RUN, "case_study")
os.makedirs(OUT, exist_ok=True)
SIM_SRC = {"runtime", "act_on"}

mems = [m for m in json.load(open(f"{RUN}/ltm_final.json", encoding="utf-8"))
        if (m.get("meta") or {}).get("source") in SIM_SRC]
byid = {m["id"]: m for m in mems}
owners = {m["id"]: sorted(set(m.get("owners", []))) for m in mems}

say = Counter()
for line in open(f"{RUN}/events.jsonl", encoding="utf-8"):
    e = json.loads(line)
    if e.get("kind") == "message" and e["message"].get("kind") == "say":
        m = e["message"]
        for r in m.get("recipients", []):
            if r != m["sender"]:
                say[tuple(sorted((m["sender"], r)))] += 1

# roster + kinds from checkpoint
kinds, roster = {}, []
ckp = f"{RUN}/checkpoints/ckpt_final.json"
if os.path.exists(ckp):
    ck = json.load(open(ckp, encoding="utf-8"))
    kinds = {a["id"]: a.get("kind") for a in ck.get("scenario", {}).get("agents", [])}
    state = ck.get("agents", {})
    roster = sorted(aid for aid, kind in kinds.items()
                    if kind == "character" and not state.get(aid, {}).get("archived"))

out = {}

# ---------- interaction ----------
G = nx.Graph()
G.add_nodes_from(roster)
for (a, b), w in say.items():
    G.add_edge(a, b, weight=w)
connected = [n for n in G.nodes() if G.degree(n) > 0]
comms = list(nx.community.greedy_modularity_communities(G.subgraph(connected), weight="weight"))
node_comm = {n: i for i, c in enumerate(comms) for n in c}
pos = nx.spring_layout(G, seed=1, weight="weight", k=0.5)


def relax(p, nodes, dmin, iters=80):
    """Push overlapping nodes apart (tightly-knit communities collapse into
    blobs under spring layout; interactive nodes need breathing room)."""
    ids = list(nodes)
    for _ in range(iters):
        moved = False
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                a, b = ids[i], ids[j]
                dx = p[a][0] - p[b][0]; dy = p[a][1] - p[b][1]
                d = (dx * dx + dy * dy) ** 0.5
                if d < dmin:
                    moved = True
                    if d < 1e-9:
                        dx, dy, d = 0.01, 0.01, 0.0141
                    push = (dmin - d) / 2 / d
                    p[a] = (p[a][0] + dx * push, p[a][1] + dy * push)
                    p[b] = (p[b][0] - dx * push, p[b][1] - dy * push)
        if not moved:
            break
    return p


pos = relax(dict(pos), G.nodes(), dmin=0.13)
isolated = sorted(n for n in G.nodes() if G.degree(n) == 0)
if isolated:
    xs = np.linspace(-1.1, 1.1, len(isolated))
    ymin = min((y for _, y in pos.values()), default=0)
    for x, n in zip(xs, isolated):
        pos[n] = (float(x), float(ymin) - 0.4)
deg = dict(G.degree(weight="weight"))
out["interaction"] = {
    "nodes": [{"id": n, "x": round(float(pos[n][0]), 4), "y": round(float(pos[n][1]), 4),
               "comm": node_comm.get(n, -1), "deg": int(deg.get(n, 0)),
               "silent": G.degree(n) == 0} for n in G.nodes()],
    "edges": [{"s": u, "t": v, "w": int(G[u][v]["weight"])} for u, v in G.edges()],
}

# ---------- affiliation (FULL graph, all sim memories) ----------
GM = nx.Graph()
GM.add_nodes_from(byid)
for m in mems:
    for a in (m.get("affiliated") or []):
        if a in byid:
            GM.add_edge(m["id"], a)
comps = sorted(nx.connected_components(GM), key=len, reverse=True)
comp_of = {n: i for i, c in enumerate(comps) for n in c}
mpos = nx.spring_layout(GM, seed=2, k=0.14)
out["affiliation"] = {
    "nodes": [{"id": n, "x": round(float(mpos[n][0]), 4), "y": round(float(mpos[n][1]), 4),
               "comp": comp_of[n], "text": byid[n]["text"],
               "owners": owners[n], "shared": len(owners[n]) >= 2} for n in GM.nodes()],
    "edges": [{"s": u, "t": v} for u, v in GM.edges()],
    "n_comps": len(comps), "largest": len(comps[0]) if comps else 0,
}

# ---------- trilayer ----------
agents = sorted(set(roster) | {o for ow in owners.values() for o in ow} |
                {a for p in say for a in p})
GA2 = nx.Graph(); GA2.add_nodes_from(agents)
for (a, b), w in say.items():
    GA2.add_edge(a, b, weight=w)
conn = [n for n in GA2.nodes() if GA2.degree(n) > 0]
comms2 = list(nx.community.greedy_modularity_communities(GA2.subgraph(conn), weight="weight"))
order = [a for c in sorted(comms2, key=len, reverse=True) for a in sorted(c)]
order += [a for a in agents if a not in order]
ax_pos = {a: i for i, a in enumerate(order)}
groups = defaultdict(list)
for mid, ow in owners.items():
    xm = float(np.mean([ax_pos[o] for o in ow]))
    groups[round(xm, 3)].append(mid)
mem_x = {}
for xm, mids in groups.items():
    span = min(0.8, 0.16 * (len(mids) - 1))
    for i, mid in enumerate(sorted(mids)):
        off = -span / 2 + (span * i / max(len(mids) - 1, 1)) if len(mids) > 1 else 0
        mem_x[mid] = round(xm + off, 3)
aff_pairs = []
for m in mems:
    for a in (m.get("affiliated") or []):
        if a in byid and a > m["id"]:
            aff_pairs.append((m["id"], a))
out["trilayer"] = {
    "agents": [{"id": a, "x": ax_pos[a], "kind": kinds.get(a, "character")} for a in order],
    "mems": [{"id": mid, "x": mem_x[mid], "text": byid[mid]["text"],
              "owners": owners[mid], "multi": len(owners[mid]) >= 2} for mid in mem_x],
    "say": [{"s": a, "t": b, "w": w} for (a, b), w in say.items()],
    "own": [{"a": o, "m": mid, "multi": len(ow) >= 2} for mid, ow in owners.items() for o in ow],
    "aff": [{"s": u, "t": v, "overlap": bool(set(owners[u]) & set(owners[v]))} for u, v in aff_pairs],
}

# ---------- heatmap ----------
co = Counter()
for m in mems:
    ow = owners[m["id"]]
    for i in range(len(ow)):
        for j in range(i + 1, len(ow)):
            co[(ow[i], ow[j])] += 1
pool = sorted(set(deg) | set(roster), key=lambda n: (node_comm.get(n, 99), -deg.get(n, 0), n))
M = [[co.get(tuple(sorted((a, b))), 0) if a != b else 0 for b in pool] for a in pool]
out["heatmap"] = {"order": pool, "matrix": M}

json.dump(out, open(f"{OUT}/graphs.json", "w", encoding="utf-8"), ensure_ascii=False)
print(f"graphs.json -> {OUT}  (interaction {len(out['interaction']['nodes'])}n/"
      f"{len(out['interaction']['edges'])}e, affiliation {len(out['affiliation']['nodes'])}n/"
      f"{len(out['affiliation']['edges'])}e, trilayer {len(agents)} agents/{len(mem_x)} mems, "
      f"heatmap {len(pool)})")
