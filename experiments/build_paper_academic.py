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
  <span><b>Scenarios</b> 三国演义 (80 ticks, 33 active agents) &middot; Russia&ndash;Ukraine (40 ticks, 47 active)</span>
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

<h3>3.1 &nbsp;Overview</h3>
<p>Agentsensus consists of three subsystems (Figure 1): an offline <b>sedimentation pipeline</b> that turns a source novel into a memory-grounded initial world; a deterministic <b>tick-barrier kernel</b> that schedules agents, routes messages, and snapshots the full system; and the <b>consensus shared memory</b>, whose write and read paths embed all of the structural mechanisms of &sect;1. Data flows left to right at start-up (sedimentation seeds the store and the world state) and cycles between kernel and store at run time: Phase-2 action effects write into the store and the conversation threads, and both feed the next tick&rsquo;s agent views through owner-scoped recall and the conversation roster.</p>
<figure>
  <img src="{IMG['arch']}" alt="Agentsensus architecture">
  <figcaption><b>Figure 1. System architecture.</b> Left: the offline sedimentation pipeline (novel &rarr; witnessed atomic events &rarr; per-backend ingest &rarr; boundary-state finalization &rarr; seeded world). Center: the tick-barrier kernel &mdash; numbered stages run each tick; conversation threads and the world map are kernel-held state; the checkpointer snapshots agents&rsquo; short-term state, kernel runtime, and the entire store every 20 ticks for bit-for-bit resumption. Right: the consensus shared memory &mdash; the row data model, the four-stage write path (atomize &rarr; pre-filter &rarr; equivalence judge &rarr; merge/insert, plus auto-affiliation), the two-stage read path (owner-scoped kNN + one-hop affiliated expansion), query-addressed mutations, and the empirical design rule that motivates placing every mechanism inside <code>remember</code>/<code>recall</code>.</figcaption>
</figure>

<h3>3.2 &nbsp;World model and tick-barrier kernel</h3>
<p><b>Entities.</b> A world is a set of agents on a location map with pairwise travel distances. <b>Characters</b> are LLM-driven: each holds a persona, a goal stack, a status register, and a short-term FIFO of recent actions; each decision is one LLM call that receives a rendered view (tick, goals, status, FIFO, co-located agents, conversation roster, known locations, plus contextual hints) and returns one action as JSON. <b>Environments</b> and <b>information carriers</b> are passive: they own memories (deposited by sedimentation or by characters&rsquo; <code>act_on</code>) but never take turns &mdash; a character&rsquo;s <code>act_on</code>/<code>read</code> is served synchronously by the kernel against the target&rsquo;s own memories, costing no extra LLM calls and giving places and documents durable, queryable state.</p>
<p><b>Scheduling.</b> Each tick runs two phases under a barrier. Phase&nbsp;1 builds every awake character&rsquo;s view from the <i>same</i> pre-tick snapshot and issues all decisions concurrently; because views are frozen before any decision, LLM latency cannot change what any agent observes. Phase&nbsp;2 applies the returned actions sequentially in a fixed agent order, so conflicting effects resolve deterministically and event order is reproducible independent of API timing. Agents sleep only by explicit <code>wait</code>; a single sleep is capped (20 ticks) after we observed uncapped waits produce narrative deadlocks &mdash; a character who delegated a task and slept &ldquo;until the report arrives&rdquo; was simply never messaged again and stayed silent for 52 ticks. A <code>wake=true</code> message still interrupts sleep early.</p>
<p><b>Messaging.</b> Messages are not agent-held inboxes but kernel-held <b>conversation threads</b>, one per interlocutor pair. Co-located speech delivers at the next tick; remote messages travel for their map distance in ticks, so information propagates at the speed of couriers rather than instantaneously. Delivery increments the recipient&rsquo;s unread counter (surfaced in its view roster) and, by default, wakes it; reading is an explicit <code>read_thread</code> action. The same threads also log observation and environment interactions, giving each pair a complete interaction history.</p>
<p><b>Checkpointing.</b> Every 20 ticks the kernel atomically snapshots the complete system &mdash; each agent&rsquo;s short-term state (FIFO, goal stack, status, sleep timer), kernel runtime (presence, in-transit moves, undelivered messages, conversation threads, event counter), and the entire memory store including embeddings. A resumed run continues bit-for-bit; all 80-tick results in &sect;5 are four resumed 20-tick stages of one continuous run per backend.</p>

