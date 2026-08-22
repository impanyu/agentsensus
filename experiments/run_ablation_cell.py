"""Run ONE ablation cell: consensus backend on 三国, with a given
(consensus_merge, cache_strategy).

The grid is one-factor-at-a-time from the paper's own configuration,
(merge on, cache fifo), so four cells are used:

    on  / fifo       the paper's configuration -- rerun here rather than
                     reused, because runs/g40_consensus predates the
                     content-language directive of 14a2ae6 and comparing
                     against it would mix the knob with a prompt change
    on  / relevance  evict the STM pair least similar to the incoming one
    on  / hybrid     evict on alpha*recency + (1-alpha)*relevance
    off / fifo       no consensus merge: every deposit stays per-owner

All four are single 40-round runs from the same sedimented start, under
the current code, so only the knob differs.

Usage: run_ablation_cell.py <on|off> <fifo|relevance|hybrid> [rounds]
"""
import os, sys, asyncio, json, time
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); sys.path.insert(0, ".")
from experiments.run_sim import run_sim

merge = sys.argv[1] == "on"
cache = sys.argv[2]
rounds = int(sys.argv[3]) if len(sys.argv) > 3 else 40
out = f"runs/abl_{'on' if merge else 'off'}_{cache}"


async def main():
    t0 = time.monotonic()
    r = await run_sim("scenarios/three_kingdoms.sim.yaml", "consensus", out,
                      max_ticks=rounds, seed=0, config_path="config_flash.json",
                      consensus_merge=merge, cache_strategy=cache,
                      checkpoint_every=20)
    r["_wall_min"] = (time.monotonic() - t0) / 60
    print(json.dumps({k: v for k, v in r.items() if k != "per_tick_memory"},
                     ensure_ascii=False), flush=True)

asyncio.run(main())
