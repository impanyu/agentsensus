"""Score the 2x3 ablation cells (consensus backend, 三国): footprint (from
result.json) + QA accuracy + grounding, over the merge x cache grid.

QA/grounding are LLM-judged and noisy per-run; ABLATION_REPEAT>1 averages.
Usage: venv/bin/python experiments/score_ablation.py
"""
import os, sys, json, asyncio
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); sys.path.insert(0, ".")
from society import evaluation as ev
from society.run import _build_llm_and_embed
from experiments.score_grounding import grounding_rate, sim_transcript
from experiments.score_fidelity import sediment_source, _ShimBackend, _batched, _mean_std

REPEAT = int(os.environ.get("ABLATION_REPEAT", "3"))
CELLS = [(m, c) for m in ("on", "off") for c in ("fifo", "relevance", "hybrid")]


async def main():
    llm, embed = _build_llm_and_embed("config_flash.json")
    embed = _batched(embed)
    qa = await ev.generate_qa(sediment_source(), llm, n=40)
    print(f"gold: {len(qa)} QA | repeat={REPEAT}", flush=True)
    rows = {}
    for m, c in CELLS:
        d = f"runs/abl_{m}_{c}"
        res = json.load(open(f"{d}/result.json"))
        entries = json.load(open(f"{d}/ltm_final.json", encoding="utf-8"))
        backend = _ShimBackend(entries)
        tr = sim_transcript(d)
        qas, grs = [], []
        for _ in range(REPEAT):
            qas.append((await ev.run_qa(backend, qa, llm, embed, llm, top_k=5))["accuracy"])
            grs.append((await grounding_rate(tr, llm, max_events=80))["rate"])
        qm, qs = _mean_std(qas); gm, gs = _mean_std(grs)
        rows[(m, c)] = {"entries": res["footprint"]["entries"], "qa_m": qm, "qa_s": qs,
                        "gr_m": gm, "gr_s": gs}
        print(f"{m}/{c}: entries {res['footprint']['entries']} | "
              f"QA {qm:.2f}±{qs:.2f} | grounding {gm:.2f}±{gs:.2f}", flush=True)
    json.dump({f"{m}_{c}": v for (m, c), v in rows.items()},
              open("runs/ablation_results.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("\n=== ABLATION TABLE (consensus, 三国) ===")
    print(f"{'merge':<6}{'cache':<11}{'entries':>9}{'QA':>13}{'grounding':>13}")
    for m, c in CELLS:
        v = rows[(m, c)]
        qa = f"{v['qa_m']:.2f}±{v['qa_s']:.2f}"
        gr = f"{v['gr_m']:.2f}±{v['gr_s']:.2f}"
        print(f"{m:<6}{c:<11}{v['entries']:>9}{qa:>13}{gr:>13}")

asyncio.run(main())