<h3>3.3 &nbsp;Sedimentation: from novel to memory-grounded world</h3>
<p>The pipeline converts chapters 1&ndash;40 into the initial world in four steps. (i) <b>Extraction and attribution</b>: an LLM pass extracts events chapter by chapter and attributes each to the characters who witnessed it, producing atomic, story-ordered records with owner-sets. (ii) <b>Per-backend ingest</b>: each memory backend stores these events under its own rule &mdash; the consensus store keeps one merged row per event carrying the full owner-set, while per-agent baselines fan out one row per witness &mdash; so every method starts from the initial state its own mechanism would have produced, and baseline machinery (importance scoring, reflection, distillation) is run over the sediment before tick 0. (iii) <b>Boundary-state finalization</b>: each character&rsquo;s aliveness and location at the story boundary are extracted from <i>its own memory timeline</i> (with a canon-knowledge fallback anchored to the boundary chapter); characters dead by chapter 40 are archived &mdash; they keep their memories as owners but are never scheduled &mdash; and living ones are placed at their last grounded location. (iv) The result: 191 characters (33 active), ~6,000 consensus events, a world whose knowledge and geography are both grounded in the text.</p>

<h3>3.4 &nbsp;The consensus shared memory</h3>
<p><b>Data model.</b> The store is a single vector collection whose rows are (text, embedding, owner-set, affiliated-set, metadata). Owner membership is additionally materialized as indexed per-agent flags, so owner-scoped retrieval is a server-side filter rather than a post-hoc scan; the affiliated-set holds ids of related rows and is what makes the store a graph.</p>
<p><b>Write path.</b> Every <code>remember(text)</code> runs four stages. <i>(1) Atomization:</i> a compound deposit is split by an LLM into atomic statements, each required to be <b>self-contained</b> &mdash; pronouns resolved to names, who/what/where carried over &mdash; so a statement is interpretable without its siblings. All four backends share this exact stage (&sect;4.3), making entry counts comparable by construction. <i>(2) Candidate pre-filter:</i> each atom is embedded and matched against the store by cosine kNN with a deliberately permissive threshold (0.70): self-contained phrasings of the same event from different viewpoints embed measurably further apart than near-identical wordings, and at the conventional 0.86 <i>zero</i> cross-witness sim memories ever reached candidacy. <i>(3) Equivalence judging:</i> an LLM judge inspects the candidates and either selects the one that describes the same event or declines. The pre-filter only bounds the judge&rsquo;s candidate list; the judge is the actual gate, so the permissive threshold trades a few extra judge calls for recall of true matches. <i>(4) Merge or insert:</i> on a match the records fold into one row &mdash; owner-sets union, affiliated-sets union, the shorter text is kept &mdash; so N witnesses of one event cost one row; otherwise a fresh row is inserted. Finally, <b>auto-affiliation</b> mutually links the atoms split from one deposit: the memory graph is built as a side-effect of writing, by the mechanism rather than the agent.</p>
<p><b>Read path.</b> <code>recall(query)</code> retrieves the top-k semantic matches <i>among rows the caller owns</i>, then follows each hit&rsquo;s affiliated edges one hop and appends linked rows the caller also owns, marked <code>via_affiliated</code>. A single recall therefore returns an event&rsquo;s scattered pieces together &mdash; in the 80-tick run every one of the 51 recalls returned expanded context (&asymp;28 linked memories per call). Expansion is deliberately uncapped; its cost is measured in &sect;5.2.</p>
<p><b>Cost placement.</b> The design pays at write time (one atomization call when a deposit is compound, one judge call when candidates pass the pre-filter) to keep the store small and structured; reads add only vector lookups. &sect;5.2&rsquo;s latency instrumentation quantifies both sides against the baselines.</p>

