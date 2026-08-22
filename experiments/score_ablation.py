"""Score the ablation grid (consensus backend, 三国, 40 rounds).

One factor at a time from the paper's configuration (merge on, cache fifo):

    on  / fifo       the paper's configuration, rerun under current code
    on  / relevance  STM evicts the pair least similar to the incoming one
    on  / hybrid     STM evicts on alpha*recency + (1-alpha)*relevance
    off / fifo       consensus merge disabled

Reports, per cell, the structure the paper claims (all deterministic, read
from the run's own export) plus grounding (LLM-judged, ABLATION_REPEAT
scorings averaged, since one scoring is noisy):

    entries      simulation-written entries, the footprint claim of 5.1
    shared %     entries owned by two or more agents
    linked %     entries carrying at least one affiliated edge
    max owners   deepest merge
    grounding    fraction of the run's own events judged canon-consistent

QA is intentionally NOT scored: it retrieves method-agnostically over the
WHOLE final store, so it measures raw compression retention and is blind to
the owner-scoped retrieval the knobs actually affect.

Usage: ABLATION_REPEAT=3 venv/bin/python -m experiments.score_ablation
"""
import os, sys, json, asyncio
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); sys.path.insert(0, ".")
from society.run import _build_llm_and_embed
from experiments.score_grounding import grounding_rate, sim_transcript
from experiments.score_fidelity import _mean_std

REPEAT = int(os.environ.get("ABLATION_REPEAT", "3"))
CELLS = [("on", "fifo"), ("on", "relevance"), ("on", "hybrid"), ("off", "fifo")]
# same sim-only accounting as experiments/prep_g80_paper.py, so entry
# counts here are comparable with Table 1
SIM_SRC = {"runtime", "act_on"}


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
    print(f"repeat={REPEAT}", flush=True)
    rows = {}
    for m, c in CELLS:
        d = f"runs/abl_{m}_{c}"
        if not os.path.exists(f"{d}/result.json"):
            print(f"{m}/{c}: not finished, skipped", flush=True)
            continue
        st = structure(d)
        grs = [(await grounding_rate(sim_transcript(d), llm, max_events=80))["rate"]
               for _ in range(REPEAT)]
        st["gr_m"], st["gr_s"] = _mean_std(grs)
        st["wall_min"] = json.load(open(f"{d}/result.json"))["cost"]["wall_clock_s"] / 60
        rows[f"{m}_{c}"] = st
        print(f"{m}/{c}: entries {st['sim_new']} | shared {st['sh_pct']}% | "
              f"linked {st['aff_pct']}% | grounding {st['gr_m']:.2f}±{st['gr_s']:.2f}", flush=True)
    json.dump(rows, open("runs/ablation_results.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("\n=== ABLATION (consensus, 三国, 40 rounds) ===")
    print(f"{'merge':<6}{'cache':<11}{'entries':>8}{'shared':>8}{'linked':>8}"
          f"{'owners':>8}{'grounding':>12}")
    for k, v in rows.items():
        m, c = k.split("_", 1)
        print(f"{m:<6}{c:<11}{v['sim_new']:>8}{v['sh_pct']:>7}%{v['aff_pct']:>7}%"
              f"{v['max_owners']:>8}{v['gr_m']:>8.2f}±{v['gr_s']:.2f}")


if __name__ == "__main__":   # importing structure() must not start a scoring run
    asyncio.run(main())
