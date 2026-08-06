"""Resume the four 红楼梦 60-tick runs to 80 ticks (one backend per
invocation): reads runs/rc60_<m>/checkpoints/ckpt_final.json, writes
runs/rc80_<m>.

checkpoint_every=20 lands a single snapshot at tick 80 for this leg (ticks
61-80), which is what a further resume would start from.

Run: venv/bin/python -m experiments.resume_rc80 <memory_kind>
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
        f"runs/rc80_{m}",
        max_ticks=80,
        seed=0,
        config_path="config_flash.json",
        checkpoint_every=20,
        resume_from=f"runs/rc60_{m}/checkpoints/ckpt_final.json",
    ))
    r["_wall_min"] = (time.monotonic() - t0) / 60
    print(json.dumps({k: r.get(k) for k in
                      ("ticks_run", "memory_kind", "stop_reason", "_wall_min")},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
