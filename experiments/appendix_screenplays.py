"""Render the consensus run's full screenplay for each world, for the appendix.

Chinese worlds get both renderings -- the scenario's own language and an
English one produced in a single grounded pass (never a translation of the
Chinese screenplay) -- so the appendix can print them side by side. English
worlds get one.

Output: runs/screenplays/<world>.<lang>.md

Run: venv/bin/python -m experiments.appendix_screenplays [world ...]
"""
import asyncio
import json
import os
import sys

os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); sys.path.insert(0, ".")

from society.events import EventLog
from society.run import _build_llm_and_embed
from society.scenario import load_scenario
from society.screenplay import generate_screenplay

WORLDS = {
    "three_kingdoms": (["g20", "g40", "g60", "g80"], "scenarios/three_kingdoms.sim.yaml",
                       ["zh", "en"], "runs/g80full_consensus"),
    "red_chamber": (["rc10", "rc40", "rc60", "rc80"], "scenarios/red_chamber.sim.yaml",
                    ["zh", "en"], "runs/rc80full_consensus"),
    "russia_ukraine": (["ru10", "ru20", "ru40"], "scenarios/russia_ukraine.sim.yaml",
                       ["en"], "runs/ru40full_consensus"),
    "hamlet": (["hl20", "hl30", "hl40"], "scenarios/hamlet.sim.yaml",
               ["en"], "runs/hl40full_consensus"),
}
OUT = "runs/screenplays"


async def render(world, llm):
    stages, scenario, langs, case_dir = WORLDS[world]
    cfg = load_scenario(scenario)
    language = cfg.get("language", "zh")
    source_names = {a["id"]: a.get("name") for a in cfg.get("agents", []) if a.get("id")}
    kinds = {a["id"]: a.get("kind") for a in cfg.get("agents", []) if a.get("id")}
    # An English screenplay must name people in English; the scenario files carry
    # Chinese display names for every world, so reuse the glossed names built for
    # the case-study figures and fall back to a readable form of the id.
    tpath = os.path.join(case_dir, "case_study", "translations.json")
    glossed = (json.load(open(tpath, encoding="utf-8")).get("agents", {})
               if os.path.exists(tpath) else {})
    english_names = {i: glossed.get(i) or i.replace("_", " ").title() for i in source_names}
    events = []
    for st in stages:
        p = f"runs/{st}_consensus/events.jsonl"
        if os.path.exists(p):
            events.extend(EventLog.load(p))
    os.makedirs(OUT, exist_ok=True)
    for target in langs:
        out = f"{OUT}/{world}.{target}.md"
        if os.path.exists(out):
            print(f"{out} exists, skipping", flush=True)
            continue
        md = await generate_screenplay(
            events, llm, out_path=out, language=language,
            names=(english_names if target == "en" else source_names),
            target_language=target, kinds=kinds)
        print(f"{out}: {len(md)} chars, {md.count('##')} scenes", flush=True)


async def main(worlds):
    llm, _ = _build_llm_and_embed("config_flash.json")
    for w in worlds:
        print(f"=== {w}", flush=True)
        await render(w, llm)


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1:] or list(WORLDS)))