<h3>3.5 &nbsp;Query-addressed operations and the design rule</h3>
<p>No memory operation takes a raw id. <code>forget</code>, <code>revise_memory</code>, and the affiliation operations address a memory by a natural-language query that the kernel resolves to the caller&rsquo;s best-matching owned row, so owner-scoping is enforced at resolution and there is no id for an agent to mishandle. The design responds to a robust behavioral finding: LLM agents never thread opaque ids across turns &mdash; in earlier runs every id-based operation had &asymp;0 uses. Query addressing removes that interface barrier; the observation that agents <i>still</i> issue zero discretionary memory-management calls (&sect;5.6) is what elevates &ldquo;structure must live inside <code>remember</code>/<code>recall</code>&rdquo; from an implementation choice to the framework&rsquo;s central design rule.</p>

<h2><span class="n">4</span> Experimental Setup</h2>

<h3>4.1 &nbsp;Scenarios</h3>
<p>三国演义 chapters 1&ndash;40 are sedimented onto 191 canonical characters (33 active at the boundary, the rest archived as dead; ~6,000 consensus events). All four backends then run the <i>same</i> 80-tick simulation &mdash; same scenario file, same action repertoire, same model (<code>gpt-5-mini</code>; embeddings <code>text-embedding-3-small</code>) &mdash; in four checkpointed 20-tick stages.</p>
<p>To test that the mechanisms are not an artifact of one fictional world, the second scenario is <b>real-world</b>: a timeline of the Russia&ndash;Ukraine conflict sedimented through 2026-07 (1,533 events over 170 entities). Real-world boundary semantics replace the novel&rsquo;s: a figure is archived if, by the boundary, they are dead <i>or out of the conflict&rsquo;s stage</i> (out of office, dismissed, disbanded), with placements grounded in the timeline or, failing that, the person&rsquo;s workplace/role (final cast: 47 active, 14 archived, manually verified). All four backends run the same 40-tick simulation under the identical fairness protocol.</p>

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
<li><b>Continuation quality</b> (LLM-judged, mean&plusmn;std over 3 scorings of the sim transcript): <i>grounding</i> &mdash; the fraction of the sim&rsquo;s own events consistent with the canon; <i>trajectory</i> &mdash; agreement of character arcs with reference arcs extracted from each world&rsquo;s held-out continuation (三国: chapters 41&ndash;60; Russia&ndash;Ukraine: the timeline beyond the 2024-04 boundary); <i>narrative</i> &mdash; judged coherence/drama/fidelity (1&ndash;5). The verbose Russia&ndash;Ukraine transcripts are compacted to the judge&rsquo;s context window (messages truncated to 280 chars, lines sampled evenly when needed); 三国 fits untruncated.</li>
<li><b>Operation latency</b> (&sect;5.2): per-call wall-clock time of <code>remember</code>/<code>recall</code>, timed in the kernel around the backend call so each mechanism&rsquo;s internal cost (equivalence judging, importance scoring, auto-expansion) falls inside the window. Ticks 61&ndash;80 are instrumented live; ticks 1&ndash;60 are measured by replaying each stage&rsquo;s logged operations against the store state the stage started from (checkpoint-exact for stages 2&ndash;3; the first stage&rsquo;s GA/G-Memory replay stores lack prime by-products, &asymp;3&ndash;5% of rows).</li>
<li><b>Three-layer alignment</b> (&sect;5.4): relations between the interaction graph, the affiliation graph, and the ownership relation.</li>
</ul>

<h2><span class="n">5</span> Results</h2>

