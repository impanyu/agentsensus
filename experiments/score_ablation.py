"""Score the ablation cells (consensus backend, 三国): footprint (from
result.json) + grounding, over the one-factor-at-a-time grid.

QA is intentionally NOT scored: it retrieves method-agnostically over the WHOLE
final store, so it only measures raw compression retention and is blind to the
per-agent (owner-scoped) retrieval the knobs actually affect -- merge-off just
duplicates the same facts per-owner, which whole-store QA cannot see as a cost.
grounding is LLM-judged and noisy per-run; ABLATION_REPEAT>1 averages.
Usage: venv/bin/python experiments/score_ablation.py
"""
import os, sys, json, asyncio
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); sys.path.insert(0, ".")
from society.run import _build_llm_and_embed
from experiments.score_grounding import grounding_rate, sim_transcript
from experiments.score_fidelity import _mean_std

REPEAT = int(os.environ.get("ABLATION_REPEAT", "3"))
# One-factor-at-a-time from the baseline (on, fifo): flip cache to relevance /
# hybrid, or flip merge off -- NOT the full 2x3 grid (double-flips off x
# {relevance,hybrid} carry no extra ablation signal).
CELLS = [("on", "fifo"), ("on", "relevance"), ("on", "hybrid"), ("off", "fifo")]


async def main():
    llm, _embed = _build_llm_and_embed("config_flash.json")
    print(f"repeat={REPEAT}", flush=True)
    rows = {}
    for m, c in CELLS:
        d = f"runs/abl_{m}_{c}"
        res = json.load(open(f"{d}/result.json"))
        tr = sim_transcript(d)
        grs = [(await grounding_rate(tr, llm, max_events=80))["rate"] for _ in range(REPEAT)]
        gm, gs = _mean_std(grs)
        rows[(m, c)] = {"entries": res["footprint"]["entries"], "gr_m": gm, "gr_s": gs}
        print(f"{m}/{c}: entries {res['footprint']['entries']} | "
              f"grounding {gm:.2f}±{gs:.2f}", flush=True)
    json.dump({f"{m}_{c}": v for (m, c), v in rows.items()},
              open("runs/ablation_results.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("\n=== ABLATION TABLE (consensus, 三国) ===")
    print(f"{'merge':<6}{'cache':<11}{'entries':>9}{'grounding':>13}")
    for m, c in CELLS:
        v = rows[(m, c)]
        gr = f"{v['gr_m']:.2f}±{v['gr_s']:.2f}"
        print(f"{m:<6}{c:<11}{v['entries']:>9}{gr:>13}")

asyncio.run(main())
