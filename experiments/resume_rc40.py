"""Resume the four 红楼梦 10-tick pilots to 40 ticks (one backend per
invocation): reads runs/rc10_<m>/checkpoints/ckpt_final.json, writes runs/rc40_<m>.

checkpoint_every=40 deliberately writes only the end-of-run snapshot: each
红楼 baseline checkpoint is ~880MB, so intermediate snapshots would cost
~2.6GB of headroom that this machine does not have.

Run: venv/bin/python -m experiments.resume_rc40 <memory_kind>
"""
import asyncio
import json
import sys
import time

from experiments.run_sim import run_sim


def main():
    m = sys.argv[1]
    t0 = time.monotonic()
    result = asyncio.run(run_sim(
        "scenarios/red_chamber.sim.yaml",
        m,
        f"runs/rc40_{m}",
        max_ticks=40,
        seed=0,
        config_path="config_flash.json",
        checkpoint_every=40,
        resume_from=f"runs/rc10_{m}/checkpoints/ckpt_final.json",
    ))
    result["_wall_min"] = (time.monotonic() - t0) / 60
    print(json.dumps({k: result.get(k) for k in
                      ("ticks_run", "memory_kind", "stop_reason", "_wall_min")},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
