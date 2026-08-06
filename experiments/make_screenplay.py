"""Render a run's screenplay in its scenario's language.

The scenario's `language` field is the script's default language -- 三国 and
红楼 render in Chinese, Hamlet and Russia-Ukraine in English -- and it is
passed as the target language, so a run whose event log is mixed-language
(any run made before the content-language directive in
society/brains/llm_brain.py) is normalized to that one language at render
time rather than by re-running the simulation.

Run:  venv/bin/python -m experiments.make_screenplay runs/hl20_consensus [...]
      venv/bin/python -m experiments.make_screenplay runs/rc40_consensus --also en
"""
import argparse
import asyncio
import json
import os
import sys

os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); sys.path.insert(0, ".")

from society.events import EventLog
from society.run import _build_llm_and_embed
from society.scenario import load_scenario
from society.screenplay import generate_screenplay


def _scenario_of(run_dir: str) -> str:
    """The scenario file a run was produced from (recorded in result.json).

    A resumed run records it as "<path> (resumed from <ckpt> @ tick N)", so
    keep only the path.
    """
    with open(os.path.join(run_dir, "result.json"), encoding="utf-8") as f:
        path = (json.load(f) or {}).get("scenario")
    if not path:
        raise SystemExit(f"{run_dir}: result.json has no 'scenario' field")
    return path.split(" (")[0].strip()


async def render(run_dir: str, also: str | None, config_path: str):
    cfg = load_scenario(_scenario_of(run_dir))
    language = cfg.get("language", "zh")
    names = {a["id"]: a.get("name") for a in cfg.get("agents", []) if a.get("id")}
    events = EventLog.load(os.path.join(run_dir, "events.jsonl"))
    llm, _ = _build_llm_and_embed(config_path)

    out = os.path.join(run_dir, "screenplay.md")
    await generate_screenplay(events, llm, out_path=out, language=language,
                              names=names, target_language=language)
    print(f"{run_dir} -> {out} ({language}, {len(events)} events)")

    if also and also != language:
        out2 = os.path.join(run_dir, f"screenplay_{also}.md")
        await generate_screenplay(events, llm, out_path=out2, language=language,
                                  names=names, target_language=also)
        print(f"{run_dir} -> {out2} ({also})")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dirs", nargs="+")
    ap.add_argument("--also", help="additionally render in this language code")
    ap.add_argument("--config", default="config_flash.json")
    args = ap.parse_args()
    for d in args.run_dirs:
        asyncio.run(render(d.rstrip("/"), args.also, args.config))


if __name__ == "__main__":
    main()