<h3>5.1 &nbsp;Footprint and structure</h3>
<p>At equal granularity, consensus writes the fewest sim memories in both worlds (三国: {C['sim_new']} vs {GA['sim_new']}&ndash;{CO['sim_new']}; Russia&ndash;Ukraine: {RUC['sim_new']} vs {RU['collaborative']['sim_new']}&ndash;{RU['generative_agents']['sim_new']}) because merging folds witnesses together &mdash; and it is the only backend whose memories acquire structure: {C['sh_pct']}% become shared and {C['aff_pct']}% become linked, against 0% for every baseline.</p>
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
</tbody></table></div>

<h4>5.1.1 &nbsp;三国演义</h4>
<figure class="two">
  <img src="{IMG['simfoot']}" alt="Sim footprint">
  <img src="{IMG['structure']}" alt="Memory structure">
  <figcaption><b>Figure 2. Footprint and structure &mdash; 三国演义 (80 ticks).</b> Left: entries written by each backend under identical atomization; consensus is lowest because equivalent records from different witnesses merge into one. Right: percentage of each backend&rsquo;s sim memories that are shared (multi-owner) and linked (affiliated); both properties exist only under consensus &mdash; per-agent stores have nothing to merge or link across.</figcaption>
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
  <figcaption><b>Figure 3. Footprint and structure &mdash; Russia&ndash;Ukraine (40 ticks).</b> Same panels as Figure 2: entries written under identical atomization (left) and the share of each backend&rsquo;s sim memories that are shared and linked (right).</figcaption>
</figure>
<p><b>Discussion.</b> The same two readings hold at one eighth the horizon: the 19&ndash;30% footprint gap is again exactly the number of equivalence-judge folds, and the structural columns remain all-or-nothing &mdash; 0% for every per-agent baseline. What is new is the real-world flavor of the folds: equivalence merges a <i>person&rsquo;s</i> record into their <i>institution&rsquo;s</i> &mdash; the same mechanism that fuses two officers&rsquo; views of one battle fuses a spokesperson&rsquo;s statement with its organization&rsquo;s record of it.</p>
<p>Merged records again pair one event seen from two sides &mdash; characteristically a person and their institution:</p>
<div class="quote"><b>owners = [guterres, un]</b> &nbsp;&ldquo;Ant&oacute;nio Guterres at UN Headquarters in New York asked the United Nations to assemble a mediation team comprising DPA, OCHA, WFP, UN Political Affairs, and UN Legal to support renewal of the Black Sea grain agreement.&rdquo;<br>
<b>owners = [podolyak, ukrainian_government]</b> &nbsp;&ldquo;Mykhailo Podolyak reported that overnight Russian drone strikes struck Dnipropetrovsk Oblast.&rdquo;<br>
<b>owners = [kremlin, sobyanin]</b> &nbsp;&ldquo;Moscow Mayor Sergey Sobyanin requested authorization to release public instructions to Moscow residents.&rdquo;</div>


<h3>5.2 &nbsp;Growth and operation latency</h3>
<p>The footprint gap of Table 1 accumulates tick by tick, and its price is paid at write time. We show both sides for each scenario.</p>

<h4>5.2.1 &nbsp;三国演义</h4>
<figure class="two">
  <img src="{IMG['gtotal']}" alt="System memory growth per tick">
  <img src="{IMG['gagents']}" alt="Per-agent memory growth per tick">
  <figcaption><b>Figure 4. Memory growth &mdash; 三国演义 (80 ticks).</b> Left: cumulative sim-generated entries per tick for all four backends (reconstructed from each entry&rsquo;s creation tick under the same sim-only accounting as Table 1) &mdash; consensus stays lowest throughout and the gap widens with horizon, the per-tick view of the merge folding witnesses together. Right: per-agent owned memories per tick in the consensus run (top 6 agents labeled; the rest gray) &mdash; memory concentrates on the characters carrying the active plotlines (徐庶 leads with 132), while merges let one event&rsquo;s record count toward every witness&rsquo;s curve.</figcaption>
