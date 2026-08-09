"""Build the full academic-format paper (60-tick data).
Reads: runs/paper_stats_g80.json, runs/results_g60.json, figures in
runs/paper_figs_g80/ + runs/g80full_consensus/case_study/.
"""
import base64, os, json
os.chdir("/Users/ypan12/git_repo/bookworld_paper/agentsensus")

FIGS = {
    "simfoot": "runs/paper_figs_g80/sim_footprint_q.png",
    "structure": "runs/paper_figs_g80/structure_q.png",
    "growth": "runs/paper_figs_g80/growth_q.png",
    "relpanels": "runs/g80full_consensus/case_study/relationship_panels_q.png",
    "gtotal": "runs/paper_figs_g80/growth_total_q.png",
    "gagents": "runs/paper_figs_g80/growth_agents_q.png",
    "quality": "runs/paper_figs_g80/quality_q.png",
    "arch": "runs/paper_figs_g80/architecture_q.png",
    "latency": "runs/paper_figs_g80/latency_q.png",
    "ru_simfoot": "runs/paper_figs_ru40/sim_footprint_q.png",
    "ru_structure": "runs/paper_figs_ru40/structure_q.png",
    "ru_growth": "runs/paper_figs_ru40/growth_q.png",
    "ru_latency": "runs/paper_figs_ru40/latency_q.png",
    "ru_relpanels": "runs/ru40full_consensus/case_study/relationship_panels_q.png",
    "ru_quality": "runs/paper_figs_ru40/quality_q.png",
    "rc_simfoot": "runs/paper_figs_rc80/sim_footprint_q.png",
    "rc_structure": "runs/paper_figs_rc80/structure_q.png",
    "rc_growth": "runs/paper_figs_rc80/growth_q.png",
    "rc_latency": "runs/paper_figs_rc80/latency_q.png",
    "rc_relpanels": "runs/rc80full_consensus/case_study/relationship_panels_q.png",
    "hl_simfoot": "runs/paper_figs_hl30/sim_footprint_q.png",
    "hl_structure": "runs/paper_figs_hl30/structure_q.png",
    "hl_growth": "runs/paper_figs_hl30/growth_q.png",
    "hl_latency": "runs/paper_figs_hl30/latency_q.png",
    "hl_relpanels": "runs/hl30full_consensus/case_study/relationship_panels_q.png",
}
IMG = {k: "data:image/png;base64," + base64.b64encode(open(v, "rb").read()).decode()
       for k, v in FIGS.items()}

def _scrub(o):
    """Strip U+FFFD from every string (token-truncation artifact in stored
    memory text; fixed at the source in textlen, scrubbed here for display)."""
    if isinstance(o, str):
        return o.replace("\ufffd", "")
    if isinstance(o, list):
        return [_scrub(x) for x in o]
    if isinstance(o, dict):
        return {k: _scrub(v) for k, v in o.items()}
    return o

S = _scrub(json.load(open("runs/paper_stats_g80.json", encoding="utf-8")))
RU = _scrub(json.load(open("runs/paper_stats_ru40.json", encoding="utf-8")))
RUC = RU["consensus"]; RUR = RU["relations"]; RUE = RU["auto_expand"]
RC = _scrub(json.load(open("runs/paper_stats_rc80.json", encoding="utf-8")))
RCC = RC["consensus"]; RCR = RC["relations"]; RCE = RC["auto_expand"]
rc_mex = RC["merge_examples"]
HL = _scrub(json.load(open("runs/paper_stats_hl30.json", encoding="utf-8")))
HLC = HL["consensus"]; HLR = HL["relations"]; HLE = HL["auto_expand"]
hl_mex = HL["merge_examples"]
Q = json.load(open("runs/results_g40.json", encoding="utf-8"))  # quality scored at the 40-tick checkpoint
QR = json.load(open("runs/results_ru40.json", encoding="utf-8"))  # RU quality at 40 ticks
def _slim_graphs(path):
    _G = json.loads(open(path, encoding="utf-8").read().replace("\ufffd", ""))
    _aidx = {n["id"]: i for i, n in enumerate(_G["affiliation"]["nodes"])}
    for _n in _G["affiliation"]["nodes"]:
        _n.pop("id", None)
    _G["affiliation"]["edges"] = [[_aidx[e["s"]], _aidx[e["t"]]] for e in _G["affiliation"]["edges"]]
    _midx = {m["id"]: i for i, m in enumerate(_G["trilayer"]["mems"])}
    for _m in _G["trilayer"]["mems"]:
        _m.pop("id", None)
    _G["trilayer"]["own"] = [{"a": o["a"], "m": _midx[o["m"]], "multi": o["multi"]} for o in _G["trilayer"]["own"]]
    _G["trilayer"]["aff"] = [[_midx[e["s"]], _midx[e["t"]], 1 if e["overlap"] else 0] for e in _G["trilayer"]["aff"]]
    return json.dumps(_G, ensure_ascii=False, separators=(",", ":"))

GRAPHS_JSON = _slim_graphs("runs/g80full_consensus/case_study/graphs.json")
GRAPHS_RU_JSON = _slim_graphs("runs/ru40full_consensus/case_study/graphs.json")
GRAPHS_RC_JSON = _slim_graphs("runs/rc80full_consensus/case_study/graphs.json")
GRAPHS_HL_JSON = _slim_graphs("runs/hl30full_consensus/case_study/graphs.json")

def cell(k, key):
    a = Q[k]["agg"][key]
    return f"{a['mean']:.2f}&thinsp;&plusmn;.{int(round(a['std']*100)):02d}"
def gn(k):
    return f"{Q[k]['agg']['grnd_n']:.0f}"

C = S["consensus"]; GA = S["generative_agents"]; GM = S["g_memory"]; CO = S["collaborative"]
R = S["relations"]; G = S["growth"]; AE = S["auto_expand"]
ao_ratio = R["AO"]["talk_mean"] / max(R["AO"]["non_mean"], 1e-9)
am_ratio = R["AM"]["talk_mean"] / max(R["AM"]["non_mean"], 1e-9)
mex = S["merge_examples"]
def owners_zh(ow):
    return ", ".join(ow)

CSS = """
<style>
:root{
  --paper:#fbfbfc; --card:#ffffff; --ink:#1a1d24; --muted:#5b6472; --faint:#8892a0;
  --line:#e7e9ee; --line2:#eef0f4; --accent:#2563eb; --accent-soft:#eaf0fe;
  --good:#0f9d6b; --warn:#c07a12; --warn-soft:#fbf1df; --cost:#d63b3b;
  --serif:Charter,"Bitstream Charter","Sitka Text",Georgia,Cambria,"Times New Roman",serif;
  --sans:system-ui,-apple-system,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif;
  --mono:ui-monospace,"SF Mono","JetBrains Mono",Menlo,Consolas,monospace;
}
@media (prefers-color-scheme:dark){:root{
  --paper:#101317; --card:#171b21; --ink:#e8ebf0; --muted:#a2acbc; --faint:#6f7987;
  --line:#252b34; --line2:#20252d; --accent:#6ea1ff; --accent-soft:#182437;
  --good:#3fd39a; --warn:#e3ab4f; --warn-soft:#2a2214; --cost:#f0736f;
}}
:root[data-theme="light"]{
  --paper:#fbfbfc; --card:#ffffff; --ink:#1a1d24; --muted:#5b6472; --faint:#8892a0;
  --line:#e7e9ee; --line2:#eef0f4; --accent:#2563eb; --accent-soft:#eaf0fe;
  --good:#0f9d6b; --warn:#c07a12; --warn-soft:#fbf1df; --cost:#d63b3b;
}
:root[data-theme="dark"]{
  --paper:#101317; --card:#171b21; --ink:#e8ebf0; --muted:#a2acbc; --faint:#6f7987;
  --line:#252b34; --line2:#20252d; --accent:#6ea1ff; --accent-soft:#182437;
  --good:#3fd39a; --warn:#e3ab4f; --warn-soft:#2a2214; --cost:#f0736f;
}
*{box-sizing:border-box}
body{margin:0;background:var(--paper);color:var(--ink);font-family:var(--serif);
  line-height:1.62;-webkit-font-smoothing:antialiased;font-size:17px}
.wrap{max-width:840px;margin:0 auto;padding:56px 24px 96px}
h1{font-family:var(--sans);font-weight:760;font-size:31px;line-height:1.15;letter-spacing:-.02em;
  margin:0 0 10px;text-wrap:balance;text-align:center}
.sub{font-size:17px;color:var(--muted);margin:0 auto 18px;max-width:60ch;text-align:center}
.byline{font-family:var(--sans);font-size:12.5px;color:var(--faint);display:flex;gap:14px;
  flex-wrap:wrap;justify-content:center;border-top:1px solid var(--line);
  border-bottom:1px solid var(--line);padding:10px 0;margin:0 0 30px}
.byline b{color:var(--muted);font-weight:600}
h2{font-family:var(--sans);font-weight:720;font-size:21px;letter-spacing:-.01em;margin:46px 0 6px;
  padding-top:18px;border-top:1px solid var(--line)}
h2 .n{font-family:var(--mono);font-size:13px;color:var(--accent);font-weight:600;
  border:1px solid var(--accent);border-radius:5px;padding:1px 7px;margin-right:10px}
h3{font-family:var(--sans);font-weight:680;font-size:16px;margin:26px 0 4px}
h4{font-family:var(--sans);font-weight:660;font-size:14px;margin:18px 0 2px}
p{margin:11px 0;max-width:68ch}
code{font-family:var(--mono);font-size:.85em;background:var(--line2);padding:1.5px 5px;border-radius:4px}
.abstract{background:var(--card);border:1px solid var(--line);border-left:3px solid var(--accent);
  border-radius:10px;padding:18px 22px;margin:0 0 26px}
.abstract .h{font-family:var(--sans);font-size:12px;letter-spacing:.12em;text-transform:uppercase;
  color:var(--accent);font-weight:680;margin:0 0 8px}
.abstract p{margin:0;max-width:none;color:var(--muted);font-size:15.5px}
.abstract b{color:var(--ink)}
.contrib{font-family:var(--serif);max-width:68ch;padding-left:20px}
.contrib li{margin:6px 0}
.tw{overflow-x:auto;margin:18px 0;border:1px solid var(--line);border-radius:11px}
table{border-collapse:collapse;width:100%;font-family:var(--sans);font-size:13.5px;
  font-variant-numeric:tabular-nums}
th,td{text-align:right;padding:10px 14px;border-bottom:1px solid var(--line2);white-space:nowrap}
th:first-child,td:first-child{text-align:left}
thead th{font-size:11px;letter-spacing:.05em;text-transform:uppercase;color:var(--faint);
  font-weight:640;background:var(--card)}
tbody tr:last-child td{border-bottom:none}
tr.hi td{background:var(--accent-soft)}
tr.hi td:first-child{font-weight:700;color:var(--accent)}
td .u{color:var(--faint);font-size:11.5px}
.best{color:var(--good);font-weight:700}
caption{caption-side:bottom;font-family:var(--sans);font-size:12.5px;color:var(--muted);
  text-align:left;padding:10px 14px;line-height:1.5}
caption b{color:var(--ink)}
figure{margin:22px 0;background:var(--card);border:1px solid var(--line);border-radius:12px;
  padding:14px;overflow:hidden}
figure img{display:block;width:100%;height:auto;border-radius:6px}
figure.two{display:grid;grid-template-columns:1fr 1fr;gap:12px;align-items:start}
figcaption{font-family:var(--sans);font-size:12.5px;color:var(--muted);margin-top:10px;
  line-height:1.55;grid-column:1/-1}
figcaption b{color:var(--ink);font-weight:660}
.quote{font-family:var(--sans);font-size:13px;background:var(--line2);border-radius:8px;
  padding:12px 15px;margin:12px 0;color:var(--muted);line-height:1.6}
.quote b{color:var(--ink)}
.rel{background:var(--card);border:1px solid var(--line);border-radius:11px;padding:14px 17px;margin:12px 0}
.rel h4{font-size:14px;margin:0 0 5px;font-weight:700}
.rel h4 .rx{font-family:var(--mono);color:var(--accent);margin-right:8px}
.rel p{font-family:var(--sans);font-size:13.5px;color:var(--muted);margin:0;max-width:none}
.rel .stat{font-family:var(--mono);color:var(--good);font-weight:600}
tr.grp td{background:var(--card);font-family:var(--sans);font-weight:700;font-size:12.5px;color:var(--muted);letter-spacing:.02em}
h5{font-family:var(--sans);font-size:13.5px;font-weight:700;margin:26px 0 8px;color:var(--ink)}
ul.body{max-width:68ch}
ul.body li{margin:6px 0}
.refs{font-family:var(--sans);font-size:13.5px;color:var(--muted);padding-left:26px}
.refs li{margin:7px 0;line-height:1.5}
.refs i{color:var(--ink);font-style:italic}
.foot{font-family:var(--sans);font-size:12px;color:var(--faint);margin-top:56px;
  border-top:1px solid var(--line);padding-top:14px}
.ig{position:relative;width:100%;border-radius:8px;overflow:hidden;background:var(--paper);
  border:1px solid var(--line2);cursor:grab}
.ig canvas{display:block;width:100%;height:100%}
.ig .tip{position:absolute;pointer-events:none;display:none;max-width:340px;
  background:var(--card);border:1px solid var(--line);border-radius:8px;
  padding:8px 11px;font-family:var(--sans);font-size:12px;line-height:1.5;color:var(--ink);
  box-shadow:0 4px 14px rgba(0,0,0,.12);z-index:5}
.ig .tip b{color:var(--accent)}
.ig .hint{position:absolute;right:10px;top:8px;font-family:var(--sans);font-size:10.5px;
  color:var(--faint);pointer-events:none}
@media (max-width:640px){.wrap{padding:40px 16px 72px}h1{font-size:25px}
  figure.two{grid-template-columns:1fr}body{font-size:16px}}
</style>
"""

