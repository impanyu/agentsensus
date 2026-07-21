"""Phase 1 only: extract the ROLE registry (characters / environment / info_carrier)
for all four scenarios, for human review BEFORE any memory sedimentation.

Runs extract_history(registry_only=True) on each scenario's SEDIMENT span (reusing
the slicing in sediment_all.py). Writes <name>.yaml.registry.json and prints a
compact per-scenario role summary. No memory deposit, no embeddings needed.
Run: venv/bin/python -m experiments.extract_roles
"""
import asyncio
import json
import os

from society.run import _build_llm_and_embed
from society.history_extract import extract_history
from experiments.sediment_all import SCENARIOS, OUT, CONFIG, PER_CONC


async def roles_one(spec: dict) -> dict:
    name = spec["name"]
    out_yaml = os.path.join(OUT, f"{name}.yaml")
    llm, embed_fn = _build_llm_and_embed(CONFIG)
    llm.max_concurrency = PER_CONC
    llm._semaphore = asyncio.Semaphore(PER_CONC)
    text = spec["slice"]()
    try:
        res = await extract_history(
            text, llm, out_yaml, embed_fn=embed_fn, language=spec["lang"],
            detail="atomic", registry_only=True,
        )
        reg = res.get("registry", {})
        rec = {
            "name": name, "ok": True,
            "characters": len(reg.get("characters", []) or []),
            "locations": len(reg.get("locations", []) or []),
            "carriers": len(reg.get("carriers", []) or []),
            "warnings": len(res.get("_warnings", [])),
            "usage": llm.usage().get("_total"),
        }
    except Exception as exc:
        rec = {"name": name, "ok": False, "error": repr(exc)}
    print(json.dumps(rec, ensure_ascii=False))
    return rec


async def main():
    results = await asyncio.gather(*(roles_one(s) for s in SCENARIOS))
    print("=== ROLE-EXTRACTION SUMMARY ===")
    for r in results:
        print(json.dumps(r, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