</figure>
<p><b>Discussion.</b> The system-level curves separate almost from the start and diverge steadily &mdash; the merge saves entries at a roughly constant <i>rate</i>, so its absolute savings compound with horizon rather than saturating; there is no sign of the gap closing by tick 80. The per-agent curves show the same mechanism from the individual&rsquo;s side: growth is stair-stepped (a burst when a character is at the center of a plotline, plateaus when off-stage), and the ranking tracks narrative centrality rather than raw talkativeness &mdash; 徐庶 leads because the 徐庶-recruitment arc dominates the middle game, and every merge credits a shared event to all of its witnesses&rsquo; curves at once.</p>

<figure>
  <img src="{IMG['latency']}" alt="Memory-operation latency vs tick">
  <figcaption><b>Figure 5. Memory-operation latency &mdash; 三国演义 (80 ticks).</b> Mean wall-clock seconds per <code>remember</code> (left) and <code>recall</code> (right) call, 5-tick bins, all four backends. Ticks 61&ndash;80 are instrumented live in the kernel; ticks 1&ndash;60 are measured by replaying each stage&rsquo;s logged operations (same agent, text/query, and order) against the exact store state that stage started from &mdash; a measurement of the same workload, not a synthesis (dotted line marks the boundary; first-stage GA/G-Memory replay stores lack their prime by-products, &asymp;3&ndash;5% of rows).</figcaption>
</figure>
<p><b>Discussion.</b> The two panels show where each design pays. <i>Writes are LLM-bound:</i> every backend pays the shared atomization call, on top of which Generative-Agents adds a per-atom importance call (the most expensive line, 35&ndash;75s) and consensus adds the equivalence judge (26&ndash;57s), while G-Memory and collaborative write for 10&ndash;25s with no per-deposit reasoning beyond atomization. <i>Reads are vector-bound and cheap everywhere</i> (&le;1.4s), and &mdash; notably &mdash; consensus recall is the <b>cheapest</b> of the four (&asymp;0.35s) despite returning &asymp;28 additional linked memories per call: auto-expansion is plain row lookup, whereas G-Memory&rsquo;s bi-level retrieval pays for graph traversal with extra vector queries (0.7&ndash;1.1s). Neither panel trends upward over 80 ticks: at this scale, store growth (&asymp;7k&ndash;22k rows) does not yet move per-call latency, so the consensus premium is a roughly constant per-write tax &mdash; the price of P1&rsquo;s deduplication &mdash; paid where agents are least latency-sensitive.</p>

<h4>5.2.2 &nbsp;Russia&ndash;Ukraine</h4>
<figure>
  <img src="{IMG['ru_growth']}" alt="RU memory growth">
  <figcaption><b>Figure 6. Memory growth &mdash; Russia&ndash;Ukraine (40 ticks).</b> Left: cumulative sim-generated entries per tick for all four backends under the same sim-only accounting as Table 1. Right: per-agent owned memories per tick in the consensus run (top agents labeled; the rest gray).</figcaption>
</figure>
<figure>
  <img src="{IMG['ru_latency']}" alt="RU memory-operation latency">
  <figcaption><b>Figure 7. Memory-operation latency &mdash; Russia&ndash;Ukraine (40 ticks).</b> Mean wall-clock seconds per <code>remember</code> (left) and <code>recall</code> (right) call, 2-tick bins, all four backends; every tick is instrumented live in the kernel.</figcaption>
</figure>
<p><b>Discussion.</b> Both figures replay the 三国 dynamics at a shorter horizon. The system curves separate from tick ~3 with consensus lowest and the gap widening, and per-agent growth again concentrates on the situation&rsquo;s protagonists. The latency ordering of Figure 5 reproduces: writes are LLM-bound (Generative-Agents&rsquo; per-atom importance calls most expensive, consensus paying the equivalence-judge tax), while reads are vector-bound and sub-second for all four backends, with consensus recall cheapest despite auto-expansion.</p>

