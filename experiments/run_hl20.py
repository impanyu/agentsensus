"""Hamlet 20-tick run, one backend per invocation (same launch protocol as
run_rc10: seed=0, config_flash, single end-of-run checkpoint).

Run: venv/bin/python -m experiments.run_hl20 <memory_kind>
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
        "scenarios/hamlet.sim.yaml",
        kind,
        f"runs/hl20_{kind}",
        max_ticks=20,
        seed=0,
        config_path="config_flash.json",
        checkpoint_every=20,
    ))
    r["_wall_min"] = (time.monotonic() - t0) / 60
    print(json.dumps({k: r.get(k) for k in
                      ("ticks_run", "memory_kind", "stop_reason", "_wall_min")},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
