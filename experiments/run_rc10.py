"""红楼梦 10-tick pilot, one backend per invocation (mirrors the ru10 launch:
seed=0, config_flash, checkpoint at the end).

Run: venv/bin/python -m experiments.run_rc10 <memory_kind>
"""
import asyncio
import json
import sys
import time

from experiments.run_sim import run_sim


def main():
    kind = sys.argv[1]
    t0 = time.monotonic()
    r = asyncio.run(run_sim(
        "scenarios/red_chamber.sim.yaml",
        kind,
        f"runs/rc10_{kind}",
        max_ticks=10,
        seed=0,
        config_path="config_flash.json",
        checkpoint_every=10,
    ))
    r["_wall_min"] = (time.monotonic() - t0) / 60
    print(json.dumps({k: v for k, v in r.items() if k != "per_tick_memory"},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
