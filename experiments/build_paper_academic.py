"""Build the full academic-format paper (60-tick data).
Reads: runs/paper_stats_g80.json, runs/results_g60.json, figures in
runs/paper_figs_g80/ + runs/g80full_consensus/case_study/.
"""
import base64, os, json, re
os.chdir("/Users/ypan12/git_repo/bookworld_paper/agentsensus")

FIGS = {
    "growth": "runs/paper_figs_g80/growth_q.png",
    "relpanels": "runs/g80full_consensus/case_study/relationship_panels_q.png",
    "gtotal": "runs/paper_figs_g80/growth_total_q.png",
    "gagents": "runs/paper_figs_g80/growth_agents_q.png",
    "quality": "runs/paper_figs_g80/quality_q.png",
    "arch": "runs/paper_figs_g80/architecture_q.png",
    "latency": "runs/paper_figs_g80/latency_q.png",
    "ru_growth": "runs/paper_figs_ru40/growth_q.png",
    "ru_latency": "runs/paper_figs_ru40/latency_q.png",
    "ru_relpanels": "runs/ru40full_consensus/case_study/relationship_panels_q.png",
    "ru_quality": "runs/paper_figs_ru40/quality_q.png",
    "rc_quality": "runs/paper_figs_rc80/quality_q.png",
    "hl_quality": "runs/paper_figs_hl40/quality_q.png",
    "rc_growth": "runs/paper_figs_rc80/growth_q.png",
    "rc_latency": "runs/paper_figs_rc80/latency_q.png",
    "rc_relpanels": "runs/rc80full_consensus/case_study/relationship_panels_q.png",
    "hl_growth": "runs/paper_figs_hl40/growth_q.png",
    "hl_latency": "runs/paper_figs_hl40/latency_q.png",
    "struct_all": "runs/paper_figs_all/structure_all_q.png",
    "ablation": "runs/paper_figs_ablation/ablation_q.png",
    "hl_relpanels": "runs/hl40full_consensus/case_study/relationship_panels_q.png",
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
HL = _scrub(json.load(open("runs/paper_stats_hl40.json", encoding="utf-8")))
HLC = HL["consensus"]; HLR = HL["relations"]; HLE = HL["auto_expand"]
hl_mex = HL["merge_examples"]

# Store size at the end of each run (footprint.entries), so the scale table can
# show what each mechanism carries out of sedimentation as well as what the
# simulation added: sediment = total - sim.
BACKENDS = ["consensus", "generative_agents", "g_memory", "collaborative"]
TOTAL = {}
for _pref in ("g80", "ru40", "rc80", "hl40"):
    for _b in BACKENDS:
        with open(f"runs/{_pref}_{_b}/result.json", encoding="utf-8") as _f:
            TOTAL[(_pref, _b)] = json.load(_f)["footprint"]["entries"]


# English renderings of the Chinese memory records quoted as merge examples.
# Keyed by the stored text; a record with no entry is shown as-is (the
# Russia-Ukraine and Hamlet stores are largely English already).
MERGE_GLOSS = {
    "夏侯渊率三百轻骑分三路从许昌出城侦察。":
        "Xiahou Yuan led three hundred light cavalry out of Xuchang on reconnaissance, in three columns.",
    "乐进督管许昌的粮草与军需。":
        "Yue Jin was put in charge of Xuchang&rsquo;s grain and military supplies.",
    "张辽被任为许昌防务的总摄指挥。":
        "Zhang Liao was appointed overall commander of Xuchang&rsquo;s defences.",
    "贾母只留下贾宝玉、林黛玉与薛宝钗到贾母身边相见。":
        "Grandmother Jia kept only Jia Baoyu, Lin Daiyu and Xue Baochai by her side to receive them.",
    "贾政召唤贾宝玉到贾政的书房。":
        "Jia Zheng summoned Jia Baoyu to his study.",
    "平儿在门廊与院外寻找贾宝玉。":
        "Ping&rsquo;er searched the gallery and the courtyard outside for Jia Baoyu.",
    "在厄耳锡诺城堡，吉尔登斯特恩与罗森克兰茨决定分头监视哈姆雷特。":
        "At Elsinore, Guildenstern and Rosencrantz decided to watch Hamlet separately.",
}


def quote_memory(text):
    """Render a stored memory for the paper: English, with the original after it
    when the record itself is not in English."""
    en = MERGE_GLOSS.get(text)
    if en is None:
        return f"&ldquo;{text}&rdquo;"
    return f"&ldquo;{en}&rdquo; <span class=\"orig\">({text})</span>"

def scale_rows(pref, stats):
    """Table rows for one world: sediment / sim / total."""
    out = []
    for b, label in zip(BACKENDS, ("consensus", "generative-agents", "g-memory", "collaborative")):
        st = stats[b]
        total = TOTAL[(pref, b)]
        sediment = total - st["sim_new"]
        best = ' class="best"' if b == "consensus" else ""
        hi = ' class="hi"' if b == "consensus" else ""
        out.append(
            f'<tr{hi}><td>{label}</td><td{best}>{sediment:,}</td><td{best}>{st["sim_new"]:,}</td>'
            f'<td>{total:,}</td></tr>'
        )
    return "\n".join(out)

# Continuation quality, one file per world, all scored off the rendered
# screenplays of the full runs (experiments/score_all.py).
Q = json.load(open("runs/results_g80.json", encoding="utf-8"))    # Three Kingdoms, 80 rounds
QC = json.load(open("runs/results_rc80.json", encoding="utf-8"))  # Red Chamber, 80 rounds
QR = json.load(open("runs/results_ru40.json", encoding="utf-8"))  # Russia-Ukraine, 40 rounds
QH = json.load(open("runs/results_hl40.json", encoding="utf-8"))  # Hamlet, 40 rounds
QUAL = {"Three Kingdoms": Q, "Red Chamber": QC, "Russia-Ukraine": QR, "Hamlet": QH}
# how often an agent acted with nothing on its goal stack, per world/backend
# (experiments/goal_timeline.py --stats); the goal-pursuit score is only
# meaningful next to it
# One-factor-at-a-time ablation of the consensus backend (三国, 40 rounds),
# experiments/score_ablation.py
ABL = json.load(open("runs/ablation_results.json", encoding="utf-8"))
ABLFP = {c: json.load(open(f"runs/abl_{c}/result.json", encoding="utf-8"))["footprint"]
         for c in ABL}


def ablation_rows():
    """Table 3, live from the ablation runs."""
    label = {"on_fifo": ("on", "fifo <i>(as published)</i>"),
             "on_relevance": ("on", "relevance"), "on_hybrid": ("on", "hybrid"),
             "off_fifo": ("<b>off</b>", "fifo")}
    rows = []
    for c, (m, k) in label.items():
        v, fp = ABL[c], ABLFP[c]
        hi = ' class="hi"' if c == "on_fifo" else ""
        rows.append(f"<tr{hi}><td>{m}</td><td>{k}</td><td>{fp['entries']:,}</td>"
                    f"<td>{v['sim_new']}</td><td>{v['sh_pct']}%</td><td>{v['aff_pct']}%</td>"
                    f"<td>{v['max_owners']}</td>"
                    f"<td>{v['gr_m']:.2f}&plusmn;{v['gr_s']:.2f}</td>"
                    f"<td>{v['wall_min']:.0f} min</td></tr>")
    return "\n".join(rows)


GSTACK = json.load(open("runs/goal_stack_stats.json", encoding="utf-8"))
_GPCT = [b["goalless_pct"] for w in GSTACK.values() for b in w.values()]
_GOALS = [q[k]["agg"]["goal"]["mean"] for q in QUAL.values() for k in q]


def _best(world_q, key):
    """Backend with the highest mean on one metric, and by how much."""
    order = sorted(world_q, key=lambda k: world_q[k]["agg"][key]["mean"], reverse=True)
    top, second = order[0], order[1]
    return top, world_q[top]["agg"][key]["mean"], world_q[second]["agg"][key]["mean"]


def quality_ledger():
    """How consensus actually does across the twelve world-metric cells."""
    leads, gaps01, gaps15 = 0, [], []
    for q in QUAL.values():
        for key in ("grnd", "traj", "narr", "goal"):
            top, hi, _ = _best(q, key)
            if top == "consensus":
                leads += 1
            else:
                (gaps15 if key == "narr" else gaps01).append(
                    hi - q["consensus"]["agg"][key]["mean"])
    n = sum(len(("grnd", "traj", "narr", "goal")) for _ in QUAL)
    word = {3: "three", 4: "four", 5: "five", 6: "six", 12: "twelve", 16: "sixteen"}
    return (f"{word.get(leads, leads)} of {word.get(n, n)}",
            f"{min(gaps01):.2f}&ndash;{max(gaps01):.2f}",
            f"{min(gaps15):.2f}&ndash;{max(gaps15):.2f}",
            _won_where())


def _won_where():
    """\"narrative in Three Kingdoms, trajectory in ...\" -- written from the data."""
    metric = {"grnd": "grounding", "traj": "trajectory", "narr": "narrative",
              "goal": "goal pursuit"}
    won = {}
    for world, q in QUAL.items():
        for key in ("grnd", "traj", "narr", "goal"):
            if _best(q, key)[0] == "consensus":
                won.setdefault(metric[key], []).append(world)
    parts = []
    for m, worlds in won.items():
        names = (worlds[0] if len(worlds) == 1
                 else " and ".join([", ".join(worlds[:-1]), worlds[-1]]))
        parts.append(f"{m} in {names}")
    return "; ".join(parts) if parts else "nothing"


def wins_table():
    """Who leads each metric in each world -- the honest summary of 5.3."""
    lbl = {"consensus": "consensus", "generative_agents": "Gen.&nbsp;Agents",
           "g_memory": "G-Memory", "collaborative": "collaborative"}
    rows = []
    for i, (world, q) in enumerate(QUAL.items()):
        cells = []
        for key in ("grnd", "traj", "narr", "goal"):
            top, hi, second = _best(q, key)
            c = q["consensus"]["agg"][key]["mean"]
            cells.append(f"{lbl[top]} {hi:.2f}" + ("" if top == "consensus"
                                                   else f" (consensus {c:.2f})"))
        hi_cls = ' class="hi"' if i == 0 else ""
        rows.append(f"<tr{hi_cls}><td>{world}</td>" + "".join(f"<td>{c}</td>" for c in cells) + "</tr>")
    return "\n".join(rows)

# Two appendix tables are counted out of whole event logs. The logs are not
# carried in the repository, so the counts are cached by
# experiments/cache_derived.py; when the logs ARE present they win, so the
# table can never drift from a rerun that forgot to refresh the cache.
DERIVED = (json.load(open("runs/derived_tables.json", encoding="utf-8"))
           if os.path.exists("runs/derived_tables.json") else {})

# Action census per world, read from the runs themselves so the appendix table
# cannot drift from the logs.
_ACTS = ["say", "read_thread", "observe", "move", "act_on", "read", "think",
         "conclude", "push_goal", "pop_goal", "replace_goal", "update_status",
         "remember", "recall", "wait"]
_NEVER = ["gesture", "noop", "remove_status", "forget", "revise_memory",
          "add_affiliated", "remove_affiliated", "set_affiliated", "get_affiliated"]


def _action_counts(pref):
    per = {b: {} for b in BACKENDS}
    cached = DERIVED.get("actions", {}).get(pref, {})
    for b in BACKENDS:
        path = f"runs/{pref}_{b}/events.jsonl"
        if not os.path.exists(path):
            per[b] = dict(cached.get(b, {}))
            continue
        with open(path, encoding="utf-8") as f:
            for line in f:
                e = json.loads(line)
                if e.get("kind") == "action":
                    n = (e.get("action") or {}).get("name")
                    per[b][n] = per[b].get(n, 0) + 1
    return per


def action_rows(pref, label, rounds):
    per = _action_counts(pref)
    rows = [f'<tr class="grp"><td colspan="5">{label} &mdash; {rounds}</td></tr>']
    for a in _ACTS:
        vals = [per[b].get(a, 0) for b in BACKENDS]
        if not sum(vals):
            continue
        hi = ' class="hi"' if a in ("remember", "recall") else ""
        rows.append(f'<tr{hi}><td><code>{a}</code></td>'
                    + "".join(f"<td>{v}</td>" for v in vals) + "</tr>")
    return "\n".join(rows)

def scene_grid(world="hamlet"):
    """The spacetime grid figure, generated by experiments/scene_grid_fig.py."""
    path = f"runs/scene_grid_{world}.svg"
    return open(path, encoding="utf-8").read() if os.path.exists(path) else ""


def grid_figure(world, number, title, note):
    """One world's spacetime grid, captioned with what it is made of."""
    from experiments.scene_grid_fig import stats
    svg = scene_grid(world)
    if not svg:
        return ""
    st = stats(world)
    return (f'<figure>\n{svg}\n<figcaption><b>Figure {number}. How the scenes were '
            f'cut &mdash; {title}.</b> Rounds {st["rounds"][0]}&ndash;{st["rounds"][1]} '
            f'across {st["places"]} places, {st["beats"]} beats by {st["speakers"]} agents, '
            f'cut into the {st["scenes"]} outlined scenes; read as Figure&nbsp;30 &mdash; the '
            f'cells narrow as the run lengthens, so the whole run stays on one screen. '
            f'{note}</figcaption>\n</figure>')

SCREENPLAY_WORLDS = [("three_kingdoms", "Three Kingdoms 三国演义", "zh"),
                     ("red_chamber", "Red Chamber 红楼梦", "zh"),
                     ("russia_ukraine", "Russia&ndash;Ukraine", "en"),
                     ("hamlet", "Hamlet", "en")]


def _sp_chars(world, lang):
    for d in ("runs/screenplays", "runs/screenplays_prev"):
        p = f"{d}/{world}.{lang}.md"
        if os.path.exists(p):
            # characters, not bytes -- a Chinese screenplay is three bytes a character
            return f"{len(open(p, encoding='utf-8').read()) // 1000}k chars"
    return "&mdash;"


def screenplay_rows():
    """Table A5, live from the event logs the screenplays were cut from."""
    from experiments.scene_grid_fig import stats
    rows = []
    for i, (world, title, lang) in enumerate(SCREENPLAY_WORLDS):
        s = stats(world)
        src = "&mdash; (en)" if lang == "en" else f"{_sp_chars(world, 'zh')} (zh)"
        hi = ' class="hi"' if i == 0 else ""
        rows.append(f"<tr{hi}><td>{title}</td><td>{s['rounds'][0]}&ndash;{s['rounds'][1]}</td>"
                    f"<td>{s['scenes']}</td><td>{s['beats']}</td><td>{s['speakers']}</td>"
                    f"<td>{s['places']}</td><td>{_sp_chars(world, 'en')}</td><td>{src}</td></tr>")
    return "\n".join(rows)


def screenplay_span():
    """\"between twelve and sixty-two scenes\" -- kept honest as the runs change."""
    from experiments.scene_grid_fig import stats
    word = {12: "twelve", 41: "forty-one", 46: "forty-six", 48: "forty-eight",
            54: "fifty-four", 62: "sixty-two"}
    n = sorted(stats(w)["scenes"] for w, _, _ in SCREENPLAY_WORLDS)
    return f"{word.get(n[0], n[0])} and {word.get(n[-1], n[-1])}"


def _screenplay_scenes(path):
    """(header, body) per scene of a rendered screenplay.

    Falls back to runs/screenplays_prev/ so a world whose screenplay has not yet
    been regenerated under the current renderer still appears.
    """
    if not os.path.exists(path):
        path = path.replace("/screenplays/", "/screenplays_prev/")
    if not os.path.exists(path):
        return []
    text = open(path, encoding="utf-8").read()
    parts = re.split(r"(?m)^(## .*)$", text)
    out = []
    for i in range(1, len(parts), 2):
        head = parts[i].lstrip("# ").strip()
        body = parts[i + 1].strip() if i + 1 < len(parts) else ""
        out.append((head, body))
    return out


def _esc(t):
    return (t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def screenplay_block(world, title, note, bilingual):
    """A collapsible full screenplay; bilingual worlds interleave scene by scene."""
    en = _screenplay_scenes(f"runs/screenplays/{world}.en.md")
    zh = _screenplay_scenes(f"runs/screenplays/{world}.zh.md") if bilingual else []
    if not en and not zh:
        return ""
    scenes = []
    for i, (head, body) in enumerate(en or zh):
        block = f'<h5>{_esc(head)}</h5>\n<pre class="sp">{_esc(body)}</pre>'
        if bilingual and i < len(zh):
            block += f'<pre class="sp orig">{_esc(zh[i][1])}</pre>'
        scenes.append(block)
    n = len(scenes)
    return (f'<details class="spwrap"><summary><b>{title}</b> &mdash; {n} scenes, '
            f'consensus run{note}</summary>\n' + "\n".join(scenes) + "\n</details>")

def _slim_graphs(path):
    _G = json.loads(open(path, encoding="utf-8").read().replace("\ufffd", ""))
    # English renderings produced by experiments/translate_case_study.py: the
    # figures read in English, with the record's own text kept alongside.
    _tpath = os.path.join(os.path.dirname(path), "translations.json")
    _tr = json.load(open(_tpath, encoding="utf-8")) if os.path.exists(_tpath) else {}
    _texts, _names = _tr.get("texts", {}), _tr.get("agents", {})
    for _n in _G["affiliation"]["nodes"] + _G["trilayer"]["mems"]:
        _en = _texts.get(_n.get("text"))
        if _en:
            _n["en"] = _en
    for _k in ("interaction", "affiliation", "trilayer", "heatmap"):
        _G[_k]["names"] = _names
    _G["names"] = _names
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
GRAPHS_HL_JSON = _slim_graphs("runs/hl40full_consensus/case_study/graphs.json")

def cell(k, key):
    a = Q[k]["agg"][key]
    return f"{a['mean']:.2f}&thinsp;&plusmn;.{int(round(a['std']*100)):02d}"
def gn(k):
    return f"{Q[k]['agg']['grnd_n']:.0f}"

C = S["consensus"]; GA = S["generative_agents"]; GM = S["g_memory"]; CO = S["collaborative"]

# How much smaller the consensus store is than the closest baseline, per world:
# the abstract quotes the range rather than a hand-picked world.
_SAVE = sorted(round(100 * (1 - w["consensus"]["sim_new"] /
                            min(w[b]["sim_new"] for b in
                                ("generative_agents", "g_memory", "collaborative"))))
               for w in (S, RC, RU, HL))
abs_fewest = f"{_SAVE[0]}&ndash;{_SAVE[-1]}%"
_MORE = sorted(round(100 * (min(w[b]["sim_new"] for b in
                                ("generative_agents", "g_memory", "collaborative"))
                            / w["consensus"]["sim_new"] - 1))
               for w in (S, RC, RU, HL))
abs_fewest_inv = f"{_MORE[0]}&ndash;{_MORE[-1]}%"
_SH = sorted(w["consensus"]["sh_pct"] for w in (S, RC, RU, HL))
_AFF = sorted(w["consensus"]["aff_pct"] for w in (S, RC, RU, HL))
abs_shared = f"{_SH[0]}&ndash;{_SH[-1]}%"
abs_linked = f"{_AFF[0]}&ndash;{_AFF[-1]}%"
abs_witnesses = max(w["max_owners"] for w in (S, RC, RU, HL))
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
.spwrap{border:1px solid var(--line);border-radius:10px;padding:10px 14px;margin:14px 0;background:var(--card)}
.spwrap summary{font-family:var(--sans);font-size:14px;cursor:pointer;color:var(--muted)}
.spwrap h5{margin:18px 0 6px;font-size:13px;color:var(--accent)}
pre.sp{white-space:pre-wrap;font-family:var(--serif);font-size:14.5px;line-height:1.6;margin:0;color:var(--ink)}
pre.sp.orig{color:var(--muted);font-size:13.5px;margin-top:8px;padding-top:8px;border-top:1px dashed var(--line)}
.quote .orig,.orig{color:var(--faint);font-size:.94em}
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
  <span><b>Scenarios</b> Three Kingdoms (三国演义) (80 rounds, 33 active agents) &middot; Russia&ndash;Ukraine (40 rounds, 47 active) &middot; Red Chamber (红楼梦) (80 rounds, 34 active) &middot; Hamlet (40 rounds, 16 active)</span>
  <span><b>Checkpointing</b> every 20 rounds</span>
  <span><b>Model</b> gpt-5-mini</span>
</div>

<div class="abstract"><div class="h">Abstract</div>
<p>Multi-agent story-world simulations give every character a private memory stream, so one shared event is stored once per witness, its copies drift apart as agents paraphrase and summarize them, and nothing links a courier&rsquo;s report to the battle it describes. We present <b>Agentsensus</b>, a story-world simulation framework whose long-term memory is a single store in which <i>sharing is computed rather than assumed</i>. Each deposit is atomized into self-contained statements; a statement close to an existing one is put to an LLM equivalence judge and, if the two are equivalent, merged into one record whose <i>owner set</i> is the union of its witnesses. Statements split from one deposit are cross-linked, and recall expands one hop along those links. Ownership stays scoped &mdash; an agent recalls only what it owns &mdash; so compression never leaks knowledge between characters, and every mechanism runs inside <code>remember</code> and <code>recall</code>, the only two memory operations agents demonstrably use: across two models and four backends, discretionary memory management was invoked zero times. Across four worlds &mdash; two classical Chinese novels, <i>Hamlet</i>, and a real-world conflict timeline &mdash; run for 40 to 80 rounds against three per-agent memory baselines under an equal-granularity protocol, consensus writes {abs_fewest} fewer entries than the closest baseline and is the only backend whose memories become shared ({abs_shared} multi-owner, single records reaching {abs_witnesses} witnesses) and linked ({abs_linked}), at judged continuation quality indistinguishable from the baselines. The memory substrate alone recovers the story&rsquo;s social organization: agents who converse overlap in memory {ao_ratio:.0f}&times; more than those who do not, and cross-agent memory links run almost exclusively between conversing pairs.</p>
</div>

<h2><span class="n">1</span> Introduction</h2>
<p>A story-world simulation places dozens of LLM-driven characters in a world with places, objects and documents, and lets a narrative emerge from what they say and do to one another [1, 2]. Unlike a task-solving multi-agent system, where the team is judged on an answer it produces [10, 12, 13], such a world is judged on what it <i>accumulates</i>: who learned what, when, and from whom. Memory is therefore not a component of these systems but their substrate. It is also the component that scales worst. A novel-seeded world starts with thousands of canonical events already deposited, adds several hundred more per hundred rounds of simulation, and must serve retrieval to every character at every round.</p>

<p>The dominant memory design, established by Generative Agents [1] and inherited by most subsequent frameworks [2, 8], gives each character a private, append-only stream scored by recency, importance and relevance. This is faithful to individual cognition &mdash; people do remember separately &mdash; but as the substrate of a <i>shared</i> world it creates three structural problems, each of which worsens as the world grows:</p>
<ul class="body">
<li><b>P1 &mdash; Witness-multiplied redundancy.</b> Every shared experience is stored once per participant: a war council attended by ten officers produces ten near-identical records, and a novel-seeded world multiplies this by thousands of canonical events. Storage, embedding cost and retrieval-index size scale with the number of <i>witnesses</i> rather than the number of <i>events</i> &mdash; in our four testbeds the per-agent baselines carry {abs_fewest_inv} more entries than the consensus store for the same history.</li>
<li><b>P2 &mdash; Fragmented, divergence-prone world knowledge.</b> The same event exists as N independently-worded copies that drift further apart as agents paraphrase, summarize and reflect on them. No mechanism reconciles them, no record knows its counterparts exist, and nothing connects a courier&rsquo;s report to the battle it describes or the order it triggers. The connective tissue of the story exists nowhere in the memory substrate &mdash; only implicitly in the transcript &mdash; so retrieval returns one agent&rsquo;s partial, possibly stale view even when the collective already holds the full picture.</li>
<li><b>P3 &mdash; Memory management that agents never perform.</b> Stream designs expose maintenance operations &mdash; linking related records, revising stale ones, forgetting duplicates &mdash; and implicitly rely on agents to use them. Empirically they do not: across two models and all four backends we test, agents issued <i>zero</i> calls to every discretionary memory-management action, even with documentation, worked examples and an id-free interface (&sect;5.6). An architecture that depends on agent-side curation therefore never acquires structure in practice, however well the operations are designed.</li>
</ul>

<p><b>Our approach.</b> Agentsensus answers all three with one architectural commitment: <b>the world&rsquo;s memory is a single store, and sharing is computed, not assumed</b>. Memories stay owner-scoped &mdash; an agent recalls only what it owns, so a shared store is not a shared mind &mdash; but when two agents record the same event, an equivalence mechanism detects it and folds the records into one entry owned by both. This is deduplication with a semantic rather than lexical criterion, closer to record linkage [24] and semantic corpus deduplication [26] than to caching, and it addresses P1 together with the divergence half of P2. Pieces split from one compound deposit are automatically cross-linked, and recall expands one hop along those links into what the caller also owns, giving the store the connective tissue P2 demands without an agent ever building a graph. And because of P3, <i>every</i> mechanism runs inside <code>remember</code> and <code>recall</code> themselves &mdash; the two operations agents demonstrably do use &mdash; rather than being offered as curation the agents would have to remember to perform.</p>

<p><b>What we find.</b> We evaluate on four worlds chosen to differ in what a memory must hold: two classical Chinese novels (<i>Romance of the Three Kingdoms</i>, <i>Dream of the Red Chamber</i>), one English play (<i>Hamlet</i>), and one real-world conflict timeline (Russia&ndash;Ukraine) whose actors are institutions rather than people. Each runs 40&ndash;80 rounds against three faithful baseline reimplementations under an equal-granularity protocol that routes every backend&rsquo;s writes through the same atomizer, so entry counts are comparable and only the mechanism differs. Three findings hold across all four worlds. <i>Structure is exclusive to consensus</i>: it is the only backend whose memories become multi-owner ({abs_shared}) or linked ({abs_linked}); the baselines sit at exactly zero on both, by construction rather than by tuning. <i>Compression compounds with horizon</i>: sharing rises monotonically as a run is extended &mdash; 13%&rarr;20%&rarr;23%&rarr;24% in Red Chamber at rounds 10/40/60/80 &mdash; because later deposits meet a store that already holds their equivalents. <i>The graph is meaningful, not incidental</i>: agents who converse overlap in memory {ao_ratio:.0f}&times; more than agents who do not, and cross-agent memory links run almost exclusively between conversing pairs, so the social structure of the story can be read off the memory substrate alone.</p>

<p>Two findings are negative and we report them as such. Judged continuation quality does <i>not</i> separate the backends: over four worlds and four metrics, consensus leads {quality_ledger()[0]} cells and trails elsewhere by margins the size of the scoring noise (&sect;5.3). And goal-pursuit consistency saturates at {min(_GOALS):.2f}&ndash;{max(_GOALS):.2f} for every backend, because the agent loop keeps a goal on the stack almost always &mdash; a metric that certifies the loop rather than discriminating between memories. The case for consensus compression is that it buys structure and footprint at no measurable cost in behaviour, not that it writes better stories.</p>

<p><b>Contributions.</b></p>
<ul class="contrib">
<li>A story-world simulation framework with a deterministic round-barrier scheduler, passive environments and information carriers, kernel-held conversation threads with distance-delayed delivery, and full-system checkpoints enabling bit-for-bit resumption.</li>
<li>A <b>consensus-compressed shared memory</b>: self-contained atomization, semantic-prefilter plus LLM-judged equivalence merging with owner-set union, automatic affiliation of split pieces, and auto-expanding owner-scoped recall &mdash; all of it inside the two operations agents actually call.</li>
<li>An <b>equal-granularity, simulation-only evaluation protocol</b> against three faithful baseline reimplementations, isolating the memory mechanism from confounds of storage granularity and seeded content, applied to four worlds spanning two languages, three genres and both human and institutional actors.</li>
<li>A three-layer <b>case-study methodology</b> (interaction graph, memory-affiliation graph, ownership relation) quantifying how the emergent memory structure tracks the story&rsquo;s social structure.</li>
<li>Two <b>negative results</b> that constrain how such systems should be designed and evaluated: agents never perform discretionary memory management, so structure must be mechanized; and judged narrative quality is insensitive to the memory architecture at this scale, so memory designs should be argued on structure and cost rather than on quality scores.</li>
</ul>

<h2><span class="n">2</span> Related Work</h2>

<h3>2.1 &nbsp;Memory for a single LLM agent</h3>
<p>Generative Agents [1] established the design most agent systems still use: a per-agent stream of observations scored by recency, importance and relevance, periodically compressed into reflections. Variants change what is stored or how it is maintained rather than who owns it. MemGPT [4] treats context as an operating-system memory hierarchy that the model itself pages in and out; MemoryBank [16] adds a forgetting curve so old memories decay; Reflexion [5] persists verbal self-feedback across episodes; Voyager [17] accumulates reusable skills rather than episodes. A-MEM [7] is closest to our linking mechanism: it connects an agent&rsquo;s notes into an evolving network as they are written. A survey of the area [8] finds the same shape throughout &mdash; the memory belongs to one agent, and structure, where it exists, is built inside that agent&rsquo;s own store. Agentsensus keeps the atomization and retrieval machinery of this line but makes <i>ownership</i> a property of a record rather than of a store, which is what allows one record to belong to several agents at once.</p>

<h3>2.2 &nbsp;Multi-agent systems and their shared state</h3>
<p>Multi-agent frameworks organize LLMs into teams: AutoGen [10] around conversable agents, CAMEL [11] around role-played dialogue, MetaGPT [12] and ChatDev [13] around a software-engineering process with defined roles. In all of them the shared state is the conversation &mdash; a transcript or blackboard the agents read &mdash; and long-term memory, where present, remains per-agent. This is adequate when a team works a task to completion, but a story world runs for hundreds of rounds and no transcript survives as a retrieval substrate at that length. Our kernel keeps conversation threads (so a message has a place and a delay) but treats them as transport, not as memory.</p>

<h3>2.3 &nbsp;Memory shared across agents</h3>
<p>Two systems address the multi-agent case directly. G-Memory [3] organizes a system&rsquo;s history into a three-tier insight/query/interaction hierarchy, queried at both team and agent level, and is our G-Memory baseline. Collaborative Memory [9] shares fragments between users under a dynamic access-control policy that decides who may read what, and is our collaborative baseline. Both keep every contributor&rsquo;s record intact and mediate access to those records; neither merges records that <i>say the same thing</i> across contributors. That difference is the subject of this paper: consensus compression changes the number of records rather than the visibility of them, and the owner set it produces is the access-control policy, derived rather than configured.</p>

<h3>2.4 &nbsp;Deduplication, record linkage and grounding</h3>
<p>The idea that two descriptions may denote one fact is older than LLM agents. Record linkage [24] formalized deciding whether two records refer to the same entity; semantic deduplication of web-scale corpora [26] showed that embedding-space near-duplicates can be removed without loss, which is the pre-filter half of our merge. What our setting adds is that the duplicate carries a <i>witness</i>: merging is not only a saving but a statement that two characters share a belief, which is why the merged record keeps a set of owners rather than a single canonical author. The psycholinguistic notion of grounding &mdash; the mutual knowledge interlocutors build and rely on [25] &mdash; is the phenomenon our owner sets approximate mechanically.</p>

<h3>2.5 &nbsp;Retrieval and graph-structured knowledge</h3>
<p>Retrieval-augmented generation [14] is the standard way to give a model access to more than fits in context, and graph-structured variants improve multi-hop and global questions: HippoRAG [6] indexes a corpus as an entity graph, GraphRAG [15] builds an entity graph and community summaries for query-focused summarization. These build structure over a <i>static</i> corpus, in an indexing pass with global knowledge of the documents. Our graph is built incrementally at deposit time by agents who cannot see the store, from two signals available locally: which atoms came from one deposit, and which existing record an incoming atom was judged equivalent to.</p>

<h3>2.6 &nbsp;Story worlds, character agents and social simulation</h3>
<p>Story generation with language models has largely been a planning problem: Dramatron [19] generates scripts hierarchically from a logline, Re3 [20] and DOC [21] plan and revise long stories against an outline. Character agents come at fiction from the other side, fitting a model to one persona [18]. Between them sit simulated worlds: the Smallville society of Generative Agents [1], scaled-up interview-grounded populations [22], geopolitical simulations whose agents are states [23], and BookWorld [2], which builds an interactive agent society from a novel and extracts per-character memories from the source &mdash; the same motivation as our sedimentation stage. Agentsensus differs from all of these in what it puts under test: not the story that comes out, but the memory substrate it comes from, measured by footprint, sharing, graph structure and their growth with horizon. The story is still evaluated (&sect;5.3), but as a check that compression costs nothing, not as the claim.</p>

<h2><span class="n">3</span> The Agentsensus Framework</h2>

<h3>3.1 &nbsp;Design motivation</h3>
<p>The per-agent memory stream is the default because it is the obvious model of a mind: what an agent knows is what it saw. In a <i>shared world</i>, however, that model makes three structural commitments that the designer never explicitly chose, and each one compounds with the number of agents and the length of the run.</p>
<p><b>Storage scales with witnesses, not with events.</b> A council attended by ten officers is ten records. Nothing in the system can tell that they describe one event, so embedding cost, index size, and retrieval noise all grow with the cast rather than with the story. Seeding a world from a novel multiplies the effect before round&nbsp;0: on the same sedimented chapters the per-agent baselines carry 3.3&ndash;5.7&times; the entries of a merged store (&sect;5.1).</p>
<p><b>Nothing reconciles the copies, and nothing connects them.</b> The ten records are ten independently-worded paraphrases that only diverge further as agents summarize and reflect. No record knows its counterparts exist; no edge links a courier&rsquo;s report to the battle it describes or to the order it triggered. The connective tissue of the story lives in the transcript, not in the memory, so retrieval returns one agent&rsquo;s partial view even when the collective already holds the whole.</p>
<p><b>The interfaces that could fix this go unused.</b> Stream designs expose maintenance operations &mdash; link related records, revise stale ones, forget duplicates &mdash; and rely on agents to call them. Across two models and all four backends we measure <i>zero</i> such calls (&sect;5.6), with documentation, worked examples, and an id-free interface all in place. Any structure that depends on agent-side curation therefore never materializes.</p>
<p>Agentsensus answers all three with one commitment: <b>the world&rsquo;s memory is a single store, and sharing is computed rather than assumed</b>. Three design decisions follow, and the rest of this section is their mechanics. <b>D1 &mdash; equivalence merging:</b> when two agents record the same event, the write path detects it and folds the records into one row whose owner-set is the union of its witnesses, so cost tracks events. <b>D2 &mdash; deposit-time graph:</b> the atoms split from one deposit are linked to each other as a side effect of writing, so the graph exists without anyone maintaining it. <b>D3 &mdash; structure inside <code>remember</code>/<code>recall</code>:</b> because agents demonstrably use only those two operations, every mechanism lives inside them; nothing is delegated to agent discretion.</p>
<p>Figure&nbsp;1 shows the framework these decisions live in; Figure&nbsp;2 shows what they change inside the store.</p>

<figure>
<svg viewBox="0 0 840 560" role="img" aria-label="The framework shared by all four backends: a source text is sedimented into owner-tagged events that seed one long-term memory store, which every agent writes to and reads from, while characters also talk to each other through kernel-held threads" style="max-width:100%;height:auto">
  <defs>
    <marker id="f1a" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="currentColor"/></marker>
    <marker id="f1b" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="var(--accent)"/></marker>
    <marker id="f1c" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="var(--good)"/></marker>
  </defs>
  <g fill="none" stroke="currentColor" stroke-width="1.3" font-family="system-ui,sans-serif">

    <text x="14" y="24" font-size="13.5" stroke="none" fill="currentColor" opacity=".6" font-weight="600">OFFLINE &mdash; sedimentation (&sect;3.4)</text>
    <path d="M20 48 h60 a8 8 0 0 1 8 8 v62 a8 8 0 0 1 -8 8 h-60 z"/>
    <line x1="31" y1="48" x2="31" y2="126"/>
    <line x1="42" y1="70" x2="78" y2="70"/><line x1="42" y1="86" x2="78" y2="86"/><line x1="42" y1="102" x2="72" y2="102"/>
    <text x="54" y="150" text-anchor="middle" font-size="14" stroke="none" fill="currentColor">source text</text>
    <line x1="92" y1="87" x2="126" y2="87" marker-end="url(#f1a)"/>
    <path d="M132 54 h74 l-23 29 v40 l-28 12 v-52 z"/>
    <text x="169" y="150" text-anchor="middle" font-size="14" stroke="none" fill="currentColor">extract + attribute</text>
    <line x1="212" y1="87" x2="246" y2="87" marker-end="url(#f1a)"/>
    <rect x="250" y="56" width="96" height="19" rx="3"/><text x="298" y="70" text-anchor="middle" font-size="12" stroke="none" fill="currentColor">event | A, B</text>
    <rect x="250" y="79" width="96" height="19" rx="3"/><text x="298" y="93" text-anchor="middle" font-size="12" stroke="none" fill="currentColor">event | C</text>
    <rect x="250" y="102" width="96" height="19" rx="3"/><text x="298" y="116" text-anchor="middle" font-size="12" stroke="none" fill="currentColor">event | A, D</text>
    <text x="298" y="150" text-anchor="middle" font-size="14" stroke="none" fill="currentColor">owner-tagged events</text>
    <path d="M352 90 C 432 96 424 214 200 236" stroke="var(--accent)" marker-end="url(#f1b)"/>
    <text x="398" y="150" font-size="13" stroke="none" fill="var(--accent)" font-weight="600">seed the store</text>

    <line x1="14" y1="178" x2="826" y2="178" opacity=".25"/>
    <text x="14" y="200" font-size="13.5" stroke="none" fill="currentColor" opacity=".6" font-weight="600">RUNTIME &mdash; one world, one store</text>

    <ellipse cx="120" cy="240" rx="62" ry="16" stroke="var(--accent)" stroke-width="1.7"/>
    <path d="M58 240 v104 a62 16 0 0 0 124 0 v-104" stroke="var(--accent)" stroke-width="1.7"/>
    <text x="120" y="286" text-anchor="middle" font-size="15" stroke="none" fill="var(--accent)" font-weight="700">long-term</text>
    <text x="120" y="306" text-anchor="middle" font-size="15" stroke="none" fill="var(--accent)" font-weight="700">memory</text>
    <text x="120" y="330" text-anchor="middle" font-size="12" stroke="none" fill="currentColor" opacity=".75">shared by all</text>
    <text x="120" y="378" text-anchor="middle" font-size="12" stroke="none" fill="currentColor" opacity=".75">internal structure</text>
    <text x="120" y="394" text-anchor="middle" font-size="12" stroke="none" fill="currentColor" opacity=".75">differs per backend</text>
    <text x="120" y="410" text-anchor="middle" font-size="12" stroke="none" fill="var(--accent)" font-weight="600">&rarr; Figure 2</text>

    <path d="M184 252 C 240 252 244 232 292 232" stroke="var(--accent)" marker-end="url(#f1b)"/>
    <text x="238" y="224" text-anchor="middle" font-size="13" stroke="none" fill="var(--accent)" font-weight="600">recall</text>
    <path d="M292 330 C 244 330 240 310 184 310" stroke="var(--accent)" marker-end="url(#f1b)"/>
    <text x="238" y="348" text-anchor="middle" font-size="13" stroke="none" fill="var(--accent)" font-weight="600">remember</text>
    <text x="238" y="364" text-anchor="middle" font-size="12" stroke="none" fill="currentColor" opacity=".7">both owner-scoped</text>

    <rect x="300" y="196" width="526" height="234" rx="10" stroke-dasharray="5 4" opacity=".5"/>
    <text x="816" y="216" text-anchor="end" font-size="12.5" stroke="none" fill="currentColor" opacity=".65">the society</text>

    <g stroke="var(--accent)"><circle cx="392" cy="248" r="10"/><path d="M379 276 a13 15 0 0 1 26 0"/></g>
    <text x="392" y="322" text-anchor="middle" font-size="13" stroke="none" fill="currentColor">character</text>

    <g stroke="var(--accent)"><circle cx="566" cy="248" r="10"/><path d="M553 276 a13 15 0 0 1 26 0"/></g>
    <text x="566" y="322" text-anchor="middle" font-size="13" stroke="none" fill="currentColor">character</text>

    <g stroke="var(--accent)"><circle cx="392" cy="368" r="10"/><path d="M379 396 a13 15 0 0 1 26 0"/></g>
    <text x="392" y="424" text-anchor="middle" font-size="13" stroke="none" fill="currentColor">character</text>

    <line x1="406" y1="248" x2="552" y2="248" marker-end="url(#f1a)" marker-start="url(#f1a)"/>
    <text x="479" y="240" text-anchor="middle" font-size="12" stroke="none" fill="currentColor" opacity=".85">say &middot; kernel-held thread</text>
    <line x1="402" y1="352" x2="556" y2="266" marker-end="url(#f1a)"/>
    <text x="500" y="300" text-anchor="middle" font-size="12" stroke="none" fill="currentColor" opacity=".85">delivery delayed by distance</text>

    <g stroke="var(--good)"><path d="M700 244 a12 12 0 1 1 0.01 0"/><path d="M690 253 l10 22 l10 -22"/></g>
    <text x="700" y="296" text-anchor="middle" font-size="13" stroke="none" fill="var(--good)">environment</text>
    <text x="700" y="312" text-anchor="middle" font-size="12" stroke="none" fill="currentColor" opacity=".7">owns memories,</text>
    <text x="700" y="326" text-anchor="middle" font-size="12" stroke="none" fill="currentColor" opacity=".7">never takes a turn</text>

    <g stroke="var(--warn)"><path d="M676 356 h38 l12 12 v32 h-50 z"/><path d="M714 356 v12 h12"/>
      <line x1="684" y1="380" x2="716" y2="380"/><line x1="684" y1="391" x2="710" y2="391"/></g>
    <text x="701" y="420" text-anchor="middle" font-size="13" stroke="none" fill="var(--warn)">info carrier</text>

    <line x1="584" y1="248" x2="672" y2="248" marker-end="url(#f1c)"/>
    <text x="628" y="240" text-anchor="middle" font-size="12" stroke="none" fill="var(--good)">act_on</text>
    <line x1="418" y1="376" x2="668" y2="376" marker-end="url(#f1c)"/>
    <text x="540" y="368" text-anchor="middle" font-size="12" stroke="none" fill="var(--good)">read</text>

    <line x1="14" y1="452" x2="826" y2="452" opacity=".25"/>
    <text x="14" y="474" font-size="13" stroke="none" fill="currentColor" opacity=".9">A character emits <tspan font-weight="600">one action per round</tspan>, from a single repertoire:</text>
    <g font-size="12.5">
      <rect x="14" y="486" width="40" height="22" rx="11"/><text x="34" y="501" text-anchor="middle" stroke="none" fill="currentColor">say</text>
      <rect x="60" y="486" width="88" height="22" rx="11"/><text x="104" y="501" text-anchor="middle" stroke="none" fill="currentColor">read_thread</text>
      <rect x="154" y="486" width="84" height="22" rx="11" stroke="var(--accent)"/><text x="196" y="501" text-anchor="middle" stroke="none" fill="var(--accent)" font-weight="600">remember</text>
      <rect x="244" y="486" width="60" height="22" rx="11" stroke="var(--accent)"/><text x="274" y="501" text-anchor="middle" stroke="none" fill="var(--accent)" font-weight="600">recall</text>
      <rect x="310" y="486" width="80" height="22" rx="11"/><text x="350" y="501" text-anchor="middle" stroke="none" fill="currentColor">push_goal</text>
      <rect x="396" y="486" width="74" height="22" rx="11"/><text x="433" y="501" text-anchor="middle" stroke="none" fill="currentColor">pop_goal</text>
      <rect x="476" y="486" width="52" height="22" rx="11" stroke="var(--good)"/><text x="502" y="501" text-anchor="middle" stroke="none" fill="var(--good)">move</text>
      <rect x="534" y="486" width="78" height="22" rx="11" stroke="var(--good)"/><text x="573" y="501" text-anchor="middle" stroke="none" fill="var(--good)">observe</text>
      <rect x="618" y="486" width="62" height="22" rx="11" stroke="var(--good)"/><text x="649" y="501" text-anchor="middle" stroke="none" fill="var(--good)">act_on</text>
      <rect x="686" y="486" width="48" height="22" rx="11" stroke="var(--good)"/><text x="710" y="501" text-anchor="middle" stroke="none" fill="var(--good)">read</text>
      <rect x="740" y="486" width="46" height="22" rx="11"/><text x="763" y="501" text-anchor="middle" stroke="none" fill="currentColor">wait</text>
      <rect x="14" y="514" width="232" height="22" rx="11" stroke-dasharray="3 3" opacity=".5"/><text x="130" y="529" text-anchor="middle" stroke="none" fill="currentColor" opacity=".75">6 memory-management: never used</text>
    </g>
    <text x="262" y="522" font-size="12" stroke="none" fill="currentColor" opacity=".8">Blue actions touch long-term memory, green ones the world. Each round freezes all views at the barrier,</text>
    <text x="262" y="538" font-size="12" stroke="none" fill="currentColor" opacity=".8">decisions issue concurrently, then apply in a fixed order &mdash; event order is reproducible.</text>
  </g>
</svg>
<figcaption><b>Figure 1. The framework, identical for all four memory designs.</b> A source text is sedimented into atomic events tagged with the characters who witnessed them, and those events seed one long-term memory store (&sect;3.4). At run time every agent reaches the <i>same</i> store through two operations &mdash; <code>remember</code> and <code>recall</code>, both owner-scoped &mdash; while characters (blue) also talk to one another through kernel-held threads whose delivery is delayed by map distance; environments (green) and information carriers (amber) own memories and answer <code>act_on</code>/<code>read</code> but never take a turn. Each character additionally carries a small short-term state (action FIFO, goal stack) that is not part of the store. What the four backends change is only the internal structure of the cylinder, which Figure 2 opens up.</figcaption>
</figure>

<h3>3.2 &nbsp;System overview</h3>
<p>Agentsensus is three subsystems, all visible in Figure&nbsp;1. An offline <b>sedimentation pipeline</b> turns a source text into a memory-grounded initial world. A deterministic <b>round-barrier kernel</b> schedules agents, routes messages, and snapshots the entire system. The <b>shared long-term memory</b> holds every agent&rsquo;s knowledge in one store, with D1&ndash;D3 implemented inside its write and read paths. Data flows left to right at start-up &mdash; sedimentation seeds both the store and the world state &mdash; and cycles between kernel and store at run time: Phase-2 action effects write into the store and into conversation threads, and both feed the next round&rsquo;s agent views through owner-scoped recall and the conversation roster.</p>


<h3>3.3 &nbsp;World model and round-barrier kernel</h3>
<p><b>Entities.</b> A world is a set of agents on a location map with pairwise travel distances. <b>Characters</b> are LLM-driven: each holds a persona, a goal stack, a status register, and a short-term FIFO of recent actions; each decision is one LLM call that receives a rendered view (round, goals, status, FIFO, co-located agents, conversation roster, known locations, plus contextual hints) and returns one action as JSON. <b>Environments</b> and <b>information carriers</b> are passive: they own memories (deposited by sedimentation or by characters&rsquo; <code>act_on</code>) but never take turns &mdash; a character&rsquo;s <code>act_on</code>/<code>read</code> is served synchronously by the kernel against the target&rsquo;s own memories, costing no extra LLM calls and giving places and documents durable, queryable state.</p>
<p><b>Scheduling.</b> Each round runs two phases under a barrier. Phase&nbsp;1 builds every awake character&rsquo;s view from the <i>same</i> pre-round snapshot and issues all decisions concurrently; because views are frozen before any decision, LLM latency cannot change what any agent observes. Phase&nbsp;2 applies the returned actions sequentially in a fixed agent order, so conflicting effects resolve deterministically and event order is reproducible independent of API timing. Agents sleep only by explicit <code>wait</code>; a single sleep is capped (20 rounds) after we observed uncapped waits produce narrative deadlocks &mdash; a character who delegated a task and slept &ldquo;until the report arrives&rdquo; was simply never messaged again and stayed silent for 52 rounds. A <code>wake=true</code> message still interrupts sleep early.</p>
<p><b>Messaging.</b> Messages are not agent-held inboxes but kernel-held <b>conversation threads</b>, one per interlocutor pair. Co-located speech delivers at the next round; remote messages travel for their map distance in rounds, so information propagates at the speed of couriers rather than instantaneously. Delivery increments the recipient&rsquo;s unread counter (surfaced in its view roster) and, by default, wakes it; reading is an explicit <code>read_thread</code> action. The same threads also log observation and environment interactions, giving each pair a complete interaction history.</p>
<p><b>Checkpointing.</b> Every 20 rounds the kernel atomically snapshots the complete system &mdash; each agent&rsquo;s short-term state (FIFO, goal stack, status, sleep timer), kernel runtime (presence, in-transit moves, undelivered messages, conversation threads, event counter), and the entire memory store including embeddings. A resumed run continues bit-for-bit; the long-horizon results in &sect;5 are consecutive resumed stages of one continuous run per backend.</p>

<h3>3.4 &nbsp;Sedimentation: from source text to memory-grounded world</h3>
<p>The pipeline converts the sediment span into the initial world in four steps. (i) <b>Extraction and attribution</b>: an LLM pass extracts events chapter by chapter and attributes each to the characters who witnessed it, producing atomic, story-ordered records with owner-sets. (ii) <b>Per-backend ingest</b>: each memory backend stores these events under its own rule &mdash; the consensus store keeps one merged row per event carrying the full owner-set, while per-agent baselines fan out one row per witness &mdash; so every method starts from the initial state its own mechanism would have produced, and baseline machinery (importance scoring, reflection, distillation) is run over the sediment before round&nbsp;0. (iii) <b>Boundary-state finalization</b>: each character&rsquo;s aliveness and location at the story boundary are extracted from <i>its own memory timeline</i> (with a canon-knowledge fallback anchored to the boundary chapter); characters dead by the boundary are archived &mdash; they keep their memories as owners but are never scheduled &mdash; and living ones are placed at their last grounded location. (iv) The result is a world whose knowledge and geography are both grounded in the text.</p>

<h3>3.5 &nbsp;The consensus shared memory</h3>
<p><b>Data model.</b> The store is a single vector collection whose rows are (text, embedding, owner-set, affiliated-set, metadata). Owner membership is additionally materialized as indexed per-agent flags, so owner-scoped retrieval is a server-side filter rather than a post-hoc scan; the affiliated-set holds ids of related rows and is what makes the store a graph.</p>
<p><b>Write path.</b> Every <code>remember(text)</code> runs four stages. <i>(1) Atomization:</i> a compound deposit is split by an LLM into atomic statements, each required to be <b>self-contained</b> &mdash; pronouns resolved to names, who/what/where carried over &mdash; so a statement is interpretable without its siblings. All four backends share this exact stage (&sect;4.3), making entry counts comparable by construction. <i>(2) Candidate pre-filter:</i> each atom is embedded and matched against the store by cosine kNN with a deliberately permissive threshold (0.70): self-contained phrasings of the same event from different viewpoints embed measurably further apart than near-identical wordings, and at the conventional 0.86 <i>zero</i> cross-witness sim memories ever reached candidacy. <i>(3) Equivalence judging:</i> an LLM judge inspects the candidates and either selects the one that describes the same event or declines. The pre-filter only bounds the judge&rsquo;s candidate list; the judge is the actual gate, so the permissive threshold trades a few extra judge calls for recall of true matches. <i>(4) Merge or insert:</i> on a match the records fold into one row &mdash; owner-sets union, affiliated-sets union, the shorter text is kept &mdash; so N witnesses of one event cost one row; otherwise a fresh row is inserted. Finally, <b>auto-affiliation</b> mutually links the atoms split from one deposit: the memory graph is built as a side-effect of writing, by the mechanism rather than the agent.</p>
<p><b>Read path.</b> <code>recall(query)</code> retrieves the top-k semantic matches <i>among rows the caller owns</i>, then follows each hit&rsquo;s affiliated edges one hop and appends linked rows the caller also owns, marked <code>via_affiliated</code>. A single recall therefore returns an event&rsquo;s scattered pieces together. Expansion is deliberately uncapped; its cost is measured in &sect;5.2.</p>
<p><b>Cost placement.</b> The design pays at write time (one atomization call when a deposit is compound, one judge call when candidates pass the pre-filter) to keep the store small and structured; reads add only vector lookups. &sect;5.2&rsquo;s latency instrumentation quantifies both sides against the baselines.</p>

<h3>3.6 &nbsp;How the four designs differ</h3>
<p>Everything above is shared by the four backends we compare: the same world model, the same sedimented events, the same two operations, the same atomization. They differ in one place only &mdash; the internal structure of the store in Figure&nbsp;1 &mdash; and Figure&nbsp;2 draws that structure for each. Read side by side, the three baselines differ in how much structure they build <i>within</i> a single owner&rsquo;s records, and consensus is the only one that builds structure <i>across</i> owners.</p>

<figure>
<svg viewBox="0 0 840 660" role="img" aria-label="The long-term memory structure of the four backends: private streams with importance scores and a reflection tree; a two-tier interaction and insight graph walked by bi-level retrieval; one access-controlled store where sharing is a permission; and merged multi-owner rows inside an affiliation graph that recall expands one hop" style="max-width:100%;height:auto">
  <defs>
    <marker id="g2a" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="currentColor"/></marker>
    <marker id="g2b" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="var(--accent)"/></marker>
  </defs>
  <g fill="none" stroke="currentColor" stroke-width="1.2" font-family="system-ui,sans-serif">

  <!-- (a) Generative-Agents -->
  <text x="14" y="22" font-size="14.5" stroke="none" fill="currentColor" font-weight="700">(a) Generative-Agents &mdash; private streams + reflection tree</text>
  <rect x="14" y="32" width="396" height="264" rx="9" opacity=".45" stroke-dasharray="5 4"/>
  <g stroke="var(--accent)"><circle cx="64" cy="60" r="8"/><path d="M53 80 a11 12 0 0 1 22 0"/></g>
  <text x="64" y="98" text-anchor="middle" font-size="13.5" stroke="none" fill="currentColor">A</text>
  <g stroke="var(--accent)"><circle cx="212" cy="60" r="8"/><path d="M201 80 a11 12 0 0 1 22 0"/></g>
  <text x="212" y="98" text-anchor="middle" font-size="13.5" stroke="none" fill="currentColor">B</text>
  <rect x="24" y="110" width="80" height="22" rx="3"/><text x="46" y="125" text-anchor="middle" font-size="13.4" stroke="none" fill="currentColor">e</text>
  <text x="88" y="125" text-anchor="middle" font-size="13.4" stroke="none" fill="currentColor" opacity=".7">.8</text>
  <rect x="24" y="136" width="80" height="22" rx="3"/><text x="88" y="151" text-anchor="middle" font-size="13.4" stroke="none" fill="currentColor" opacity=".7">.4</text>
  <rect x="24" y="162" width="80" height="22" rx="3"/><text x="88" y="177" text-anchor="middle" font-size="13.4" stroke="none" fill="currentColor" opacity=".7">.9</text>
  <rect x="172" y="110" width="80" height="22" rx="3"/><text x="194" y="125" text-anchor="middle" font-size="13.4" stroke="none" fill="currentColor">e</text>
  <text x="236" y="125" text-anchor="middle" font-size="13.4" stroke="none" fill="currentColor" opacity=".7">.7</text>
  <rect x="172" y="136" width="80" height="22" rx="3"/><text x="236" y="151" text-anchor="middle" font-size="13.4" stroke="none" fill="currentColor" opacity=".7">.5</text>
  <rect x="172" y="162" width="80" height="22" rx="3"/><text x="236" y="177" text-anchor="middle" font-size="13.4" stroke="none" fill="currentColor" opacity=".7">.6</text>
  <text x="132" y="104" text-anchor="middle" font-size="13.4" stroke="none" fill="currentColor" opacity=".7">importance</text>
  <rect x="24" y="204" width="80" height="24" rx="3" stroke-dasharray="4 3"/><text x="64" y="220" text-anchor="middle" font-size="13.4" stroke="none" fill="currentColor" opacity=".9">reflection</text>
  <rect x="24" y="248" width="80" height="24" rx="3" stroke-dasharray="4 3"/><text x="64" y="264" text-anchor="middle" font-size="13.4" stroke="none" fill="currentColor" opacity=".9">reflection&sup2;</text>
  <path d="M34 186 L46 202" stroke-dasharray="3 3" marker-end="url(#g2a)"/>
  <path d="M94 186 L78 202" stroke-dasharray="3 3" marker-end="url(#g2a)"/>
  <line x1="64" y1="228" x2="64" y2="246" stroke-dasharray="3 3" marker-end="url(#g2a)"/>
  <text x="120" y="216" font-size="13.4" stroke="none" fill="currentColor" opacity=".75">evidence links,</text>
  <text x="120" y="232" font-size="13.4" stroke="none" fill="currentColor" opacity=".75">reflections stack</text>
  <text x="120" y="262" font-size="13.4" stroke="none" fill="currentColor" opacity=".75">&mdash; all inside one lane</text>
  <text x="330" y="130" text-anchor="middle" font-size="13.4" stroke="none" fill="currentColor" opacity=".8">recall scores</text>
  <text x="330" y="146" text-anchor="middle" font-size="13.4" stroke="none" fill="currentColor" opacity=".8">recency &times;</text>
  <text x="330" y="162" text-anchor="middle" font-size="13.4" stroke="none" fill="currentColor" opacity=".8">importance &times;</text>
  <text x="330" y="178" text-anchor="middle" font-size="13.4" stroke="none" fill="currentColor" opacity=".8">relevance</text>
  <text x="212" y="288" text-anchor="middle" font-size="13.4" stroke="none" fill="currentColor" opacity=".9">event <tspan font-style="italic">e</tspan> stored once per witness; no edge crosses lanes</text>

  <!-- (b) G-Memory -->
  <text x="430" y="22" font-size="14.5" stroke="none" fill="currentColor" font-weight="700">(b) G-Memory &mdash; two-tier graph, per owner</text>
  <rect x="430" y="32" width="396" height="264" rx="9" opacity=".45" stroke-dasharray="5 4"/>
  <g stroke="var(--accent)"><circle cx="480" cy="60" r="8"/><path d="M469 80 a11 12 0 0 1 22 0"/></g>
  <text x="480" y="98" text-anchor="middle" font-size="13.5" stroke="none" fill="currentColor">A</text>
  <g stroke="var(--accent)"><circle cx="690" cy="60" r="8"/><path d="M679 80 a11 12 0 0 1 22 0"/></g>
  <text x="690" y="98" text-anchor="middle" font-size="13.5" stroke="none" fill="currentColor">B</text>
  <text x="440" y="120" font-size="13.4" stroke="none" fill="currentColor" opacity=".7">insight tier</text>
  <text x="440" y="238" font-size="13.4" stroke="none" fill="currentColor" opacity=".7">interaction tier</text>
  <line x1="440" y1="168" x2="816" y2="168" opacity=".25" stroke-dasharray="2 4"/>
  <ellipse cx="530" cy="134" rx="38" ry="18" stroke-dasharray="4 3"/><text x="530" y="139" text-anchor="middle" font-size="13.4" stroke="none" fill="currentColor">insight</text>
  <ellipse cx="716" cy="134" rx="38" ry="18" stroke-dasharray="4 3"/><text x="716" y="139" text-anchor="middle" font-size="13.4" stroke="none" fill="currentColor">insight</text>
  <rect x="490" y="192" width="34" height="22" rx="3"/><text x="507" y="207" text-anchor="middle" font-size="13.4" stroke="none" fill="currentColor">e</text>
  <rect x="530" y="192" width="34" height="22" rx="3"/>
  <rect x="570" y="192" width="34" height="22" rx="3"/>
  <rect x="676" y="192" width="34" height="22" rx="3"/><text x="693" y="207" text-anchor="middle" font-size="13.4" stroke="none" fill="currentColor">e</text>
  <rect x="716" y="192" width="34" height="22" rx="3"/>
  <rect x="756" y="192" width="34" height="22" rx="3"/>
  <line x1="512" y1="152" x2="507" y2="190" marker-end="url(#g2a)"/>
  <line x1="530" y1="152" x2="547" y2="190" marker-end="url(#g2a)"/>
  <line x1="548" y1="152" x2="587" y2="190" marker-end="url(#g2a)"/>
  <line x1="698" y1="152" x2="693" y2="190" marker-end="url(#g2a)"/>
  <line x1="716" y1="152" x2="733" y2="190" marker-end="url(#g2a)"/>
  <line x1="734" y1="152" x2="773" y2="190" marker-end="url(#g2a)"/>
  <text x="604" y="166" font-size="13.4" stroke="none" fill="currentColor" opacity=".75">derived_from</text>
  <text x="624" y="120" text-anchor="middle" font-size="13.4" stroke="none" fill="currentColor" opacity=".7">distilled every 20</text>
  <path d="M600 240 L556 220" stroke="var(--accent)" marker-end="url(#g2b)"/>
  <path d="M600 240 C 580 200 548 176 542 156" stroke="var(--accent)" marker-end="url(#g2b)"/>
  <text x="612" y="246" font-size="13.4" stroke="none" fill="var(--accent)" font-weight="600">bi-level recall:</text>
  <text x="612" y="264" font-size="13.4" stroke="none" fill="currentColor" opacity=".8">hit both tiers, then</text>
  <text x="612" y="280" font-size="13.4" stroke="none" fill="currentColor" opacity=".8">walk derived_from</text>
  <text x="628" y="306" text-anchor="middle" font-size="13.4" stroke="none" fill="currentColor" opacity=".9">a real graph &mdash; never across owners</text>

  <!-- (c) Collaborative -->
  <text x="14" y="346" font-size="14.5" stroke="none" fill="currentColor" font-weight="700">(c) Collaborative &mdash; one store, ACL-partitioned</text>
  <rect x="14" y="356" width="396" height="264" rx="9" opacity=".45" stroke-dasharray="5 4"/>
  <g stroke="var(--accent)"><circle cx="70" cy="384" r="8"/><path d="M59 404 a11 12 0 0 1 22 0"/></g>
  <text x="70" y="422" text-anchor="middle" font-size="13.5" stroke="none" fill="currentColor">A</text>
  <g stroke="var(--accent)"><circle cx="210" cy="384" r="8"/><path d="M199 404 a11 12 0 0 1 22 0"/></g>
  <text x="210" y="422" text-anchor="middle" font-size="13.5" stroke="none" fill="currentColor">B</text>
  <rect x="26" y="440" width="372" height="128" rx="7"/>
  <text x="212" y="458" text-anchor="middle" font-size="13.4" stroke="none" fill="currentColor" opacity=".7">one physical collection, no merge</text>
  <rect x="42" y="470" width="164" height="26" rx="3"/><text x="124" y="487" text-anchor="middle" font-size="13.4" stroke="none" fill="currentColor">e &nbsp;&middot;&nbsp; acl {{A}}</text>
  <rect x="42" y="502" width="164" height="26" rx="3"/><text x="124" y="519" text-anchor="middle" font-size="13.4" stroke="none" fill="currentColor">&hellip; &nbsp;&middot;&nbsp; acl {{A}}</text>
  <rect x="222" y="470" width="164" height="26" rx="3"/><text x="304" y="487" text-anchor="middle" font-size="13.4" stroke="none" fill="currentColor">e &nbsp;&middot;&nbsp; acl {{A, B}}</text>
  <rect x="222" y="502" width="164" height="26" rx="3"/><text x="304" y="519" text-anchor="middle" font-size="13.4" stroke="none" fill="currentColor">&hellip; &nbsp;&middot;&nbsp; acl {{B}}</text>
  <line x1="70" y1="430" x2="100" y2="466" marker-end="url(#g2a)"/>
  <line x1="210" y1="430" x2="270" y2="466" marker-end="url(#g2a)"/>
  <path d="M304 496 C 240 512 160 500 130 496" stroke-dasharray="4 3"/>
  <text x="212" y="586" text-anchor="middle" font-size="13.4" stroke="none" fill="currentColor" opacity=".75">B may be granted access to A&rsquo;s copy; the copy remains</text>
  <text x="212" y="608" text-anchor="middle" font-size="13.4" stroke="none" fill="currentColor" opacity=".9">sharing is a <tspan font-style="italic">permission</tspan>, not a merge</text>

  <!-- (d) Consensus -->
  <text x="430" y="346" font-size="14.5" stroke="none" fill="var(--accent)" font-weight="700">(d) Consensus (ours) &mdash; merged rows in a graph</text>
  <rect x="430" y="356" width="396" height="264" rx="9" stroke="var(--accent)" stroke-dasharray="5 4" opacity=".75"/>
  <g stroke="var(--accent)"><circle cx="490" cy="384" r="8"/><path d="M479 404 a11 12 0 0 1 22 0"/></g>
  <text x="490" y="422" text-anchor="middle" font-size="13.5" stroke="none" fill="currentColor">A</text>
  <g stroke="var(--accent)"><circle cx="620" cy="384" r="8"/><path d="M609 404 a11 12 0 0 1 22 0"/></g>
  <text x="620" y="422" text-anchor="middle" font-size="13.5" stroke="none" fill="currentColor">B</text>
  <g stroke="var(--accent)"><circle cx="750" cy="384" r="8"/><path d="M739 404 a11 12 0 0 1 22 0"/></g>
  <text x="750" y="422" text-anchor="middle" font-size="13.5" stroke="none" fill="currentColor">C</text>
  <line x1="490" y1="430" x2="576" y2="454" stroke="var(--accent)" marker-end="url(#g2b)"/>
  <line x1="620" y1="430" x2="620" y2="454" stroke="var(--accent)" marker-end="url(#g2b)"/>
  <line x1="750" y1="430" x2="664" y2="454" stroke="var(--accent)" marker-end="url(#g2b)"/>
  <rect x="532" y="456" width="176" height="44" rx="5" stroke="var(--accent)" stroke-width="1.8"/>
  <text x="620" y="474" text-anchor="middle" font-size="13.4" stroke="none" fill="currentColor">e</text>
  <text x="620" y="492" text-anchor="middle" font-size="13.4" stroke="none" fill="var(--accent)" font-weight="700">owners {{A, B, C}}</text>
  <rect x="452" y="524" width="150" height="30" rx="4" stroke="var(--accent)"/>
  <text x="527" y="543" text-anchor="middle" font-size="13.4" stroke="none" fill="currentColor">sibling &middot; {{A, B}}</text>
  <rect x="638" y="524" width="150" height="30" rx="4" stroke="var(--accent)"/>
  <text x="713" y="543" text-anchor="middle" font-size="13.4" stroke="none" fill="currentColor">sibling &middot; {{C}}</text>
  <line x1="570" y1="500" x2="540" y2="522" stroke="var(--accent)"/>
  <line x1="670" y1="500" x2="700" y2="522" stroke="var(--accent)"/>
  <line x1="602" y1="539" x2="636" y2="539" stroke="var(--accent)" stroke-dasharray="3 3"/>
  <text x="620" y="516" text-anchor="middle" font-size="13.4" stroke="none" fill="currentColor" opacity=".8">affiliated</text>
  <text x="620" y="576" text-anchor="middle" font-size="13.4" stroke="none" fill="currentColor" opacity=".8">recall: rows you own, then one hop along these edges</text>
  <text x="628" y="600" text-anchor="middle" font-size="13.4" stroke="none" fill="var(--accent)" font-weight="600">one row per event, owned by all witnesses</text>

  <line x1="14" y1="634" x2="826" y2="634" opacity=".3"/>
  <text x="14" y="650" font-size="13.4" stroke="none" fill="currentColor" opacity=".75">Same event <tspan font-style="italic">e</tspan> in every panel &middot; person = owner &middot; solid box = stored row &middot; dashed = mechanism-generated</text>
  </g>
</svg>
<figcaption><b>Figure 2. What the long-term memory looks like inside, per backend.</b> The same event <i>e</i>, witnessed by several agents, is drawn in all four stores. <b>(a)</b> Generative-Agents keeps one append-only stream per agent, each row carrying an LLM-assigned importance score that recall combines with recency and relevance; reflections are synthesized from high-importance windows, link back to the evidence they summarize, and stack into a tree &mdash; all within one lane. <b>(b)</b> G-Memory adds a second tier: every 20 deposits a distillation pass writes an insight node and connects it to its source interactions with <code>derived_from</code> edges, and bi-level retrieval hits both tiers and then walks those edges. It is a genuine graph, and it is built inside one owner&rsquo;s records. (The paper&rsquo;s third, query tier is defined in our port but never written, since traversal is seeded from insight and interaction hits.) <b>(c)</b> Collaborative memory puts everything in one physical collection and partitions reads by access control; an ACL may name several principals, so B can be granted access to A&rsquo;s copy &mdash; but the copy remains, because permission is not merging. <b>(d)</b> Consensus stores one row per event whose owner-set is the union of its witnesses, links the atoms split from one deposit into an affiliation graph, and expands recall one hop along it. The distinction the figure is drawn to make: (a)&ndash;(c) differ in how much structure they build <i>within</i> an owner; only (d) puts structure <i>across</i> owners.</figcaption>
</figure>

<h3>3.7 &nbsp;Query-addressed operations and the design rule</h3>
<p>No memory operation takes a raw id. <code>forget</code>, <code>revise_memory</code>, and the affiliation operations address a memory by a natural-language query that the kernel resolves to the caller&rsquo;s best-matching owned row, so owner-scoping is enforced at resolution and there is no id for an agent to mishandle. The design responds to a robust behavioral finding: LLM agents never thread opaque ids across turns &mdash; in earlier runs every id-based operation had &asymp;0 uses. Query addressing removes that interface barrier; the observation that agents <i>still</i> issue zero discretionary memory-management calls (&sect;5.6) is what elevates &ldquo;structure must live inside <code>remember</code>/<code>recall</code>&rdquo; from an implementation choice to the framework&rsquo;s central design rule.</p>

<h2><span class="n">4</span> Experimental Setup</h2>

<h3>4.1 &nbsp;Scenarios</h3>
<p>Three Kingdoms (三国演义) chapters 1&ndash;40 are sedimented onto 191 canonical characters (33 active at the boundary, the rest archived as dead; ~6,000 consensus events). All four backends then run the <i>same</i> 80-round simulation &mdash; same scenario file, same action repertoire, same model (<code>gpt-5-mini</code>; embeddings <code>text-embedding-3-small</code>) &mdash; in four checkpointed 20-round stages.</p>
<p>To test that the mechanisms are not an artifact of one fictional world, the second scenario is <b>real-world</b>: a timeline of the Russia&ndash;Ukraine conflict sedimented through 2026-07 (1,533 events over 170 entities). Real-world boundary semantics replace the novel&rsquo;s: a figure is archived if, by the boundary, they are dead <i>or out of the conflict&rsquo;s stage</i> (out of office, dismissed, disbanded), with placements grounded in the timeline or, failing that, the person&rsquo;s workplace/role (final cast: 47 active, 14 archived, manually verified). All four backends run the same 40-round simulation under the identical fairness protocol.</p>

<p>The third scenario returns to fiction in a different register: <b>Red Chamber (红楼梦)</b> (<i>Dream of the Red Chamber</i>), chapters 1&ndash;40 sedimented onto 152 registry characters (6,506 consensus events; chapters 41&ndash;80 held out). The active cast is the 37 characters above the memory threshold (34 living; Qin Keqing (秦可卿), Jia Rui (贾瑞) and Qin Zhong (秦钟), dead by chapter 40, stay archived owners), and the boundary state is a freeze-frame of chapter 40&rsquo;s garden banquet &mdash; Grandmother Jia (贾母) and Granny Liu (刘姥姥) at the Grand View Pavilion (大观楼), the touring party at Hengwu Court (蘅芜苑), the musicians at the Lotus Fragrance Pavilion (藕香榭) &mdash; grounded per character in the sediment and manually verified. Where Three Kingdoms is war and statecraft among factions, Red Chamber is dense domestic society &mdash; one household, fine-grained relationships &mdash; a different social topology for the same mechanisms. All four backends run the same 80-round simulation under the identical fairness protocol.</p>

<p>The fourth scenario is deliberately the smallest: <b>Hamlet</b>, Acts&nbsp;1&ndash;3 sedimented onto a 22-character registry (1,135 consensus events; Acts&nbsp;4&ndash;5 held out). Sixteen characters pass the memory threshold, plus Fortinbras, who owns no sediment memories at all &mdash; he never appears on stage before Act&nbsp;4 &mdash; but is retained because the continuation is his; England is likewise retained as an environment because it is where the sealed commission leads. Two characters are archived at the boundary: Polonius, killed behind the arras in 3.4, and the Ghost, absent from the canon after that scene. Where the other three worlds have dozens of agents spread over a map, Hamlet is a chamber drama &mdash; sixteen agents in one castle, most scenes a two-person exchange &mdash; which makes it the sharpest test of whether the mechanisms need scale to show anything. All four backends run the same 40-round simulation under the identical fairness protocol.</p>

<h3>4.2 &nbsp;Baselines</h3>
<ul class="body">
<li><b>Generative-Agents memory</b> [1]: per-agent private streams; insert-time importance scoring; reflection synthesis over high-importance windows.</li>
<li><b>G-Memory</b> [3]: shared store organized as interaction/insight tiers with periodic LLM distillation into insight nodes and bi-level retrieval over provenance edges.</li>
<li><b>Collaborative memory</b> [9]: per-owner fragments guarded by access-control lists; recall is ACL-filtered server-side.</li>
</ul>
<p>All three ingest the sediment under their own rule (one row per witness) and run their own machinery over it (GA importance+reflections; G-Memory distillation) before round 0, so each starts from a self-consistent initial state.</p>

<h3>4.3 &nbsp;Fairness protocol</h3>
<p><b>Equal granularity.</b> Every backend routes <code>remember</code> through the <i>same</i> atomization code with the same self-containment requirement. Entry counts are therefore directly comparable; the only remaining difference is what each mechanism does with identical atoms.</p>
<p><b>Simulation-only accounting.</b> All reported numbers cover memories the simulation itself generated (<code>remember</code>/<code>act_on</code> deposits). Sedimented content and baseline by-products (GA reflection nodes, G-Memory distillation nodes) are excluded on all sides.</p>

<h3>4.4 &nbsp;Metrics</h3>
<ul class="body">
<li><b>Structure</b> (deterministic): sim-entry count; share of multi-owner entries; share of entries with affiliated edges.</li>
<li><b>Continuation quality</b> (LLM-judged, mean&plusmn;std over 3 scorings of the run&rsquo;s rendered screenplay): <i>grounding</i> &mdash; the fraction of the sim&rsquo;s own events consistent with the canon; <i>trajectory</i> &mdash; agreement of character arcs with reference arcs extracted from each world&rsquo;s held-out continuation (Three Kingdoms: chapters 41&ndash;60; Red Chamber: chapters 41&ndash;80; Russia&ndash;Ukraine: the timeline beyond the 2024-04 boundary; Hamlet: Acts&nbsp;4&ndash;5); <i>narrative</i> &mdash; judged coherence/drama/fidelity (1&ndash;5); <i>goal pursuit</i> &mdash; whether each agent&rsquo;s actions consistently pursue its declared goals, judged against the goal stack the agent itself maintains and read from the event log rather than the screenplay; achievement is deliberately not scored, since a faithful tragedy requires goals to fail. Scoring reads the screenplay rather than the raw transcript (&sect;5.3): a 40-round Russia&ndash;Ukraine log is 1.6M characters, past any judge&rsquo;s context window, while its screenplay is an order of magnitude smaller and in one language, so no truncation or sampling is needed. Where a held-out span is itself too long to read at once &mdash; Red Chamber&rsquo;s forty chapters &mdash; reference arcs are extracted chapter-group by chapter-group and condensed per character.</li>
<li><b>Operation latency</b> (&sect;5.2): per-call wall-clock time of <code>remember</code>/<code>recall</code>, timed in the kernel around the backend call so each mechanism&rsquo;s internal cost (equivalence judging, importance scoring, auto-expansion) falls inside the window. Rounds 61&ndash;80 are instrumented live; rounds 1&ndash;60 are measured by replaying each stage&rsquo;s logged operations against the store state the stage started from (checkpoint-exact for stages 2&ndash;3; the first stage&rsquo;s GA/G-Memory replay stores lack prime by-products, &asymp;3&ndash;5% of rows).</li>
<li><b>Three-layer alignment</b> (&sect;5.4): relations between the interaction graph, the affiliation graph, and the ownership relation.</li>
</ul>

<h2><span class="n">5</span> Results</h2>

<h3>5.1 &nbsp;Footprint and structure</h3>
<p>At equal granularity, consensus writes the fewest sim memories in all three worlds (Three Kingdoms: {C['sim_new']} vs {GA['sim_new']}&ndash;{CO['sim_new']}; Russia&ndash;Ukraine: {RUC['sim_new']} vs {RU['collaborative']['sim_new']}&ndash;{RU['generative_agents']['sim_new']}; Red Chamber: {RCC['sim_new']} vs {RC['generative_agents']['sim_new']}&ndash;{RC['g_memory']['sim_new']}) because merging folds witnesses together. The same holds for structure: in every world consensus is the only backend whose memories become shared and linked ({C['sh_pct']}%/{C['aff_pct']}% in Three Kingdoms, {RUC['sh_pct']}%/{RUC['aff_pct']}% in Russia&ndash;Ukraine, {RCC['sh_pct']}%/{RCC['aff_pct']}% in Red Chamber), against 0% for every baseline.</p>
<div class="tw"><table>
<caption><b>Table 1. Store size by backend and world.</b> &ldquo;Sediment&rdquo; is the store at round&nbsp;0, produced by each mechanism&rsquo;s own ingest of the identical source events (&sect;3.4) &mdash; one row per event under consensus, one row per witness under every baseline, plus each backend&rsquo;s own by-products (Generative-Agents reflections, G-Memory insight nodes). &ldquo;Sim&rdquo; is what the simulation then added and is the comparison the fairness protocol licenses: all four backends atomize identically, so entry counts are comparable by construction. Structure &mdash; what fraction of those sim entries becomes shared and linked &mdash; is Figure&nbsp;3.</caption>
<thead><tr><th>backend</th><th>sediment</th><th>sim</th><th>total</th></tr></thead>
<tbody>
<tr class="grp"><td colspan="4">Three Kingdoms (三国演义) &mdash; fiction, 80 rounds, 6,052 source events</td></tr>
{scale_rows('g80', S)}
<tr class="grp"><td colspan="4">Russia&ndash;Ukraine &mdash; real world, 40 rounds, 1,533 source events</td></tr>
{scale_rows('ru40', RU)}
<tr class="grp"><td colspan="4">Red Chamber (红楼梦) &mdash; fiction, 80 rounds, 6,506 source events</td></tr>
{scale_rows('rc80', RC)}
<tr class="grp"><td colspan="4">Hamlet &mdash; fiction, 40 rounds, 1,135 source events</td></tr>
{scale_rows('hl40', HL)}
</tbody></table></div>
<p><b>Two columns, two effects.</b> The sediment column is consensus compression applied to the seeded history, and its multiplier is a property of the <i>world</i> rather than of the mechanism: the per-witness fan-out is 3.3&times; in Three Kingdoms, 4.1&ndash;5.7&times; in Red Chamber, 5.5&ndash;9.4&times; in Russia&ndash;Ukraine and 4.7&ndash;6.2&times; in Hamlet, tracking the average number of witnesses per event, which a war room with institutional spokespeople maximizes and a two-hander chamber drama minimizes. The sim column is the same effect measured over events the simulation itself generated, at rates of roughly 12 (Three Kingdoms), 20 (Russia&ndash;Ukraine), 5 (Red Chamber) and 4 (Hamlet) consensus entries per round. Everything else in &sect;5 is computed over the sim column only.</p>

<figure>
  <img src="{IMG['struct_all']}" alt="Consensus sharing and linking across the four worlds">
  <figcaption><b>Figure 3. Structure of the consensus store, all four worlds.</b> Share of consensus sim memories that are <i>shared</i> (multi-owner, i.e. produced by an equivalence merge) and <i>linked</i> (carrying affiliated edges). Only consensus is plotted because the three per-agent baselines sit at 0% on both measures in every world &mdash; they have no cross-agent rows to merge and no deposit-siblings to link, so the columns measure capabilities they lack architecturally rather than parameters they tuned differently. Linking is near-total everywhere (94&ndash;99%) because auto-affiliation fires on every compound deposit; sharing varies with the world (14&ndash;26%) and with horizon (&sect;5.5).</figcaption>
</figure>

<h4>5.1.1 &nbsp;Three Kingdoms (三国演义)</h4>

<p><b>Discussion.</b> Two readings matter here. First, the footprint gap is <i>mechanistic</i>, not behavioral: all four backends receive the same actions and atomize identically, so the 481-entry spread between consensus and the largest baseline is exactly the number of times the equivalence judge folded one agent&rsquo;s record into another&rsquo;s &mdash; each fold is a deduplicated witness (P1). Second, the structural columns are all-or-nothing by design: per-agent stores have no cross-agent rows to merge and no deposit-siblings to link, so the 19% / 97% columns measure capabilities the baselines lack architecturally, not parameters they tuned differently.</p>
<p>Merged records are precisely the cross-viewpoint deduplication the mechanism targets &mdash; {S['n_3plus']} memories carry three or more witnesses (maximum {S['max_owners']}):</p>
<div class="quote">""" + "<br>\n".join(
    f"<b>owners = [{owners_zh(e['owners'])}]</b> &nbsp;{quote_memory(e['text'])}" for e in mex[:3]
) + f"""</div>

<h4>5.1.2 &nbsp;Russia&ndash;Ukraine</h4>

<p><b>Discussion.</b> The same two readings hold at one eighth the horizon: the 19&ndash;30% footprint gap is again exactly the number of equivalence-judge folds, and the structural columns remain all-or-nothing &mdash; 0% for every per-agent baseline. What is new is the real-world flavor of the folds: equivalence merges a <i>person&rsquo;s</i> record into their <i>institution&rsquo;s</i> &mdash; the same mechanism that fuses two officers&rsquo; views of one battle fuses a spokesperson&rsquo;s statement with its organization&rsquo;s record of it.</p>
<p>Merged records again pair one event seen from two sides &mdash; characteristically a person and their institution:</p>
<div class="quote"><b>owners = [guterres, un]</b> &nbsp;&ldquo;Ant&oacute;nio Guterres at UN Headquarters in New York asked the United Nations to assemble a mediation team comprising DPA, OCHA, WFP, UN Political Affairs, and UN Legal to support renewal of the Black Sea grain agreement.&rdquo;<br>
<b>owners = [podolyak, ukrainian_government]</b> &nbsp;&ldquo;Mykhailo Podolyak reported that overnight Russian drone strikes struck Dnipropetrovsk Oblast.&rdquo;<br>
<b>owners = [kremlin, sobyanin]</b> &nbsp;&ldquo;Moscow Mayor Sergey Sobyanin requested authorization to release public instructions to Moscow residents.&rdquo;</div>

<h4>5.1.3 &nbsp;Red Chamber (红楼梦)</h4>

<p><b>Discussion.</b> Red Chamber is where the two claims of &sect;5.1 can be watched separating in time, because it was run at four horizons. Structure was already complete at ten rounds (13% shared, 87% linked, baselines 0%); footprint was not &mdash; the four backends then sat at 62&ndash;98 entries with consensus not the smallest, within run-to-run variance. From forty rounds on consensus is lowest and stays lowest, and the gap holds as both sides grow: 216 vs 379&ndash;492 at forty, 338 vs 625&ndash;683 at sixty, {RCC['sim_new']} vs {RC['generative_agents']['sim_new']}&ndash;{RC['g_memory']['sim_new']} at eighty &mdash; a {round(100-100*RCC['sim_new']/RC['g_memory']['sim_new'])}% reduction against the largest. Sharing rises along the same curve and flattens as it saturates &mdash; 13%&rarr;20%&rarr;23%&rarr;{RCC['sh_pct']}% &mdash; while multi-witness merges keep accumulating: {RC['n_3plus']} entries carry three or more witnesses (17 at sixty, nine at forty, three at ten), the deepest still the banquet where Grandmother Jia (贾母) keeps Baoyu (宝玉), Daiyu (黛玉) and Baochai (宝钗) by her side, co-owned by {RC['max_owners']}. The ordering is the point: the structural properties are architectural and appear immediately, whereas the footprint advantage is a <i>compounding</i> effect that needs enough repeated witnessing to overcome noise. A household world reaches that point later than a war does, because fewer people witness each event.</p>
<p>Merged records in the household world fold family witnesses of one scene:</p>
<div class="quote">""" + "<br>\n".join(
    f"<b>owners = [{owners_zh(e['owners'])}]</b> &nbsp;{quote_memory(e['text'])}" for e in rc_mex[:3]
) + f"""</div>


<h4>5.1.4 &nbsp;Hamlet</h4>

<p><b>Discussion.</b> Sixteen agents are enough. Consensus writes {HLC['sim_new']} entries against {HL['generative_agents']['sim_new']}&ndash;{HL['collaborative']['sim_new']}, with {HLC['sh_pct']}% shared and {HLC['aff_pct']}% linked &mdash; the highest sharing rate of any world at any horizon, in the smallest one tested. Run at three horizons, it compounds like the others: sharing goes 19%&rarr;26%&rarr;{HLC['sh_pct']}% at twenty, thirty and forty rounds, and three-witness merges appear at thirty (the players&rsquo; troupe beginning the performance, owned by the First Player, the Prologue and Guildenstern together) where every merge at twenty had been a strict pair. Depth still lags the larger worlds ({HL['n_3plus']} entries with three or more witnesses, against {S['n_3plus']} in Three Kingdoms and {RC['n_3plus']} in Red Chamber), and the reason is the play&rsquo;s staging rather than the mechanism&rsquo;s reach: Shakespeare writes in two-person exchanges &mdash; the sentinels on the battlements, Laertes and Polonius, Rosencrantz with Guildenstern &mdash; and merge depth tracks how many people the world puts in a room together. The play-within-a-play is the one scene that assembles an audience, and it is exactly where the three-way merges appear.</p>
<p>The pairs the mechanism finds are the play&rsquo;s own dyads:</p>
<div class="quote">""" + "<br>\n".join(
    f"<b>owners = [{owners_zh(e['owners'])}]</b> &nbsp;{quote_memory(e['text'])}" for e in hl_mex[:3]
) + f"""</div>

<h3>5.2 &nbsp;Growth and operation latency</h3>
<p>The footprint gap of Table 1 accumulates round by round, and its price is paid at write time. We show both sides for each scenario.</p>

<h4>5.2.1 &nbsp;Three Kingdoms (三国演义)</h4>
<figure class="two">
  <img src="{IMG['gtotal']}" alt="System memory growth per round">
  <img src="{IMG['gagents']}" alt="Per-agent memory growth per round">
  <figcaption><b>Figure 4. Memory growth &mdash; Three Kingdoms (三国演义) (80 rounds).</b> Left: cumulative sim-generated entries per round for all four backends (reconstructed from each entry&rsquo;s creation round under the same sim-only accounting as Table 1) &mdash; consensus stays lowest throughout and the gap widens with horizon, the per-round view of the merge folding witnesses together. Right: per-agent owned memories per round in the consensus run (top 6 agents labeled; the rest gray) &mdash; memory concentrates on the characters carrying the active plotlines (Xu Shu 徐庶 leads with 132), while merges let one event&rsquo;s record count toward every witness&rsquo;s curve.</figcaption>
</figure>
<p><b>Discussion.</b> The system-level curves separate almost from the start and diverge steadily &mdash; the merge saves entries at a roughly constant <i>rate</i>, so its absolute savings compound with horizon rather than saturating; there is no sign of the gap closing by round 80. The per-agent curves show the same mechanism from the individual&rsquo;s side: growth is stair-stepped (a burst when a character is at the center of a plotline, plateaus when off-stage), and the ranking tracks narrative centrality rather than raw talkativeness &mdash; Xu Shu (徐庶) leads because the Xu Shu recruitment arc dominates the middle game, and every merge credits a shared event to all of its witnesses&rsquo; curves at once.</p>

<figure>
  <img src="{IMG['latency']}" alt="Memory-operation latency vs round">
  <figcaption><b>Figure 5. Memory-operation latency &mdash; Three Kingdoms (三国演义) (80 rounds).</b> Mean wall-clock seconds per <code>remember</code> (left) and <code>recall</code> (right) call, 5-round bins, all four backends. Rounds 61&ndash;80 are instrumented live in the kernel; rounds 1&ndash;60 are measured by replaying each stage&rsquo;s logged operations (same agent, text/query, and order) against the exact store state that stage started from &mdash; a measurement of the same workload, not a synthesis (dotted line marks the boundary; first-stage GA/G-Memory replay stores lack their prime by-products, &asymp;3&ndash;5% of rows).</figcaption>
</figure>
<p><b>Discussion.</b> The two panels show where each design pays. <i>Writes are LLM-bound:</i> every backend pays the shared atomization call, on top of which Generative-Agents adds a per-atom importance call (the most expensive line, 35&ndash;75s) and consensus adds the equivalence judge (26&ndash;57s), while G-Memory and collaborative write for 10&ndash;25s with no per-deposit reasoning beyond atomization. <i>Reads are vector-bound and cheap everywhere</i> (&le;1.4s), and &mdash; notably &mdash; consensus recall is the <b>cheapest</b> of the four (&asymp;0.35s) despite returning &asymp;28 additional linked memories per call: auto-expansion is plain row lookup, whereas G-Memory&rsquo;s bi-level retrieval pays for graph traversal with extra vector queries (0.7&ndash;1.1s). Neither panel trends upward over 80 rounds: at this scale, store growth (&asymp;7k&ndash;22k rows) does not yet move per-call latency, so the consensus premium is a roughly constant per-write tax &mdash; the price of P1&rsquo;s deduplication &mdash; paid where agents are least latency-sensitive.</p>

<h4>5.2.2 &nbsp;Russia&ndash;Ukraine</h4>
<figure>
  <img src="{IMG['ru_growth']}" alt="RU memory growth">
  <figcaption><b>Figure 6. Memory growth &mdash; Russia&ndash;Ukraine (40 rounds).</b> Left: cumulative sim-generated entries per round for all four backends under the same sim-only accounting as Table 1. Right: per-agent owned memories per round in the consensus run (top agents labeled; the rest gray).</figcaption>
</figure>
<figure>
  <img src="{IMG['ru_latency']}" alt="RU memory-operation latency">
  <figcaption><b>Figure 7. Memory-operation latency &mdash; Russia&ndash;Ukraine (40 rounds).</b> Mean wall-clock seconds per <code>remember</code> (left) and <code>recall</code> (right) call, 2-round bins, all four backends; every round is instrumented live in the kernel.</figcaption>
</figure>
<p><b>Discussion.</b> Both figures replay the Three Kingdoms dynamics at a shorter horizon. The system curves separate from round ~3 with consensus lowest and the gap widening, and per-agent growth again concentrates on the situation&rsquo;s protagonists. The latency ordering of Figure 5 reproduces: writes are LLM-bound (Generative-Agents&rsquo; per-atom importance calls most expensive, consensus paying the equivalence-judge tax), while reads are vector-bound and sub-second for all four backends, with consensus recall cheapest despite auto-expansion.</p>

<h4>5.2.3 &nbsp;Red Chamber (红楼梦)</h4>
<figure>
  <img src="{IMG['rc_growth']}" alt="RC memory growth">
  <figcaption><b>Figure 8. Memory growth &mdash; Red Chamber (红楼梦) (80 rounds).</b> Left: cumulative sim-generated entries per round for all four backends under the same sim-only accounting as Table 1. Right: per-agent owned memories per round in the consensus run (top agents labeled; the rest gray).</figcaption>
</figure>
<figure>
  <img src="{IMG['rc_latency']}" alt="RC memory-operation latency">
  <figcaption><b>Figure 9. Memory-operation latency &mdash; Red Chamber (红楼梦) (80 rounds).</b> Mean wall-clock seconds per <code>remember</code> (left) and <code>recall</code> (right) call, 2-round bins, all four backends; every round is instrumented live in the kernel.</figcaption>
</figure>
<p><b>Discussion.</b> The domestic world writes more slowly than either other scenario (~{RCC['sim_new']//80} consensus entries per round against ~20 in Russia&ndash;Ukraine) &mdash; garden conversation generates fewer memory-worthy events than a war &mdash; and the curves that interleaved through the first ten rounds separate cleanly thereafter, consensus lowest and the gap holding to eighty rounds, exactly as in Figures 4 and 6. Per-agent growth concentrates on the household&rsquo;s centers of gravity (Grandmother Jia 贾母, Wang Xifeng 王熙凤, Jia Baoyu 贾宝玉 and the banquet guests). The read side reproduces both other worlds: consensus recall is cheapest despite auto-expansion returning &asymp;{RCE['items']//max(RCE['recalls'],1)} linked memories per call, while G-Memory&rsquo;s bi-level retrieval pays for graph traversal with extra vector queries.</p>

<h4>5.2.4 &nbsp;Hamlet</h4>
<figure>
  <img src="{IMG['hl_growth']}" alt="HL memory growth">
  <figcaption><b>Figure 10. Memory growth &mdash; Hamlet (40 rounds).</b> Left: cumulative sim-generated entries per round for all four backends under the same sim-only accounting as Table 1. Right: per-agent owned memories per round in the consensus run (top agents labeled; the rest gray).</figcaption>
</figure>
<figure>
  <img src="{IMG['hl_latency']}" alt="HL memory-operation latency">
  <figcaption><b>Figure 11. Memory-operation latency &mdash; Hamlet (40 rounds).</b> Mean wall-clock seconds per <code>remember</code> (left) and <code>recall</code> (right) call, 2-round bins, all four backends; every round is instrumented live in the kernel.</figcaption>
</figure>
<p><b>Discussion.</b> The smallest world writes at a rate between the other two fictions (~{HLC['sim_new']//40} consensus entries per round), and the four curves separate early with consensus lowest &mdash; at this cast size a single merge is a large fraction of a round's writes, so the gap opens without the compounding Red Chamber needed. Latency is dominated by per-call LLM cost exactly as elsewhere; with only {HLE['recalls']} recalls over the whole run the read-side curves are too sparse to rank backends, and we read nothing into their ordering here.</p>

<h3>5.3 &nbsp;Continuation quality</h3>
<p>Every world is judged the same way. Three of the four metrics are read from the run&rsquo;s <i>rendered screenplay</i> rather than its raw event log (&sect;A.6 prints all four screenplays). The screenplay is the run&rsquo;s own events dramatized under a no-invention constraint, which buys two things the raw log cannot give: one language per world, whatever the agents happened to emit, and a text an order of magnitude smaller than the transcript, so the judge reads a coherent whole instead of a sampled fragment. Each metric is scored three times and reported mean&plusmn;1 std:</p>
<ul>
<li><b>grounding</b> &mdash; fraction of the run&rsquo;s own events consistent with the world&rsquo;s canon.</li>
<li><b>trajectory</b> &mdash; agreement of ten principals&rsquo; arcs with arcs extracted from a held-out span: Three Kingdoms chapters&nbsp;41&ndash;60, Red Chamber chapters&nbsp;41&ndash;80, Russia&ndash;Ukraine the timeline from 2024-05, Hamlet Acts&nbsp;4&ndash;5.</li>
<li><b>narrative</b> &mdash; coherence / distinctiveness / drama / fidelity, 1&ndash;5.</li>
<li><b>goal pursuit</b> &mdash; of the actions a principal took, the fraction that plausibly serve a goal that was on <i>its own</i> goal stack at that moment. This one is read from the event log, not the screenplay, because goal management is internal: pushing a goal is not a dramatizable beat and never reaches the script. Pursuit is scored, not achievement &mdash; an agent that works doggedly at a goal it never reaches should score high, since a faithful tragedy requires goals to fail.</li>
</ul>

<p><b>No backend wins this.</b> Of the sixteen world-metric cells, consensus is the best-scoring backend in {quality_ledger()[0]} &mdash; {quality_ledger()[3]} &mdash; and trails the leader in the rest by {quality_ledger()[1]} on the 0&ndash;1 metrics and {quality_ledger()[2]} on the 1&ndash;5 narrative scale. Those margins are of the same order as the spread across three scorings of the <i>same</i> text. We report this as a wash rather than as a win: compression neither buys judged quality nor costs it, and the case for consensus is made by the structural results of &sect;5.1, not here.</p>
<p><b>Goal pursuit saturates.</b> All sixteen cells land between {min(_GOALS):.2f} and {max(_GOALS):.2f}: whatever memory sits underneath, agents do the things they said they were going to do. The reason is structural rather than flattering &mdash; the goal stack is part of every agent&rsquo;s prompt and the kernel prompts an agent with an empty stack to push a goal before acting, so across all four worlds only {min(_GPCT):.1f}&ndash;{max(_GPCT):.1f}% of actions are taken with no goal held at all. The metric therefore certifies that the agent loop works and separates nothing; we report it because a memory mechanism <i>could</i> have broken it &mdash; an agent that cannot recall what it was doing drifts off its own goals &mdash; and none of the four does.</p>
<div class="tw"><table>
<caption><b>Table 2. Who leads each metric, by world.</b> The best-scoring backend on each metric with its mean, and consensus&rsquo;s own mean in parentheses when it is not the leader. No backend leads everywhere, and no world has the same leader on all three metrics; leads are of the order of the &plusmn;1 std whiskers in Figures&nbsp;12&ndash;15.</caption>
<thead><tr><th>world</th><th>grounding</th><th>trajectory</th><th>narrative</th><th>goal pursuit</th></tr></thead>
<tbody>
{wins_table()}
</tbody></table></div>

<h4>5.3.1 &nbsp;Three Kingdoms (三国演义)</h4>
<figure>
  <img src="{IMG['quality']}" alt="Three Kingdoms continuation quality comparison">
  <figcaption><b>Figure 12. Continuation quality &mdash; Three Kingdoms (三国演义) (80 rounds).</b> Grounding (fraction of the run&rsquo;s own events judged canon-consistent), trajectory (agreement of ten principals&rsquo; arcs with reference arcs from held-out chapters 41&ndash;60), narrative (judged coherence/drama/fidelity, 1&ndash;5), and goal pursuit (fraction of the agent&rsquo;s actions serving a goal it had itself pushed); bars are means over 3 independent LLM scorings, whiskers &plusmn;1 std. The first three panels are scored from the rendered screenplay, the fourth from the event log. Consensus leads narrative ({Q['consensus']['agg']['narr']['mean']:.2f}) and shares the top of trajectory; its grounding sits at the bottom of a {min(Q[k]['agg']['grnd']['mean'] for k in Q):.2f}&ndash;{max(Q[k]['agg']['grnd']['mean'] for k in Q):.2f} band.</figcaption>
</figure>

<h4>5.3.2 &nbsp;Russia&ndash;Ukraine</h4>
<figure>
  <img src="{IMG['ru_quality']}" alt="Russia-Ukraine continuation quality comparison">
  <figcaption><b>Figure 13. Continuation quality &mdash; Russia&ndash;Ukraine (40 rounds).</b> Same protocol against the real conflict: grounding judges each event for real entities, correct roles and allegiances and plausible dynamics; trajectory compares ten principals&rsquo; arcs against the held-out timeline from 2024-05; narrative is the same rubric. Grounding is uniformly high ({min(QR[k]['agg']['grnd']['mean'] for k in QR):.2f}&ndash;{max(QR[k]['agg']['grnd']['mean'] for k in QR):.2f}) &mdash; institutional actors reciting real capabilities rarely fabricate &mdash; and consensus leads trajectory ({QR['consensus']['agg']['traj']['mean']:.2f} against {min(QR[k]['agg']['traj']['mean'] for k in QR if k!='consensus'):.2f}&ndash;{max(QR[k]['agg']['traj']['mean'] for k in QR if k!='consensus'):.2f}) while scoring last on narrative.</figcaption>
</figure>

<h4>5.3.3 &nbsp;Red Chamber (红楼梦)</h4>
<figure>
  <img src="{IMG['rc_quality']}" alt="Red Chamber continuation quality comparison">
  <figcaption><b>Figure 14. Continuation quality &mdash; Red Chamber (红楼梦) (80 rounds).</b> Same protocol, held-out chapters 41&ndash;80; because that span is 313k characters of Chinese &mdash; past the judge&rsquo;s context window &mdash; the reference arcs are extracted chapter-group by chapter-group and condensed per character. This is the one world where consensus leads nothing: collaborative is best on all three metrics ({QC['collaborative']['agg']['grnd']['mean']:.2f} / {QC['collaborative']['agg']['traj']['mean']:.2f} / {QC['collaborative']['agg']['narr']['mean']:.2f} against consensus&rsquo;s {QC['consensus']['agg']['grnd']['mean']:.2f} / {QC['consensus']['agg']['traj']['mean']:.2f} / {QC['consensus']['agg']['narr']['mean']:.2f}).</figcaption>
</figure>

<h4>5.3.4 &nbsp;Hamlet</h4>
<figure>
  <img src="{IMG['hl_quality']}" alt="Hamlet continuation quality comparison">
  <figcaption><b>Figure 15. Continuation quality &mdash; Hamlet (40 rounds).</b> Same protocol, held-out Acts&nbsp;4&ndash;5. Hamlet is the smallest run in the set &mdash; 117 beats in 12 scenes &mdash; so the judge extracts about {QH['consensus']['agg']['grnd_n']:.0f} events per scoring against 60&ndash;80 in the other worlds, and every number here rests on less evidence. Consensus and Generative-Agents track the principals&rsquo; arcs markedly better ({QH['consensus']['agg']['traj']['mean']:.2f} / {QH['generative_agents']['agg']['traj']['mean']:.2f}) than G-Memory and collaborative ({QH['g_memory']['agg']['traj']['mean']:.2f} / {QH['collaborative']['agg']['traj']['mean']:.2f}) &mdash; the largest single gap anywhere in &sect;5.3.</figcaption>
</figure>

<p><b>Discussion.</b> Three things are worth separating. First, the metrics that <i>should</i> be insensitive to memory architecture are: grounding sits in a narrow band in every world ({min(Q[k]['agg']['grnd']['mean'] for k in Q):.2f}&ndash;{max(Q[k]['agg']['grnd']['mean'] for k in Q):.2f} in Three Kingdoms, {min(QR[k]['agg']['grnd']['mean'] for k in QR):.2f}&ndash;{max(QR[k]['agg']['grnd']['mean'] for k in QR):.2f} in Russia&ndash;Ukraine) because it is mostly a property of the persona and canon material every backend shares. Second, where consensus does lead it leads on <i>consistency over time</i> &mdash; {quality_ledger()[3]} &mdash; which is what one witness-merged record per event should buy: agents act on the same premises rather than on N drifting paraphrases. Third, and against us, Red Chamber reverses this cleanly: collaborative leads every screenplay metric there, and consensus&rsquo;s narrative in Russia&ndash;Ukraine is last. We do not have a mechanism-level account of either, and with three scorings per cell we do not claim one; the honest reading is that quality differences at this scale are noise around a common mean, while the structural differences of Figure&nbsp;3 are order-of-magnitude and deterministic. The design argument for consensus rests on structure and footprint, not on these bars.</p>
<p style="font-size:14px;color:var(--muted)">One scoring caveat, since it bit us: a scoring repeat whose event extraction comes back empty is a harness failure, not a score of zero. Such repeats are retried and, if still empty, dropped from the mean rather than averaged in &mdash; an earlier pass reported a spurious 0.59&plusmn;0.42 for one cell on the strength of a single empty extraction.</p>

<h3>5.4 &nbsp;Case study: three graphs over each world</h3>
<p>Each world&rsquo;s consensus run induces the same three graphs: the <b>interaction graph</b> (who talks to whom), the <b>affiliation graph</b> (which memories are linked), and the <b>ownership relation</b> (who owns which memories). For each scenario we show the three layers, then all three in one view, then quantify their pairwise alignment.</p>

<h4>5.4.1 &nbsp;Three Kingdoms (三国演义)</h4>

<h5>The three layers <span style="font-family:var(--sans);font-size:12px;color:var(--faint);font-weight:400">&mdash; interactive: drag to pan, scroll to zoom, hover for details, drag nodes to rearrange</span></h5>
<figure>
  <div class="ig" id="ig-interaction" style="height:520px"></div>
  <figcaption><b>Figure 16a. The interaction graph (interactive) &mdash; Three Kingdoms (三国演义).</b> Nodes are the complete active-character roster (silent characters parked on the bottom row); edge width is conversation frequency; colors are detected communities, which recover the canonical factions without being told about them. Hover a character for its name, community, and conversation volume; click to highlight its neighbourhood.</figcaption>
</figure>
<figure>
  <div class="ig" id="ig-affiliation" style="height:600px"></div>
  <figcaption><b>Figure 16b. The full memory-affiliation graph (interactive) &mdash; Three Kingdoms (三国演义).</b> Every sim-generated memory is a node ({R['MO']['link_n']} affiliated edges; components colored, singletons gray; shared multi-owner memories drawn larger with a red ring). <b>Hover any node to read the memory&rsquo;s full text and its owners</b> &mdash; each cluster is one plotline&rsquo;s linked pieces, assembled bottom-up by auto-affiliation and merging.</figcaption>
</figure>
<figure>
  <div class="ig" id="ig-heatmap" style="height:620px"></div>
  <figcaption><b>Figure 16. The ownership layer (interactive) &mdash; Three Kingdoms (三国演义).</b> Pairwise co-owned memory counts over the complete roster, ordered by interaction community. Hover a cell for the pair and its count. Non-zero cells concentrate in the diagonal blocks &mdash; agents share memories with their own faction &mdash; and each strong cell corresponds to consensus merges of jointly experienced events.</figcaption>
</figure>

<h5>All three layers in one view</h5>
<figure>
  <div class="ig" id="ig-trilayer" style="height:560px"></div>
  <figcaption><b>Figure 17. All three layers in one view (interactive) &mdash; Three Kingdoms (三国演义).</b> Agents on the top row (circles = characters, squares = passive memory owners) with conversation arcs above (blue; width = frequency); memories on the bottom row with affiliation arcs below (green when the linked memories share a witness, gray when disjoint); ownership as vertical lines, red when the memory is shared. <b>Hover an agent</b> to isolate its conversations and owned memories; <b>hover a memory</b> (&starf; = merged multi-owner) to read its text and see its links. Shared structure sits where conversation sits.</figcaption>
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
  <figcaption><b>Figure 18. Each pairwise relation as a with/without pair of distributions &mdash; Three Kingdoms (三国演义)</b> (columns share x and y axes; log density so tails read against the mass at zero; top row = pairs with the relation, bottom = without). Left: owned-memory-set Jaccard for talking vs non-talking agent pairs. Middle: owner-set Jaccard for memory pairs with vs without an affiliated edge. Right: cross-set affiliated-edge counts for talking vs non-talking agent pairs. In all three, the without-group concentrates at zero and the with-group carries the entire tail.</figcaption>
</figure>
<p><b>Synthesis.</b> The three alignments are not three separate facts but one: the consensus mechanisms transcribe the story&rsquo;s social structure into the memory substrate. Conversations are where shared experience happens, so merges (ownership overlap) land on talking pairs; deposits narrate the conversation an agent just had, so affiliation clusters coincide with events and their witnesses; and cross-agent links therefore run along conversation edges. In a per-agent store all three relations are identically zero &mdash; the substrate cannot express them &mdash; which is why the case study is run on the consensus backend alone.</p>

<h4>5.4.2 &nbsp;Russia&ndash;Ukraine</h4>
<h5>The three layers <span style="font-family:var(--sans);font-size:12px;color:var(--faint);font-weight:400">&mdash; interactive: drag to pan, scroll to zoom, hover for details, drag nodes to rearrange</span></h5>
<figure>
  <div class="ig" id="ig-ru-interaction" style="height:480px"></div>
  <figcaption><b>Figure 19a. The interaction graph (interactive) &mdash; Russia&ndash;Ukraine.</b> 65 entities; community detection recovers the conflict&rsquo;s blocs &mdash; the Kyiv government cluster, the Moscow cluster, and the international mediators &mdash; without being told about them.</figcaption>
</figure>
<figure>
  <div class="ig" id="ig-ru-affiliation" style="height:520px"></div>
  <figcaption><b>Figure 19b. The full memory-affiliation graph (interactive) &mdash; Russia&ndash;Ukraine.</b> {RUC['sim_new']} sim memories, {RUR['MO']['link_n']} affiliated edges; hover any node to read the memory and its owners. Clusters are single storylines (a strike wave, a negotiation) assembled by auto-affiliation.</figcaption>
</figure>
<figure>
  <div class="ig" id="ig-ru-heatmap" style="height:560px"></div>
  <figcaption><b>Figure 19. The ownership layer (interactive) &mdash; Russia&ndash;Ukraine.</b> Pairwise co-owned memory counts over the Russia&ndash;Ukraine roster, ordered by interaction community. Hover a cell for the pair and its count. As in Figure 16, non-zero cells sit on pairs that jointly experienced events &mdash; here the strongest cells are spokesperson&harr;institution pairs, the real-world counterpart of faction comrades.</figcaption>
</figure>
<h5>All three layers in one view</h5>
<figure>
  <div class="ig" id="ig-ru-trilayer" style="height:520px"></div>
  <figcaption><b>Figure 20. All three layers in one view (interactive) &mdash; Russia&ndash;Ukraine.</b> Conversations above, ownership between, affiliation below; merged memories (&starf;) hang between the parties that share them.</figcaption>
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
  <figcaption><b>Figure 21. Each pairwise relation as a with/without pair of distributions &mdash; Russia&ndash;Ukraine</b> (same format as Figure 18). The structural signature transfers intact to a real-world scenario at one eighth the horizon.</figcaption>
</figure>

<h4>5.4.3 &nbsp;Red Chamber (红楼梦)</h4>
<h5>The three layers <span style="font-family:var(--sans);font-size:12px;color:var(--faint);font-weight:400">&mdash; interactive: drag to pan, scroll to zoom, hover for details, drag nodes to rearrange</span></h5>
<figure>
  <div class="ig" id="ig-rc-interaction" style="height:480px"></div>
  <figcaption><b>Figure 22a. The interaction graph (interactive) &mdash; Red Chamber (红楼梦).</b> 31 conversing characters; community detection recovers the household&rsquo;s social circles &mdash; the Grandmother Jia (贾母) banquet orbit, the young poets&rsquo; circle, and the stewards &mdash; without being told about them.</figcaption>
</figure>
<figure>
  <div class="ig" id="ig-rc-affiliation" style="height:520px"></div>
  <figcaption><b>Figure 22b. The full memory-affiliation graph (interactive) &mdash; Red Chamber (红楼梦).</b> {RCC['sim_new']} sim memories, {RCR['MO']['link_n']} affiliated edges; hover any node to read the memory and its owners. Clusters are single storylines assembled by auto-affiliation.</figcaption>
</figure>
<figure>
  <div class="ig" id="ig-rc-heatmap" style="height:560px"></div>
  <figcaption><b>Figure 22. The ownership layer (interactive) &mdash; Red Chamber (红楼梦).</b> Pairwise co-owned memory counts over the Red Chamber roster, ordered by interaction community. Hover a cell for the pair and its count. As in Figure 16, non-zero cells sit on pairs that jointly experienced scenes &mdash; here the strongest cells are kin who attended the same banquet, the domestic counterpart of faction comrades.</figcaption>
</figure>
<h5>All three layers in one view</h5>
<figure>
  <div class="ig" id="ig-rc-trilayer" style="height:520px"></div>
  <figcaption><b>Figure 23. All three layers in one view (interactive) &mdash; Red Chamber (红楼梦).</b> Conversations above, ownership between, affiliation below; merged memories (&starf;) hang between the parties that share them.</figcaption>
</figure>
<h5>Pairwise alignment of the layers</h5>
<div class="rel"><h4><span class="rx">A&harr;O</span> Agents who talk own overlapping memories <span class="stat">({RCR['AO']['talk_mean']:.3f} vs {RCR['AO']['non_mean']:.4f}, {RCR['AO']['talk_mean']/max(RCR['AO']['non_mean'],1e-9):.0f}&times;)</span></h4>
<p>Talking pairs overlap in memory at {RCR['AO']['talk_mean']:.3f} against {RCR['AO']['non_mean']:.4f} for silent pairs &mdash; the household&rsquo;s conversation network and its memory network coincide from the first ten rounds.</p></div>
<div class="rel"><h4><span class="rx">M&harr;O</span> Linked memories have the same witnesses <span class="stat">({RCR['MO']['link_mean']:.2f} vs {RCR['MO']['non_mean']:.2f})</span></h4>
<p>Affiliated pairs share owners at Jaccard {RCR['MO']['link_mean']:.2f} against {RCR['MO']['non_mean']:.2f} for random pairs &mdash; the same order-of-magnitude alignment as both other worlds.</p></div>
<div class="rel"><h4><span class="rx">A&harr;M</span> Cross-agent memory links follow conversations <span class="stat">({RCR['AM']['talk_mean']:.2f} vs {RCR['AM']['non_mean']:.3f} edges)</span></h4>
<p>Talking pairs average {RCR['AM']['talk_mean']:.2f} affiliated edges between their memory sets against {RCR['AM']['non_mean']:.3f} for non-talking pairs &mdash; the separation sharpens with the horizon (2.09 vs 0.15 at ten rounds).</p></div>
<figure>
  <img src="{IMG['rc_relpanels']}" alt="RC relationship panels">
  <figcaption><b>Figure 24. Each pairwise relation as a with/without pair of distributions &mdash; Red Chamber (红楼梦)</b> (same format as Figure 18). The structural signature holds in a third world with a markedly different social topology.</figcaption>
</figure>

<h4>5.4.4 &nbsp;Hamlet</h4>
<h5>The three layers <span style="font-family:var(--sans);font-size:12px;color:var(--faint);font-weight:400">&mdash; interactive: drag to pan, scroll to zoom, hover for details, drag nodes to rearrange</span></h5>
<figure>
  <div class="ig" id="ig-hl-interaction" style="height:440px"></div>
  <figcaption><b>Figure 25a. The interaction graph (interactive) &mdash; Hamlet.</b> 15 conversing characters, 22 pairs &mdash; the whole court in one castle. At this size the graph is the cast list rather than a community structure to be recovered.</figcaption>
</figure>
<figure>
  <div class="ig" id="ig-hl-affiliation" style="height:480px"></div>
  <figcaption><b>Figure 25b. The full memory-affiliation graph (interactive) &mdash; Hamlet.</b> {HLC['sim_new']} sim memories, {HLR['MO']['link_n']} affiliated edges; hover any node to read the memory and its owners. Clusters are single scenes assembled by auto-affiliation.</figcaption>
</figure>
<figure>
  <div class="ig" id="ig-hl-heatmap" style="height:520px"></div>
  <figcaption><b>Figure 25. The ownership layer (interactive) &mdash; Hamlet.</b> Pairwise co-owned memory counts over the Hamlet roster, ordered by interaction community. Every non-zero cell is a two-person scene; the densest are the play&rsquo;s standing pairs.</figcaption>
</figure>
<h5>All three layers in one view</h5>
<figure>
  <div class="ig" id="ig-hl-trilayer" style="height:480px"></div>
  <figcaption><b>Figure 26. All three layers in one view (interactive) &mdash; Hamlet.</b> Conversations above, ownership between, affiliation below; merged memories (&starf;) hang between the parties that share them.</figcaption>
</figure>
<h5>Pairwise alignment of the layers</h5>
<div class="rel"><h4><span class="rx">A&harr;O</span> Agents who talk own overlapping memories <span class="stat">({HLR['AO']['talk_mean']:.3f} vs {HLR['AO']['non_mean']:.4f}, {HLR['AO']['talk_mean']/max(HLR['AO']['non_mean'],1e-9):.0f}&times;)</span></h4>
<p>Still the weakest separation of the four worlds, and for a structural reason: a single castle with sixteen residents has few genuinely non-interacting pairs, so the &ldquo;without&rdquo; baseline is contaminated by people who simply have not spoken <i>yet</i> &mdash; though ten more rounds widened it from 5&times; to {HLR['AO']['talk_mean']/max(HLR['AO']['non_mean'],1e-9):.0f}&times; as those pairs met.</p></div>
<div class="rel"><h4><span class="rx">M&harr;O</span> Linked memories have the same witnesses <span class="stat">({HLR['MO']['link_mean']:.2f} vs {HLR['MO']['non_mean']:.2f})</span></h4>
<p>Affiliated pairs share owners at Jaccard {HLR['MO']['link_mean']:.2f} against {HLR['MO']['non_mean']:.2f} for random pairs &mdash; the two-person scene keeps affiliated memories on nearly identical owner sets.</p></div>
<div class="rel"><h4><span class="rx">A&harr;M</span> Cross-agent memory links follow conversations <span class="stat">({HLR['AM']['talk_mean']:.2f} vs {HLR['AM']['non_mean']:.2f} edges)</span></h4>
<p>Talking pairs average {HLR['AM']['talk_mean']:.2f} affiliated edges between their memory sets against {HLR['AM']['non_mean']:.2f} for non-talking pairs &mdash; the same direction as the larger worlds at a tenth of the scale, and four times sharper than at twenty rounds.</p></div>
<figure>
  <img src="{IMG['hl_relpanels']}" alt="HL relationship panels">
  <figcaption><b>Figure 27. Each pairwise relation as a with/without pair of distributions &mdash; Hamlet</b> (same format as Figure 18). The signature survives at the smallest scale tested, with the A&harr;O panel visibly the noisiest.</figcaption>
</figure>

<h3>5.5 &nbsp;Structure compounds with horizon</h3>
<p>Shared and linked structure is not a transient: across the 20/40/60-round checkpoints, sim memories grow roughly linearly while shared memories and affiliated edges grow with them &mdash; the merge finds more cross-witness events as the story densifies.</p>

<h4>5.5.1 &nbsp;Three Kingdoms (三国演义)</h4>
<figure>
  <img src="{IMG['growth']}" alt="Growth across horizon">
  <figcaption><b>Figure 28. Consensus structure across the horizon &mdash; Three Kingdoms (三国演义).</b> Sim-memory count (left), shared multi-owner memories (middle), and affiliated edges (right) at the 20/40/60/80-round checkpoints of the same continuously-resumed run. All three grow super-linearly in usefulness even where counts grow linearly: each new shared memory raises the chance that a future deposit finds a merge partner, and each new edge widens what a single auto-expanding recall can surface.</figcaption>
</figure>

<h4>5.5.2 &nbsp;Russia&ndash;Ukraine</h4>
<p>Forty rounds in a second, structurally different world (real entities, institutional actors, English-language events, a live timeline rather than a novel) reproduce every qualitative claim of &sect;5: fewest entries, exclusive sharing and linking, the three-layer alignment, and the latency profile. The horizon effect predicted by Three Kingdoms is directly observable here: the sharing rate rose 6%&rarr;9%&rarr;{RUC['sh_pct']}% at rounds 10/20/40, three-plus-witness merges went from zero to {RU['n_3plus']}, and the deepest merge grew from two witnesses to {RU['max_owners']} &mdash; a presidential air-defense directive whose single record is co-owned by the president, his chief of staff and adviser, the interior minister, the air-force and intelligence commanders, and the security service &mdash; tracking Three Kingdoms&rsquo;s 19% at 80 rounds on the same compounding curve.</p>

<h3>5.6 &nbsp;Agents do not manage memory &mdash; mechanisms must</h3>
<p>Across all four backends and both models tested, agents issued <b>zero</b> calls to every discretionary memory-management action &mdash; linking (<code>add/set/remove_affiliated</code>), explicit link-reading (<code>get_affiliated</code>), forgetting, and revision &mdash; despite documentation, worked skill examples, and the id-free query interface. In contrast, the two mechanism-embedded operations carried everything: <code>remember</code> (with atomization, merging, auto-affiliation inside) and <code>recall</code> (with auto-expansion inside; {AE['with_expansion']}/{AE['recalls']} recalls returned linked context). We take this as a design principle for agent memory systems: <b>structure must be a side-effect of the operations agents already perform, not a task delegated to them.</b></p>

<h3>5.7 &nbsp;Ablation: which knob does the work</h3>
<p>Everything above compares consensus against other designs. This section takes consensus apart. Four cells, one factor at a time from the configuration the paper reports (merge on, FIFO short-term cache), all run on Three Kingdoms (三国演义) for 40 rounds from the same sedimented start under the same code, so only the knob differs. The published run is <i>rerun</i> here rather than reused: the reported run predates the content-language directive of &sect;A.4, and comparing against it would mix a knob with a prompt change. That rerun also serves as a replication &mdash; it lands within 1% of the published numbers ({ABLFP['on_fifo']['entries']:,} entries against 6,551, sharing {100 * ABLFP['on_fifo']['shared'] / ABLFP['on_fifo']['entries']:.0f}% against 84%), which is worth knowing given that every number in this paper comes from a single stochastic run.</p>

<figure>
  <img src="{IMG['ablation']}" alt="Ablation of the consensus backend">
  <figcaption><b>Figure 29. What each knob does &mdash; consensus on Three Kingdoms (三国演义), 40 rounds.</b> Left: entries in the whole store (sediment plus simulation) and in the simulation-written part alone. Right: the two structural properties of the simulation-written entries. Turning the merge off is the only change visible in either panel, and it moves sharing and store size while leaving linking untouched.</figcaption>
</figure>

<div class="tw"><table>
<caption><b>Table 3. One factor at a time from the published configuration.</b> Structure is deterministic, read from each run&rsquo;s own export under the same simulation-only accounting as Table&nbsp;1; grounding is LLM-judged, mean&plusmn;1 std over 3 scorings. Wall-clock is one run on one machine and is indicative only.</caption>
<thead><tr><th>merge</th><th>cache</th><th>whole store</th><th>sim entries</th><th>shared</th><th>linked</th><th>deepest merge</th><th>grounding</th><th>wall-clock</th></tr></thead>
<tbody>
{ablation_rows()}
</tbody></table></div>

<p><b>The merge is doing the work.</b> Disabling it multiplies the store by {ABLFP['off_fifo']['entries'] / ABLFP['on_fifo']['entries']:.1f}&times; ({ABLFP['off_fifo']['entries']:,} entries against {ABLFP['on_fifo']['entries']:,}), and the multiplication is concentrated in the sedimented history &mdash; {(ABLFP['off_fifo']['entries'] - ABL['off_fifo']['sim_new']) / (ABLFP['on_fifo']['entries'] - ABL['on_fifo']['sim_new']):.1f}&times; there against {ABL['off_fifo']['sim_new'] / ABL['on_fifo']['sim_new']:.2f}&times; for what the simulation itself writes &mdash; because a novel deposits one canonical event once per witness. This is the redundancy of P1 measured against its own control rather than against a different system: the same events, the same atomizer, the same agents, with only the equivalence test removed. Sharing goes to exactly zero and the deepest record falls from {ABL['on_fifo']['max_owners']} owners to one.</p>

<p><b>Sharing and linking are separable, and we had been treating them as one thing.</b> With the merge off, sharing is 0% but linking is {ABL['off_fifo']['aff_pct']}% &mdash; statistically the same as the {ABL['on_fifo']['aff_pct']}% of the published configuration. The two structures come from different mechanisms: sharing from the equivalence merge, linking from the atomizer, which mutually affiliates the pieces of one compound deposit whether or not anything is ever merged. A system that wanted the memory graph without the compression could have it, and &sect;5.4&rsquo;s three-layer alignment rests on the linking half, which the merge does not create.</p>

<p><b>The short-term cache policy is not a research variable.</b> Relevance- and hybrid-based eviction leave every structural quantity where FIFO leaves it (sharing 18&ndash;21%, linking 96%), while costing 15&ndash;19% more wall-clock, since each cached line must be embedded to be scored. They do write {ABL['on_relevance']['sim_new'] - ABL['on_fifo']['sim_new']}&ndash;{ABL['on_hybrid']['sim_new'] - ABL['on_fifo']['sim_new']} more entries, but that is agents holding different context and therefore saying different things, not a property of the memory mechanism. FIFO is reported as the default because nothing recommends the alternatives, not because they were tuned away.</p>

<p><b>Grounding does not separate on the merge.</b> The published cell scores lowest of the four ({ABL['on_fifo']['gr_m']:.2f}&plusmn;{ABL['on_fifo']['gr_s']:.2f} against {ABL['off_fifo']['gr_m']:.2f}&plusmn;{ABL['off_fifo']['gr_s']:.2f} with the merge off), which read alone would suggest that merging costs factual consistency &mdash; plausibly, since a merge keeps the shorter of two equivalent texts and discards whatever detail the longer one carried. But the two cells that keep the merge and only change the cache score {ABL['on_relevance']['gr_m']:.2f} and {ABL['on_hybrid']['gr_m']:.2f}, level with the merge-off cell. The variation tracks the cache knob rather than the merge knob, which at three scorings per cell is what noise looks like. We therefore claim no grounding effect for the merge; testing the keep-the-shorter-text policy properly needs its own cell, which we have not run.</p>

<h2><span class="n">6</span> Discussion and Limitations</h2>
<p><b>What consensus buys.</b> Under equal granularity and sim-only accounting, consensus dominates structurally &mdash; fewest entries, all sharing, all graph structure &mdash; and buys this at no measurable cost in judged quality: across four worlds and three metrics the four backends land within noise of one another, with no backend leading everywhere and consensus leading three cells of twelve (&sect;5.3). The three-layer alignment argues the structure is meaningful: it recovers the story&rsquo;s social organization from the memory substrate alone.</p>
<p><b>Limitations.</b> (i) Quality metrics are LLM-judged and noisy; we report 3-scoring means with std, but ranking claims beyond narrative should be treated cautiously. (ii) Results cover one scenario (Three Kingdoms) and one 60-round horizon; the protocol ports directly to other sedimented worlds and longer runs (checkpoints exist), but those runs remain future work. (iii) Auto-expansion is deliberately uncapped, appending &asymp;{AE['items']//max(AE['recalls'],1)} linked memories per recall; this enriches context but grows prompts, and its cost&ndash;benefit curve is unmeasured. (iv) The equivalence judge and atomizer consume extra LLM calls per deposit &mdash; the price of compression is paid at write time. (v) One baseline artifact: G-Memory re-runs distillation on resume (its distill bookkeeping is not check-pointed); sim-only accounting excludes distillation nodes, so reported numbers are unaffected.</p>

<h2><span class="n">7</span> Conclusion</h2>
<p>Agentsensus treats a story world&rsquo;s memory as a single consensus store: equivalent memories merge across witnesses, split memories link into a graph, and recall walks that graph automatically. On a novel-seeded 80-round simulation, this yields the smallest memory footprint at equal granularity, the only shared and linked memory structure among four backends, and an emergent memory graph that mirrors the story&rsquo;s social structure &mdash; while judged continuation quality stays within noise of the baselines in all four worlds. The broader lesson is that memory structure in multi-agent systems must be mechanized, not delegated: agents reliably use only <code>remember</code> and <code>recall</code>, so that is where the structure has to live.</p>

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
<li>[10] Q. Wu, G. Bansal, J. Zhang, et al. <i>AutoGen: Enabling Next-Gen LLM Applications via Multi-Agent Conversation.</i> 2023. arXiv:2308.08155.</li>
<li>[11] G. Li, H. Hammoud, H. Itani, D. Khizbullin, B. Ghanem. <i>CAMEL: Communicative Agents for &ldquo;Mind&rdquo; Exploration of Large Language Model Society.</i> NeurIPS 2023. arXiv:2303.17760.</li>
<li>[12] S. Hong, X. Zheng, J. Chen, et al. <i>MetaGPT: Meta Programming for a Multi-Agent Collaborative Framework.</i> ICLR 2024. arXiv:2308.00352.</li>
<li>[13] C. Qian, W. Liu, H. Liu, et al. <i>ChatDev: Communicative Agents for Software Development.</i> ACL 2024. arXiv:2307.07924.</li>
<li>[14] P. Lewis, E. Perez, A. Piktus, et al. <i>Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks.</i> NeurIPS 2020. arXiv:2005.11401.</li>
<li>[15] D. Edge, H. Trinh, N. Cheng, et al. <i>From Local to Global: A Graph RAG Approach to Query-Focused Summarization.</i> 2024. arXiv:2404.16130.</li>
<li>[16] W. Zhong, L. Guo, Q. Gao, H. Ye, Y. Wang. <i>MemoryBank: Enhancing Large Language Models with Long-Term Memory.</i> AAAI 2024. arXiv:2305.10250.</li>
<li>[17] G. Wang, Y. Xie, Y. Jiang, et al. <i>Voyager: An Open-Ended Embodied Agent with Large Language Models.</i> 2023. arXiv:2305.16291.</li>
<li>[18] Y. Shao, L. Li, J. Dai, X. Qiu. <i>Character-LLM: A Trainable Agent for Role-Playing.</i> EMNLP 2023. arXiv:2310.10158.</li>
<li>[19] P. Mirowski, K.&thinsp;W. Mathewson, J. Pittman, R. Evans. <i>Co-Writing Screenplays and Theatre Scripts with Language Models: An Evaluation by Industry Professionals.</i> CHI 2023. arXiv:2209.14958.</li>
<li>[20] K. Yang, Y. Tian, N. Peng, D. Klein. <i>Re3: Generating Longer Stories With Recursive Reprompting and Revision.</i> EMNLP 2022. arXiv:2210.06774.</li>
<li>[21] K. Yang, D. Klein, N. Peng, Y. Tian. <i>DOC: Improving Long Story Coherence With Detailed Outline Control.</i> ACL 2023. arXiv:2212.10077.</li>
<li>[22] J.&thinsp;S. Park, C. Zou, A. Shaw, et al. <i>Generative Agent Simulations of 1,000 People.</i> 2024. arXiv:2411.10109.</li>
<li>[23] W. Hua, L. Fan, L. Li, et al. <i>War and Peace (WarAgent): Large Language Model-based Multi-Agent Simulation of World Wars.</i> 2023. arXiv:2311.17227.</li>
<li>[24] I.&thinsp;P. Fellegi, A.&thinsp;B. Sunter. <i>A Theory for Record Linkage.</i> Journal of the American Statistical Association, 64(328):1183&ndash;1210, 1969.</li>
<li>[25] H.&thinsp;H. Clark, S.&thinsp;E. Brennan. <i>Grounding in Communication.</i> In Perspectives on Socially Shared Cognition, APA, 1991.</li>
<li>[26] A. Abbas, K. Tirumala, D. Simig, S. Ganguli, A.&thinsp;S. Morcos. <i>SemDeDup: Data-Efficient Learning at Web-Scale through Semantic Deduplication.</i> 2023. arXiv:2303.09540.</li>
</ol>

<h2><span class="n">A</span> Appendix</h2>
<p>The appendix reports material the main text summarizes or omits: a census of what agents actually do with the action repertoire (A.1), transcript excerpts from all four worlds with a reading of how each memory design shows up in behavior (A.2), the sedimentation and cast-selection numbers behind each world (A.3), the language composition of the runs (A.4), and the merge-depth and expansion statistics behind the structural claims (A.5).</p>

<h3>A.1 &nbsp;What agents actually call</h3>
<p>&sect;5.6 asserts that agents never perform memory management. Table&nbsp;A1 is the evidence in full: every action invocation across the four worlds&rsquo; final stages, by backend. The repertoire is identical for all four and documented in the same skill file, with worked examples; the id-free query addressing of &sect;3.7 removes the interface barrier that an earlier design was suspected of having.</p>
<div class="tw"><table>
<caption><b>Table A1. Action census, per world.</b> Every action invocation in each world&rsquo;s full run, by backend. Rows are omitted where all four backends are at zero in that world. Nine of the repertoire&rsquo;s twenty-four actions were never invoked anywhere: <code>gesture</code>, <code>noop</code>, <code>remove_status</code>, and the six memory-management calls <code>forget</code>, <code>revise_memory</code>, <code>add_affiliated</code>, <code>remove_affiliated</code>, <code>set_affiliated</code>, <code>get_affiliated</code>.</caption>
<thead><tr><th>action</th><th>consensus</th><th>gen-agents</th><th>g-memory</th><th>collab.</th></tr></thead>
<tbody>
{action_rows('g80', 'Three Kingdoms 三国演义', '80 rounds')}
{action_rows('rc80', 'Red Chamber 红楼梦', '80 rounds')}
{action_rows('ru40', 'Russia&ndash;Ukraine', '40 rounds')}
{action_rows('hl40', 'Hamlet', '40 rounds')}
</tbody></table></div>
<p><b>Reading.</b> The memory interface agents actually use is two calls wide. <code>remember</code> runs 8&ndash;84 times per backend per world and <code>recall</code> 0&ndash;12, and every one of the six discretionary memory-management actions sits at zero in every world &mdash; the empirical basis for D3, since a mechanism placed behind <code>add_affiliated</code> would simply never run. Two further readings. The distribution is nearly identical across backends within a world, which is what the fairness protocol wants: the backends differ in what <code>remember</code> and <code>recall</code> <i>do</i>, not in how often they are called. And writes outnumber reads by roughly 8:1 in the novels and 15:1 in Russia&ndash;Ukraine &mdash; agents deposit far more than they retrieve, which is why &sect;5.2 treats the write path as the one whose cost matters. Hamlet is the sharpest case: <code>recall</code> was invoked <i>zero</i> times by any backend across 40 rounds, so its whole run is written memory that no agent ever asked for again.</p>

<h3>A.2 &nbsp;Transcript excerpts</h3>
<p>One deduplicated <code>say</code> message per backend, from each world&rsquo;s final stage, chosen by length so a block fits here; only the recipient list is abridged. The two Chinese worlds are given in English with the original beneath; the two English worlds are given as written. The point of the comparison is not prose quality &mdash; &sect;5.3 measures that and finds the backends within error bars of one another &mdash; but what a memory design looks like from the outside.</p>

<h4>Three Kingdoms 三国演义 (80 rounds, Chinese)</h4>
<div class="quote"><b>consensus</b> &nbsp;[r61] Cheng Yu 程昱 &rarr; Yue Jin 乐进<br>
Yue Jin: regarding tonight&rsquo;s midnight collection of Xu Shu&rsquo;s mother&rsquo;s letter east of Xuchang &mdash; which timing now stands? Still midnight, or moved to the third quarter after noon tomorrow at the post-house? Report back at once.<br>
<span class="orig">乐进：今夜子时于许昌城东取徐母家书之事，今以何时为准？仍按子时取回，还是改为明日午后三刻于馆驿交接？请速回禀。</span></div>
<div class="quote"><b>generative-agents</b> &nbsp;[r61] Mi Zhu 糜竺 &rarr; Liu Bei 刘备, Guan Yu 关羽, Sun Qian 孙乾<br>
Reporting to my lord: the ruling is received. The force stands at three hundred; three days&rsquo; rations drawn from Fancheng are approved; I will issue the supplies at once and have the Fancheng grain officer seal and register them&hellip;<br>
<span class="orig">回禀主公：承受圣裁。兵数仍定为三百，准用樊城抽拨之三日口粮；我即刻领发粮草并督樊城粮官封存登记&hellip;</span></div>
<div class="quote"><b>g-memory</b> &nbsp;[r62] Xiahou Yuan 夏侯渊 &rarr; Xun Yu 荀彧<br>
Lord Xun: Yu Jin and Yue Jin have carried the registers to the yamen; I have also compiled the scouts&rsquo; summaries and the camp inspection books&hellip; can it be consolidated into a memorial to His Majesty within three quarters, as agreed?<br>
<span class="orig">荀公：于禁、乐进已携册赴府衙呈上，臣亦已将斥候回报摘要与各营点验簿整理成册&hellip;能否按议于三刻内汇整为摘要上奏陛下？</span></div>
<div class="quote"><b>collaborative</b> &nbsp;[r61] Xu Chu 许褚 &rarr; Guan Yu 关羽, Zhuge Liang 诸葛亮, Zhao Yun 赵云<br>
Reconnaissance of Mount Bailang is complete. Observing along the ridge, no main enemy force was seen &mdash; only scattered scout riders and a few suspicious tents and campfires. Signals are set; returning by the same route, arrival expected within the hour.<br>
<span class="orig">白狼山侦察已毕。沿山脊侦望，未见敌军主力，仅见零星侦骑与少数可疑营帐、营火。已设回报信号，现按原路返营，预计一小时内抵达。</span></div>

<h4>Red Chamber 红楼梦 (80 rounds, Chinese)</h4>
<div class="quote"><b>consensus</b> &nbsp;[r60] Jia Baoyu 贾宝玉 &rarr; Grandmother Jia 贾母, Jia Zhen 贾珍, Wang Xifeng 王熙凤<br>
Grandmother, Jia Zhen, Sister Feng, Baochai &mdash; I am waiting here. Does Grandmother wish me to come up and sit beside her now, or to wait until Miss Lin arrives and be seated together?<br>
<span class="orig">外祖母、贾珍、凤姐、宝钗，晚辈已在此恭候。请问外祖母现在是要我先近前到贾母身侧就座陪侍，还是等林姑娘到齐再并列就座？</span></div>
<div class="quote"><b>generative-agents</b> &nbsp;[r60] Jia Lian 贾琏 &rarr; Ban&rsquo;er 板儿, You-shi 尤氏<br>
Ban&rsquo;er, state your name and Granny&rsquo;s, your business, and whether you carry a letter of introduction or any proof of identity; You-shi, have a page bring Ban&rsquo;er and Granny Liu to the hall to wait, and let them not wander&hellip;<br>
<span class="orig">板儿，请将你与姥姥的姓名、来意及是否带有介绍信或能证明身份的凭证一并禀明；尤氏，请差小厮将板儿与刘姥姥领到厅上等候，不可四处走动&hellip;</span></div>
<div class="quote"><b>g-memory</b> &nbsp;[r60] Jia Tanchun 贾探春 &rarr; Li Wan 李纨<br>
Sister Li, as you asked, I have offered the club a model verse at the table (&lsquo;the crab-apple newly opened, dew holding its scent&hellip;&rsquo;), Xiangyun has answered it, and the others are responding in turn&hellip; as for this month&rsquo;s host, Xichun is willing to take a turn.<br>
<span class="orig">李姐姐，承你所托，探春已于席间为社中示范一首（海棠初绽露凝香……）且湘云已和唱，诸位正依次应和&hellip;关于本月轮主，惜春愿任一任。</span></div>
<div class="quote"><b>collaborative</b> &nbsp;[r60] Qingwen 晴雯 &rarr; Jia Yun 贾芸, Xiaohong 小红<br>
Jia Yun, were you just now holding a white embroidered handkerchief with a word stitched in the corner? Xiaohong says it is hers. If you have it, produce it for her to see; if not, say so plainly.<br>
<span class="orig">贾芸，你刚才可曾拿着一方白底绣花、角上有绣字的绢子？小红说那是她的，若你有请拿出来让小红看；若没有请直言。</span></div>

<h4>Russia&ndash;Ukraine (40 rounds, English)</h4>
<div class="quote"><b>consensus</b> &nbsp;[r24] un &rarr; guterres<br>
&ldquo;Rosemary DiCarlo, please begin your 5-minute brief now and name the DPA drafting lead for the Security Council text.&rdquo;</div>
<div class="quote"><b>generative-agents</b> &nbsp;[r24] iaea &rarr; grossi<br>
&ldquo;Director General IAEA requests immediate confirmation of the current status at Zaporizhzhia NPP. Please secure safe, unimpeded access for an IAEA expert mission, coordinate with Energoatom&hellip;&rdquo;</div>
<div class="quote"><b>g-memory</b> &nbsp;[r24] zaluzhnyi &rarr; radakin<br>
&ldquo;Brigadier Foster &mdash; I am transmitting Colonel Andriy Kovalenko&rsquo;s secure contact details and the prioritized spreadsheet to you and the UK team now via the agreed secure channel&hellip;&rdquo;</div>
<div class="quote"><b>collaborative</b> &nbsp;[r33] un &rarr; guterres<br>
&ldquo;Secretary-General, DPO has not yet delivered its update. Shall OCHA proceed now with its five-minute update on civilian needs and corridor routes, or wait a moment longer for DPO?&rdquo;</div>
<p style="font-size:14px;color:var(--muted);max-width:68ch">These are English-language excerpts, but not every message in this world was English: 12% of the run&rsquo;s memories are Chinese and 2% Russian (Table&nbsp;A3), the latter because agents adopted the language of the character they were playing.</p>

<h4>Hamlet (40 rounds, English)</h4>
<div class="quote"><b>consensus</b> &nbsp;[r24] fortinbras &rarr; marcellus<br>
&ldquo;Marcellus, report the current troop and weapon counts on the battlements, and prepare to escort me to the Great Hall so we can inventory arms and gather grain.&rdquo;</div>
<div class="quote"><b>generative-agents</b> &nbsp;[r20] marcellus &rarr; barnardo<br>
&ldquo;Barnardo &mdash; go wake Horatio at once and tell him to come to the battlements immediately. Do not go alone; wait here until he arrives.&rdquo;</div>
<div class="quote"><b>g-memory</b> &nbsp;[r28] barnardo &rarr; horatio<br>
&ldquo;Horatio, Marcellus and I just saw a ghost on the battlements.&rdquo;</div>
<div class="quote"><b>collaborative</b> &nbsp;[r20] first_player &rarr; rosencrantz<br>
&ldquo;Thank you, Rosencrantz. I&rsquo;m glad the play is engaging. Watch King Claudius closely and tell me if his countenance changes during the performance.&rdquo;</div>

<p><b>Reading.</b> Three things hold across all four worlds. <i>The register is set by the action repertoire, not by the memory design.</i> Every backend drifts toward administrative correspondence &mdash; requests, confirmations, rosters, timings &mdash; because what an agent can do is speak, set goals, and report; Red Chamber&rsquo;s poetry club and Hamlet&rsquo;s battlements are pulled into the same idiom as Three Kingdoms&rsquo;s supply trains. <i>The worlds differ more than the backends do.</i> The institutional worlds produce long procedural messages (Russia&ndash;Ukraine&rsquo;s shortest English line runs 285 characters); the chamber drama produces short ones (&ldquo;Horatio, Marcellus and I just saw a ghost on the battlements&rdquo;); the household world sits between, with etiquette carrying most of the content.</p>
<p>What does track the memory design is the <i>direction of reference</i>. Consensus lines characteristically ask which branch of an already-shared arrangement now applies &mdash; Cheng Yu (程昱) asks whether the pickup still stands at midnight <i>or</i> has moved to the post-house; Baoyu (宝玉) asks whether to sit now <i>or</i> wait for Daiyu (黛玉); the UN chair asks a named official to begin <i>the</i> brief. The speaker treats the prior arrangement as a record both sides hold and asks only for the delta. Baseline lines more often re-establish the arrangement before acting on it: Mi Zhu (糜竺) restates troop count, rations, and the sealing of the granary; Xu Chu (许褚) re-reports the whole scouting result; Jia Lian (贾琏) asks for names, business, and proof of identity that the household already has. That is what an agent does when it cannot assume the other party&rsquo;s copy matches its own. The pattern is consistent with the mechanism &mdash; N witnesses holding one row do not need to re-establish premises &mdash; but it is an observation on selected excerpts, not a measurement; the quality metrics of &sect;5.3 put the backends within each other&rsquo;s error bars, and we do not claim more than that.</p>
<p>One artifact worth recording, because it affects anything built on the event log: the kernel logs a single utterance both as an <code>action</code> event and as one <code>message</code> event per recipient, so a line addressed to three agents appears four times. Naive transcript assembly therefore triples parts of a run; the excerpts above and the screenplay renderer both deduplicate by (round, speaker, content).</p>

<h3>A.3 &nbsp;Sedimentation and cast selection</h3>
<p>Each world is built by the pipeline of &sect;3.4 and then reduced to a simulable cast. A character participates iff it owns more than a per-world threshold of sediment memories; below-threshold characters remain owners of their memories but are never scheduled. Environments are kept if an active character stands there or if they own memories of their own; information carriers (letters, commissions, play scripts) are always kept.</p>
<div class="tw"><table>
<caption><b>Table A2. Sedimentation cost and cast composition.</b> Wall-clock and token figures are for the sedimentation pass only, on the consensus store; the per-backend ingest of the same events is additional. &ldquo;Warnings&rdquo; counts extraction records the pipeline flagged for review (unresolved referents, ambiguous attributions).</caption>
<thead><tr><th>world</th><th>registry</th><th>events</th><th>LLM calls</th><th>tokens</th><th>wall</th><th>active</th><th>archived</th><th>envs</th><th>carriers</th><th>warn</th></tr></thead>
<tbody>
<tr><td>Three Kingdoms (三国演义)</td><td>399</td><td>6,052</td><td>764</td><td>9.2M</td><td>124 min</td><td>33</td><td>38</td><td>115</td><td>5</td><td>235</td></tr>
<tr><td>Red Chamber (红楼梦)</td><td>152</td><td>6,506</td><td>848</td><td>8.5M</td><td>129 min</td><td>34</td><td>3</td><td>88</td><td>9</td><td>222</td></tr>
<tr><td>Russia&ndash;Ukraine</td><td>170</td><td>1,533</td><td>1,373</td><td>12.3M</td><td>69 min</td><td>47</td><td>14</td><td>71</td><td>0</td><td>61</td></tr>
<tr><td>Hamlet</td><td>22</td><td>1,135</td><td>212</td><td>0.9M</td><td>31 min</td><td>16</td><td>2</td><td>8</td><td>3</td><td>10</td></tr>
</tbody></table></div>
<p><b>Reading.</b> Cost tracks source length, not cast size: Russia&ndash;Ukraine extracts the fewest events (1,533 dated entries) yet costs the most tokens, because a timeline entry names many institutional actors and attribution must resolve each one. The archived column is the boundary-state finalization of &sect;3.4 at work and is worth reading per world: Three Kingdoms archives 38 characters dead by chapter&nbsp;40; Red Chamber archives three (秦可卿, 贾瑞, 秦钟); Hamlet archives Polonius, killed in 3.4, and the Ghost, absent from the canon thereafter; Russia&ndash;Ukraine archives 14 under real-world semantics, where &ldquo;no longer a participant&rdquo; covers leaving office or being disbanded as well as dying, and where every placement was verified by hand against the 2026-07 boundary. Two cases required overrides that no automatic rule would produce: Fortinbras owns zero sediment memories &mdash; he never appears before Act&nbsp;4 &mdash; but is retained because the continuation is his, and England is retained as an environment for the same reason.</p>

<h3>A.4 &nbsp;Language composition of the runs</h3>
<p>Each world declares a language: Three Kingdoms and Red Chamber run in Chinese, Russia&ndash;Ukraine and Hamlet in English. The declaration selects the action-skill document and the output-format block, and the sediment is in the source language throughout. It did <i>not</i>, in the runs reported here, constrain what agents wrote: the language of a memory followed the language of the profile and of whatever the agent recalled, and drifted when those disagreed.</p>
<div class="tw"><table>
<caption><b>Table A3. Language of simulation memories</b> (consensus store, final stage of each world). Classification is by script: an entry with CJK characters and no substantial Latin text counts as Chinese, an entry with both counts as mixed, Cyrillic-dominant entries count as Russian.</caption>
<thead><tr><th>world</th><th>declared</th><th>Chinese</th><th>English</th><th>mixed</th><th>Russian</th></tr></thead>
<tbody>
<tr><td>Three Kingdoms (三国演义)</td><td>zh</td><td>90%</td><td>9%</td><td>&mdash;</td><td>&mdash;</td></tr>
<tr><td>Red Chamber (红楼梦)</td><td>zh</td><td>97%</td><td>1%</td><td>1%</td><td>&mdash;</td></tr>
<tr><td>Russia&ndash;Ukraine</td><td>en</td><td>12%</td><td>81%</td><td>2%</td><td>2%</td></tr>
<tr><td>Hamlet</td><td>en</td><td>26%</td><td>59%</td><td>14%</td><td>&mdash;</td></tr>
</tbody></table></div>
<p><b>Reading.</b> The drift is largest where the two implicit signals disagree most. All four worlds carried Chinese-authored character profiles, so an English world with an English sediment still pulled toward Chinese, and Hamlet &mdash; the smallest sediment, hence the weakest counterweight &mdash; drifted furthest (26% Chinese, 14% mixed). Russia&ndash;Ukraine additionally produced Russian-language memories: agents adopted the language of the character they were playing, which no instruction had asked for and none had forbidden. We report this as a finding about implicit conditioning rather than a defect of the memory mechanisms, which are language-agnostic: entry counts, sharing, and graph structure are unaffected. The framework now carries an explicit content-language directive in the agent system prompt, and screenplays are normalized to the world&rsquo;s language at render time; the runs above predate the directive and were not regenerated for it.</p>

<h3>A.5 &nbsp;Merge depth, graph density, and expansion</h3>
<p>&sect;5.1 reports the share of memories that are shared and linked. The distribution behind those shares, and what recall does with the graph, are below.</p>
<div class="tw"><table>
<caption><b>Table A4. Consensus structure per world</b> (final stage). &ldquo;3+&rdquo; counts entries with three or more witnesses; &ldquo;max&rdquo; is the deepest merge; &ldquo;expanded&rdquo; is the fraction of recalls that returned at least one memory reached along an affiliated edge, with the mean number of such memories per call.</caption>
<thead><tr><th>world</th><th>sim entries</th><th>shared</th><th>3+</th><th>max</th><th>linked</th><th>expanded recalls</th><th>linked per call</th></tr></thead>
<tbody>
<tr><td>Three Kingdoms (三国演义) (80t)</td><td>974</td><td>188 (19%)</td><td>38</td><td>6</td><td>97%</td><td>51/51</td><td>28</td></tr>
<tr><td>Red Chamber (红楼梦) (80t)</td><td>438</td><td>107 (24%)</td><td>24</td><td>6</td><td>94%</td><td>19/19</td><td>38</td></tr>
<tr><td>Russia&ndash;Ukraine (40t)</td><td>814</td><td>113 (14%)</td><td>23</td><td>10</td><td>99%</td><td>23/41</td><td>2</td></tr>
<tr><td>Hamlet (40t)</td><td>110</td><td>29 (26%)</td><td>1</td><td>3</td><td>98%</td><td>3/3</td><td>39</td></tr>
</tbody></table></div>
<p><b>Reading.</b> Merge depth is a property of the world&rsquo;s staging, not of the mechanism. Russia&ndash;Ukraine reaches ten witnesses on a single presidential air-defense directive because a real command chain broadcasts one instruction to many named institutions at once; Hamlet tops out at three, and only once &mdash; on the players&rsquo; performance, the one scene in the play that assembles an audience &mdash; because Shakespeare stages almost everything as a two-person exchange. The two novels sit between, at six. Expansion behaves differently for a different reason: it returns few linked memories in Russia&ndash;Ukraine (2 per call, and only 23 of 41 recalls expanded at all) because institutional deposits are short and rarely split into several atoms, so there are fewer siblings to link; in the novels a single compound recollection atomizes into many pieces, and a recall pulls back 28&ndash;39 of them. The sharing rate itself is horizon-dependent and saturating &mdash; Red Chamber, run at four horizons, goes 13%&rarr;20%&rarr;23%&rarr;24% at rounds 10/40/60/80 &mdash; which is the compounding argument of &sect;5.1.3 measured directly.</p>

<h3>A.6 &nbsp;Screenplays</h3>
<p>The full screenplay of each world&rsquo;s consensus run, rendered from its event log by the pipeline of &sect;5.3: beats are grouped into scenes by place and stretch of time, each scene is dramatized in one grounded pass, and a check-and-repair round catches any beat the renderer dropped. Nothing outside the log may appear &mdash; the cast, the location and every action are constrained to what the run actually produced &mdash; while the wording must be rewritten rather than copied, with no line running longer than a spoken breath and no memo formatting inside dialogue. This is the text the continuation-quality judge reads.</p>

<p>Each screenplay is long &mdash; between """ + screenplay_span() + """ scenes &mdash; so the four are collapsed by default and printed after the grids below.</p>
<div class="tw"><table>
<caption><b>Table A5. The four screenplays.</b> &ldquo;Beats&rdquo; are the dramatizable events the run produced after deduplication (one utterance is one beat, however many recipients it was logged against); &ldquo;scenes&rdquo; are the groupings of those beats by place and stretch of time that each become one render call. Length is the rendered markdown; the Chinese worlds carry two renderings of the same beats.</caption>
<thead><tr><th>world</th><th>rounds</th><th>scenes</th><th>beats</th><th>speakers</th><th>places</th><th>English</th><th>source language</th></tr></thead>
<tbody>
""" + screenplay_rows() + """
</tbody></table></div>
<p><b>Reading.</b> Scene count tracks how scattered a world is, not how much happens in it: Hamlet&rsquo;s 117 beats fall into 12 scenes because the play keeps returning to the same six places, while Red Chamber&rsquo;s 390 beats spread over 26 locations and split into 62. Length per beat is a property of what the agents say, not of how many of them speak: Russia&ndash;Ukraine writes 313k characters from 334 beats because an institutional order carries a page of particulars the renderer may not drop, while Red Chamber&rsquo;s 390 beats come to 30k characters in Chinese because a household exchange is mostly short questions. The English rendering of a Chinese world runs about three times the length of its source-language twin, which is a property of the writing systems rather than of the content.</p>

<p style="font-size:14px;color:var(--muted)">A note on register: the dialogue reads administratively because the simulation does. Agents can speak, set goals and report, so they write like officers filing returns; the screenplay can stage that exchange, give it voices and cut it into speakable lines, but it cannot make a supply conference lyrical. &sect;A.2 makes the same point from the raw transcripts.</p>

<p><b>How the scenes were cut.</b> One figure per world: every cell is one round at one place, coloured when an agent acted there. The four are read the same way, so the first is annotated in full and the rest carry only what is particular to that world.</p>
<figure>
""" + scene_grid("hamlet") + """
<figcaption><b>Figure 30. How the scenes were cut &mdash; Hamlet.</b> Every cell is one round at one place. A cell is coloured when an agent acted there and left white when nothing did; hatched cells are rounds where several agents acted in the same place. The outlined rectangles are the scenes the renderer produced, numbered as they appear in the screenplay below. The rule is visible in the picture: a scene is one row (one place) and a run of rounds whose neighbours are no more than five apart, cut at twenty rounds so no scene swallows the story &mdash; which is why the busy hall at Elsinore becomes two scenes (1 and 9) rather than one, and why the single action in Norway at round 3 is a scene of its own (4). Rounds are numbered as the kernel numbers them, from zero, so a forty-round run reads 0&ndash;39 and an eighty-round run 0&ndash;79. Ordering the rectangles by the round they open on is what makes the screenplay read forwards.</figcaption>
</figure>

""" + grid_figure("three_kingdoms", 31, "Three Kingdoms (三国演义)",
    "The pattern of a campaign narrative: four places carry the war "
    "(Xuchang, Xinye, Fancheng, Jiangdong) in long unbroken bands, while a "
    "dozen others are visited once and become one-cell scenes.") + """
""" + grid_figure("red_chamber", 32, "Red Chamber (红楼梦)",
    "The densest world in the set: the household keeps returning to the same "
    "handful of courtyards, so Daguanlou, Hengwuyuan, Yihong Yuan and "
    "Rongguofu each split into three or four scenes across the eighty "
    "rounds.") + """
""" + grid_figure("russia_ukraine", 33, "Russia&ndash;Ukraine",
    "Institutional actors work from fixed seats, so activity concentrates in "
    "a few capitals and headquarters; the hatched cells are where several "
    "institutions act in the same place and round, which is also where the "
    "many-witness merges of &sect;5.1 come from.") + """

<p>The screenplays themselves follow, one collapsible block per world, in the same order. """ + """The Chinese worlds are given in English with the scenario-language rendering beneath each scene; both are produced directly from the same beats in a single pass, not by translating one into the other.</p>

""" + screenplay_block("three_kingdoms", "Three Kingdoms 三国演义", " &middot; 80 rounds", True) + """
""" + screenplay_block("red_chamber", "Red Chamber 红楼梦", " &middot; 80 rounds", True) + """
""" + screenplay_block("russia_ukraine", "Russia&ndash;Ukraine", " &middot; 40 rounds", False) + """
""" + screenplay_block("hamlet", "Hamlet", " &middot; 40 rounds", False) + f"""

<p class="foot">Agentsensus &middot; four worlds, run in resumed stages to 80 rounds (Three Kingdoms, Red Chamber) and 40 rounds (Russia&ndash;Ukraine, Hamlet) &middot; chat gpt-5-mini, embeddings text-embedding-3-small &middot; simulation-only accounting under uniform atomization &middot; structural counts deterministic; quality metrics mean&plusmn;std over 3 LLM scorings &middot; data: <code>runs/g20_* &hellip; g80_*</code>, <code>runs/rc10_* &hellip; rc80_*</code>, <code>runs/ru10_* &hellip; ru40_*</code>, <code>runs/hl20_* &hellip; hl40_*</code>.</p>

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
  const NM=id=>((data&&data.names)||{})[id]||id;
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
        if(on) ctx.fillText(NM(n.id),SX(n),SY(n)-(opt.r(n)+4)*h.dpr);
      });
    } else if(focus>=0){
      ctx.font=(10.5*h.dpr)+"px system-ui"; ctx.fillStyle=ink; ctx.textAlign="center";
      [focus,...nbr[focus]].slice(0,40).forEach(i=>{const n=N[i];
        ctx.fillText(opt.shortLabel?opt.shortLabel(n):NM(n.id),SX(n),SY(n)-(opt.r(n)+4)*h.dpr);});
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
  const NM=id=>((data&&data.names)||{})[id]||id;
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
      ctx.textAlign="right"; ctx.fillText(NM(ord[i]),ox-4*h.dpr,oy+i*cell+cell*0.7);
      ctx.save(); ctx.translate(ox+i*cell+cell*0.7,oy-4*h.dpr); ctx.rotate(-Math.PI/2);
      ctx.textAlign="left"; ctx.fillText(NM(ord[i]),0,0); ctx.restore();
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
  const NM=id=>((data&&data.names)||{})[id]||id;
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
        ctx.fillStyle=ink; ctx.textAlign="left"; ctx.fillText(NM(a.id),0,0); ctx.restore();
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
      showTip(h,`<b>memory</b> ${m.multi?"(shared ★)":""}<br>${esc(m.en||m.text)}${m.en?`<br><span style="opacity:.65">(${esc(m.text)})</span>`:""}<br><b>owners:</b> ${esc(m.owners.map(o=>NM(o)).join(", "))}`,
        ev.clientX-r.left,ev.clientY-r.top);
    } else if(ba>=0){ const a=A[ba];
      const owned=OWN.filter(o=>o.a===a.id).length;
      showTip(h,`<b>${esc(NM(a.id))}</b> (${a.kind})<br>owned sim memories: <b>${owned}</b>`,
        ev.clientX-r.left,ev.clientY-r.top);
    } else h.tip.style.display="none";
  });
  h.cv.addEventListener("mouseleave",()=>{hovA=-1;hovM=-1;h.tip.style.display="none";draw();});
  window.addEventListener("resize",()=>{h.size();geom();draw();});
}

function initSet(GG,pfx){
const NAMES=GG.names||{};
// Node labels and tooltips show the English name; the id stays the fallback so
// a world whose agents were never glossed still renders.
const NM=id=>NAMES[id]||id;
nodeLink(pfx+"interaction",GG.interaction,{
  r:n=>5.5+1.1*Math.sqrt(Math.min(n.deg||0,80)),
  color:n=> n.comm>=0? PAL[n.comm%10] : "#9ca3af",
  ew:e=>0.5+2.2*e.w/Math.max(1,...GG.interaction.edges.map(x=>x.w)),
  edgeColor:"#8fa3c8", edgeAlpha:0.4, labels:true,
  tip:n=>`<b>${esc(NM(n.id))}</b><br>${n.silent?"silent this run":"conversation volume: <b>"+n.deg+"</b>"}<br>community: ${n.comm>=0?n.comm+1:"—"}`
});
nodeLink(pfx+"affiliation",GG.affiliation,{
  r:n=> n.shared?5:3,
  color:n=> (GG.affiliation.nodes.filter(x=>x.comp===n.comp).length>1)? PAL[n.comp%10] : "#b9c0cc",
  ring:n=>n.shared,
  ew:()=>0.5, edgeColor:"#9fb4d8", edgeAlpha:0.3, labels:false,
  shortLabel:n=>"",
  tip:n=>`<b>memory</b> ${n.shared?"(shared)":""}<br>${esc(n.en||n.text)}${n.en?`<br><span style="opacity:.65">(${esc(n.text)})</span>`:""}<br><b>owners:</b> ${esc(n.owners.map(o=>NM(o)).join(", "))}`
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
