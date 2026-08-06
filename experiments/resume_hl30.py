"""Resume the four Hamlet 20-tick runs to 30 ticks (one backend per
invocation): reads runs/hl20_<m>/checkpoints/ckpt_final.json, writes
runs/hl30_<m>.

Run: venv/bin/python -m experiments.resume_hl30 <memory_kind>
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
        "scenarios/hamlet.sim.yaml",
        m,
        f"runs/hl30_{m}",
        max_ticks=30,
        seed=0,
        config_path="config_flash.json",
        checkpoint_every=30,
        resume_from=f"runs/hl20_{m}/checkpoints/ckpt_final.json",
    ))
    r["_wall_min"] = (time.monotonic() - t0) / 60
    print(json.dumps({k: r.get(k) for k in
                      ("ticks_run", "memory_kind", "stop_reason", "_wall_min")},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
