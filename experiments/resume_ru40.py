"""Resume the four Russia-Ukraine 20-tick runs to 40 ticks (one backend per
invocation): reads runs/ru20_<m>/checkpoints/ckpt_final.json, writes runs/ru40_<m>.

Run: venv/bin/python -m experiments.resume_ru40 <memory_kind>
"""
import asyncio
import json
import sys

from experiments.run_sim import run_sim


def main():
    m = sys.argv[1]
    result = asyncio.run(run_sim(
        "scenarios/russia_ukraine.sim.yaml",
        m,
        f"runs/ru40_{m}",
        max_ticks=40,
        config_path="config_flash.json",
        checkpoint_every=20,
        resume_from=f"runs/ru20_{m}/checkpoints/ckpt_final.json",
    ))
    print(json.dumps({k: result.get(k) for k in ("ticks", "memory_kind", "wall_seconds")},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
