"""Continue a fair3 run by 50 more ticks (-> 100-tick total data), reusing the
already-run memory and reconstructing each agent's tick-50 position from the
run's own event log.

Faithful-continuation recipe (no full checkpoint needed):
  - LTM: reuse runs/fair3_<method>/ltm_final.json as the starting shared memory
    (run_sim ltm_file=, skip_prime=True).
  - Positions: replay the run's `arrival` events over the scenario's initial
    status.location to get each active character's EXACT tick-50 location, and
    bake it into a per-method continuation scenario. (This is the same "derive
    agent state from the run" idea as boundary-state finalization, but exact and
    LLM-free because the sim logged every move -- unlike the novel sediment.)
  - Aliveness/archived: carried over from the base scenario unchanged (the sim
    does not mechanically archive agents mid-run over 50 ticks).
  - STM (goal stack / FIFO) resets to scenario initial -- not recoverable and
    not important for continuity.

Usage: run_continue.py <consensus|generative_agents|g_memory|collaborative>
"""
import os
import sys
import json
import copy
import asyncio
import time

os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ".")

import yaml
from experiments.run_sim import run_sim

BASE_SCENARIO = "scenarios/three_kingdoms.sim.yaml"
method = sys.argv[1]
run_dir = f"runs/fair3_{method}"
out_dir = f"runs/t100_{method}"


def reconstruct_positions(scn):
    """active char id -> tick-50 location (scenario initial, then replay arrivals)."""
    loc = {}
    for a in scn["agents"]:
        if a.get("kind") == "character" and not a.get("archived"):
            loc[a["id"]] = (a.get("status", {}) or {}).get("location")
    for line in open(f"{run_dir}/events.jsonl", encoding="utf-8"):
        e = json.loads(line)
        if e.get("kind") == "system" and e.get("event") == "arrival":
            if e["agent"] in loc:
                loc[e["agent"]] = e["dest"]
    return loc


def build_continuation_scenario():
    scn = yaml.safe_load(open(BASE_SCENARIO, encoding="utf-8"))
    loc = reconstruct_positions(scn)
    moved = 0
    for a in scn["agents"]:
        if a.get("kind") == "character" and not a.get("archived"):
            new = loc.get(a["id"])
            if new:
                st = a.setdefault("status", {})
                if st.get("location") != new:
                    moved += 1
                st["location"] = new
    # drop the tick-0 kickoff so the continuation isn't re-seeded with the
    # opening beat -- the reused memory already reflects it.
    scn.pop("kickoff", None)
    cont_path = f"scenarios/three_kingdoms.cont_{method}.sim.yaml"
    yaml.safe_dump(scn, open(cont_path, "w", encoding="utf-8"), allow_unicode=True, sort_keys=False)
    print(f"[{method}] continuation scenario: {cont_path} | repositioned {moved} chars", flush=True)
    return cont_path


async def main():
    cont = build_continuation_scenario()
    t0 = time.monotonic()
    r = await run_sim(
        cont, method, out_dir,
        max_ticks=50, seed=0, config_path="config_flash.json",
        ltm_file=f"{run_dir}/ltm_final.json", skip_prime=True,
    )
    r["_wall_min"] = (time.monotonic() - t0) / 60
    print(json.dumps({k: v for k, v in r.items() if k != "per_tick_memory"}, ensure_ascii=False))


asyncio.run(main())
