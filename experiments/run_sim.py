"""Task S3: single-run experiment wrapper.

Runs ONE (scenario, memory backend, seed) combination end-to-end and writes
a self-contained result directory: `result.json` (the per-run metrics the
paper's experiment matrix consumes), `transcripts/*.md` (reused from
`society.run.write_transcripts`), `events.jsonl` (the raw EventLog, written
incrementally as the run progresses), and `ltm_final.json` (the holographic
memory export, for later offline evaluation via `society.evaluation`).

This module deliberately does NOT do the 32-run matrix orchestration or any
evaluation-metric SCORING (event hit rate, QA accuracy, ...) -- those are a
separate, later task. It only runs the simulation and records footprint/cost/
adaptive-stop bookkeeping for a single run.
"""

import argparse
import asyncio
import json
import os
import time

from society import evaluation
from society.events import EventLog
from society.run import _build_llm_and_embed, write_transcripts
from society.scenario import build_society, load_scenario

_MEMORY_KINDS = ("consensus", "generative_agents", "g_memory", "collaborative")

# stop_reason values this module can produce, beyond whatever
# Kernel.run() itself reports (currently "quiescent", "budget", "wall_time",
# "max_ticks" -- see society/kernel.py):
#   "adaptive_target": (current_total - sediment_start) >= adaptive_new_memories
_ADAPTIVE_STOP_REASON = "adaptive_target"


async def _step_until_stop(kernel, *, max_ticks: int, adaptive_new_memories, sediment_start: int):
    """Run `kernel` one tick at a time (reusing `Kernel.run`'s absolute
    `max_ticks` semantics -- each call just asks for one more tick than the
    kernel has already reached) until a stop condition fires.

    Returns (stop_reason, per_tick_memory) where per_tick_memory[i] is the
    shared-memory `stats()["total"]` count as of the END of tick i+1 (so
    len(per_tick_memory) == the final kernel.tick, i.e. ticks_run). Stepping
    by 1 tick at a time is what lets us (a) take a memory-count reading
    after every single tick for `per_tick_memory`, and (b) check the
    adaptive-target delta between every tick -- both needs are served by
    the same mechanism, one direct probe of `shared.stats()["total"]" per
    tick.

    A single `kernel.run(max_ticks=t)` call can advance `kernel.tick` by
    MORE than requested (Kernel.run's fast-forward: if no agent is awake
    and nothing was delivered, it jumps straight to the next pending
    timer/arrival). When that happens here, the skipped ticks are
    backfilled with the same memory count (nothing changed during a
    fast-forward by definition), so per_tick_memory always ends up exactly
    `ticks_run` entries long regardless of fast-forwards.
    """
    shared = kernel.shared_memory
    per_tick_memory: list[int] = []
    last_recorded_tick = 0

    while True:
        if kernel.tick >= max_ticks:
            return "max_ticks", per_tick_memory

        target = min(kernel.tick + 1, max_ticks)
        summary = await kernel.run(max_ticks=target)

        total = shared.stats()["total"]
        while last_recorded_tick < kernel.tick:
            per_tick_memory.append(total)
            last_recorded_tick += 1

        if summary["stop_reason"] in ("quiescent", "budget", "wall_time"):
            return summary["stop_reason"], per_tick_memory

        if (
            adaptive_new_memories is not None
            and (total - sediment_start) >= adaptive_new_memories
        ):
            return _ADAPTIVE_STOP_REASON, per_tick_memory

        # summary["stop_reason"] == "max_ticks" just means this single-tick
        # increment finished normally -- loop again and let the top-of-loop
        # check (or the next iteration's adaptive check) decide whether to
        # keep going.