<h3>5.3 &nbsp;Continuation quality</h3>
<p>Compression does not cost judged quality in either world. In 三国, consensus scores highest on narrative and is competitive elsewhere; in Russia&ndash;Ukraine all four backends land within overlapping error bars on every metric, with consensus tied-best on grounding and trajectory. The structural gaps of &sect;5.1 do not translate into behavioral penalties.</p>

<h4>5.3.1 &nbsp;三国演义</h4>
<figure>
  <img src="{IMG['quality']}" alt="Continuation quality comparison">
  <figcaption><b>Figure 8. Continuation quality &mdash; 三国演义 (40-tick checkpoint).</b> Grounding (fraction of the sim&rsquo;s own events judged canon-consistent), trajectory (agreement of character arcs with reference arcs from held-out chapters 41&ndash;60), and narrative (judged coherence/drama/fidelity, 1&ndash;5), scored at the 40-tick checkpoint of the same continuously-resumed runs; bars are means over 3 independent LLM scorings, whiskers &plusmn;1 std. Consensus scores highest on narrative and is competitive on trajectory; grounding sits mid-pack (GA/collaborative slightly higher).</figcaption>
</figure>
<p><b>Discussion.</b> The quality profile is consistent with what compression should and should not affect. Narrative coherence benefits from consensus (4.25, the clear leader): agents recalling one shared record of an event act on consistent premises, where baseline agents can act on N drifting paraphrases of it. Trajectory sits in the pack (0.68 vs 0.59&ndash;0.72): arc-following depends mostly on the persona and goal machinery all backends share. Grounding is mid-pack (0.86 vs 0.83&ndash;0.92, overlapping error bars): merging keeps the <i>shorter</i> of two equivalent texts, which occasionally discards a viewpoint detail a canon-consistency judge rewards. None of the differences approach the structural gaps of Figure 2 &mdash; the mechanisms separate on architecture, not on judged behavior.</p>

<h4>5.3.2 &nbsp;Russia&ndash;Ukraine</h4>
<figure>
  <img src="{IMG['ru_quality']}" alt="RU continuation quality comparison">
  <figcaption><b>Figure 9. Continuation quality &mdash; Russia&ndash;Ukraine (40 ticks).</b> Same protocol as Figure 8 at the same horizon: grounding judges each sim event against the real conflict&rsquo;s world (real entities, correct roles/allegiances, plausible dynamics), trajectory compares ten principals&rsquo; arcs against arcs extracted from the held-out timeline (2024-05 onward), narrative is the same 4-dimension rubric; bars are means over 3 independent LLM scorings, whiskers &plusmn;1 std.</figcaption>
</figure>
<p><b>Discussion.</b> The real-world replication is a wash &mdash; which is the point. Grounding is uniformly high ({min(QR[k]['agg']['grnd']['mean'] for k in QR):.2f}&ndash;{max(QR[k]['agg']['grnd']['mean'] for k in QR):.2f}: institutional actors reciting real capabilities rarely fabricate), trajectory is tied within error bars ({QR['consensus']['agg']['traj']['mean']:.2f} for consensus vs {min(QR[k]['agg']['traj']['mean'] for k in QR if k!='consensus'):.2f}&ndash;{max(QR[k]['agg']['traj']['mean'] for k in QR if k!='consensus'):.2f}), and narrative spreads {QR['g_memory']['agg']['narr']['mean']:.2f}&ndash;{QR['generative_agents']['agg']['narr']['mean']:.2f} with overlapping whiskers and no stable leader across scorings. As in 三国, the mechanisms separate on architecture (Figure 3), not on judged behavior: consensus deduplicates {RUC['sim_new']} entries against the baselines&rsquo; {RU['collaborative']['sim_new']}&ndash;{RU['generative_agents']['sim_new']} and builds all the structure &mdash; while giving none of it back in quality.</p>

<h3>5.4 &nbsp;Case study: three graphs over each world</h3>
<p>Each world&rsquo;s consensus run induces the same three graphs: the <b>interaction graph</b> (who talks to whom), the <b>affiliation graph</b> (which memories are linked), and the <b>ownership relation</b> (who owns which memories). For each scenario we show the three layers, then all three in one view, then quantify their pairwise alignment.</p>

