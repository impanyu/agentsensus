"""Score the ablation grid (consensus backend, 三国, 40 rounds).

One factor at a time from the paper's configuration (merge on, cache fifo):

    on  / fifo       the paper's configuration, rerun under current code
    on  / relevance  STM evicts the pair least similar to the incoming one
    on  / hybrid     STM evicts on alpha*recency + (1-alpha)*relevance
    off / fifo       consensus merge disabled

Reports, per cell, the structure the paper claims (deterministic, read from
the run's own export) and all four continuation-quality metrics.

Every metric here reads the EVENT LOG, not a rendered screenplay. Section
5.3 renders first because a 40-round Russia-Ukraine log is 1.6M characters
and mixes languages; neither problem arises here (a 40-round Three Kingdoms
log is 56-84k characters, one language), and rendering would put a separate
LLM pass between each cell and its score -- renderer variation the ablation
would then read as mechanism. The transcript is assembled deterministically
from the same beats the screenplay is cut from, so nothing is dropped:

    entries      simulation-written entries, the footprint claim of 5.1
    shared %     entries owned by two or more agents
    linked %     entries carrying at least one affiliated edge
    max owners   deepest merge
    grounding    fraction of the run's own events judged canon-consistent
    trajectory   agreement of ten principals' arcs with chapters 41-60
    narrative    coherence / distinctiveness / drama / fidelity, 1-5
    goal         actions that serve a goal the agent itself pushed

Because the source text differs from 5.3's, these numbers compare across
cells, not against Table 2.

QA is intentionally NOT scored: it retrieves method-agnostically over the
WHOLE final store, so it measures raw compression retention and is blind to
the owner-scoped retrieval the knobs actually affect.

Usage: ABLATION_REPEAT=3 venv/bin/python -m experiments.score_ablation
"""
import os, re, sys, json, asyncio
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); sys.path.insert(0, ".")
from society import evaluation as ev
from society.run import _build_llm_and_embed
from experiments.score_fidelity import _mean_std
from experiments.goal_timeline import timelines
from experiments.score_all import WORLDS, gold_arcs, grounding_rate
from society.events import EventLog
from society.screenplay import (_beat_content, _beat_speaker, _dedupe, _is_beat,
                                _sort_key)

REPEAT = int(os.environ.get("ABLATION_REPEAT", "3"))
CELLS = [("on", "fifo"), ("on", "relevance"), ("on", "hybrid"), ("off", "fifo")]
# same sim-only accounting as experiments/prep_g80_paper.py, so entry
# counts here are comparable with Table 1
SIM_SRC = {"runtime", "act_on"}


def log_transcript(run_dir):
    """The run's own events as plain text, with no LLM in between.

    Same beats the screenplay is cut from -- speech, gestures, actions,
    thoughts, reads -- flattened one per line with round, speaker and place,
    so the judge sees everything the run produced and sees it identically
    for every cell.
    """
    events = EventLog.load(os.path.join(run_dir, "events.jsonl"))
    beats = _dedupe(sorted((e for e in events if _is_beat(e)), key=_sort_key))
    lines, place = [], None
    for b in beats:
        place = b.get("location") or place
        name = (b.get("action") or {}).get("name") or (b.get("message") or {}).get("kind", "say")
        # the delivery counter is bookkeeping, not content; an eta or a
        # think's conclusion is content and stays
        body = re.sub(r"\s*\|\s*\{'delivered': \d+\}", "", _beat_content(b))
        lines.append(f"[round {b.get('tick', 0)} · {place}] {_beat_speaker(b)} "
                     f"({name}): {body}")
    return "\n".join(lines)


def structure(run_dir):
    """Footprint and structure of the simulation-written entries."""
    d = json.load(open(f"{run_dir}/ltm_final.json", encoding="utf-8"))
    sn = [e for e in d if (e.get("meta") or {}).get("source") in SIM_SRC]
    sh = [e for e in sn if len(e.get("owners", [])) >= 2]
    aff = sum(1 for e in sn if e.get("affiliated"))
    n = max(len(sn), 1)
    return {"sim_new": len(sn), "sh_pct": round(100 * len(sh) / n),
            "aff_pct": round(100 * aff / n),
            "max_owners": max((len(e["owners"]) for e in sh), default=1)}


async def main():
    llm, _embed = _build_llm_and_embed("config_flash.json")
    spec = WORLDS["three_kingdoms"]
    print(f"repeat={REPEAT}: extracting gold arcs", flush=True)
    gold = await gold_arcs(spec["reference"](), spec["arcs"], llm)
    rows = {}
    for m, c in CELLS:
        d = f"runs/abl_{m}_{c}"
        if not os.path.exists(f"{d}/result.json"):
            print(f"{m}/{c}: not finished, skipped", flush=True)
            continue
        st = structure(d)
        text = log_transcript(d)
        goals = timelines([d], spec["arcs"])
        runs = []
        for _ in range(REPEAT):
            gr = await grounding_rate(text, spec["canon"], llm)
            runs.append({
                "grnd": gr["rate"],
                "traj": (await ev.trajectory_consistency(gold, text, llm))["mean"],
                "narr": (await ev.narrative_quality(text, llm))["overall"],
                "goal": (await ev.goal_pursuit(goals, llm))["mean"],
            })
        for k in ("grnd", "traj", "narr", "goal"):
            mean, sd = _mean_std([r[k] for r in runs if r[k] is not None])
            st[f"{k}_m"], st[f"{k}_s"] = mean, sd
        st["chars"] = len(text)
        st["wall_min"] = json.load(open(f"{d}/result.json"))["cost"]["wall_clock_s"] / 60
        rows[f"{m}_{c}"] = st
        print(f"{m}/{c}: entries {st['sim_new']} | shared {st['sh_pct']}% | "
              f"linked {st['aff_pct']}% | grnd {st['grnd_m']:.2f}±{st['grnd_s']:.2f} | "
              f"traj {st['traj_m']:.2f}±{st['traj_s']:.2f} | "
              f"narr {st['narr_m']:.2f}±{st['narr_s']:.2f} | "
              f"goal {st['goal_m']:.2f}±{st['goal_s']:.2f}", flush=True)
    json.dump(rows, open("runs/ablation_results.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("\n=== ABLATION (consensus, 三国, 40 rounds) ===")
    print(f"{'merge':<6}{'cache':<11}{'entries':>8}{'shared':>8}{'linked':>8}"
          f"{'grnd':>7}{'traj':>7}{'narr':>7}{'goal':>7}")
    for k, v in rows.items():
        m, c = k.split("_", 1)
        print(f"{m:<6}{c:<11}{v['sim_new']:>8}{v['sh_pct']:>7}%{v['aff_pct']:>7}%"
              f"{v['grnd_m']:>7.2f}{v['traj_m']:>7.2f}{v['narr_m']:>7.2f}{v['goal_m']:>7.2f}")


if __name__ == "__main__":   # importing structure() must not start a scoring run
    asyncio.run(main())
