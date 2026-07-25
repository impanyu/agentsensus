"""Task S2.1 backfill: place existing info_carrier agents.

One-off script for scenarios that were extracted BEFORE the Task S2.1 fix
to `_assemble_history_scenario` (which now assigns every info_carrier
agent a location -- and optionally portable/holder -- via
`_assign_carrier_placements`, run from `extract_history` right before
assembly). Scenario yamls extracted before that fix have every
info_carrier agent frozen at `"status": {}`, no `portable`/`holder`
-- which makes Kernel `_is_readable` (society/kernel.py) permanently
`False` for them (it requires the reader to share the carrier's location,
or the carrier to be portable-and-held), so `read` was unreachable for
e.g. Hamlet's love_letter/sealed_commission/gonzago_script, three_kingdoms's
5 carriers, red_chamber's 9.

This script re-runs the SAME `_assign_carrier_placements` LLM call against
an existing scenario's already-written registry (no duplicated prompt/
parse/fallback logic -- imported straight from society.history_extract,
covered by tests/test_carrier_placement.py) and patches the scenario
yaml's info_carrier agents in place: `status.location`, `portable`
(present only if true), `holder` (present only if resolved).

Usage:
    venv/bin/python -m experiments.place_carriers hamlet
    venv/bin/python -m experiments.place_carriers hamlet three_kingdoms red_chamber
    venv/bin/python -m experiments.place_carriers --scenarios-dir scenarios \\
        --config config.json hamlet

For each SCENARIO name, expects `<scenarios-dir>/<name>.yaml` (the
scenario file to patch, overwritten in place) and
`<scenarios-dir>/<name>.yaml.registry.json` (the registry
`extract_history` wrote alongside it) to both already exist.
"""
import argparse
import asyncio
import json
import os

import yaml

from society.history_extract import _assign_carrier_placements
from society.run import _build_llm_and_embed

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_SCENARIOS_DIR = os.path.join(BASE, "scenarios")
DEFAULT_CONFIG = os.path.join(BASE, "config.json")


async def place_one(name: str, scenarios_dir: str, llm) -> None:
    """Loads `<scenarios_dir>/<name>.yaml` + its `.registry.json` sidecar,
    runs `_assign_carrier_placements`, patches every info_carrier agent's
    status/portable/holder in place, and overwrites the yaml. Prints one
    line per patched carrier plus any warnings; raises FileNotFoundError
    if either file is missing (fail loudly rather than silently skip --
    this is an explicit one-off backfill, not a best-effort batch job)."""
    yaml_path = os.path.join(scenarios_dir, f"{name}.yaml")
    registry_path = yaml_path + ".registry.json"
    if not os.path.exists(yaml_path):
        raise FileNotFoundError(yaml_path)
    if not os.path.exists(registry_path):
        raise FileNotFoundError(registry_path)

    with open(yaml_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    with open(registry_path, "r", encoding="utf-8") as f:
        registry = json.load(f)

    warnings: list[str] = []
    placements = await _assign_carrier_placements(llm, registry, warnings)

    for w in warnings:
        print(f"[{name}] warning: {w}")

    if not placements:
        print(f"[{name}] no placements produced (no carriers, or no environments); yaml unchanged")
        return

    patched = 0
    for agent in cfg.get("agents", []):
        if agent.get("kind") != "info_carrier":
            continue
        placement = placements.get(agent.get("id"))
        if placement is None:
            continue

        loc = placement.get("location")
        portable = bool(placement.get("portable", False))
        holder = placement.get("holder")

        agent["status"] = {"location": loc} if loc is not None else {}
        if portable:
            agent["portable"] = True
        else:
            agent.pop("portable", None)
        if holder is not None:
            agent["holder"] = holder
        else:
            agent.pop("holder", None)

        patched += 1
        print(f"[{name}] {agent['id']}: location={loc!r} portable={portable} holder={holder!r}")

    with open(yaml_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(cfg, f, allow_unicode=True, sort_keys=False)
    print(f"[{name}] patched {patched} carrier agent(s); wrote {yaml_path}")


async def main_async(args: argparse.Namespace) -> None:
    llm, _embed_fn = _build_llm_and_embed(args.config)
    for name in args.scenario:
        await place_one(name, args.scenarios_dir, llm)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Backfill info_carrier placements (location/portable/holder) into "
            "already-extracted history-sedimentation scenario yaml(s), so Kernel "
            "`_is_readable` can be satisfied and `read` becomes reachable for them."
        )
    )
    parser.add_argument(
        "scenario",
        nargs="+",
        help="scenario name(s) (e.g. hamlet), matching <scenarios-dir>/<name>.yaml",
    )
    parser.add_argument(
        "--scenarios-dir",
        default=DEFAULT_SCENARIOS_DIR,
        help=f"directory holding <name>.yaml + <name>.yaml.registry.json (default: {DEFAULT_SCENARIOS_DIR})",
    )
    parser.add_argument(
        "--config",
        default=DEFAULT_CONFIG,
        help=f"LLM config.json path (default: {DEFAULT_CONFIG})",
    )
    args = parser.parse_args()
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