<h4>5.4.1 &nbsp;三国演义</h4>

<h5>The three layers <span style="font-family:var(--sans);font-size:12px;color:var(--faint);font-weight:400">&mdash; interactive: drag to pan, scroll to zoom, hover for details, drag nodes to rearrange</span></h5>
<figure>
  <div class="ig" id="ig-interaction" style="height:520px"></div>
  <figcaption><b>Figure 9a. The interaction graph (interactive) &mdash; 三国演义.</b> Nodes are the complete active-character roster (silent characters parked on the bottom row); edge width is conversation frequency; colors are detected communities, which recover the canonical factions without being told about them. Hover a character for its name, community, and conversation volume; click to highlight its neighbourhood.</figcaption>
</figure>
<figure>
  <div class="ig" id="ig-affiliation" style="height:600px"></div>
  <figcaption><b>Figure 9b. The full memory-affiliation graph (interactive) &mdash; 三国演义.</b> Every sim-generated memory is a node ({R['MO']['link_n']} affiliated edges; components colored, singletons gray; shared multi-owner memories drawn larger with a red ring). <b>Hover any node to read the memory&rsquo;s full text and its owners</b> &mdash; each cluster is one plotline&rsquo;s linked pieces, assembled bottom-up by auto-affiliation and merging.</figcaption>
</figure>
<figure>
  <div class="ig" id="ig-heatmap" style="height:620px"></div>
  <figcaption><b>Figure 10. The ownership layer (interactive) &mdash; 三国演义.</b> Pairwise co-owned memory counts over the complete roster, ordered by interaction community. Hover a cell for the pair and its count. Non-zero cells concentrate in the diagonal blocks &mdash; agents share memories with their own faction &mdash; and each strong cell corresponds to consensus merges of jointly experienced events.</figcaption>
</figure>

<h5>All three layers in one view</h5>
<figure>
  <div class="ig" id="ig-trilayer" style="height:560px"></div>
  <figcaption><b>Figure 11. All three layers in one view (interactive) &mdash; 三国演义.</b> Agents on the top row (circles = characters, squares = passive memory owners) with conversation arcs above (blue; width = frequency); memories on the bottom row with affiliation arcs below (green when the linked memories share a witness, gray when disjoint); ownership as vertical lines, red when the memory is shared. <b>Hover an agent</b> to isolate its conversations and owned memories; <b>hover a memory</b> (&starf; = merged multi-owner) to read its text and see its links. Shared structure sits where conversation sits.</figcaption>
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
  <figcaption><b>Figure 12. Each pairwise relation as a with/without pair of distributions &mdash; 三国演义</b> (columns share x and y axes; log density so tails read against the mass at zero; top row = pairs with the relation, bottom = without). Left: owned-memory-set Jaccard for talking vs non-talking agent pairs. Middle: owner-set Jaccard for memory pairs with vs without an affiliated edge. Right: cross-set affiliated-edge counts for talking vs non-talking agent pairs. In all three, the without-group concentrates at zero and the with-group carries the entire tail.</figcaption>
</figure>
<p><b>Synthesis.</b> The three alignments are not three separate facts but one: the consensus mechanisms transcribe the story&rsquo;s social structure into the memory substrate. Conversations are where shared experience happens, so merges (ownership overlap) land on talking pairs; deposits narrate the conversation an agent just had, so affiliation clusters coincide with events and their witnesses; and cross-agent links therefore run along conversation edges. In a per-agent store all three relations are identically zero &mdash; the substrate cannot express them &mdash; which is why the case study is run on the consensus backend alone.</p>