HTML = CSS + f"""
<div class="wrap">

<h1>Agentsensus: Consensus-Compressed Shared Memory for<br>Multi-Agent Story-World Simulation</h1>
<p class="sub">A shared long-term memory that merges agents&rsquo; equivalent memories into multi-witness records and self-organizes into a navigable memory graph.</p>
<div class="byline">
  <span><b>Scenarios</b> 三国演义 (80 ticks, 33 active agents) &middot; Russia&ndash;Ukraine (40 ticks, 47 active) &middot; 红楼梦 (80 ticks, 34 active) &middot; Hamlet (30 ticks, 16 active)</span>
  <span><b>Checkpointing</b> every 20 ticks</span>
  <span><b>Model</b> gpt-5-mini</span>
</div>

<div class="abstract"><div class="h">Abstract</div>
<p>Multi-agent story-world simulations give every agent a private memory stream, so the same event is stored once per witness, memories of one plotline are scattered across isolated stores, and nothing connects what one agent knows to what another experienced. We present <b>Agentsensus</b>, a story-world simulation framework whose shared long-term memory performs <b>consensus compression</b>: every deposited memory is atomized into self-contained statements, semantically matched against the store, and &mdash; when an LLM judge deems two statements equivalent &mdash; merged into a single record whose <i>owner-set</i> is the union of its witnesses. Atomized pieces of one compound memory are automatically linked (<i>affiliated</i>), and recall automatically expands one hop along these links, so the memory self-organizes into a graph that retrieval exploits without any agent-side memory management. On an 80-tick simulation of <i>Romance of the Three Kingdoms</i> seeded with memories sedimented from chapters 1&ndash;40, and compared under an equal-granularity protocol against three per-agent memory baselines (Generative-Agents-style streams, G-Memory-style hierarchical graph, ACL-based collaborative memory), consensus is the only backend whose simulation memories become shared ({C['sh_pct']}% multi-owner, merges reaching {S['max_owners']} witnesses; baselines 0%) and linked ({C['aff_pct']}% with affiliated edges; baselines 0%), while also writing the fewest entries ({C['sim_new']} vs {GA['sim_new']}&ndash;{CO['sim_new']}). The emergent memory graph tracks the story&rsquo;s social structure: agents who talk overlap in memory {ao_ratio:.0f}&times; more than those who don&rsquo;t, linked memories share witnesses at Jaccard {R['MO']['link_mean']:.2f} vs {R['MO']['non_mean']:.2f}, and cross-agent memory links run almost exclusively between conversing agents. A 40-tick replication on a real-world Russia&ndash;Ukraine scenario reproduces the full structural signature &mdash; sharing grows 6%&rarr;9%&rarr;14% as the horizon doubles and redoubles, with one presidential directive merging across ten institutional witnesses &mdash; confirming that consensus structure compounds with horizon in a real-world setting.</p>
</div>

<h2><span class="n">1</span> Introduction</h2>
<p>Story-world simulation places dozens of LLM-driven characters into a fictional world and lets a narrative unfold from their interactions. The dominant memory design, inherited from Generative Agents [1] and adopted by most subsequent frameworks [2, 8], gives each character a private, append-only memory stream. This is faithful to individual cognition, but for a <i>shared</i> world it creates three structural problems that worsen with scale:</p>
<ul class="body">
<li><b>P1 &mdash; Witness-multiplied redundancy.</b> Every shared experience is stored once per participant: a war council attended by ten officers produces ten near-identical records, and a novel-seeded world multiplies this by thousands of canonical events. Storage, embedding cost, and retrieval-index size all scale with the number of witnesses rather than the number of events &mdash; in our testbed the per-agent baselines carry 3&times; the entries of the consensus store for the same seeded history.</li>
<li><b>P2 &mdash; Fragmented, divergence-prone world knowledge.</b> The same event exists as N independently-worded copies that only drift further apart as agents paraphrase, summarize, and reflect. No mechanism reconciles them, no record knows its counterparts exist, and nothing connects a courier&rsquo;s report to the battle it describes or the order it triggers &mdash; the connective tissue of the story exists nowhere in the memory substrate, only implicitly in the transcript. Retrieval consequently returns one agent&rsquo;s partial, possibly stale view even when the collective already holds the full picture.</li>
<li><b>P3 &mdash; Memory management that agents never perform.</b> Stream designs expose maintenance operations &mdash; linking related records, revising stale ones, forgetting duplicates &mdash; and implicitly rely on agents to use them. Empirically they do not: across two models and all four backends we test, agents issued <i>zero</i> calls to every discretionary memory-management action, even with documentation, worked examples, and an id-free interface (&sect;5.6). A memory architecture that depends on agent-side curation therefore never acquires structure in practice.</li>
</ul>
<p>Agentsensus answers all three problems with one architectural commitment: <b>the world&rsquo;s memory is a single shared store, and sharing is computed, not assumed</b>. Memories remain owner-scoped &mdash; an agent recalls only what it owns &mdash; but when two agents record the same event, an equivalence mechanism detects it and folds the records into one entry owned by both (addressing P1 and the divergence half of P2). Pieces split from one compound memory are automatically cross-linked and recall automatically surfaces linked memories the caller also owns, giving the store the connective tissue P2 demands. And because of P3, <i>every</i> structural mechanism runs inside <code>remember</code> and <code>recall</code> themselves &mdash; the only two memory operations agents demonstrably use &mdash; rather than being delegated to agent-side curation.</p>
<p><b>Contributions.</b></p>
<ul class="contrib">
<li>A story-world simulation framework with a deterministic tick-barrier scheduler, passive environments and information carriers, kernel-held conversation threads with distance-delayed delivery, and full-system checkpoints enabling bit-for-bit resumption.</li>
<li>A <b>consensus-compressed shared memory</b>: self-contained atomization, semantic-prefilter + LLM-judged equivalence merging with owner-set union, automatic affiliation of split pieces, and auto-expanding owner-scoped recall.</li>
<li>An <b>equal-granularity, simulation-only evaluation protocol</b> against three faithful baseline reimplementations, isolating the memory mechanism from confounds of storage granularity and seeded content.</li>
<li>A three-layer <b>case-study methodology</b> (interaction graph, memory-affiliation graph, ownership relation) quantifying how the emergent memory structure tracks the story&rsquo;s social structure.</li>
</ul>

<h2><span class="n">2</span> Related Work</h2>
<h4>Memory for LLM agents.</h4>
<p>Generative Agents [1] established the stream-of-memories design &mdash; per-agent records scored by recency, importance, and relevance, periodically compressed into reflections &mdash; which subsequent agent frameworks largely inherit [8]. MemGPT [4] treats context as a memory hierarchy managed by the LLM itself; Reflexion [5] persists self-feedback across episodes. Closer to our graph mechanisms, HippoRAG [6] indexes a corpus as an entity graph for multi-hop retrieval, and A-MEM [7] links an agent&rsquo;s notes into an evolving network. These systems structure the memory of <i>one</i> agent or one corpus; Agentsensus structures memory <i>across</i> agents, with ownership as a first-class dimension.</p>
<h4>Multi-agent memory.</h4>
<p>G-Memory [3] organizes a multi-agent system&rsquo;s history into a hierarchical insight/query/interaction graph queried at both team and agent level. Collaborative-memory designs [9] share fragments across users under dynamic access control. Both keep per-contributor records intact; neither merges equivalent records across contributors &mdash; the core of consensus compression &mdash; nor derives the memory graph automatically from deposit-time structure.</p>
<h4>Story-world simulation.</h4>
<p>BookWorld [2] builds interactive agent societies from novels, with per-character memories extracted from the source text; our sedimentation stage follows the same motivation. Agentsensus differs in making the sedimented and runtime memory a single consensus store, and in evaluating the memory substrate itself (footprint, sharing, graph structure) rather than only the produced narrative.</p>

<h2><span class="n">3</span> The Agentsensus Framework</h2>

<h3>3.1 &nbsp;Design motivation</h3>
<p>The per-agent memory stream is the default because it is the obvious model of a mind: what an agent knows is what it saw. In a <i>shared world</i>, however, that model makes three structural commitments that the designer never explicitly chose, and each one compounds with the number of agents and the length of the run.</p>
<p><b>Storage scales with witnesses, not with events.</b> A council attended by ten officers is ten records. Nothing in the system can tell that they describe one event, so embedding cost, index size, and retrieval noise all grow with the cast rather than with the story. Seeding a world from a novel multiplies the effect before tick&nbsp;0: on the same sedimented chapters the per-agent baselines carry 3.3&ndash;5.7&times; the entries of a merged store (&sect;5.1).</p>
<p><b>Nothing reconciles the copies, and nothing connects them.</b> The ten records are ten independently-worded paraphrases that only diverge further as agents summarize and reflect. No record knows its counterparts exist; no edge links a courier&rsquo;s report to the battle it describes or to the order it triggered. The connective tissue of the story lives in the transcript, not in the memory, so retrieval returns one agent&rsquo;s partial view even when the collective already holds the whole.</p>
<p><b>The interfaces that could fix this go unused.</b> Stream designs expose maintenance operations &mdash; link related records, revise stale ones, forget duplicates &mdash; and rely on agents to call them. Across two models and all four backends we measure <i>zero</i> such calls (&sect;5.6), with documentation, worked examples, and an id-free interface all in place. Any structure that depends on agent-side curation therefore never materializes.</p>
<p>Agentsensus answers all three with one commitment: <b>the world&rsquo;s memory is a single store, and sharing is computed rather than assumed</b>. Three design decisions follow, and the rest of this section is their mechanics. <b>D1 &mdash; equivalence merging:</b> when two agents record the same event, the write path detects it and folds the records into one row whose owner-set is the union of its witnesses, so cost tracks events. <b>D2 &mdash; deposit-time graph:</b> the atoms split from one deposit are linked to each other as a side effect of writing, so the graph exists without anyone maintaining it. <b>D3 &mdash; structure inside <code>remember</code>/<code>recall</code>:</b> because agents demonstrably use only those two operations, every mechanism lives inside them; nothing is delegated to agent discretion.</p>
<p>Figure&nbsp;1 makes the difference concrete on a single event.</p>

<figure>
<svg viewBox="0 0 840 330" role="img" aria-label="One event witnessed by four agents becomes four unlinked rows under per-agent designs and one four-owner linked row under consensus" style="max-width:100%;height:auto">
  <defs>
    <marker id="ar" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
      <path d="M0,0 L10,5 L0,10 z" fill="currentColor"/>
    </marker>
  </defs>
  <g fill="none" stroke="currentColor" stroke-width="1.3" font-family="system-ui,sans-serif">
    <rect x="250" y="14" width="340" height="34" rx="6"/>
    <text x="420" y="36" text-anchor="middle" font-size="16.2" stroke="none" fill="currentColor">one event e, witnessed by A, B, C, D</text>
    <line x1="120" y1="48" x2="120" y2="86" marker-end="url(#ar)"/>
    <line x1="320" y1="48" x2="320" y2="86" marker-end="url(#ar)"/>
    <line x1="520" y1="48" x2="520" y2="86" marker-end="url(#ar)"/>
    <line x1="720" y1="48" x2="720" y2="86" marker-end="url(#ar)"/>
    <text x="238" y="32" text-anchor="end" font-size="12.5" stroke="none" fill="currentColor" opacity=".75">deposit</text>

    <text x="120" y="104" text-anchor="middle" font-size="15.6" stroke="none" fill="currentColor" font-weight="600">Generative-Agents</text>
    <rect x="40" y="116" width="160" height="26" rx="4"/><text x="120" y="133" text-anchor="middle" font-size="13.8" stroke="none" fill="currentColor">e &nbsp;|&nbsp; owner A</text>
    <rect x="40" y="148" width="160" height="26" rx="4"/><text x="120" y="165" text-anchor="middle" font-size="13.8" stroke="none" fill="currentColor">e &nbsp;|&nbsp; owner B</text>
    <rect x="40" y="180" width="160" height="26" rx="4"/><text x="120" y="197" text-anchor="middle" font-size="13.8" stroke="none" fill="currentColor">e &nbsp;|&nbsp; owner C</text>
    <rect x="40" y="212" width="160" height="26" rx="4"/><text x="120" y="229" text-anchor="middle" font-size="13.8" stroke="none" fill="currentColor">e &nbsp;|&nbsp; owner D</text>
    <rect x="40" y="248" width="160" height="26" rx="4" stroke-dasharray="4 3"/><text x="120" y="265" text-anchor="middle" font-size="13.1" stroke="none" fill="currentColor" opacity=".8">reflection (own stream)</text>
    <text x="120" y="296" text-anchor="middle" font-size="13.8" stroke="none" fill="currentColor" opacity=".8">4 rows, no cross-agent edge</text>

    <text x="320" y="104" text-anchor="middle" font-size="15.6" stroke="none" fill="currentColor" font-weight="600">G-Memory</text>
    <rect x="240" y="116" width="160" height="26" rx="4"/><text x="320" y="133" text-anchor="middle" font-size="13.8" stroke="none" fill="currentColor">e &nbsp;|&nbsp; owner A</text>
    <rect x="240" y="148" width="160" height="26" rx="4"/><text x="320" y="165" text-anchor="middle" font-size="13.8" stroke="none" fill="currentColor">e &nbsp;|&nbsp; owner B</text>
    <rect x="240" y="180" width="160" height="26" rx="4"/><text x="320" y="197" text-anchor="middle" font-size="13.8" stroke="none" fill="currentColor">e &nbsp;|&nbsp; owner C</text>
    <rect x="240" y="212" width="160" height="26" rx="4"/><text x="320" y="229" text-anchor="middle" font-size="13.8" stroke="none" fill="currentColor">e &nbsp;|&nbsp; owner D</text>
    <rect x="240" y="248" width="160" height="26" rx="4" stroke-dasharray="4 3"/><text x="320" y="265" text-anchor="middle" font-size="13.1" stroke="none" fill="currentColor" opacity=".8">insight node (per owner)</text>
    <text x="320" y="296" text-anchor="middle" font-size="13.8" stroke="none" fill="currentColor" opacity=".8">4 rows + within-owner edges</text>

    <text x="520" y="104" text-anchor="middle" font-size="15.6" stroke="none" fill="currentColor" font-weight="600">Collaborative</text>
    <rect x="440" y="116" width="160" height="26" rx="4"/><text x="520" y="133" text-anchor="middle" font-size="13.8" stroke="none" fill="currentColor">e &nbsp;|&nbsp; acl A</text>
    <rect x="440" y="148" width="160" height="26" rx="4"/><text x="520" y="165" text-anchor="middle" font-size="13.8" stroke="none" fill="currentColor">e &nbsp;|&nbsp; acl B</text>
    <rect x="440" y="180" width="160" height="26" rx="4"/><text x="520" y="197" text-anchor="middle" font-size="13.8" stroke="none" fill="currentColor">e &nbsp;|&nbsp; acl C</text>
    <rect x="440" y="212" width="160" height="26" rx="4"/><text x="520" y="229" text-anchor="middle" font-size="13.8" stroke="none" fill="currentColor">e &nbsp;|&nbsp; acl D</text>
    <text x="520" y="296" text-anchor="middle" font-size="13.8" stroke="none" fill="currentColor" opacity=".8">4 rows, ACL-scoped reads</text>

    <text x="720" y="104" text-anchor="middle" font-size="15.6" stroke="none" fill="var(--accent)" font-weight="700">Consensus (ours)</text>
    <rect x="640" y="116" width="160" height="58" rx="4" stroke="var(--accent)" stroke-width="1.8"/>
    <text x="720" y="139" text-anchor="middle" font-size="13.8" stroke="none" fill="currentColor">e</text>
    <text x="720" y="158" text-anchor="middle" font-size="13.8" stroke="none" fill="var(--accent)" font-weight="600">owners A, B, C, D</text>
    <line x1="720" y1="174" x2="720" y2="196" stroke="var(--accent)" marker-end="url(#ar)"/>
    <text x="732" y="190" font-size="12.5" stroke="none" fill="currentColor" opacity=".8">affiliated</text>
    <rect x="640" y="196" width="160" height="26" rx="4" stroke="var(--accent)"/>
    <text x="720" y="213" text-anchor="middle" font-size="13.8" stroke="none" fill="currentColor">sibling atom of e</text>
    <text x="720" y="296" text-anchor="middle" font-size="13.8" stroke="none" fill="var(--accent)" font-weight="600">1 row, 4 owners, linked</text>
  </g>
</svg>
<figcaption><b>Figure 1. What one event becomes in each design.</b> Four agents witness the same event and each deposits it. The three per-agent designs store four rows that no mechanism relates to one another; their internal structure (Generative-Agents reflections, G-Memory insight nodes) is built <i>within</i> one owner&rsquo;s records and never crosses agents. Consensus detects the equivalence at write time and keeps one row whose owner-set is the union of the witnesses, linked to the other atoms of the same deposit. The columns are the mechanisms&rsquo; outputs, not a storage-efficiency claim: &sect;5.1 measures what this does over a full run.</figcaption>
</figure>

<h3>3.2 &nbsp;System overview</h3>
<p>Agentsensus is three subsystems. An offline <b>sedimentation pipeline</b> turns a source text into a memory-grounded initial world. A deterministic <b>tick-barrier kernel</b> schedules agents, routes messages, and snapshots the entire system. The <b>consensus shared memory</b> holds every agent&rsquo;s knowledge in one store, with D1&ndash;D3 implemented inside its write and read paths. Data flows left to right at start-up &mdash; sedimentation seeds both the store and the world state &mdash; and cycles between kernel and store at run time: Phase-2 action effects write into the store and into conversation threads, and both feed the next tick&rsquo;s agent views through owner-scoped recall and the conversation roster.</p>
<figure>
  <img src="{IMG['arch']}" alt="Agentsensus architecture">
  <figcaption><b>Figure 2. System architecture.</b> Left: the offline sedimentation pipeline (novel &rarr; witnessed atomic events &rarr; per-backend ingest &rarr; boundary-state finalization &rarr; seeded world). Center: the tick-barrier kernel &mdash; numbered stages run each tick; conversation threads and the world map are kernel-held state; the checkpointer snapshots agents&rsquo; short-term state, kernel runtime, and the entire store every 20 ticks for bit-for-bit resumption. Right: the consensus shared memory &mdash; the row data model, the four-stage write path, the two-stage read path, query-addressed mutations, and the empirical design rule behind placing every mechanism inside <code>remember</code>/<code>recall</code>.</figcaption>
</figure>

<h3>3.3 &nbsp;World model and tick-barrier kernel</h3>
<p><b>Entities.</b> A world is a set of agents on a location map with pairwise travel distances. <b>Characters</b> are LLM-driven: each holds a persona, a goal stack, a status register, and a short-term FIFO of recent actions; each decision is one LLM call that receives a rendered view (tick, goals, status, FIFO, co-located agents, conversation roster, known locations, plus contextual hints) and returns one action as JSON. <b>Environments</b> and <b>information carriers</b> are passive: they own memories (deposited by sedimentation or by characters&rsquo; <code>act_on</code>) but never take turns &mdash; a character&rsquo;s <code>act_on</code>/<code>read</code> is served synchronously by the kernel against the target&rsquo;s own memories, costing no extra LLM calls and giving places and documents durable, queryable state.</p>
<p><b>Scheduling.</b> Each tick runs two phases under a barrier. Phase&nbsp;1 builds every awake character&rsquo;s view from the <i>same</i> pre-tick snapshot and issues all decisions concurrently; because views are frozen before any decision, LLM latency cannot change what any agent observes. Phase&nbsp;2 applies the returned actions sequentially in a fixed agent order, so conflicting effects resolve deterministically and event order is reproducible independent of API timing. Agents sleep only by explicit <code>wait</code>; a single sleep is capped (20 ticks) after we observed uncapped waits produce narrative deadlocks &mdash; a character who delegated a task and slept &ldquo;until the report arrives&rdquo; was simply never messaged again and stayed silent for 52 ticks. A <code>wake=true</code> message still interrupts sleep early.</p>
<p><b>Messaging.</b> Messages are not agent-held inboxes but kernel-held <b>conversation threads</b>, one per interlocutor pair. Co-located speech delivers at the next tick; remote messages travel for their map distance in ticks, so information propagates at the speed of couriers rather than instantaneously. Delivery increments the recipient&rsquo;s unread counter (surfaced in its view roster) and, by default, wakes it; reading is an explicit <code>read_thread</code> action. The same threads also log observation and environment interactions, giving each pair a complete interaction history.</p>
<p><b>Checkpointing.</b> Every 20 ticks the kernel atomically snapshots the complete system &mdash; each agent&rsquo;s short-term state (FIFO, goal stack, status, sleep timer), kernel runtime (presence, in-transit moves, undelivered messages, conversation threads, event counter), and the entire memory store including embeddings. A resumed run continues bit-for-bit; the long-horizon results in &sect;5 are consecutive resumed stages of one continuous run per backend.</p>

<h3>3.4 &nbsp;Sedimentation: from source text to memory-grounded world</h3>
<p>The pipeline converts the sediment span into the initial world in four steps. (i) <b>Extraction and attribution</b>: an LLM pass extracts events chapter by chapter and attributes each to the characters who witnessed it, producing atomic, story-ordered records with owner-sets. (ii) <b>Per-backend ingest</b>: each memory backend stores these events under its own rule &mdash; the consensus store keeps one merged row per event carrying the full owner-set, while per-agent baselines fan out one row per witness &mdash; so every method starts from the initial state its own mechanism would have produced, and baseline machinery (importance scoring, reflection, distillation) is run over the sediment before tick&nbsp;0. (iii) <b>Boundary-state finalization</b>: each character&rsquo;s aliveness and location at the story boundary are extracted from <i>its own memory timeline</i> (with a canon-knowledge fallback anchored to the boundary chapter); characters dead by the boundary are archived &mdash; they keep their memories as owners but are never scheduled &mdash; and living ones are placed at their last grounded location. (iv) The result is a world whose knowledge and geography are both grounded in the text.</p>

<h3>3.5 &nbsp;The consensus shared memory</h3>
<p><b>Data model.</b> The store is a single vector collection whose rows are (text, embedding, owner-set, affiliated-set, metadata). Owner membership is additionally materialized as indexed per-agent flags, so owner-scoped retrieval is a server-side filter rather than a post-hoc scan; the affiliated-set holds ids of related rows and is what makes the store a graph.</p>
<p><b>Write path.</b> Every <code>remember(text)</code> runs four stages. <i>(1) Atomization:</i> a compound deposit is split by an LLM into atomic statements, each required to be <b>self-contained</b> &mdash; pronouns resolved to names, who/what/where carried over &mdash; so a statement is interpretable without its siblings. All four backends share this exact stage (&sect;4.3), making entry counts comparable by construction. <i>(2) Candidate pre-filter:</i> each atom is embedded and matched against the store by cosine kNN with a deliberately permissive threshold (0.70): self-contained phrasings of the same event from different viewpoints embed measurably further apart than near-identical wordings, and at the conventional 0.86 <i>zero</i> cross-witness sim memories ever reached candidacy. <i>(3) Equivalence judging:</i> an LLM judge inspects the candidates and either selects the one that describes the same event or declines. The pre-filter only bounds the judge&rsquo;s candidate list; the judge is the actual gate, so the permissive threshold trades a few extra judge calls for recall of true matches. <i>(4) Merge or insert:</i> on a match the records fold into one row &mdash; owner-sets union, affiliated-sets union, the shorter text is kept &mdash; so N witnesses of one event cost one row; otherwise a fresh row is inserted. Finally, <b>auto-affiliation</b> mutually links the atoms split from one deposit: the memory graph is built as a side-effect of writing, by the mechanism rather than the agent.</p>
<p><b>Read path.</b> <code>recall(query)</code> retrieves the top-k semantic matches <i>among rows the caller owns</i>, then follows each hit&rsquo;s affiliated edges one hop and appends linked rows the caller also owns, marked <code>via_affiliated</code>. A single recall therefore returns an event&rsquo;s scattered pieces together. Expansion is deliberately uncapped; its cost is measured in &sect;5.2.</p>
<p><b>Cost placement.</b> The design pays at write time (one atomization call when a deposit is compound, one judge call when candidates pass the pre-filter) to keep the store small and structured; reads add only vector lookups. &sect;5.2&rsquo;s latency instrumentation quantifies both sides against the baselines.</p>

<h3>3.6 &nbsp;The four designs, module by module</h3>
<p>Figures&nbsp;3&ndash;6 draw the same picture four times: two agents deposit their accounts of one event on the left, the write path runs through the middle, the resulting store state sits on the right, and the read path is the return arrow along the bottom. Drawn this way the designs differ in exactly one structural respect &mdash; whether the two deposit lanes ever meet. In the three baselines they run in parallel to two separate rows; in consensus they converge at the equivalence judge. Everything else (atomization, embedding, owner-scoped reads) is held identical by the fairness protocol of &sect;4.3.</p>

<figure>
<svg viewBox="0 0 840 250" role="img" aria-label="Generative-Agents: two agents deposit into two private streams that never meet; a periodic reflection module summarizes within one stream" style="max-width:100%;height:auto">
  <defs><marker id="ar1" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="currentColor"/></marker></defs>
  <g fill="none" stroke="currentColor" stroke-width="1.3" font-family="system-ui,sans-serif">
    <rect x="14" y="42" width="86" height="36" rx="6"/><text x="57" y="65" text-anchor="middle" font-size="15" stroke="none" fill="currentColor">Agent A</text>
    <rect x="14" y="132" width="86" height="36" rx="6"/><text x="57" y="155" text-anchor="middle" font-size="15" stroke="none" fill="currentColor">Agent B</text>
    <line x1="100" y1="60" x2="146" y2="60" marker-end="url(#ar1)"/><text x="123" y="52" text-anchor="middle" font-size="12.5" stroke="none" fill="currentColor" opacity=".8">remember(e)</text>
    <line x1="100" y1="150" x2="146" y2="150" marker-end="url(#ar1)"/><text x="123" y="142" text-anchor="middle" font-size="12.5" stroke="none" fill="currentColor" opacity=".8">remember(e)</text>
    <rect x="148" y="42" width="104" height="36" rx="6"/><text x="200" y="65" text-anchor="middle" font-size="14.4" stroke="none" fill="currentColor">atomize</text>
    <rect x="148" y="132" width="104" height="36" rx="6"/><text x="200" y="155" text-anchor="middle" font-size="14.4" stroke="none" fill="currentColor">atomize</text>
    <line x1="252" y1="60" x2="292" y2="60" marker-end="url(#ar1)"/>
    <line x1="252" y1="150" x2="292" y2="150" marker-end="url(#ar1)"/>
    <rect x="294" y="42" width="128" height="36" rx="6"/><text x="358" y="59" text-anchor="middle" font-size="14.4" stroke="none" fill="currentColor">importance score</text><text x="358" y="72" text-anchor="middle" font-size="11.9" stroke="none" fill="currentColor" opacity=".75">1 LLM call per atom</text>
    <rect x="294" y="132" width="128" height="36" rx="6"/><text x="358" y="149" text-anchor="middle" font-size="14.4" stroke="none" fill="currentColor">importance score</text><text x="358" y="162" text-anchor="middle" font-size="11.9" stroke="none" fill="currentColor" opacity=".75">1 LLM call per atom</text>
    <line x1="422" y1="60" x2="470" y2="60" marker-end="url(#ar1)"/><text x="446" y="52" text-anchor="middle" font-size="12.5" stroke="none" fill="currentColor" opacity=".8">append</text>
    <line x1="422" y1="150" x2="470" y2="150" marker-end="url(#ar1)"/><text x="446" y="142" text-anchor="middle" font-size="12.5" stroke="none" fill="currentColor" opacity=".8">append</text>
    <rect x="472" y="30" width="170" height="60" rx="6"/><text x="557" y="49" text-anchor="middle" font-size="14.4" stroke="none" fill="currentColor" font-weight="600">A&rsquo;s private stream</text><text x="557" y="70" text-anchor="middle" font-size="13.8" stroke="none" fill="currentColor">e | owner A</text>
    <rect x="472" y="120" width="170" height="60" rx="6"/><text x="557" y="139" text-anchor="middle" font-size="14.4" stroke="none" fill="currentColor" font-weight="600">B&rsquo;s private stream</text><text x="557" y="160" text-anchor="middle" font-size="13.8" stroke="none" fill="currentColor">e | owner B</text>
    <rect x="672" y="60" width="150" height="90" rx="6" stroke-dasharray="4 3"/>
    <text x="747" y="82" text-anchor="middle" font-size="14.4" stroke="none" fill="currentColor">reflection</text>
    <text x="747" y="100" text-anchor="middle" font-size="11.9" stroke="none" fill="currentColor" opacity=".75">importance over</text>
    <text x="747" y="113" text-anchor="middle" font-size="11.9" stroke="none" fill="currentColor" opacity=".75">threshold &rarr; synthesize</text>
    <text x="747" y="131" text-anchor="middle" font-size="11.9" stroke="none" fill="currentColor" opacity=".75">stays inside one stream</text>
    <line x1="642" y1="70" x2="670" y2="88" stroke-dasharray="4 3" marker-end="url(#ar1)"/>
    <line x1="642" y1="140" x2="670" y2="122" stroke-dasharray="4 3" marker-end="url(#ar1)"/>
    <line x1="640" y1="215" x2="60" y2="215" marker-end="url(#ar1)"/>
    <text x="350" y="207" text-anchor="middle" font-size="13.1" stroke="none" fill="currentColor" opacity=".85">recall: kNN over the caller&rsquo;s own stream, scored by recency &times; importance &times; relevance</text>
  </g>
</svg>
<figcaption><b>Figure 3. Generative-Agents memory.</b> Each agent&rsquo;s deposit is atomized, scored for importance by an LLM call, and appended to that agent&rsquo;s private stream. The two lanes never meet, so one event held by two witnesses is two rows. Reflection (dashed) is the only structure-building module, and it operates strictly within a single stream.</figcaption>
</figure>

<figure>
<svg viewBox="0 0 840 250" role="img" aria-label="G-Memory: per-owner interaction rows plus a periodic distillation into insight nodes with derived-from edges, read by bi-level retrieval" style="max-width:100%;height:auto">
  <defs><marker id="ar2" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="currentColor"/></marker></defs>
  <g fill="none" stroke="currentColor" stroke-width="1.3" font-family="system-ui,sans-serif">
    <rect x="14" y="42" width="86" height="36" rx="6"/><text x="57" y="65" text-anchor="middle" font-size="15" stroke="none" fill="currentColor">Agent A</text>
    <rect x="14" y="132" width="86" height="36" rx="6"/><text x="57" y="155" text-anchor="middle" font-size="15" stroke="none" fill="currentColor">Agent B</text>
    <line x1="100" y1="60" x2="146" y2="60" marker-end="url(#ar2)"/><text x="123" y="52" text-anchor="middle" font-size="12.5" stroke="none" fill="currentColor" opacity=".8">remember(e)</text>
    <line x1="100" y1="150" x2="146" y2="150" marker-end="url(#ar2)"/><text x="123" y="142" text-anchor="middle" font-size="12.5" stroke="none" fill="currentColor" opacity=".8">remember(e)</text>
    <rect x="148" y="42" width="104" height="36" rx="6"/><text x="200" y="65" text-anchor="middle" font-size="14.4" stroke="none" fill="currentColor">atomize</text>
    <rect x="148" y="132" width="104" height="36" rx="6"/><text x="200" y="155" text-anchor="middle" font-size="14.4" stroke="none" fill="currentColor">atomize</text>
    <line x1="252" y1="60" x2="300" y2="60" marker-end="url(#ar2)"/>
    <line x1="252" y1="150" x2="300" y2="150" marker-end="url(#ar2)"/>
    <rect x="302" y="30" width="170" height="60" rx="6"/><text x="387" y="49" text-anchor="middle" font-size="14.4" stroke="none" fill="currentColor" font-weight="600">interaction tier (A)</text><text x="387" y="70" text-anchor="middle" font-size="13.8" stroke="none" fill="currentColor">e | owner A</text>
    <rect x="302" y="120" width="170" height="60" rx="6"/><text x="387" y="139" text-anchor="middle" font-size="14.4" stroke="none" fill="currentColor" font-weight="600">interaction tier (B)</text><text x="387" y="160" text-anchor="middle" font-size="13.8" stroke="none" fill="currentColor">e | owner B</text>
    <rect x="512" y="72" width="130" height="66" rx="6" stroke-dasharray="4 3"/>
    <text x="577" y="94" text-anchor="middle" font-size="14.4" stroke="none" fill="currentColor">distill</text>
    <text x="577" y="110" text-anchor="middle" font-size="11.9" stroke="none" fill="currentColor" opacity=".75">every 20 deposits</text>
    <text x="577" y="126" text-anchor="middle" font-size="11.9" stroke="none" fill="currentColor" opacity=".75">1 LLM call</text>
    <line x1="472" y1="62" x2="510" y2="86" stroke-dasharray="4 3" marker-end="url(#ar2)"/>
    <line x1="472" y1="148" x2="510" y2="124" stroke-dasharray="4 3" marker-end="url(#ar2)"/>
    <rect x="672" y="42" width="150" height="36" rx="6"/><text x="747" y="65" text-anchor="middle" font-size="13.8" stroke="none" fill="currentColor">insight node (A)</text>
    <rect x="672" y="132" width="150" height="36" rx="6"/><text x="747" y="155" text-anchor="middle" font-size="13.8" stroke="none" fill="currentColor">insight node (B)</text>
    <line x1="642" y1="92" x2="670" y2="72" marker-end="url(#ar2)"/>
    <line x1="642" y1="118" x2="670" y2="138" marker-end="url(#ar2)"/>
    <text x="700" y="105" text-anchor="middle" font-size="11.9" stroke="none" fill="currentColor" opacity=".8">derived_from</text>
    <line x1="820" y1="215" x2="60" y2="215" marker-end="url(#ar2)"/>
    <text x="430" y="207" text-anchor="middle" font-size="13.1" stroke="none" fill="currentColor" opacity=".85">recall: query the insight tier, then walk derived_from edges down to the caller&rsquo;s interaction rows</text>
  </g>
</svg>
<figcaption><b>Figure 4. G-Memory.</b> Deposits land as interaction rows in the depositing agent&rsquo;s tier; a periodic distillation pass (dashed) synthesizes insight nodes and links them to their sources with <code>derived_from</code> edges, which bi-level retrieval then walks. The graph is real but grows <i>within</i> an owner: the two lanes remain separate rows, and no edge crosses from A&rsquo;s record of the event to B&rsquo;s.</figcaption>
</figure>

<figure>
<svg viewBox="0 0 840 210" role="img" aria-label="Collaborative memory: deposits become access-controlled fragments read back through server-side ACL filtering" style="max-width:100%;height:auto">
  <defs><marker id="ar3" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="currentColor"/></marker></defs>
  <g fill="none" stroke="currentColor" stroke-width="1.3" font-family="system-ui,sans-serif">
    <rect x="14" y="34" width="86" height="36" rx="6"/><text x="57" y="57" text-anchor="middle" font-size="15" stroke="none" fill="currentColor">Agent A</text>
    <rect x="14" y="112" width="86" height="36" rx="6"/><text x="57" y="135" text-anchor="middle" font-size="15" stroke="none" fill="currentColor">Agent B</text>
    <line x1="100" y1="52" x2="146" y2="52" marker-end="url(#ar3)"/><text x="123" y="44" text-anchor="middle" font-size="12.5" stroke="none" fill="currentColor" opacity=".8">remember(e)</text>
    <line x1="100" y1="130" x2="146" y2="130" marker-end="url(#ar3)"/><text x="123" y="122" text-anchor="middle" font-size="12.5" stroke="none" fill="currentColor" opacity=".8">remember(e)</text>
    <rect x="148" y="34" width="104" height="36" rx="6"/><text x="200" y="57" text-anchor="middle" font-size="14.4" stroke="none" fill="currentColor">atomize</text>
    <rect x="148" y="112" width="104" height="36" rx="6"/><text x="200" y="135" text-anchor="middle" font-size="14.4" stroke="none" fill="currentColor">atomize</text>
    <line x1="252" y1="52" x2="300" y2="52" marker-end="url(#ar3)"/><text x="276" y="44" text-anchor="middle" font-size="12.5" stroke="none" fill="currentColor" opacity=".8">tag acl</text>
    <line x1="252" y1="130" x2="300" y2="130" marker-end="url(#ar3)"/><text x="276" y="122" text-anchor="middle" font-size="12.5" stroke="none" fill="currentColor" opacity=".8">tag acl</text>
    <rect x="302" y="22" width="200" height="60" rx="6"/><text x="402" y="41" text-anchor="middle" font-size="14.4" stroke="none" fill="currentColor" font-weight="600">fragment</text><text x="402" y="62" text-anchor="middle" font-size="13.8" stroke="none" fill="currentColor">e | acl A</text>
    <rect x="302" y="100" width="200" height="60" rx="6"/><text x="402" y="119" text-anchor="middle" font-size="14.4" stroke="none" fill="currentColor" font-weight="600">fragment</text><text x="402" y="140" text-anchor="middle" font-size="13.8" stroke="none" fill="currentColor">e | acl B</text>
    <rect x="562" y="60" width="260" height="62" rx="6"/>
    <text x="692" y="82" text-anchor="middle" font-size="14.4" stroke="none" fill="currentColor" font-weight="600">shared collection</text>
    <text x="692" y="102" text-anchor="middle" font-size="12.5" stroke="none" fill="currentColor" opacity=".8">one physical store, ACL-partitioned reads</text>
    <line x1="502" y1="52" x2="560" y2="76" marker-end="url(#ar3)"/>
    <line x1="502" y1="130" x2="560" y2="106" marker-end="url(#ar3)"/>
    <line x1="690" y1="178" x2="60" y2="178" marker-end="url(#ar3)"/>
    <text x="375" y="170" text-anchor="middle" font-size="13.1" stroke="none" fill="currentColor" opacity=".85">recall: kNN filtered server-side to fragments whose ACL admits the caller</text>
  </g>
</svg>
<figcaption><b>Figure 5. Collaborative memory.</b> Deposits become access-controlled fragments in one physical collection, and reads are ACL-filtered at the server. Sharing here is a <i>permission</i>, not a merge: A and B can be granted access to each other&rsquo;s fragments, but their two accounts of one event remain two rows, and nothing links them.</figcaption>
</figure>

<figure>
<svg viewBox="0 0 840 270" role="img" aria-label="Consensus memory: both agents' deposits converge at a pre-filter and an LLM equivalence judge that merges them into one row with a union owner-set, plus auto-affiliation and one-hop expanding recall" style="max-width:100%;height:auto">
  <defs><marker id="ar4" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="currentColor"/></marker>
  <marker id="ar4a" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="var(--accent)"/></marker></defs>
  <g fill="none" stroke="currentColor" stroke-width="1.3" font-family="system-ui,sans-serif">
    <rect x="8" y="42" width="78" height="36" rx="6"/><text x="47" y="65" text-anchor="middle" font-size="15" stroke="none" fill="currentColor">Agent A</text>
    <rect x="8" y="132" width="78" height="36" rx="6"/><text x="47" y="155" text-anchor="middle" font-size="15" stroke="none" fill="currentColor">Agent B</text>
    <line x1="86" y1="60" x2="122" y2="60" marker-end="url(#ar4)"/><text x="104" y="52" text-anchor="middle" font-size="12.5" stroke="none" fill="currentColor" opacity=".8">remember(e)</text>
    <line x1="86" y1="150" x2="122" y2="150" marker-end="url(#ar4)"/><text x="104" y="142" text-anchor="middle" font-size="12.5" stroke="none" fill="currentColor" opacity=".8">remember(e)</text>
    <rect x="124" y="40" width="134" height="40" rx="6"/><text x="191" y="58" text-anchor="middle" font-size="14.4" stroke="none" fill="currentColor">atomize + embed</text><text x="191" y="73" text-anchor="middle" font-size="11.9" stroke="none" fill="currentColor" opacity=".75">self-contained</text>
    <rect x="124" y="130" width="134" height="40" rx="6"/><text x="191" y="148" text-anchor="middle" font-size="14.4" stroke="none" fill="currentColor">atomize + embed</text><text x="191" y="163" text-anchor="middle" font-size="11.9" stroke="none" fill="currentColor" opacity=".75">self-contained</text>
    <line x1="258" y1="62" x2="290" y2="88" stroke="var(--accent)" marker-end="url(#ar4a)"/>
    <line x1="258" y1="148" x2="290" y2="122" stroke="var(--accent)" marker-end="url(#ar4a)"/>
    <rect x="292" y="84" width="152" height="42" rx="6" stroke="var(--accent)" stroke-width="1.7"/>
    <text x="368" y="103" text-anchor="middle" font-size="14.4" stroke="none" fill="currentColor">pre-filter</text>
    <text x="368" y="118" text-anchor="middle" font-size="11.9" stroke="none" fill="currentColor" opacity=".75">cosine &ge; 0.70, all rows</text>
    <line x1="444" y1="105" x2="472" y2="105" stroke="var(--accent)" marker-end="url(#ar4a)"/>
    <rect x="474" y="84" width="152" height="42" rx="6" stroke="var(--accent)" stroke-width="1.7"/>
    <text x="550" y="103" text-anchor="middle" font-size="14.4" stroke="none" fill="currentColor">equivalence judge</text>
    <text x="550" y="118" text-anchor="middle" font-size="11.9" stroke="none" fill="currentColor" opacity=".75">1 LLM call: same event?</text>
    <line x1="626" y1="105" x2="654" y2="105" stroke="var(--accent)" marker-end="url(#ar4a)"/>
    <text x="640" y="97" text-anchor="middle" font-size="11.9" stroke="none" fill="currentColor" opacity=".8">yes</text>
    <rect x="656" y="80" width="176" height="52" rx="6" stroke="var(--accent)" stroke-width="1.8"/>
    <text x="744" y="99" text-anchor="middle" font-size="14.4" stroke="none" fill="currentColor" font-weight="600">one row</text>
    <text x="744" y="119" text-anchor="middle" font-size="13.1" stroke="none" fill="var(--accent)" font-weight="600">e | owners A, B</text>
    <line x1="550" y1="126" x2="550" y2="166" marker-end="url(#ar4)"/>
    <text x="562" y="150" font-size="11.9" stroke="none" fill="currentColor" opacity=".8">no &rarr; insert new row</text>
    <rect x="656" y="152" width="176" height="36" rx="6" stroke-dasharray="4 3"/>
    <text x="744" y="174" text-anchor="middle" font-size="12.5" stroke="none" fill="currentColor" opacity=".85">auto-affiliate siblings</text>
    <line x1="744" y1="132" x2="744" y2="150" marker-end="url(#ar4)"/>
    <line x1="830" y1="238" x2="50" y2="238" stroke="var(--accent)" marker-end="url(#ar4a)"/>
    <text x="440" y="228" text-anchor="middle" font-size="12.5" stroke="none" fill="currentColor" opacity=".85">recall: owner-scoped kNN, then one hop along affiliated edges</text>
  </g>
</svg>
<figcaption><b>Figure 6. Consensus shared memory (ours).</b> The two deposit lanes converge: every atom is matched against the <i>whole</i> store, and an LLM judge decides whether it describes an event already recorded. On a match the rows fold into one whose owner-set is the union of the witnesses (D1); the atoms split from one deposit are linked to each other on the way in (D2); recall expands one hop along those links (D3). Accent marks the path that exists in no baseline.</figcaption>
</figure>

<h3>3.7 &nbsp;Query-addressed operations and the design rule</h3>
<p>No memory operation takes a raw id. <code>forget</code>, <code>revise_memory</code>, and the affiliation operations address a memory by a natural-language query that the kernel resolves to the caller&rsquo;s best-matching owned row, so owner-scoping is enforced at resolution and there is no id for an agent to mishandle. The design responds to a robust behavioral finding: LLM agents never thread opaque ids across turns &mdash; in earlier runs every id-based operation had &asymp;0 uses. Query addressing removes that interface barrier; the observation that agents <i>still</i> issue zero discretionary memory-management calls (&sect;5.6) is what elevates &ldquo;structure must live inside <code>remember</code>/<code>recall</code>&rdquo; from an implementation choice to the framework&rsquo;s central design rule.</p>

<h2><span class="n">4</span> Experimental Setup</h2>

<h3>4.1 &nbsp;Scenarios</h3>
<p>三国演义 chapters 1&ndash;40 are sedimented onto 191 canonical characters (33 active at the boundary, the rest archived as dead; ~6,000 consensus events). All four backends then run the <i>same</i> 80-tick simulation &mdash; same scenario file, same action repertoire, same model (<code>gpt-5-mini</code>; embeddings <code>text-embedding-3-small</code>) &mdash; in four checkpointed 20-tick stages.</p>
<p>To test that the mechanisms are not an artifact of one fictional world, the second scenario is <b>real-world</b>: a timeline of the Russia&ndash;Ukraine conflict sedimented through 2026-07 (1,533 events over 170 entities). Real-world boundary semantics replace the novel&rsquo;s: a figure is archived if, by the boundary, they are dead <i>or out of the conflict&rsquo;s stage</i> (out of office, dismissed, disbanded), with placements grounded in the timeline or, failing that, the person&rsquo;s workplace/role (final cast: 47 active, 14 archived, manually verified). All four backends run the same 40-tick simulation under the identical fairness protocol.</p>

<p>The third scenario returns to fiction in a different register: <b>红楼梦</b> (<i>Dream of the Red Chamber</i>), chapters 1&ndash;40 sedimented onto 152 registry characters (6,506 consensus events; chapters 41&ndash;80 held out). The active cast is the 37 characters above the memory threshold (34 living; 秦可卿, 贾瑞 and 秦钟, dead by chapter 40, stay archived owners), and the boundary state is a freeze-frame of chapter 40&rsquo;s garden banquet &mdash; 贾母 and 刘姥姥 at 大观楼, the touring party at 蘅芜苑, the musicians at 藕香榭 &mdash; grounded per character in the sediment and manually verified. Where 三国 is war and statecraft among factions, 红楼 is dense domestic society &mdash; one household, fine-grained relationships &mdash; a different social topology for the same mechanisms. All four backends run the same 80-tick simulation under the identical fairness protocol.</p>

<p>The fourth scenario is deliberately the smallest: <b>Hamlet</b>, Acts&nbsp;1&ndash;3 sedimented onto a 22-character registry (1,135 consensus events; Acts&nbsp;4&ndash;5 held out). Sixteen characters pass the memory threshold, plus Fortinbras, who owns no sediment memories at all &mdash; he never appears on stage before Act&nbsp;4 &mdash; but is retained because the continuation is his; England is likewise retained as an environment because it is where the sealed commission leads. Two characters are archived at the boundary: Polonius, killed behind the arras in 3.4, and the Ghost, absent from the canon after that scene. Where the other three worlds have dozens of agents spread over a map, Hamlet is a chamber drama &mdash; sixteen agents in one castle, most scenes a two-person exchange &mdash; which makes it the sharpest test of whether the mechanisms need scale to show anything. All four backends run the same 30-tick simulation under the identical fairness protocol.</p>

<h3>4.2 &nbsp;Baselines</h3>
<ul class="body">
<li><b>Generative-Agents memory</b> [1]: per-agent private streams; insert-time importance scoring; reflection synthesis over high-importance windows.</li>
<li><b>G-Memory</b> [3]: shared store organized as interaction/insight tiers with periodic LLM distillation into insight nodes and bi-level retrieval over provenance edges.</li>
<li><b>Collaborative memory</b> [9]: per-owner fragments guarded by access-control lists; recall is ACL-filtered server-side.</li>
</ul>
<p>All three ingest the sediment under their own rule (one row per witness) and run their own machinery over it (GA importance+reflections; G-Memory distillation) before tick 0, so each starts from a self-consistent initial state.</p>

<h3>4.3 &nbsp;Fairness protocol</h3>
<p><b>Equal granularity.</b> Every backend routes <code>remember</code> through the <i>same</i> atomization code with the same self-containment requirement. Entry counts are therefore directly comparable; the only remaining difference is what each mechanism does with identical atoms.</p>
<p><b>Simulation-only accounting.</b> All reported numbers cover memories the simulation itself generated (<code>remember</code>/<code>act_on</code> deposits). Sedimented content and baseline by-products (GA reflection nodes, G-Memory distillation nodes) are excluded on all sides.</p>

<h3>4.4 &nbsp;Metrics</h3>
<ul class="body">
<li><b>Structure</b> (deterministic): sim-entry count; share of multi-owner entries; share of entries with affiliated edges.</li>
<li><b>Continuation quality</b> (LLM-judged, mean&plusmn;std over 3 scorings of the sim transcript): <i>grounding</i> &mdash; the fraction of the sim&rsquo;s own events consistent with the canon; <i>trajectory</i> &mdash; agreement of character arcs with reference arcs extracted from each world&rsquo;s held-out continuation (三国: chapters 41&ndash;60; Russia&ndash;Ukraine: the timeline beyond the 2024-04 boundary); <i>narrative</i> &mdash; judged coherence/drama/fidelity (1&ndash;5); <i>goal pursuit</i> &mdash; whether each agent&rsquo;s actions consistently pursue its declared goals (judged against the goal stack the agent itself maintains; defined here, measurement deferred &mdash; achievement itself is deliberately not scored, since a faithful tragedy requires goals to fail). The verbose Russia&ndash;Ukraine transcripts are compacted to the judge&rsquo;s context window (messages truncated to 280 chars, lines sampled evenly when needed); 三国 fits untruncated.</li>
<li><b>Operation latency</b> (&sect;5.2): per-call wall-clock time of <code>remember</code>/<code>recall</code>, timed in the kernel around the backend call so each mechanism&rsquo;s internal cost (equivalence judging, importance scoring, auto-expansion) falls inside the window. Ticks 61&ndash;80 are instrumented live; ticks 1&ndash;60 are measured by replaying each stage&rsquo;s logged operations against the store state the stage started from (checkpoint-exact for stages 2&ndash;3; the first stage&rsquo;s GA/G-Memory replay stores lack prime by-products, &asymp;3&ndash;5% of rows).</li>
<li><b>Three-layer alignment</b> (&sect;5.4): relations between the interaction graph, the affiliation graph, and the ownership relation.</li>
</ul>

<h2><span class="n">5</span> Results</h2>

<h3>5.1 &nbsp;Footprint and structure</h3>
<p>At equal granularity, consensus writes the fewest sim memories in all three worlds (三国: {C['sim_new']} vs {GA['sim_new']}&ndash;{CO['sim_new']}; Russia&ndash;Ukraine: {RUC['sim_new']} vs {RU['collaborative']['sim_new']}&ndash;{RU['generative_agents']['sim_new']}; 红楼: {RCC['sim_new']} vs {RC['generative_agents']['sim_new']}&ndash;{RC['g_memory']['sim_new']}) because merging folds witnesses together. The same holds for structure: in every world consensus is the only backend whose memories become shared and linked ({C['sh_pct']}%/{C['aff_pct']}% in 三国, {RUC['sh_pct']}%/{RUC['aff_pct']}% in Russia&ndash;Ukraine, {RCC['sh_pct']}%/{RCC['aff_pct']}% in 红楼), against 0% for every baseline.</p>
<div class="tw"><table>
<caption><b>Table 1.</b> Sim-generated memories under uniform atomization, per scenario. &ldquo;Shared&rdquo; = multi-owner entries created by consensus merging; &ldquo;linked&rdquo; = entries carrying affiliated edges. Baseline mechanism by-products (GA reflections, G-Memory distillations) are excluded from all columns. In both worlds consensus writes the fewest entries and is the only backend with shared or linked memories.</caption>
<thead><tr><th>backend</th><th>sim entries</th><th>shared (multi-owner)</th><th>linked (affiliated)</th></tr></thead>
<tbody>
<tr class="grp"><td colspan="4">三国演义 &mdash; fiction, 80 ticks</td></tr>
<tr class="hi"><td>consensus</td><td class="best">{C['sim_new']}</td><td class="best">{C['multi_owner']} ({C['sh_pct']}%)</td><td class="best">{C['aff_pct']}%</td></tr>
<tr><td>generative-agents</td><td>{GA['sim_new']}</td><td>0</td><td>0</td></tr>
<tr><td>g-memory</td><td>{GM['sim_new']}</td><td>0</td><td>0</td></tr>
<tr><td>collaborative</td><td>{CO['sim_new']}</td><td>0</td><td>0</td></tr>
<tr class="grp"><td colspan="4">Russia&ndash;Ukraine &mdash; real world, 40 ticks</td></tr>
<tr class="hi"><td>consensus</td><td class="best">{RUC['sim_new']}</td><td class="best">{RUC['multi_owner']} ({RUC['sh_pct']}%)</td><td class="best">{RUC['aff_pct']}%</td></tr>
<tr><td>generative-agents</td><td>{RU['generative_agents']['sim_new']}</td><td>0</td><td>0</td></tr>
<tr><td>g-memory</td><td>{RU['g_memory']['sim_new']}</td><td>0</td><td>0</td></tr>
<tr><td>collaborative</td><td>{RU['collaborative']['sim_new']}</td><td>0</td><td>0</td></tr>
<tr class="grp"><td colspan="4">红楼梦 &mdash; fiction, 80 ticks</td></tr>
<tr class="hi"><td>consensus</td><td class="best">{RCC['sim_new']}</td><td class="best">{RCC['multi_owner']} ({RCC['sh_pct']}%)</td><td class="best">{RCC['aff_pct']}%</td></tr>
<tr><td>generative-agents</td><td>{RC['generative_agents']['sim_new']}</td><td>0</td><td>0</td></tr>
<tr><td>g-memory</td><td>{RC['g_memory']['sim_new']}</td><td>0</td><td>0</td></tr>
<tr><td>collaborative</td><td>{RC['collaborative']['sim_new']}</td><td>0</td><td>0</td></tr>
<tr class="grp"><td colspan="4">Hamlet &mdash; fiction, 30 ticks</td></tr>
<tr class="hi"><td>consensus</td><td class="best">{HLC['sim_new']}</td><td class="best">{HLC['multi_owner']} ({HLC['sh_pct']}%)</td><td class="best">{HLC['aff_pct']}%</td></tr>
<tr><td>generative-agents</td><td>{HL['generative_agents']['sim_new']}</td><td>0</td><td>0</td></tr>
<tr><td>g-memory</td><td>{HL['g_memory']['sim_new']}</td><td>0</td><td>0</td></tr>
<tr><td>collaborative</td><td>{HL['collaborative']['sim_new']}</td><td>0</td><td>0</td></tr>
</tbody></table></div>

<h4>5.1.1 &nbsp;三国演义</h4>
<figure class="two">
  <img src="{IMG['simfoot']}" alt="Sim footprint">
  <img src="{IMG['structure']}" alt="Memory structure">
  <figcaption><b>Figure 7. Footprint and structure &mdash; 三国演义 (80 ticks).</b> Left: entries written by each backend under identical atomization; consensus is lowest because equivalent records from different witnesses merge into one. Right: percentage of each backend&rsquo;s sim memories that are shared (multi-owner) and linked (affiliated); both properties exist only under consensus &mdash; per-agent stores have nothing to merge or link across.</figcaption>
</figure>
<p><b>Discussion.</b> Two readings matter here. First, the footprint gap is <i>mechanistic</i>, not behavioral: all four backends receive the same actions and atomize identically, so the 481-entry spread between consensus and the largest baseline is exactly the number of times the equivalence judge folded one agent&rsquo;s record into another&rsquo;s &mdash; each fold is a deduplicated witness (P1). Second, the structural columns are all-or-nothing by design: per-agent stores have no cross-agent rows to merge and no deposit-siblings to link, so the 19% / 97% columns measure capabilities the baselines lack architecturally, not parameters they tuned differently.</p>
<p>Merged records are precisely the cross-viewpoint deduplication the mechanism targets &mdash; {S['n_3plus']} memories carry three or more witnesses (maximum {S['max_owners']}):</p>
<div class="quote">""" + "<br>\n".join(
    f"<b>owners = [{owners_zh(e['owners'])}]</b> &nbsp;&ldquo;{e['text']}&rdquo;" for e in mex[:3]
) + f"""</div>

<h4>5.1.2 &nbsp;Russia&ndash;Ukraine</h4>
<figure class="two">
  <img src="{IMG['ru_simfoot']}" alt="RU sim footprint">
  <img src="{IMG['ru_structure']}" alt="RU memory structure">
  <figcaption><b>Figure 8. Footprint and structure &mdash; Russia&ndash;Ukraine (40 ticks).</b> Same panels as Figure 7: entries written under identical atomization (left) and the share of each backend&rsquo;s sim memories that are shared and linked (right).</figcaption>
</figure>
<p><b>Discussion.</b> The same two readings hold at one eighth the horizon: the 19&ndash;30% footprint gap is again exactly the number of equivalence-judge folds, and the structural columns remain all-or-nothing &mdash; 0% for every per-agent baseline. What is new is the real-world flavor of the folds: equivalence merges a <i>person&rsquo;s</i> record into their <i>institution&rsquo;s</i> &mdash; the same mechanism that fuses two officers&rsquo; views of one battle fuses a spokesperson&rsquo;s statement with its organization&rsquo;s record of it.</p>
<p>Merged records again pair one event seen from two sides &mdash; characteristically a person and their institution:</p>
<div class="quote"><b>owners = [guterres, un]</b> &nbsp;&ldquo;Ant&oacute;nio Guterres at UN Headquarters in New York asked the United Nations to assemble a mediation team comprising DPA, OCHA, WFP, UN Political Affairs, and UN Legal to support renewal of the Black Sea grain agreement.&rdquo;<br>
<b>owners = [podolyak, ukrainian_government]</b> &nbsp;&ldquo;Mykhailo Podolyak reported that overnight Russian drone strikes struck Dnipropetrovsk Oblast.&rdquo;<br>
<b>owners = [kremlin, sobyanin]</b> &nbsp;&ldquo;Moscow Mayor Sergey Sobyanin requested authorization to release public instructions to Moscow residents.&rdquo;</div>

<h4>5.1.3 &nbsp;红楼梦</h4>
<figure class="two">
  <img src="{IMG['rc_simfoot']}" alt="RC sim footprint">
  <img src="{IMG['rc_structure']}" alt="RC memory structure">
  <figcaption><b>Figure 9. Footprint and structure &mdash; 红楼梦 (80 ticks).</b> Same panels as Figures 7&ndash;8: entries written under identical atomization (left) and the share of each backend&rsquo;s sim memories that are shared and linked (right).</figcaption>
</figure>
<p><b>Discussion.</b> 红楼 is where the two claims of &sect;5.1 can be watched separating in time, because it was run at four horizons. Structure was already complete at ten ticks (13% shared, 87% linked, baselines 0%); footprint was not &mdash; the four backends then sat at 62&ndash;98 entries with consensus not the smallest, within run-to-run variance. From forty ticks on consensus is lowest and stays lowest, and the gap holds as both sides grow: 216 vs 379&ndash;492 at forty, 338 vs 625&ndash;683 at sixty, {RCC['sim_new']} vs {RC['generative_agents']['sim_new']}&ndash;{RC['g_memory']['sim_new']} at eighty &mdash; a {round(100-100*RCC['sim_new']/RC['g_memory']['sim_new'])}% reduction against the largest. Sharing rises along the same curve and flattens as it saturates &mdash; 13%&rarr;20%&rarr;23%&rarr;{RCC['sh_pct']}% &mdash; while multi-witness merges keep accumulating: {RC['n_3plus']} entries carry three or more witnesses (17 at sixty, nine at forty, three at ten), the deepest still the banquet where 贾母 keeps 宝玉, 黛玉 and 宝钗 by her side, co-owned by {RC['max_owners']}. The ordering is the point: the structural properties are architectural and appear immediately, whereas the footprint advantage is a <i>compounding</i> effect that needs enough repeated witnessing to overcome noise. A household world reaches that point later than a war does, because fewer people witness each event.</p>
<p>Merged records in the household world fold family witnesses of one scene:</p>
<div class="quote">""" + "<br>\n".join(
    f"<b>owners = [{owners_zh(e['owners'])}]</b> &nbsp;&ldquo;{e['text']}&rdquo;" for e in rc_mex[:3]
) + f"""</div>


<h4>5.1.4 &nbsp;Hamlet</h4>
<figure class="two">
  <img src="{IMG['hl_simfoot']}" alt="HL sim footprint">
  <img src="{IMG['hl_structure']}" alt="HL memory structure">
  <figcaption><b>Figure 10. Footprint and structure &mdash; Hamlet (30 ticks).</b> Same panels as Figures 7&ndash;9 on the smallest world: entries written under identical atomization (left) and the share of each backend&rsquo;s sim memories that are shared and linked (right).</figcaption>
</figure>
<p><b>Discussion.</b> Sixteen agents are enough. Consensus writes {HLC['sim_new']} entries against {HL['generative_agents']['sim_new']}&ndash;{HL['g_memory']['sim_new']}, with {HLC['sh_pct']}% shared and {HLC['aff_pct']}% linked &mdash; the highest sharing rate of any world at any horizon, in the smallest one tested. The extension from twenty ticks to thirty shows the same compounding the other worlds display: sharing rose 19%&rarr;{HLC['sh_pct']}% and the first three-witness merge appeared (the players' troupe beginning the performance, owned by the First Player, the Prologue, and Guildenstern together), where every merge at twenty ticks had been a strict pair. Depth still lags the larger worlds ({HL['n_3plus']} entry with three or more witnesses, against {S['n_3plus']} in 三国 and {RC['n_3plus']} in 红楼), and the reason is the play's staging rather than the mechanism's reach: Shakespeare writes in two-person exchanges &mdash; the sentinels on the battlements, Laertes and Polonius, Rosencrantz with Guildenstern &mdash; and merge depth tracks how many people the world puts in a room together. The play-within-a-play is the one scene that assembles an audience, and it is exactly where the three-way merge appears.</p>
<p>The pairs the mechanism finds are the play&rsquo;s own dyads:</p>
<div class="quote">""" + "<br>\n".join(
    f"<b>owners = [{owners_zh(e['owners'])}]</b> &nbsp;&ldquo;{e['text']}&rdquo;" for e in hl_mex[:3]
) + f"""</div>

<h3>5.2 &nbsp;Growth and operation latency</h3>
<p>The footprint gap of Table 1 accumulates tick by tick, and its price is paid at write time. We show both sides for each scenario.</p>

<h4>5.2.1 &nbsp;三国演义</h4>
<figure class="two">
  <img src="{IMG['gtotal']}" alt="System memory growth per tick">
  <img src="{IMG['gagents']}" alt="Per-agent memory growth per tick">
  <figcaption><b>Figure 11. Memory growth &mdash; 三国演义 (80 ticks).</b> Left: cumulative sim-generated entries per tick for all four backends (reconstructed from each entry&rsquo;s creation tick under the same sim-only accounting as Table 1) &mdash; consensus stays lowest throughout and the gap widens with horizon, the per-tick view of the merge folding witnesses together. Right: per-agent owned memories per tick in the consensus run (top 6 agents labeled; the rest gray) &mdash; memory concentrates on the characters carrying the active plotlines (徐庶 leads with 132), while merges let one event&rsquo;s record count toward every witness&rsquo;s curve.</figcaption>
</figure>
<p><b>Discussion.</b> The system-level curves separate almost from the start and diverge steadily &mdash; the merge saves entries at a roughly constant <i>rate</i>, so its absolute savings compound with horizon rather than saturating; there is no sign of the gap closing by tick 80. The per-agent curves show the same mechanism from the individual&rsquo;s side: growth is stair-stepped (a burst when a character is at the center of a plotline, plateaus when off-stage), and the ranking tracks narrative centrality rather than raw talkativeness &mdash; 徐庶 leads because the 徐庶-recruitment arc dominates the middle game, and every merge credits a shared event to all of its witnesses&rsquo; curves at once.</p>

<figure>
  <img src="{IMG['latency']}" alt="Memory-operation latency vs tick">
  <figcaption><b>Figure 12. Memory-operation latency &mdash; 三国演义 (80 ticks).</b> Mean wall-clock seconds per <code>remember</code> (left) and <code>recall</code> (right) call, 5-tick bins, all four backends. Ticks 61&ndash;80 are instrumented live in the kernel; ticks 1&ndash;60 are measured by replaying each stage&rsquo;s logged operations (same agent, text/query, and order) against the exact store state that stage started from &mdash; a measurement of the same workload, not a synthesis (dotted line marks the boundary; first-stage GA/G-Memory replay stores lack their prime by-products, &asymp;3&ndash;5% of rows).</figcaption>
</figure>
<p><b>Discussion.</b> The two panels show where each design pays. <i>Writes are LLM-bound:</i> every backend pays the shared atomization call, on top of which Generative-Agents adds a per-atom importance call (the most expensive line, 35&ndash;75s) and consensus adds the equivalence judge (26&ndash;57s), while G-Memory and collaborative write for 10&ndash;25s with no per-deposit reasoning beyond atomization. <i>Reads are vector-bound and cheap everywhere</i> (&le;1.4s), and &mdash; notably &mdash; consensus recall is the <b>cheapest</b> of the four (&asymp;0.35s) despite returning &asymp;28 additional linked memories per call: auto-expansion is plain row lookup, whereas G-Memory&rsquo;s bi-level retrieval pays for graph traversal with extra vector queries (0.7&ndash;1.1s). Neither panel trends upward over 80 ticks: at this scale, store growth (&asymp;7k&ndash;22k rows) does not yet move per-call latency, so the consensus premium is a roughly constant per-write tax &mdash; the price of P1&rsquo;s deduplication &mdash; paid where agents are least latency-sensitive.</p>

<h4>5.2.2 &nbsp;Russia&ndash;Ukraine</h4>
<figure>
  <img src="{IMG['ru_growth']}" alt="RU memory growth">
  <figcaption><b>Figure 13. Memory growth &mdash; Russia&ndash;Ukraine (40 ticks).</b> Left: cumulative sim-generated entries per tick for all four backends under the same sim-only accounting as Table 1. Right: per-agent owned memories per tick in the consensus run (top agents labeled; the rest gray).</figcaption>
</figure>
<figure>
  <img src="{IMG['ru_latency']}" alt="RU memory-operation latency">
  <figcaption><b>Figure 14. Memory-operation latency &mdash; Russia&ndash;Ukraine (40 ticks).</b> Mean wall-clock seconds per <code>remember</code> (left) and <code>recall</code> (right) call, 2-tick bins, all four backends; every tick is instrumented live in the kernel.</figcaption>
</figure>
<p><b>Discussion.</b> Both figures replay the 三国 dynamics at a shorter horizon. The system curves separate from tick ~3 with consensus lowest and the gap widening, and per-agent growth again concentrates on the situation&rsquo;s protagonists. The latency ordering of Figure 12 reproduces: writes are LLM-bound (Generative-Agents&rsquo; per-atom importance calls most expensive, consensus paying the equivalence-judge tax), while reads are vector-bound and sub-second for all four backends, with consensus recall cheapest despite auto-expansion.</p>

<h4>5.2.3 &nbsp;红楼梦</h4>
<figure>
  <img src="{IMG['rc_growth']}" alt="RC memory growth">
  <figcaption><b>Figure 15. Memory growth &mdash; 红楼梦 (80 ticks).</b> Left: cumulative sim-generated entries per tick for all four backends under the same sim-only accounting as Table 1. Right: per-agent owned memories per tick in the consensus run (top agents labeled; the rest gray).</figcaption>
</figure>
<figure>
  <img src="{IMG['rc_latency']}" alt="RC memory-operation latency">
  <figcaption><b>Figure 16. Memory-operation latency &mdash; 红楼梦 (80 ticks).</b> Mean wall-clock seconds per <code>remember</code> (left) and <code>recall</code> (right) call, 2-tick bins, all four backends; every tick is instrumented live in the kernel.</figcaption>
</figure>
<p><b>Discussion.</b> The domestic world writes more slowly than either other scenario (~{RCC['sim_new']//80} consensus entries per tick against ~20 in Russia&ndash;Ukraine) &mdash; garden conversation generates fewer memory-worthy events than a war &mdash; and the curves that interleaved through the first ten ticks separate cleanly thereafter, consensus lowest and the gap holding to eighty ticks, exactly as in Figures 11 and 13. Per-agent growth concentrates on the household&rsquo;s centers of gravity (贾母, 王熙凤, 贾宝玉 and the banquet guests). The read side reproduces both other worlds: consensus recall is cheapest despite auto-expansion returning &asymp;{RCE['items']//max(RCE['recalls'],1)} linked memories per call, while G-Memory&rsquo;s bi-level retrieval pays for graph traversal with extra vector queries.</p>

<h4>5.2.4 &nbsp;Hamlet</h4>
<figure>
  <img src="{IMG['hl_growth']}" alt="HL memory growth">
  <figcaption><b>Figure 17. Memory growth &mdash; Hamlet (30 ticks).</b> Left: cumulative sim-generated entries per tick for all four backends under the same sim-only accounting as Table 1. Right: per-agent owned memories per tick in the consensus run (top agents labeled; the rest gray).</figcaption>
</figure>
<figure>
  <img src="{IMG['hl_latency']}" alt="HL memory-operation latency">
  <figcaption><b>Figure 18. Memory-operation latency &mdash; Hamlet (30 ticks).</b> Mean wall-clock seconds per <code>remember</code> (left) and <code>recall</code> (right) call, 2-tick bins, all four backends; every tick is instrumented live in the kernel.</figcaption>
</figure>
<p><b>Discussion.</b> The smallest world writes at a rate between the other two fictions (~{HLC['sim_new']//30} consensus entries per tick), and the four curves separate early with consensus lowest &mdash; at this cast size a single merge is a large fraction of a tick's writes, so the gap opens without the compounding 红楼 needed. Latency is dominated by per-call LLM cost exactly as elsewhere; with only {HLE['recalls']} recalls over the whole run the read-side curves are too sparse to rank backends, and we read nothing into their ordering here.</p>

<h3>5.3 &nbsp;Continuation quality</h3>
<p>Compression does not cost judged quality in either world. In 三国, consensus scores highest on narrative and is competitive elsewhere; in Russia&ndash;Ukraine all four backends land within overlapping error bars on every metric, with consensus tied-best on grounding and trajectory. The structural gaps of &sect;5.1 do not translate into behavioral penalties.</p>

<h4>5.3.1 &nbsp;三国演义</h4>
<figure>
  <img src="{IMG['quality']}" alt="Continuation quality comparison">
  <figcaption><b>Figure 19. Continuation quality &mdash; 三国演义 (40-tick checkpoint).</b> Grounding (fraction of the sim&rsquo;s own events judged canon-consistent), trajectory (agreement of character arcs with reference arcs from held-out chapters 41&ndash;60), and narrative (judged coherence/drama/fidelity, 1&ndash;5), scored at the 40-tick checkpoint of the same continuously-resumed runs; bars are means over 3 independent LLM scorings, whiskers &plusmn;1 std. Consensus scores highest on narrative and is competitive on trajectory; grounding sits mid-pack (GA/collaborative slightly higher).</figcaption>
</figure>
<p><b>Discussion.</b> The quality profile is consistent with what compression should and should not affect. Narrative coherence benefits from consensus (4.25, the clear leader): agents recalling one shared record of an event act on consistent premises, where baseline agents can act on N drifting paraphrases of it. Trajectory sits in the pack (0.68 vs 0.59&ndash;0.72): arc-following depends mostly on the persona and goal machinery all backends share. Grounding is mid-pack (0.86 vs 0.83&ndash;0.92, overlapping error bars): merging keeps the <i>shorter</i> of two equivalent texts, which occasionally discards a viewpoint detail a canon-consistency judge rewards. None of the differences approach the structural gaps of Figure 7 &mdash; the mechanisms separate on architecture, not on judged behavior.</p>

<h4>5.3.2 &nbsp;Russia&ndash;Ukraine</h4>
<figure>
  <img src="{IMG['ru_quality']}" alt="RU continuation quality comparison">
  <figcaption><b>Figure 20. Continuation quality &mdash; Russia&ndash;Ukraine (40 ticks).</b> Same protocol as Figure 19 at the same horizon: grounding judges each sim event against the real conflict&rsquo;s world (real entities, correct roles/allegiances, plausible dynamics), trajectory compares ten principals&rsquo; arcs against arcs extracted from the held-out timeline (2024-05 onward), narrative is the same 4-dimension rubric; bars are means over 3 independent LLM scorings, whiskers &plusmn;1 std.</figcaption>
</figure>
<p><b>Discussion.</b> The real-world replication is a wash &mdash; which is the point. Grounding is uniformly high ({min(QR[k]['agg']['grnd']['mean'] for k in QR):.2f}&ndash;{max(QR[k]['agg']['grnd']['mean'] for k in QR):.2f}: institutional actors reciting real capabilities rarely fabricate), trajectory is tied within error bars ({QR['consensus']['agg']['traj']['mean']:.2f} for consensus vs {min(QR[k]['agg']['traj']['mean'] for k in QR if k!='consensus'):.2f}&ndash;{max(QR[k]['agg']['traj']['mean'] for k in QR if k!='consensus'):.2f}), and narrative spreads {QR['g_memory']['agg']['narr']['mean']:.2f}&ndash;{QR['generative_agents']['agg']['narr']['mean']:.2f} with overlapping whiskers and no stable leader across scorings. As in 三国, the mechanisms separate on architecture (Figure 8), not on judged behavior: consensus deduplicates {RUC['sim_new']} entries against the baselines&rsquo; {RU['collaborative']['sim_new']}&ndash;{RU['generative_agents']['sim_new']} and builds all the structure &mdash; while giving none of it back in quality.</p>

<h4>5.3.3 &nbsp;红楼梦</h4>
<p>Not scored yet: at 80 ticks the 红楼 runs match 三国&rsquo;s horizon and exceed the 40-tick checkpoint at which both scored worlds were judged, so the protocol of &sect;5.3.1&ndash;5.3.2 applies unchanged; the scoring pass is pending and will be reported alongside the other two worlds.</p>

<h4>5.3.4 &nbsp;Hamlet</h4>
<p>Not scored: at 30 ticks Hamlet remains below the 40-tick horizon used by both scored worlds, and its held-out reference (Acts&nbsp;4&ndash;5) is short enough that arc extraction would rest on very few events. Scoring follows if the run is extended.</p>

<h3>5.4 &nbsp;Case study: three graphs over each world</h3>
<p>Each world&rsquo;s consensus run induces the same three graphs: the <b>interaction graph</b> (who talks to whom), the <b>affiliation graph</b> (which memories are linked), and the <b>ownership relation</b> (who owns which memories). For each scenario we show the three layers, then all three in one view, then quantify their pairwise alignment.</p>

<h4>5.4.1 &nbsp;三国演义</h4>

<h5>The three layers <span style="font-family:var(--sans);font-size:12px;color:var(--faint);font-weight:400">&mdash; interactive: drag to pan, scroll to zoom, hover for details, drag nodes to rearrange</span></h5>
<figure>
  <div class="ig" id="ig-interaction" style="height:520px"></div>
  <figcaption><b>Figure 21a. The interaction graph (interactive) &mdash; 三国演义.</b> Nodes are the complete active-character roster (silent characters parked on the bottom row); edge width is conversation frequency; colors are detected communities, which recover the canonical factions without being told about them. Hover a character for its name, community, and conversation volume; click to highlight its neighbourhood.</figcaption>
</figure>
<figure>
  <div class="ig" id="ig-affiliation" style="height:600px"></div>
  <figcaption><b>Figure 21b. The full memory-affiliation graph (interactive) &mdash; 三国演义.</b> Every sim-generated memory is a node ({R['MO']['link_n']} affiliated edges; components colored, singletons gray; shared multi-owner memories drawn larger with a red ring). <b>Hover any node to read the memory&rsquo;s full text and its owners</b> &mdash; each cluster is one plotline&rsquo;s linked pieces, assembled bottom-up by auto-affiliation and merging.</figcaption>
</figure>
<figure>
  <div class="ig" id="ig-heatmap" style="height:620px"></div>
  <figcaption><b>Figure 21. The ownership layer (interactive) &mdash; 三国演义.</b> Pairwise co-owned memory counts over the complete roster, ordered by interaction community. Hover a cell for the pair and its count. Non-zero cells concentrate in the diagonal blocks &mdash; agents share memories with their own faction &mdash; and each strong cell corresponds to consensus merges of jointly experienced events.</figcaption>
</figure>

<h5>All three layers in one view</h5>
<figure>
  <div class="ig" id="ig-trilayer" style="height:560px"></div>
  <figcaption><b>Figure 22. All three layers in one view (interactive) &mdash; 三国演义.</b> Agents on the top row (circles = characters, squares = passive memory owners) with conversation arcs above (blue; width = frequency); memories on the bottom row with affiliation arcs below (green when the linked memories share a witness, gray when disjoint); ownership as vertical lines, red when the memory is shared. <b>Hover an agent</b> to isolate its conversations and owned memories; <b>hover a memory</b> (&starf; = merged multi-owner) to read its text and see its links. Shared structure sits where conversation sits.</figcaption>
</figure>

<h5>Pairwise alignment of the layers</h5>
<div class="rel"><h4><span class="rx">A&harr;O</span> Agents who talk own overlapping memories <span class="stat">({R['AO']['talk_mean']:.3f} vs {R['AO']['non_mean']:.3f}, {ao_ratio:.0f}&times;)</span></h4>
<p>Owned-memory-set Jaccard between agent pairs: the {R['AO']['talk_n']} talking pairs average {R['AO']['talk_mean']:.3f}; the {R['AO']['non_n']} non-talking pairs average {R['AO']['non_mean']:.3f}. The entire upper tail belongs to talking pairs.</p></div>
<div class="rel"><h4><span class="rx">M&harr;O</span> Linked memories have the same witnesses <span class="stat">({R['MO']['link_mean']:.2f} vs {R['MO']['non_mean']:.2f})</span></h4>
<p>Owner-set Jaccard between memory pairs: the {R['MO']['link_n']} affiliated pairs mass near 1.0 (mean {R['MO']['link_mean']:.2f}); unlinked pairs mass at zero (mean {R['MO']['non_mean']:.2f}). One event&rsquo;s pieces belong to one event&rsquo;s witnesses.</p></div>
<div class="rel"><h4><span class="rx">A&harr;M</span> Cross-agent memory links follow conversations <span class="stat">({R['AM']['talk_mean']:.1f} vs {R['AM']['non_mean']:.2f} edges)</span></h4>
<p>Affiliated edges running between two agents&rsquo; memory sets: talking pairs average {R['AM']['talk_mean']:.1f}; non-talking pairs {R['AM']['non_mean']:.2f}. The memory graph bridges exactly the agents the conversation graph connects.</p></div>
<figure>
  <img src="{IMG['relpanels']}" alt="Three pairwise relationships">
  <figcaption><b>Figure 23. Each pairwise relation as a with/without pair of distributions &mdash; 三国演义</b> (columns share x and y axes; log density so tails read against the mass at zero; top row = pairs with the relation, bottom = without). Left: owned-memory-set Jaccard for talking vs non-talking agent pairs. Middle: owner-set Jaccard for memory pairs with vs without an affiliated edge. Right: cross-set affiliated-edge counts for talking vs non-talking agent pairs. In all three, the without-group concentrates at zero and the with-group carries the entire tail.</figcaption>
</figure>
<p><b>Synthesis.</b> The three alignments are not three separate facts but one: the consensus mechanisms transcribe the story&rsquo;s social structure into the memory substrate. Conversations are where shared experience happens, so merges (ownership overlap) land on talking pairs; deposits narrate the conversation an agent just had, so affiliation clusters coincide with events and their witnesses; and cross-agent links therefore run along conversation edges. In a per-agent store all three relations are identically zero &mdash; the substrate cannot express them &mdash; which is why the case study is run on the consensus backend alone.</p>

<h4>5.4.2 &nbsp;Russia&ndash;Ukraine</h4>
<h5>The three layers <span style="font-family:var(--sans);font-size:12px;color:var(--faint);font-weight:400">&mdash; interactive: drag to pan, scroll to zoom, hover for details, drag nodes to rearrange</span></h5>
<figure>
  <div class="ig" id="ig-ru-interaction" style="height:480px"></div>
  <figcaption><b>Figure 24a. The interaction graph (interactive) &mdash; Russia&ndash;Ukraine.</b> 65 entities; community detection recovers the conflict&rsquo;s blocs &mdash; the Kyiv government cluster, the Moscow cluster, and the international mediators &mdash; without being told about them.</figcaption>
</figure>
<figure>
  <div class="ig" id="ig-ru-affiliation" style="height:520px"></div>
  <figcaption><b>Figure 24b. The full memory-affiliation graph (interactive) &mdash; Russia&ndash;Ukraine.</b> {RUC['sim_new']} sim memories, {RUR['MO']['link_n']} affiliated edges; hover any node to read the memory and its owners. Clusters are single storylines (a strike wave, a negotiation) assembled by auto-affiliation.</figcaption>
</figure>
<figure>
  <div class="ig" id="ig-ru-heatmap" style="height:560px"></div>
  <figcaption><b>Figure 24. The ownership layer (interactive) &mdash; Russia&ndash;Ukraine.</b> Pairwise co-owned memory counts over the Russia&ndash;Ukraine roster, ordered by interaction community. Hover a cell for the pair and its count. As in Figure 21, non-zero cells sit on pairs that jointly experienced events &mdash; here the strongest cells are spokesperson&harr;institution pairs, the real-world counterpart of faction comrades.</figcaption>
</figure>
<h5>All three layers in one view</h5>
<figure>
  <div class="ig" id="ig-ru-trilayer" style="height:520px"></div>
  <figcaption><b>Figure 25. All three layers in one view (interactive) &mdash; Russia&ndash;Ukraine.</b> Conversations above, ownership between, affiliation below; merged memories (&starf;) hang between the parties that share them.</figcaption>
</figure>
<h5>Pairwise alignment of the layers</h5>
<div class="rel"><h4><span class="rx">A&harr;O</span> Agents who talk own overlapping memories <span class="stat">({RUR['AO']['talk_mean']:.3f} vs {RUR['AO']['non_mean']:.4f}, {RUR['AO']['talk_mean']/max(RUR['AO']['non_mean'],1e-9):.0f}&times;)</span></h4>
<p>The separation is even sharper than in the fictional world &mdash; real-world discourse is more role-bound, so shared memory concentrates almost entirely on institutional interlocutors.</p></div>
<div class="rel"><h4><span class="rx">M&harr;O</span> Linked memories have the same witnesses <span class="stat">({RUR['MO']['link_mean']:.2f} vs {RUR['MO']['non_mean']:.2f})</span></h4>
<p>Affiliated pairs share owners at Jaccard {RUR['MO']['link_mean']:.2f} against {RUR['MO']['non_mean']:.2f} for random pairs &mdash; the tightest alignment measured in either world.</p></div>
<div class="rel"><h4><span class="rx">A&harr;M</span> Cross-agent memory links follow conversations <span class="stat">({RUR['AM']['talk_mean']:.2f} vs {RUR['AM']['non_mean']:.3f} edges)</span></h4>
<p>Talking pairs average {RUR['AM']['talk_mean']:.2f} affiliated edges between their memory sets; non-talking pairs essentially none.</p></div>
<figure>
  <img src="{IMG['ru_relpanels']}" alt="RU relationship panels">
  <figcaption><b>Figure 26. Each pairwise relation as a with/without pair of distributions &mdash; Russia&ndash;Ukraine</b> (same format as Figure 23). The structural signature transfers intact to a real-world scenario at one eighth the horizon.</figcaption>
</figure>

<h4>5.4.3 &nbsp;红楼梦</h4>
<h5>The three layers <span style="font-family:var(--sans);font-size:12px;color:var(--faint);font-weight:400">&mdash; interactive: drag to pan, scroll to zoom, hover for details, drag nodes to rearrange</span></h5>
<figure>
  <div class="ig" id="ig-rc-interaction" style="height:480px"></div>
  <figcaption><b>Figure 27a. The interaction graph (interactive) &mdash; 红楼梦.</b> 31 conversing characters; community detection recovers the household&rsquo;s social circles &mdash; the 贾母 banquet orbit, the young poets&rsquo; circle, and the stewards &mdash; without being told about them.</figcaption>
</figure>
<figure>
  <div class="ig" id="ig-rc-affiliation" style="height:520px"></div>
  <figcaption><b>Figure 27b. The full memory-affiliation graph (interactive) &mdash; 红楼梦.</b> {RCC['sim_new']} sim memories, {RCR['MO']['link_n']} affiliated edges; hover any node to read the memory and its owners. Clusters are single storylines assembled by auto-affiliation.</figcaption>
</figure>
<figure>
  <div class="ig" id="ig-rc-heatmap" style="height:560px"></div>
  <figcaption><b>Figure 27. The ownership layer (interactive) &mdash; 红楼梦.</b> Pairwise co-owned memory counts over the 红楼 roster, ordered by interaction community. Hover a cell for the pair and its count. As in Figure 21, non-zero cells sit on pairs that jointly experienced scenes &mdash; here the strongest cells are kin who attended the same banquet, the domestic counterpart of faction comrades.</figcaption>
</figure>
<h5>All three layers in one view</h5>
<figure>
  <div class="ig" id="ig-rc-trilayer" style="height:520px"></div>
  <figcaption><b>Figure 28. All three layers in one view (interactive) &mdash; 红楼梦.</b> Conversations above, ownership between, affiliation below; merged memories (&starf;) hang between the parties that share them.</figcaption>
</figure>
<h5>Pairwise alignment of the layers</h5>
<div class="rel"><h4><span class="rx">A&harr;O</span> Agents who talk own overlapping memories <span class="stat">({RCR['AO']['talk_mean']:.3f} vs {RCR['AO']['non_mean']:.4f}, {RCR['AO']['talk_mean']/max(RCR['AO']['non_mean'],1e-9):.0f}&times;)</span></h4>
<p>Talking pairs overlap in memory at {RCR['AO']['talk_mean']:.3f} against {RCR['AO']['non_mean']:.4f} for silent pairs &mdash; the household&rsquo;s conversation network and its memory network coincide from the first ten ticks.</p></div>
<div class="rel"><h4><span class="rx">M&harr;O</span> Linked memories have the same witnesses <span class="stat">({RCR['MO']['link_mean']:.2f} vs {RCR['MO']['non_mean']:.2f})</span></h4>
<p>Affiliated pairs share owners at Jaccard {RCR['MO']['link_mean']:.2f} against {RCR['MO']['non_mean']:.2f} for random pairs &mdash; the same order-of-magnitude alignment as both other worlds.</p></div>
<div class="rel"><h4><span class="rx">A&harr;M</span> Cross-agent memory links follow conversations <span class="stat">({RCR['AM']['talk_mean']:.2f} vs {RCR['AM']['non_mean']:.3f} edges)</span></h4>
<p>Talking pairs average {RCR['AM']['talk_mean']:.2f} affiliated edges between their memory sets against {RCR['AM']['non_mean']:.3f} for non-talking pairs &mdash; the separation sharpens with the horizon (2.09 vs 0.15 at ten ticks).</p></div>
<figure>
  <img src="{IMG['rc_relpanels']}" alt="RC relationship panels">
  <figcaption><b>Figure 29. Each pairwise relation as a with/without pair of distributions &mdash; 红楼梦</b> (same format as Figure 23). The structural signature holds in a third world with a markedly different social topology.</figcaption>
</figure>

<h4>5.4.4 &nbsp;Hamlet</h4>
<h5>The three layers <span style="font-family:var(--sans);font-size:12px;color:var(--faint);font-weight:400">&mdash; interactive: drag to pan, scroll to zoom, hover for details, drag nodes to rearrange</span></h5>
<figure>
  <div class="ig" id="ig-hl-interaction" style="height:440px"></div>
  <figcaption><b>Figure 30a. The interaction graph (interactive) &mdash; Hamlet.</b> 15 conversing characters, 22 pairs &mdash; the whole court in one castle. At this size the graph is the cast list rather than a community structure to be recovered.</figcaption>
</figure>
<figure>
  <div class="ig" id="ig-hl-affiliation" style="height:480px"></div>
  <figcaption><b>Figure 30b. The full memory-affiliation graph (interactive) &mdash; Hamlet.</b> {HLC['sim_new']} sim memories, {HLR['MO']['link_n']} affiliated edges; hover any node to read the memory and its owners. Clusters are single scenes assembled by auto-affiliation.</figcaption>
</figure>
<figure>
  <div class="ig" id="ig-hl-heatmap" style="height:520px"></div>
  <figcaption><b>Figure 30. The ownership layer (interactive) &mdash; Hamlet.</b> Pairwise co-owned memory counts over the Hamlet roster, ordered by interaction community. Every non-zero cell is a two-person scene; the densest are the play&rsquo;s standing pairs.</figcaption>
</figure>
<h5>All three layers in one view</h5>
<figure>
  <div class="ig" id="ig-hl-trilayer" style="height:480px"></div>
  <figcaption><b>Figure 31. All three layers in one view (interactive) &mdash; Hamlet.</b> Conversations above, ownership between, affiliation below; merged memories (&starf;) hang between the parties that share them.</figcaption>
</figure>
<h5>Pairwise alignment of the layers</h5>
<div class="rel"><h4><span class="rx">A&harr;O</span> Agents who talk own overlapping memories <span class="stat">({HLR['AO']['talk_mean']:.3f} vs {HLR['AO']['non_mean']:.4f}, {HLR['AO']['talk_mean']/max(HLR['AO']['non_mean'],1e-9):.0f}&times;)</span></h4>
<p>Still the weakest separation of the four worlds, and for a structural reason: a single castle with sixteen residents has few genuinely non-interacting pairs, so the &ldquo;without&rdquo; baseline is contaminated by people who simply have not spoken <i>yet</i> &mdash; though ten more ticks widened it from 5&times; to {HLR['AO']['talk_mean']/max(HLR['AO']['non_mean'],1e-9):.0f}&times; as those pairs met.</p></div>
<div class="rel"><h4><span class="rx">M&harr;O</span> Linked memories have the same witnesses <span class="stat">({HLR['MO']['link_mean']:.2f} vs {HLR['MO']['non_mean']:.2f})</span></h4>
<p>Affiliated pairs share owners at Jaccard {HLR['MO']['link_mean']:.2f} against {HLR['MO']['non_mean']:.2f} for random pairs &mdash; the two-person scene keeps affiliated memories on nearly identical owner sets.</p></div>
<div class="rel"><h4><span class="rx">A&harr;M</span> Cross-agent memory links follow conversations <span class="stat">({HLR['AM']['talk_mean']:.2f} vs {HLR['AM']['non_mean']:.2f} edges)</span></h4>
<p>Talking pairs average {HLR['AM']['talk_mean']:.2f} affiliated edges between their memory sets against {HLR['AM']['non_mean']:.2f} for non-talking pairs &mdash; the same direction as the larger worlds at a tenth of the scale, and four times sharper than at twenty ticks.</p></div>
<figure>
  <img src="{IMG['hl_relpanels']}" alt="HL relationship panels">
  <figcaption><b>Figure 32. Each pairwise relation as a with/without pair of distributions &mdash; Hamlet</b> (same format as Figure 23). The signature survives at the smallest scale tested, with the A&harr;O panel visibly the noisiest.</figcaption>
</figure>

<h3>5.5 &nbsp;Structure compounds with horizon</h3>
<p>Shared and linked structure is not a transient: across the 20/40/60-tick checkpoints, sim memories grow roughly linearly while shared memories and affiliated edges grow with them &mdash; the merge finds more cross-witness events as the story densifies.</p>

<h4>5.5.1 &nbsp;三国演义</h4>
<figure>
  <img src="{IMG['growth']}" alt="Growth across horizon">
  <figcaption><b>Figure 33. Consensus structure across the horizon &mdash; 三国演义.</b> Sim-memory count (left), shared multi-owner memories (middle), and affiliated edges (right) at the 20/40/60/80-tick checkpoints of the same continuously-resumed run. All three grow super-linearly in usefulness even where counts grow linearly: each new shared memory raises the chance that a future deposit finds a merge partner, and each new edge widens what a single auto-expanding recall can surface.</figcaption>
</figure>

<h4>5.5.2 &nbsp;Russia&ndash;Ukraine</h4>
<p>Forty ticks in a second, structurally different world (real entities, institutional actors, English-language events, a live timeline rather than a novel) reproduce every qualitative claim of &sect;5: fewest entries, exclusive sharing and linking, the three-layer alignment, and the latency profile. The horizon effect predicted by 三国 is directly observable here: the sharing rate rose 6%&rarr;9%&rarr;{RUC['sh_pct']}% at ticks 10/20/40, three-plus-witness merges went from zero to {RU['n_3plus']}, and the deepest merge grew from two witnesses to {RU['max_owners']} &mdash; a presidential air-defense directive whose single record is co-owned by the president, his chief of staff and adviser, the interior minister, the air-force and intelligence commanders, and the security service &mdash; tracking 三国&rsquo;s 19% at 80 ticks on the same compounding curve.</p>

<h3>5.6 &nbsp;Agents do not manage memory &mdash; mechanisms must</h3>
<p>Across all four backends and both models tested, agents issued <b>zero</b> calls to every discretionary memory-management action &mdash; linking (<code>add/set/remove_affiliated</code>), explicit link-reading (<code>get_affiliated</code>), forgetting, and revision &mdash; despite documentation, worked skill examples, and the id-free query interface. In contrast, the two mechanism-embedded operations carried everything: <code>remember</code> (with atomization, merging, auto-affiliation inside) and <code>recall</code> (with auto-expansion inside; {AE['with_expansion']}/{AE['recalls']} recalls returned linked context). We take this as a design principle for agent memory systems: <b>structure must be a side-effect of the operations agents already perform, not a task delegated to them.</b></p>

<h2><span class="n">6</span> Discussion and Limitations</h2>
<p><b>What consensus buys.</b> Under equal granularity and sim-only accounting, consensus dominates structurally &mdash; fewest entries, all sharing, all graph structure &mdash; and this no longer trades against judged quality (best narrative, competitive elsewhere). The three-layer alignment argues the structure is meaningful: it recovers the story&rsquo;s social organization from the memory substrate alone.</p>
<p><b>Limitations.</b> (i) Quality metrics are LLM-judged and noisy; we report 3-scoring means with std, but ranking claims beyond narrative should be treated cautiously. (ii) Results cover one scenario (三国) and one 60-tick horizon; the protocol ports directly to other sedimented worlds and longer runs (checkpoints exist), but those runs remain future work. (iii) Auto-expansion is deliberately uncapped, appending &asymp;{AE['items']//max(AE['recalls'],1)} linked memories per recall; this enriches context but grows prompts, and its cost&ndash;benefit curve is unmeasured. (iv) The equivalence judge and atomizer consume extra LLM calls per deposit &mdash; the price of compression is paid at write time. (v) One baseline artifact: G-Memory re-runs distillation on resume (its distill bookkeeping is not check-pointed); sim-only accounting excludes distillation nodes, so reported numbers are unaffected.</p>

<h2><span class="n">7</span> Conclusion</h2>
<p>Agentsensus treats a story world&rsquo;s memory as a single consensus store: equivalent memories merge across witnesses, split memories link into a graph, and recall walks that graph automatically. On a novel-seeded 80-tick simulation, this yields the smallest memory footprint at equal granularity, the only shared and linked memory structure among four backends, and an emergent memory graph that mirrors the story&rsquo;s social structure &mdash; at no cost to judged narrative quality. The broader lesson is that memory structure in multi-agent systems must be mechanized, not delegated: agents reliably use only <code>remember</code> and <code>recall</code>, so that is where the structure has to live.</p>

<h2><span class="n">R</span> References</h2>
<ol class="refs">
<li>[1] J.&thinsp;S. Park, J. O&rsquo;Brien, C.&thinsp;J. Cai, M. Morris, P. Liang, M.&thinsp;S. Bernstein. <i>Generative Agents: Interactive Simulacra of Human Behavior.</i> UIST 2023. arXiv:2304.03442.</li>
<li>[2] Y. Ran, Y. Wang, Y. Li, et al. <i>BookWorld: From Novels to Interactive Agent Societies for Creative Story Generation.</i> 2025. arXiv:2504.14538.</li>
<li>[3] G. Zhang, et al. <i>G-Memory: Tracing Hierarchical Memory for Multi-Agent Systems.</i> 2025. arXiv:2506.07398.</li>
<li>[4] C. Packer, S. Wooders, K. Lin, et al. <i>MemGPT: Towards LLMs as Operating Systems.</i> 2023. arXiv:2310.08560.</li>
<li>[5] N. Shinn, F. Cassano, E. Berman, et al. <i>Reflexion: Language Agents with Verbal Reinforcement Learning.</i> NeurIPS 2023. arXiv:2303.11366.</li>
<li>[6] B.&thinsp;J. Guti&eacute;rrez, Y. Shu, Y. Gu, M. Yasunaga, Y. Su. <i>HippoRAG: Neurobiologically Inspired Long-Term Memory for Large Language Models.</i> NeurIPS 2024. arXiv:2405.14831.</li>
<li>[7] W. Xu, et al. <i>A-MEM: Agentic Memory for LLM Agents.</i> 2025. arXiv:2502.12110.</li>
<li>[8] Z. Zhang, X. Bo, C. Ma, et al. <i>A Survey on the Memory Mechanism of Large Language Model based Agents.</i> 2024. arXiv:2404.13501.</li>
<li>[9] A. Rezazadeh, et al. <i>Collaborative Memory: Multi-User Memory Sharing in LLM Agents with Dynamic Access Control.</i> 2025. arXiv:2505.18279.</li>
</ol>


<h2><span class="n">A</span> Appendix</h2>
<p>The appendix reports material the main text summarizes or omits: the full per-backend scale of every run (A.1), a census of what agents actually do with the action repertoire (A.2), transcript excerpts with a reading of how each memory design shows up in behavior (A.3), the sedimentation and cast-selection numbers behind each world (A.4), the language composition of the runs (A.5), and the merge-depth and expansion statistics behind the structural claims (A.6).</p>

<h3>A.1 &nbsp;Per-backend scale, all four worlds</h3>
<p>Table&nbsp;1 in &sect;5.1 reports simulation-generated entries only, which is the comparison the fairness protocol licenses. The full picture also includes what each backend carries out of sedimentation, because that is where consensus compression first applies: the same source events become one row per event under consensus and one row per witness under every baseline. &ldquo;Sediment&rdquo; below is the store at tick&nbsp;0 (including each backend&rsquo;s own by-products &mdash; Generative-Agents reflections, G-Memory insight nodes); &ldquo;sim&rdquo; is what the simulation then added; &ldquo;total&rdquo; is the store at the end of the run.</p>
<div class="tw"><table>
<caption><b>Table A1. Store size by backend and world.</b> Sediment rows are produced by each mechanism&rsquo;s own ingest of the identical source events (&sect;3.4), so the ratio in that column is consensus compression applied to the seeded history; sim rows are the &sect;5.1 comparison. All four backends atomize identically.</caption>
<thead><tr><th>world</th><th>backend</th><th>sediment</th><th>sim</th><th>total</th></tr></thead>
<tbody>
<tr class="grp"><td colspan="5">三国演义 &mdash; 80 ticks, 6,052 source events</td></tr>
<tr class="hi"><td></td><td>consensus</td><td class="best">6,051</td><td class="best">974</td><td class="best">7,025</td></tr>
<tr><td></td><td>generative-agents</td><td>20,896</td><td>1,251</td><td>22,147</td></tr>
<tr><td></td><td>g-memory</td><td>27,156</td><td>1,434</td><td>28,590</td></tr>
<tr><td></td><td>collaborative</td><td>19,856</td><td>1,455</td><td>21,311</td></tr>
<tr class="grp"><td colspan="5">红楼梦 &mdash; 80 ticks, 6,506 source events</td></tr>
<tr class="hi"><td></td><td>consensus</td><td class="best">6,506</td><td class="best">438</td><td class="best">6,944</td></tr>
<tr><td></td><td>generative-agents</td><td>27,306</td><td>785</td><td>28,091</td></tr>
<tr><td></td><td>g-memory</td><td>37,124</td><td>882</td><td>38,006</td></tr>
<tr><td></td><td>collaborative</td><td>26,681</td><td>789</td><td>27,470</td></tr>
<tr class="grp"><td colspan="5">Russia&ndash;Ukraine &mdash; 40 ticks, 1,533 source events</td></tr>
<tr class="hi"><td></td><td>consensus</td><td class="best">1,533</td><td class="best">814</td><td class="best">2,347</td></tr>
<tr><td></td><td>generative-agents</td><td>9,492</td><td>1,268</td><td>10,760</td></tr>
<tr><td></td><td>g-memory</td><td>14,346</td><td>1,191</td><td>15,537</td></tr>
<tr><td></td><td>collaborative</td><td>8,493</td><td>1,091</td><td>9,584</td></tr>
<tr class="grp"><td colspan="5">Hamlet &mdash; 30 ticks, 1,135 source events</td></tr>
<tr class="hi"><td></td><td>consensus</td><td class="best">1,135</td><td class="best">110</td><td class="best">1,245</td></tr>
<tr><td></td><td>generative-agents</td><td>5,819</td><td>152</td><td>5,971</td></tr>
<tr><td></td><td>g-memory</td><td>7,056</td><td>152</td><td>7,208</td></tr>
<tr><td></td><td>collaborative</td><td>5,310</td><td>151</td><td>5,461</td></tr>
</tbody></table></div>
<p><b>Reading.</b> The sediment column varies by world in a way the sim column does not: the per-witness fan-out is 3.3&times; in 三国, 4.1&ndash;5.7&times; in 红楼, 5.5&ndash;9.4&times; in Russia&ndash;Ukraine, 4.7&ndash;6.2&times; in Hamlet. The multiplier is not a property of the mechanism but of the world &mdash; it is the average number of witnesses per event, which a war room with institutional spokespeople maximizes and a two-hander chamber drama minimizes. The sim column is the same effect measured over events the simulation itself generated, at rates of roughly 12 (三国), 20 (Russia&ndash;Ukraine), 5 (红楼) and 4 (Hamlet) consensus entries per tick.</p>

<h3>A.2 &nbsp;What agents actually call</h3>
<p>&sect;5.6 asserts that agents never perform memory management. Table&nbsp;A2 is the evidence in full: every action invocation across the four worlds&rsquo; final stages, by backend. The repertoire is identical for all four and documented in the same skill file, with worked examples; the id-free query addressing of &sect;3.7 removes the interface barrier that an earlier design was suspected of having.</p>
<div class="tw"><table>
<caption><b>Table A2. Action census.</b> Counts are invocations in the final stage of each world (三国 g80, 红楼 rc80, Russia&ndash;Ukraine ru40, Hamlet hl30), summed across worlds, per backend. Rows at zero for all four backends are actions the repertoire offers and no agent ever used.</caption>
<thead><tr><th>action</th><th>consensus</th><th>gen-agents</th><th>g-memory</th><th>collab.</th></tr></thead>
<tbody>
<tr><td>read_thread</td><td>531</td><td>492</td><td>490</td><td>501</td></tr>
<tr><td>push_goal</td><td>418</td><td>434</td><td>421</td><td>358</td></tr>
<tr><td>say</td><td>325</td><td>297</td><td>307</td><td>314</td></tr>
<tr class="hi"><td>remember</td><td>168</td><td>181</td><td>169</td><td>177</td></tr>
<tr><td>wait</td><td>142</td><td>138</td><td>133</td><td>134</td></tr>
<tr><td>pop_goal</td><td>97</td><td>139</td><td>109</td><td>94</td></tr>
<tr><td>observe</td><td>82</td><td>74</td><td>84</td><td>81</td></tr>
<tr><td>act_on</td><td>19</td><td>21</td><td>39</td><td>46</td></tr>
<tr class="hi"><td>recall</td><td>19</td><td>8</td><td>24</td><td>19</td></tr>
<tr><td>read</td><td>17</td><td>23</td><td>54</td><td>20</td></tr>
<tr><td>move</td><td>13</td><td>9</td><td>15</td><td>15</td></tr>
<tr><td>update_status</td><td>6</td><td>2</td><td>1</td><td>1</td></tr>
<tr><td>think</td><td>3</td><td>4</td><td>5</td><td>3</td></tr>
<tr><td>conclude</td><td>2</td><td>0</td><td>9</td><td>0</td></tr>
<tr><td>replace_goal</td><td>1</td><td>1</td><td>4</td><td>2</td></tr>
<tr><td>forget</td><td>0</td><td>0</td><td>0</td><td>0</td></tr>
<tr><td>revise_memory</td><td>0</td><td>0</td><td>0</td><td>0</td></tr>
<tr><td>add_affiliated</td><td>0</td><td>0</td><td>0</td><td>0</td></tr>
<tr><td>remove_affiliated</td><td>0</td><td>0</td><td>0</td><td>0</td></tr>
<tr><td>set_affiliated</td><td>0</td><td>0</td><td>0</td><td>0</td></tr>
<tr><td>get_affiliated</td><td>0</td><td>0</td><td>0</td><td>0</td></tr>
<tr><td>remove_status</td><td>0</td><td>0</td><td>0</td><td>0</td></tr>
<tr><td>gesture / broadcast / noop</td><td>0</td><td>0</td><td>0</td><td>0</td></tr>
</tbody></table></div>
<p><b>Reading.</b> Three things stand out. First, the memory interface agents do use is exactly two calls wide: <code>remember</code> (168&ndash;181 per backend) and <code>recall</code> (8&ndash;24), and nothing else &mdash; every one of the six discretionary memory-management actions sits at zero for every backend. This is the empirical basis for D3: a mechanism placed behind <code>add_affiliated</code> would never run. Second, the distribution is nearly identical across backends, which is what the fairness protocol wants: the backends differ in what <code>remember</code> and <code>recall</code> <i>do</i>, not in how often agents call them. Third, the ratio of writes to reads is roughly 9:1 &mdash; agents deposit far more than they retrieve &mdash; which is why the cost analysis of &sect;5.2 treats the write path as the one that matters.</p>

<h3>A.3 &nbsp;Transcript excerpts</h3>
<p>The excerpts below are consecutive <code>say</code> messages from the 三国 run at ticks 60&ndash;64, one block per backend, chosen by length so that a block fits here (40&ndash;150 characters). They are unedited apart from truncation of the recipient list. Their purpose is not to show that one backend writes better prose &mdash; &sect;5.3 measures that, and finds the backends within error bars of one another &mdash; but to show what the memory mechanism looks like from the outside.</p>

<div class="quote"><b>consensus</b><br>
[t61] 程昱 &rarr; 乐进: &ldquo;乐进：今夜子时于许昌城东取徐母家书之事，今以何时为准？仍按子时取回，还是改为明日午后三刻于馆驿交接？请速回禀。&rdquo;<br>
[t62] 张昭 &rarr; 程普, 太史慈: &ldquo;程公、太史慈：拟于明日将荐表呈于主公。烦二子明示：一、是否坚持先由吾引见以正名分，抑或准吾先呈表并颁行路引以便速发？&hellip;&rdquo;<br>
[t63] 糜竺 &rarr; 孙乾: &ldquo;孙乾，盘点单现在可交否？若在途中请报预计到达确时；若已在手，请当面将盘点原件呈于我&hellip;&rdquo;</div>

<div class="quote"><b>generative-agents</b><br>
[t60] 乐进 &rarr; 徐庶: &ldquo;徐公，奉陛下与张督之令，烦请私札将你所辖各营、各仓当前粮草存量&hellip;及各处可出动预备队人数&hellip;呈报于臣&rdquo;<br>
[t61] 糜竺 &rarr; 刘备, 关羽, 孙乾: &ldquo;回禀主公：承受圣裁。兵数仍定为三百，准用樊城抽拨之三日口粮；我即刻领发粮草并督樊城粮官封存登记&hellip;&rdquo;<br>
[t62] 曹操 &rarr; 陈登: &ldquo;陈登收：得报，照准。吾将预备骑兵一千、步卒若干与工匠若干，备粮一月以待调度&hellip;联络暗号仍按汝所拟&rdquo;</div>

<div class="quote"><b>g-memory</b><br>
[t61] 荀彧 &rarr; 汉献帝: &ldquo;陛下启奏：臣今将《许昌局势摘要》暨各将书面条陈与斥候所获之证物一并呈上&hellip;&rdquo;<br>
[t62] 夏侯渊 &rarr; 荀彧: &ldquo;荀公：于禁、乐进已携册赴府衙呈上，臣亦已将斥候回报摘要与各营点验簿整理成册&hellip;能否按议于三刻内汇整为摘要上奏陛下？&rdquo;<br>
[t62] 赵云 &rarr; 张飞, 诸葛亮, 许褚: &ldquo;张将军，承你勇意。但依诸葛丞相与许将军所令，城中首务当以灭火固守三门为先&hellip;&rdquo;</div>

<div class="quote"><b>collaborative</b><br>
[t61] 程普 &rarr; 太史慈, 张昭: &ldquo;承二位之言，属下今即前往长史署内候見，烦请张長史代為轉呈主上&hellip;&rdquo;<br>
[t61] 许褚 &rarr; 关羽, 诸葛亮, 赵云: &ldquo;白狼山侦察已毕。沿山脊侦望，未见敌军主力，仅见零星侦骑与少数可疑营帐、营火。已设回报信号，现按原路返营&hellip;&rdquo;<br>
[t64] 伏皇后 &rarr; 孙乾: &ldquo;孙乾，已派骑卒与信使往大阳探查。你在荆州暂为主事：即刻整备近卫三百人、粮草与马匹，随时待命增援&hellip;&rdquo;</div>

<p><b>Reading.</b> The four blocks share a register &mdash; the simulation drifts toward administrative correspondence in every backend, which is a property of the action repertoire (agents can <code>say</code>, set goals, and report) rather than of memory. What differs is the <i>direction of reference</i>. Consensus lines characteristically ask a counterpart to confirm or amend a detail both sides already hold (&ldquo;仍按子时取回，还是改为明日午后三刻&rdquo;, &ldquo;盘点单现在可交否&rdquo;): the speaker is treating an earlier arrangement as a shared record and asking which branch of it now applies. Baseline lines more often restate the arrangement in full before acting on it &mdash; Generative-Agents&rsquo; 糜竺 recapitulates troop count, rations, and the sealing of the granary; collaborative&rsquo;s 许褚 re-reports the entire scouting result &mdash; which is what an agent does when it cannot assume the other party&rsquo;s copy matches its own. This is consistent with, though not proof of, the mechanism: when N witnesses hold one row, the premises of a conversation do not need re-establishing. It is also the plausible source of the narrative-coherence edge consensus shows in 三国 (&sect;5.3.1) and of nothing else &mdash; the effect is small, and the quality metrics say so.</p>
<p>One artifact worth recording, because it affects anything built on the event log: the kernel logs a single utterance both as an <code>action</code> event and as one <code>message</code> event per recipient, so a line addressed to three agents appears four times. Naive transcript assembly therefore triples parts of a run; the excerpts above and the screenplay renderer both deduplicate by (tick, speaker, content).</p>

<h3>A.4 &nbsp;Sedimentation and cast selection</h3>
<p>Each world is built by the pipeline of &sect;3.4 and then reduced to a simulable cast. A character participates iff it owns more than a per-world threshold of sediment memories; below-threshold characters remain owners of their memories but are never scheduled. Environments are kept if an active character stands there or if they own memories of their own; information carriers (letters, commissions, play scripts) are always kept.</p>
<div class="tw"><table>
<caption><b>Table A3. Sedimentation cost and cast composition.</b> Wall-clock and token figures are for the sedimentation pass only, on the consensus store; the per-backend ingest of the same events is additional. &ldquo;Warnings&rdquo; counts extraction records the pipeline flagged for review (unresolved referents, ambiguous attributions).</caption>
<thead><tr><th>world</th><th>registry</th><th>events</th><th>LLM calls</th><th>tokens</th><th>wall</th><th>active</th><th>archived</th><th>envs</th><th>carriers</th><th>warn</th></tr></thead>
<tbody>
<tr><td>三国演义</td><td>399</td><td>6,052</td><td>764</td><td>9.2M</td><td>124 min</td><td>33</td><td>38</td><td>115</td><td>5</td><td>235</td></tr>
<tr><td>红楼梦</td><td>152</td><td>6,506</td><td>848</td><td>8.5M</td><td>129 min</td><td>34</td><td>3</td><td>88</td><td>9</td><td>222</td></tr>
<tr><td>Russia&ndash;Ukraine</td><td>170</td><td>1,533</td><td>1,373</td><td>12.3M</td><td>69 min</td><td>47</td><td>14</td><td>71</td><td>0</td><td>61</td></tr>
<tr><td>Hamlet</td><td>22</td><td>1,135</td><td>212</td><td>0.9M</td><td>31 min</td><td>16</td><td>2</td><td>8</td><td>3</td><td>10</td></tr>
</tbody></table></div>
<p><b>Reading.</b> Cost tracks source length, not cast size: Russia&ndash;Ukraine extracts the fewest events (1,533 dated entries) yet costs the most tokens, because a timeline entry names many institutional actors and attribution must resolve each one. The archived column is the boundary-state finalization of &sect;3.4 at work and is worth reading per world: 三国 archives 38 characters dead by chapter&nbsp;40; 红楼 archives three (秦可卿, 贾瑞, 秦钟); Hamlet archives Polonius, killed in 3.4, and the Ghost, absent from the canon thereafter; Russia&ndash;Ukraine archives 14 under real-world semantics, where &ldquo;no longer a participant&rdquo; covers leaving office or being disbanded as well as dying, and where every placement was verified by hand against the 2026-07 boundary. Two cases required overrides that no automatic rule would produce: Fortinbras owns zero sediment memories &mdash; he never appears before Act&nbsp;4 &mdash; but is retained because the continuation is his, and England is retained as an environment for the same reason.</p>

<h3>A.5 &nbsp;Language composition of the runs</h3>
<p>Each world declares a language: 三国 and 红楼 run in Chinese, Russia&ndash;Ukraine and Hamlet in English. The declaration selects the action-skill document and the output-format block, and the sediment is in the source language throughout. It did <i>not</i>, in the runs reported here, constrain what agents wrote: the language of a memory followed the language of the profile and of whatever the agent recalled, and drifted when those disagreed.</p>
<div class="tw"><table>
<caption><b>Table A4. Language of simulation memories</b> (consensus store, final stage of each world). Classification is by script: an entry with CJK characters and no substantial Latin text counts as Chinese, an entry with both counts as mixed, Cyrillic-dominant entries count as Russian.</caption>
<thead><tr><th>world</th><th>declared</th><th>Chinese</th><th>English</th><th>mixed</th><th>Russian</th></tr></thead>
<tbody>
<tr><td>三国演义</td><td>zh</td><td>90%</td><td>9%</td><td>&mdash;</td><td>&mdash;</td></tr>
<tr><td>红楼梦</td><td>zh</td><td>97%</td><td>1%</td><td>1%</td><td>&mdash;</td></tr>
<tr><td>Russia&ndash;Ukraine</td><td>en</td><td>12%</td><td>81%</td><td>2%</td><td>2%</td></tr>
<tr><td>Hamlet</td><td>en</td><td>26%</td><td>59%</td><td>14%</td><td>&mdash;</td></tr>
</tbody></table></div>
<p><b>Reading.</b> The drift is largest where the two implicit signals disagree most. All four worlds carried Chinese-authored character profiles, so an English world with an English sediment still pulled toward Chinese, and Hamlet &mdash; the smallest sediment, hence the weakest counterweight &mdash; drifted furthest (26% Chinese, 14% mixed). Russia&ndash;Ukraine additionally produced Russian-language memories: agents adopted the language of the character they were playing, which no instruction had asked for and none had forbidden. We report this as a finding about implicit conditioning rather than a defect of the memory mechanisms, which are language-agnostic: entry counts, sharing, and graph structure are unaffected. The framework now carries an explicit content-language directive in the agent system prompt, and screenplays are normalized to the world&rsquo;s language at render time; the runs above predate the directive and were not regenerated for it.</p>

<h3>A.6 &nbsp;Merge depth, graph density, and expansion</h3>
<p>&sect;5.1 reports the share of memories that are shared and linked. The distribution behind those shares, and what recall does with the graph, are below.</p>
<div class="tw"><table>
<caption><b>Table A5. Consensus structure per world</b> (final stage). &ldquo;3+&rdquo; counts entries with three or more witnesses; &ldquo;max&rdquo; is the deepest merge; &ldquo;expanded&rdquo; is the fraction of recalls that returned at least one memory reached along an affiliated edge, with the mean number of such memories per call.</caption>
<thead><tr><th>world</th><th>sim entries</th><th>shared</th><th>3+</th><th>max</th><th>linked</th><th>expanded recalls</th><th>linked per call</th></tr></thead>
<tbody>
<tr><td>三国演义 (80t)</td><td>974</td><td>188 (19%)</td><td>38</td><td>6</td><td>97%</td><td>51/51</td><td>28</td></tr>
<tr><td>红楼梦 (80t)</td><td>438</td><td>107 (24%)</td><td>24</td><td>6</td><td>94%</td><td>19/19</td><td>38</td></tr>
<tr><td>Russia&ndash;Ukraine (40t)</td><td>814</td><td>113 (14%)</td><td>23</td><td>10</td><td>99%</td><td>23/41</td><td>2</td></tr>
<tr><td>Hamlet (30t)</td><td>110</td><td>29 (26%)</td><td>1</td><td>3</td><td>98%</td><td>3/3</td><td>39</td></tr>
</tbody></table></div>
<p><b>Reading.</b> Merge depth is a property of the world&rsquo;s staging, not of the mechanism. Russia&ndash;Ukraine reaches ten witnesses on a single presidential air-defense directive because a real command chain broadcasts one instruction to many named institutions at once; Hamlet tops out at three, and only once &mdash; on the players&rsquo; performance, the one scene in the play that assembles an audience &mdash; because Shakespeare stages almost everything as a two-person exchange. The two novels sit between, at six. Expansion behaves differently for a different reason: it returns few linked memories in Russia&ndash;Ukraine (2 per call, and only 23 of 41 recalls expanded at all) because institutional deposits are short and rarely split into several atoms, so there are fewer siblings to link; in the novels a single compound recollection atomizes into many pieces, and a recall pulls back 28&ndash;39 of them. The sharing rate itself is horizon-dependent and saturating &mdash; 红楼, run at four horizons, goes 13%&rarr;20%&rarr;23%&rarr;24% at ticks 10/40/60/80 &mdash; which is the compounding argument of &sect;5.1.3 measured directly.</p>

<p class="foot">Agentsensus &middot; 三国演义 60-tick, three resumed 20-tick stages &middot; chat gpt-5-mini, embeddings text-embedding-3-small &middot; simulation-only accounting under uniform atomization &middot; structural counts deterministic; quality metrics mean&plusmn;std over 3 LLM scorings &middot; data: <code>runs/g20_* ... g80_*</code>.</p>

</div>
"""

