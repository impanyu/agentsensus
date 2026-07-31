"""Run ONE ablation cell: consensus backend on 三国, with a given
(consensus_merge, cache_strategy).

The ablation is one-factor-at-a-time from the baseline (on, fifo), so only
FOUR cells are used: (on,fifo) baseline, (on,relevance), (on,hybrid),
(off,fifo). All are (re)run with the current skill docs so they are
skill-consistent with each other (do NOT reuse the old-skill fair3_consensus
for the on/fifo cell).

Usage: run_ablation_cell.py <on|off> <fifo|relevance|hybrid>
"""
import os, sys, asyncio, json, time
os.chdir("/Users/ypan12/git_repo/bookworld_paper/agentsensus"); sys.path.insert(0, ".")
from experiments.run_sim import run_sim

merge = sys.argv[1] == "on"
cache = sys.argv[2]
out = f"runs/abl_{'on' if merge else 'off'}_{cache}"

async def main():
    t0 = time.monotonic()
    r = await run_sim("scenarios/three_kingdoms.sim.yaml", "consensus", out,
                      max_ticks=50, seed=0, config_path="config_flash.json",
                      consensus_merge=merge, cache_strategy=cache)
    r["_wall_min"] = (time.monotonic() - t0) / 60
    print(json.dumps({k: v for k, v in r.items() if k != "per_tick_memory"}, ensure_ascii=False))

asyncio.run(main())