<h4>5.4.2 &nbsp;Russia&ndash;Ukraine</h4>
<h5>The three layers <span style="font-family:var(--sans);font-size:12px;color:var(--faint);font-weight:400">&mdash; interactive: drag to pan, scroll to zoom, hover for details, drag nodes to rearrange</span></h5>
<figure>
  <div class="ig" id="ig-ru-interaction" style="height:480px"></div>
  <figcaption><b>Figure 13a. The interaction graph (interactive) &mdash; Russia&ndash;Ukraine.</b> 65 entities; community detection recovers the conflict&rsquo;s blocs &mdash; the Kyiv government cluster, the Moscow cluster, and the international mediators &mdash; without being told about them.</figcaption>
</figure>
<figure>
  <div class="ig" id="ig-ru-affiliation" style="height:520px"></div>
  <figcaption><b>Figure 13b. The full memory-affiliation graph (interactive) &mdash; Russia&ndash;Ukraine.</b> {RUC['sim_new']} sim memories, {RUR['MO']['link_n']} affiliated edges; hover any node to read the memory and its owners. Clusters are single storylines (a strike wave, a negotiation) assembled by auto-affiliation.</figcaption>
</figure>
<figure>
  <div class="ig" id="ig-ru-heatmap" style="height:560px"></div>
  <figcaption><b>Figure 13. The ownership layer (interactive) &mdash; Russia&ndash;Ukraine.</b> Pairwise co-owned memory counts over the Russia&ndash;Ukraine roster, ordered by interaction community. Hover a cell for the pair and its count. As in Figure 10, non-zero cells sit on pairs that jointly experienced events &mdash; here the strongest cells are spokesperson&harr;institution pairs, the real-world counterpart of faction comrades.</figcaption>
</figure>
<h5>All three layers in one view</h5>
<figure>
  <div class="ig" id="ig-ru-trilayer" style="height:520px"></div>
  <figcaption><b>Figure 14. All three layers in one view (interactive) &mdash; Russia&ndash;Ukraine.</b> Conversations above, ownership between, affiliation below; merged memories (&starf;) hang between the parties that share them.</figcaption>
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
  <figcaption><b>Figure 15. Each pairwise relation as a with/without pair of distributions &mdash; Russia&ndash;Ukraine</b> (same format as Figure 12). The structural signature transfers intact to a real-world scenario at one eighth the horizon.</figcaption>
</figure>

<h3>5.5 &nbsp;Structure compounds with horizon</h3>
<p>Shared and linked structure is not a transient: across the 20/40/60-tick checkpoints, sim memories grow roughly linearly while shared memories and affiliated edges grow with them &mdash; the merge finds more cross-witness events as the story densifies.</p>

<h4>5.5.1 &nbsp;三国演义</h4>
<figure>
  <img src="{IMG['growth']}" alt="Growth across horizon">
  <figcaption><b>Figure 16. Consensus structure across the horizon &mdash; 三国演义.</b> Sim-memory count (left), shared multi-owner memories (middle), and affiliated edges (right) at the 20/40/60/80-tick checkpoints of the same continuously-resumed run. All three grow super-linearly in usefulness even where counts grow linearly: each new shared memory raises the chance that a future deposit finds a merge partner, and each new edge widens what a single auto-expanding recall can surface.</figcaption>
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

<p class="foot">Agentsensus &middot; 三国演义 60-tick, three resumed 20-tick stages &middot; chat gpt-5-mini, embeddings text-embedding-3-small &middot; simulation-only accounting under uniform atomization &middot; structural counts deterministic; quality metrics mean&plusmn;std over 3 LLM scorings &middot; data: <code>runs/g20_* ... g80_*</code>.</p>

</div>
"""

JS = r"""
<script>
(function(){
const G = __GRAPHS__;
const GRU = __GRAPHS_RU__;
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
})();
</script>
"""

out = "docs/index.html"
with open(out, "w") as f:
    f.write("<title>Agentsensus &mdash; Consensus-Compressed Shared Memory</title>\n" + HTML
            + JS.replace("__GRAPHS__", GRAPHS_JSON).replace("__GRAPHS_RU__", GRAPHS_RU_JSON))
print("wrote", out, len(HTML) + len(JS) + len(GRAPHS_JSON), "bytes")
