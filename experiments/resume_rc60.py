"""Resume the four 红楼梦 40-tick runs to 60 ticks (one backend per
invocation): reads runs/rc40_<m>/checkpoints/ckpt_final.json, writes
runs/rc60_<m>.

checkpoint_every=20 lands a single snapshot at tick 60 for this leg (ticks
41-60), which is what a further resume would start from.

Run: venv/bin/python -m experiments.resume_rc60 <memory_kind>
"""
import asyncio
import json
import sys
import time

from experiments.run_sim import run_sim


def main():
    m = sys.argv[1]
    t0 = time.monotonic()
    r = asyncio.run(run_sim(
        "scenarios/red_chamber.sim.yaml",
        m,
        f"runs/rc60_{m}",
        max_ticks=60,
        seed=0,
        config_path="config_flash.json",
        checkpoint_every=20,
        resume_from=f"runs/rc40_{m}/checkpoints/ckpt_final.json",
    ))
    r["_wall_min"] = (time.monotonic() - t0) / 60
    print(json.dumps({k: r.get(k) for k in
                      ("ticks_run", "memory_kind", "stop_reason", "_wall_min")},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