JS = r"""
<script>
(function(){
const G = __GRAPHS__;
const GRU = __GRAPHS_RU__;
const GRC = __GRAPHS_RC__;
const GHL = __GRAPHS_HL__;
const PAL = ["#2563eb","#d97706","#059669","#dc2626","#7c3aed","#0891b2","#be185d","#65a30d","#475569","#b45309"];
function css(v){ return getComputedStyle(document.documentElement).getPropertyValue(v).trim() || "#888"; }
function esc(s){ return String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;"); }

function mk(el){
  const cv=document.createElement("canvas"), tip=document.createElement("div"), hint=document.createElement("div");
  tip.className="tip"; hint.className="hint"; hint.textContent="drag: pan · scroll: zoom · hover: details";
  el.appendChild(cv); el.appendChild(tip); el.appendChild(hint);
  const dpr=window.devicePixelRatio||1;
  function size(){ cv.width=el.clientWidth*dpr; cv.height=el.clientHeight*dpr; }
  size();
  return {cv,ctx:cv.getContext("2d"),tip,dpr,size,el};
}
function showTip(h,html,mx,my){
  h.tip.innerHTML=html; h.tip.style.display="block";
  const r=h.el.getBoundingClientRect();
  let x=mx+14,y=my+12;
  h.tip.style.left="0px"; h.tip.style.top="0px";
  const tw=h.tip.offsetWidth,th=h.tip.offsetHeight;
  if(x+tw>r.width-6)x=mx-tw-10; if(y+th>r.height-6)y=my-th-8;
  h.tip.style.left=Math.max(4,x)+"px"; h.tip.style.top=Math.max(4,y)+"px";
}

/* ---------- generic node-link view (interaction / affiliation) ---------- */
function nodeLink(elId,data,opt){
  const el=document.getElementById(elId); if(!el)return;
  const h=mk(el), N=data.nodes, E0=data.edges;
  const idx={}; N.forEach((n,i)=>{ if(n.id!==undefined) idx[n.id]=i; });
  const E=E0.map(e=>Array.isArray(e)?{a:e[0],b:e[1],w:e[2]||1}:{a:idx[e.s],b:idx[e.t],w:e.w||1});
  const nbr=N.map(()=>[]);
  E.forEach(e=>{ nbr[e.a].push(e.b); nbr[e.b].push(e.a); });
  let s,tx,ty;
  function fit(){
    const xs=N.map(n=>n.x),ys=N.map(n=>n.y);
    const x0=Math.min(...xs),x1=Math.max(...xs),y0=Math.min(...ys),y1=Math.max(...ys);
    const W=h.cv.width,H=h.cv.height,p=46*h.dpr;
    s=Math.min((W-2*p)/Math.max(x1-x0,1e-6),(H-2*p)/Math.max(y1-y0,1e-6));
    tx=(W-s*(x0+x1))/2; ty=(H-s*(y0+y1))/2;
  }
  fit();
  const SX=n=>s*n.x+tx, SY=n=>s*n.y+ty;
  let hov=-1, sel=-1;
  function draw(){
    const ctx=h.ctx,W=h.cv.width,H=h.cv.height;
    const ink=css("--ink"), faint=css("--faint");
    ctx.clearRect(0,0,W,H);
    const focus = sel>=0?sel:hov;
    ctx.lineCap="round";
    E.forEach(e=>{
      const a=e.a,b=e.b;
      const on = focus<0 || a===focus||b===focus;
      ctx.strokeStyle = on ? (opt.edgeColor||"#8fa3c8") : "rgba(150,150,150,.08)";
      ctx.globalAlpha = on ? (opt.edgeAlpha||0.35) : 1;
      ctx.lineWidth = ((opt.ew?opt.ew(e):1))*h.dpr*(on&&focus>=0?1.8:1);
      ctx.beginPath(); ctx.moveTo(SX(N[a]),SY(N[a])); ctx.lineTo(SX(N[b]),SY(N[b])); ctx.stroke();
    });
    ctx.globalAlpha=1;
    N.forEach((n,i)=>{
      const on = focus<0 || i===focus || nbr[focus].includes(i);
      const r=(opt.r(n))*h.dpr;
      ctx.beginPath(); ctx.arc(SX(n),SY(n),r,0,7);
      ctx.fillStyle = on ? opt.color(n) : "rgba(150,150,150,.25)";
      ctx.fill();
      if(opt.ring&&opt.ring(n)&&on){ ctx.lineWidth=1.6*h.dpr; ctx.strokeStyle="#d63b3b"; ctx.stroke(); }
    });
    if(opt.labels){
      ctx.font=(10.5*h.dpr)+"px system-ui"; ctx.fillStyle=ink; ctx.textAlign="center";
      N.forEach((n,i)=>{
        const on = focus<0 || i===focus || nbr[focus].includes(i);
        if(on) ctx.fillText(n.id,SX(n),SY(n)-(opt.r(n)+4)*h.dpr);
      });
    } else if(focus>=0){
      ctx.font=(10.5*h.dpr)+"px system-ui"; ctx.fillStyle=ink; ctx.textAlign="center";
      [focus,...nbr[focus]].slice(0,40).forEach(i=>{const n=N[i];
        ctx.fillText(opt.shortLabel?opt.shortLabel(n):n.id,SX(n),SY(n)-(opt.r(n)+4)*h.dpr);});
    }
  }
  draw();
  let drag=null,panning=false,px=0,py=0;
  function pick(mx,my){
    let best=-1,bd=14*h.dpr;
    N.forEach((n,i)=>{const d=Math.hypot(SX(n)-mx,SY(n)-my); if(d<bd){bd=d;best=i;}});
    return best;
  }
  h.cv.addEventListener("mousemove",ev=>{
    const r=h.cv.getBoundingClientRect(),mx=(ev.clientX-r.left)*h.dpr,my=(ev.clientY-r.top)*h.dpr;
    if(drag!==null){ N[drag].x=(mx-tx)/s; N[drag].y=(my-ty)/s; draw(); return; }
    if(panning){ tx+=(mx-px); ty+=(my-py); px=mx; py=my; draw(); return; }
    const p=pick(mx,my);
    if(p!==hov){ hov=p; draw(); }
    if(p>=0){ showTip(h,opt.tip(N[p]),(ev.clientX-r.left),(ev.clientY-r.top)); h.el.style.cursor="pointer"; }
    else { h.tip.style.display="none"; h.el.style.cursor="grab"; }
  });
  h.cv.addEventListener("mousedown",ev=>{
    const r=h.cv.getBoundingClientRect(),mx=(ev.clientX-r.left)*h.dpr,my=(ev.clientY-r.top)*h.dpr;
    const p=pick(mx,my);
    if(p>=0){ drag=p; } else { panning=true; px=mx; py=my; h.el.style.cursor="grabbing"; }
  });
  window.addEventListener("mouseup",()=>{ drag=null; panning=false; h.el.style.cursor="grab"; });
  h.cv.addEventListener("mouseleave",()=>{ hov=-1; h.tip.style.display="none"; draw(); });
  h.cv.addEventListener("click",ev=>{
    const r=h.cv.getBoundingClientRect();
    const p=pick((ev.clientX-r.left)*h.dpr,(ev.clientY-r.top)*h.dpr);
    sel = (p===sel)? -1 : p; draw();
  });
  h.cv.addEventListener("wheel",ev=>{
    ev.preventDefault();
    const r=h.cv.getBoundingClientRect(),mx=(ev.clientX-r.left)*h.dpr,my=(ev.clientY-r.top)*h.dpr;
    const f=Math.exp(-ev.deltaY*0.0015);
    tx=mx-(mx-tx)*f; ty=my-(my-ty)*f; s*=f; draw();
  },{passive:false});
  window.addEventListener("resize",()=>{ h.size(); fit(); draw(); });
}

/* ---------- heatmap ---------- */
function heatmap(elId,data){
  const el=document.getElementById(elId); if(!el)return;
  const h=mk(el), ord=data.order, M=data.matrix, n=ord.length;
  const vmax=Math.max(1,...M.flat());
  function color(v){
    if(v<=0) return css("--line2");
    const t=Math.pow(v/vmax,0.5);
    const stops=[[37,99,235,.15],[37,99,235,.55],[214,59,59,.9]];
    const i=t<0.5?0:1, u=(t<0.5?t*2:(t-0.5)*2);
    const a=stops[i],b=stops[i+1];
    const mix=(x,y)=>Math.round(x+(y-x)*u);
    return `rgba(${mix(a[0],b[0])},${mix(a[1],b[1])},${mix(a[2],b[2])},${(a[3]+(b[3]-a[3])*u).toFixed(2)})`;
  }
  let cell,ox,oy;
  function draw(){
    const ctx=h.ctx,W=h.cv.width,H=h.cv.height;
    ctx.clearRect(0,0,W,H);
    const L=110*h.dpr;
    cell=Math.min((W-L-10*h.dpr)/n,(H-L-10*h.dpr)/n); ox=L; oy=L;
    ctx.font=(9*h.dpr)+"px system-ui";
    for(let i=0;i<n;i++)for(let j=0;j<n;j++){
      ctx.fillStyle=color(M[i][j]);
      ctx.fillRect(ox+j*cell,oy+i*cell,cell-1,cell-1);
    }
    ctx.fillStyle=css("--muted");
    for(let i=0;i<n;i++){
      ctx.textAlign="right"; ctx.fillText(ord[i],ox-4*h.dpr,oy+i*cell+cell*0.7);
      ctx.save(); ctx.translate(ox+i*cell+cell*0.7,oy-4*h.dpr); ctx.rotate(-Math.PI/2);
      ctx.textAlign="left"; ctx.fillText(ord[i],0,0); ctx.restore();
    }
  }
  draw();
  h.cv.addEventListener("mousemove",ev=>{
    const r=h.cv.getBoundingClientRect(),mx=(ev.clientX-r.left)*h.dpr,my=(ev.clientY-r.top)*h.dpr;
    const j=Math.floor((mx-ox)/cell), i=Math.floor((my-oy)/cell);
    if(i>=0&&i<ord.length&&j>=0&&j<ord.length&&i!==j){
      showTip(h,`<b>${esc(ord[i])}</b> ↔ <b>${esc(ord[j])}</b><br>co-owned memories: <b>${M[i][j]}</b>`,
        ev.clientX-r.left,ev.clientY-r.top);
    } else h.tip.style.display="none";
  });
  h.cv.addEventListener("mouseleave",()=>h.tip.style.display="none");
  window.addEventListener("resize",()=>{h.size();draw();});
}

/* ---------- tri-layer ---------- */
function trilayer(elId,data){
  const el=document.getElementById(elId); if(!el)return;
  const h=mk(el);
  const A=data.agents,M=data.mems;
  const ai={},mi={}; A.forEach((a,i)=>ai[a.id]=i); M.forEach((m,i)=>{ if(m.id!==undefined) mi[m.id]=i; });
  const OWN=data.own.map(o=>({a:o.a, m:(typeof o.m==="number")?o.m:mi[o.m], multi:o.multi}));
  const AFF=data.aff.map(e=>Array.isArray(e)?{u:e[0],v:e[1],ov:!!e[2]}:{u:mi[e.s],v:mi[e.t],ov:e.overlap});
  const wmax=Math.max(1,...data.say.map(e=>e.w));
  let s,tx;
  const xmax=Math.max(...A.map(a=>a.x),...M.map(m=>m.x));
  function geom(){
    const W=h.cv.width,p=40*h.dpr;
    s=(W-2*p)/Math.max(xmax,1); tx=p;
  }
  geom();
  const X=x=>s*x+tx;
  const YA=()=>h.cv.height*0.30, YM=()=>h.cv.height*0.72;
  let hovA=-1,hovM=-1;
  function arc(ctx,x1,x2,y,hgt,up){
    ctx.beginPath(); ctx.moveTo(x1,y);
    ctx.quadraticCurveTo((x1+x2)/2, up? y-hgt : y+hgt, x2,y); ctx.stroke();
  }
  function draw(){
    const ctx=h.ctx,W=h.cv.width,H=h.cv.height;
    const ink=css("--ink");
    ctx.clearRect(0,0,W,H);
    const focusA=hovA, focusM=hovM, any=focusA>=0||focusM>=0;
    // ownership lines
    OWN.forEach(o=>{
      const a=A[ai[o.a]],m=M[o.m]; if(!a||!m)return;
      const on=!any || (focusA>=0&&ai[o.a]===focusA) || (focusM>=0&&o.m===focusM);
      ctx.strokeStyle=o.multi? (on?"#d63b3b":"rgba(214,59,59,.10)") : (on?"rgba(160,170,190,.4)":"rgba(160,170,190,.06)");
      ctx.lineWidth=(o.multi?1.6:0.6)*h.dpr;
      ctx.beginPath(); ctx.moveTo(X(a.x),YA()+8*h.dpr); ctx.lineTo(X(m.x),YM()-6*h.dpr); ctx.stroke();
    });
    // say arcs
    data.say.forEach(e=>{
      const a=ai[e.s],b=ai[e.t]; if(a===undefined||b===undefined)return;
      const on=!any || (focusA>=0&&(a===focusA||b===focusA));
      ctx.strokeStyle= on? "#2563eb":"rgba(37,99,235,.07)";
      ctx.globalAlpha= on?0.55:1;
      ctx.lineWidth=(0.7+2.4*e.w/wmax)*h.dpr;
      arc(ctx,X(A[a].x),X(A[b].x),YA()-8*h.dpr,(18+55*Math.abs(A[a].x-A[b].x)/(xmax||1))*h.dpr,true);
    });
    ctx.globalAlpha=1;
    // affiliation arcs
    AFF.forEach(e=>{
      const u=e.u,v=e.v; if(u===undefined||v===undefined)return;
      const on=!any || (focusM>=0&&(u===focusM||v===focusM)) ||
        (focusA>=0 && (M[u].owners.includes(A[focusA].id)||M[v].owners.includes(A[focusA].id)));
      ctx.strokeStyle = e.ov ? (on?"#10b981":"rgba(16,185,129,.05)") : (on?"#9ca3af":"rgba(156,163,175,.08)");
      ctx.lineWidth=(e.ov?0.7:1.4)*h.dpr;
      arc(ctx,X(M[u].x),X(M[v].x),YM()+7*h.dpr,(14+50*Math.abs(M[u].x-M[v].x)/(xmax||1))*h.dpr,false);
    });
    // memory nodes
    M.forEach((m,i)=>{
      const on=!any || i===focusM || (focusA>=0&&m.owners.includes(A[focusA].id));
      ctx.fillStyle = m.multi? (on?"#d63b3b":"rgba(214,59,59,.25)") : (on?"#8fa3c8":"rgba(143,163,200,.2)");
      const r=(m.multi?5:3)*h.dpr;
      ctx.beginPath(); ctx.arc(X(m.x),YM(),r,0,7); ctx.fill();
    });
    // agent nodes + labels
    ctx.font=(9.5*h.dpr)+"px system-ui";
    A.forEach((a,i)=>{
      const on=!any || i===focusA || (focusM>=0&&M[focusM].owners.includes(a.id));
      const isChar=a.kind==="character";
      ctx.fillStyle= on? (isChar?"#2563eb":"#7c9ff5") : "rgba(120,140,180,.25)";
      const r=7*h.dpr;
      if(isChar){ ctx.beginPath(); ctx.arc(X(a.x),YA(),r,0,7); ctx.fill(); }
      else ctx.fillRect(X(a.x)-r*0.8,YA()-r*0.8,r*1.6,r*1.6);
      if(on){
        ctx.save(); ctx.translate(X(a.x)+2*h.dpr,YA()-10*h.dpr); ctx.rotate(-0.9);
        ctx.fillStyle=ink; ctx.textAlign="left"; ctx.fillText(a.id,0,0); ctx.restore();
      }
    });
  }
  draw();
  h.cv.addEventListener("mousemove",ev=>{
    const r=h.cv.getBoundingClientRect(),mx=(ev.clientX-r.left)*h.dpr,my=(ev.clientY-r.top)*h.dpr;
    let ba=-1,bd=13*h.dpr;
    A.forEach((a,i)=>{const d=Math.hypot(X(a.x)-mx,YA()-my); if(d<bd){bd=d;ba=i;}});
    let bm=-1; bd=11*h.dpr;
    M.forEach((m,i)=>{const d=Math.hypot(X(m.x)-mx,YM()-my); if(d<bd){bd=d;bm=i;}});
    if(bm>=0) ba=-1;
    if(ba!==hovA||bm!==hovM){ hovA=ba; hovM=bm; draw(); }
    if(bm>=0){ const m=M[bm];
      showTip(h,`<b>memory</b> ${m.multi?"(shared ★)":""}<br>${esc(m.text)}<br><b>owners:</b> ${esc(m.owners.join(", "))}`,
        ev.clientX-r.left,ev.clientY-r.top);
    } else if(ba>=0){ const a=A[ba];
      const owned=OWN.filter(o=>o.a===a.id).length;
      showTip(h,`<b>${esc(a.id)}</b> (${a.kind})<br>owned sim memories: <b>${owned}</b>`,
        ev.clientX-r.left,ev.clientY-r.top);
    } else h.tip.style.display="none";
  });
  h.cv.addEventListener("mouseleave",()=>{hovA=-1;hovM=-1;h.tip.style.display="none";draw();});
  window.addEventListener("resize",()=>{h.size();geom();draw();});
}

function initSet(GG,pfx){
nodeLink(pfx+"interaction",GG.interaction,{
  r:n=>5.5+1.1*Math.sqrt(Math.min(n.deg||0,80)),
  color:n=> n.comm>=0? PAL[n.comm%10] : "#9ca3af",
  ew:e=>0.5+2.2*e.w/Math.max(1,...GG.interaction.edges.map(x=>x.w)),
  edgeColor:"#8fa3c8", edgeAlpha:0.4, labels:true,
  tip:n=>`<b>${esc(n.id)}</b><br>${n.silent?"silent this run":"conversation volume: <b>"+n.deg+"</b>"}<br>community: ${n.comm>=0?n.comm+1:"—"}`
});
nodeLink(pfx+"affiliation",GG.affiliation,{
  r:n=> n.shared?5:3,
  color:n=> (GG.affiliation.nodes.filter(x=>x.comp===n.comp).length>1)? PAL[n.comp%10] : "#b9c0cc",
  ring:n=>n.shared,
  ew:()=>0.5, edgeColor:"#9fb4d8", edgeAlpha:0.3, labels:false,
  shortLabel:n=>"",
  tip:n=>`<b>memory</b> ${n.shared?"(shared)":""}<br>${esc(n.text)}<br><b>owners:</b> ${esc(n.owners.join(", "))}`
});
heatmap(pfx+"heatmap",GG.heatmap);
trilayer(pfx+"trilayer",GG.trilayer);
}
initSet(G,"ig-");
initSet(GRU,"ig-ru-");
initSet(GRC,"ig-rc-");
initSet(GHL,"ig-hl-");
})();
</script>
"""

out = "docs/index.html"
with open(out, "w") as f:
    f.write("<title>Agentsensus &mdash; Consensus-Compressed Shared Memory</title>\n" + HTML
            + JS.replace("__GRAPHS__", GRAPHS_JSON).replace("__GRAPHS_RU__", GRAPHS_RU_JSON).replace("__GRAPHS_RC__", GRAPHS_RC_JSON).replace("__GRAPHS_HL__", GRAPHS_HL_JSON))
print("wrote", out, len(HTML) + len(JS) + len(GRAPHS_JSON), "bytes")