async def run_sim(
    scenario_path: str,
    memory_kind: str,
    out_dir: str,
    *,
    max_ticks: int,
    adaptive_new_memories: int | None = None,
    seed: int = 0,
    config_path: str = "config.json",
    llm=None,
    embed_fn=None,
    wake_all_characters: bool | None = None,
) -> dict:
    """Run ONE (scenario, memory backend, seed) and write a self-contained
    result to `out_dir`.

    `llm`/`embed_fn` are optional injection points (tests pass a FakeLLM +
    a fake embed function here so nothing ever hits a real API); when
    either is omitted, it is built from `config_path` via
    `society.run._build_llm_and_embed` -- the same real-LLMClient path
    `society.run.main` uses.

    `seed` is a run-replicate LABEL ONLY, recorded verbatim in
    result.json["seed"] -- there is no LLM-output RNG in this codebase to
    fix, so passing the same seed twice does NOT reproduce identical LLM
    outputs. It exists purely so the experiment matrix can distinguish
    replicate runs of the same (scenario, memory_kind) pair on disk;
    determinism of EVENT ORDER/SCHEDULING (not LLM content) comes from the
    kernel's deterministic tick-barrier scheduler, not from this seed.

    `wake_all_characters` (Task S4): overrides the scenario's
    `defaults.wake_all_characters` (see `society.scenario.build_society`)
    on the built kernel's config. `None` (the default) leaves the
    scenario's own setting in place; `True`/`False` forces the "every
    character eligible every tick" ablation arm on/off regardless of what
    the scenario file says.

    Adaptive-tick stop (Task S3 criterion): when `adaptive_new_memories`
    (N) is given, the kernel is run in 1-tick increments until
    `(shared.stats()["total"] - sediment_start) >= N` (stop_reason
    "adaptive_target") or `max_ticks` is reached (stop_reason "max_ticks"),
    whichever comes first. When `adaptive_new_memories` is None, the run
    simply goes to `max_ticks` (or quiesces/budgets out first, exactly as
    `run_scenario` does).

    Writes to `out_dir`:
      - `events.jsonl`: the raw EventLog (written incrementally as the run
        progresses, same as `run_scenario`).
      - `transcripts/<agent_id>.md`: per-agent markdown, via
        `society.run.write_transcripts`.
      - `ltm_final.json`: `shared.export()` -- the holographic memory dump,
        for later offline evaluation (`society.evaluation`).
      - `result.json`: {"scenario", "memory_kind", "seed", "ticks_run",
        "stop_reason", "footprint", "cost", "sediment_memories",
        "new_memories", "per_tick_memory"} -- see the module docstring.

    Returns the same dict written to result.json.
    """
    if llm is None or embed_fn is None:
        cfg_llm, cfg_embed_fn = _build_llm_and_embed(config_path)
        if llm is None:
            llm = cfg_llm
        if embed_fn is None:
            embed_fn = cfg_embed_fn

    os.makedirs(out_dir, exist_ok=True)

    cfg = load_scenario(scenario_path)
    event_log = EventLog(os.path.join(out_dir, "events.jsonl"))

    kernel = await build_society(
        cfg,
        llm=llm,
        embed_fn=embed_fn,
        event_log=event_log,
        out_dir=out_dir,
        memory_kind=memory_kind,
    )

    if wake_all_characters is not None:
        kernel.config["wake_all_characters"] = wake_all_characters

    # Starting memory count: the post-restore (or post-seed) sediment size,
    # BEFORE any tick runs.
    sediment_start = kernel.shared_memory.stats()["total"]

    wall_start = time.monotonic()
    stop_reason, per_tick_memory = await _step_until_stop(
        kernel,
        max_ticks=max_ticks,
        adaptive_new_memories=adaptive_new_memories,
        sediment_start=sediment_start,
    )
    wall_s = time.monotonic() - wall_start

    if kernel.metrics is not None:
        kernel.metrics.snapshot(kernel.tick)

    write_transcripts(kernel.event_log.all(), kernel.agents, out_dir)

    with open(os.path.join(out_dir, "ltm_final.json"), "w", encoding="utf-8") as f:
        json.dump(kernel.shared_memory.export(), f, ensure_ascii=False)

    usage_fn = getattr(llm, "usage", None)
    usage = usage_fn() if usage_fn is not None else {}

    final_total = kernel.shared_memory.stats()["total"]

    result = {
        "scenario": scenario_path,
        "memory_kind": memory_kind,
        "seed": seed,
        "ticks_run": kernel.tick,
        "stop_reason": stop_reason,
        "footprint": evaluation.footprint(kernel.shared_memory),
        "cost": evaluation.cost_summary(usage, wall_s),
        "sediment_memories": sediment_start,
        "new_memories": final_total - sediment_start,
        "per_tick_memory": per_tick_memory,
    }

    with open(os.path.join(out_dir, "result.json"), "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    return result


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Run one (scenario, memory backend, seed) simulation and write result.json"
    )
    parser.add_argument("--scenario", required=True, help="path to scenario yaml")
    parser.add_argument(
        "--memory", choices=_MEMORY_KINDS, default="consensus", help="shared-memory backend"
    )
    parser.add_argument("--out", required=True, help="output directory")
    parser.add_argument("--max-ticks", type=int, required=True, help="hard cap on ticks")
    parser.add_argument(
        "--adaptive-new-memories",
        type=int,
        default=None,
        help="stop once this many NEW memories have been deposited since the "
        "post-restore starting count (default: run to --max-ticks fixed)",
    )
    parser.add_argument(
        "--seed", type=int, default=0, help="run-replicate label only (no LLM RNG; see run_sim docstring)"
    )
    parser.add_argument(
        "--config", default="config.json", help="path to config.json (api_key, base_url, ...)"
    )
    wake_all_group = parser.add_mutually_exclusive_group()
    wake_all_group.add_argument(
        "--wake-all", dest="wake_all_characters", action="store_true", default=None,
        help="force every character eligible every tick (overrides scenario default)",
    )
    wake_all_group.add_argument(
        "--no-wake-all", dest="wake_all_characters", action="store_false",
        help="force event-driven scheduling for characters (overrides scenario default)",
    )
    args = parser.parse_args(argv)

    result = asyncio.run(
        run_sim(
            args.scenario,
            args.memory,
            args.out,
            max_ticks=args.max_ticks,
            adaptive_new_memories=args.adaptive_new_memories,
            seed=args.seed,
            config_path=args.config,
            wake_all_characters=args.wake_all_characters,
        )
    )
    print(json.dumps(result, ensure_ascii=False))
    return result


if __name__ == "__main__":
    main()
