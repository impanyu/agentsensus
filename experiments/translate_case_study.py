"""Translate the case-study graph data so the interactive figures read in English.

The graphs carry two kinds of text the paper shows on hover: the stored memory
records themselves, and the agent ids used as node labels. Both are rendered as
English with the original alongside (the paper's convention for proper nouns and
for source-language lines), so a reader who does not read Chinese can follow the
figures while the record stays verifiable.

Writes `case_study/translations.json` next to each `graphs.json`:
    {"texts": {<original>: <english>}, "agents": {<id>: <English Name>}}
Existing entries are kept, so a re-run only translates what is new.

Run: venv/bin/python -m experiments.translate_case_study [run_dir ...]
"""
import asyncio
import json
import os
import sys

os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); sys.path.insert(0, ".")
import yaml

from society import evaluation as ev
from society.run import _build_llm_and_embed

DEFAULT_DIRS = ["runs/g80full_consensus", "runs/rc80full_consensus",
                "runs/ru40full_consensus", "runs/hl40full_consensus"]
BATCH = 30


def _has_cjk(s):
    return any("一" <= c <= "鿿" for c in s)


def _scenario_of(run_dir):
    stem = os.path.basename(run_dir).split("full")[0]
    return {"g80": "three_kingdoms", "rc80": "red_chamber",
            "ru40": "russia_ukraine", "hl40": "hamlet",
            "hl30": "hamlet"}[stem]


async def _batch(llm, items, instruction, retries=2):
    """Translate a {key: text} batch, returning {key: english}."""
    prompt = (instruction + "\n\n" + json.dumps(items, ensure_ascii=False, indent=1)
              + '\n\nReturn STRICT JSON mapping every key above to its English '
                'string. Return ONLY the JSON.')
    for _ in range(retries + 1):
        reply = await llm.chat(prompt, system=None, bucket="translate")
        parsed = ev._parse_json(reply, default=None)
        if isinstance(parsed, dict) and parsed:
            return {k: str(v) for k, v in parsed.items() if k in items}
    return {}


async def translate_dir(run_dir, llm):
    gpath = os.path.join(run_dir, "case_study", "graphs.json")
    tpath = os.path.join(run_dir, "case_study", "translations.json")
    graphs = json.load(open(gpath, encoding="utf-8"))
    cache = json.load(open(tpath, encoding="utf-8")) if os.path.exists(tpath) else {}
    texts = cache.setdefault("texts", {})
    agents = cache.setdefault("agents", {})

    # --- agent display names (proper nouns: English, original kept by the page)
    cfg = yaml.safe_load(open(f"scenarios/{_scenario_of(run_dir)}.sim.yaml", encoding="utf-8"))
    names = {a["id"]: (a.get("name") or a["id"]) for a in cfg.get("agents", [])}
    ids = ({n["id"] for n in graphs["interaction"]["nodes"]}
           | {a["id"] for a in graphs["trilayer"]["agents"]}
           | set(graphs["heatmap"]["order"]))
    todo = {i: names.get(i, i) for i in sorted(ids) if i not in agents}
    for k in range(0, len(todo), BATCH):
        chunk = dict(list(todo.items())[k:k + BATCH])
        agents.update(await _batch(
            llm, chunk,
            "Give the standard English name for each character, place or "
            "organization. Keys are agent ids, values are their names in the "
            "source language. Use the conventional English rendering where one "
            "exists (e.g. a well-known translation of a classical novel's "
            "character), otherwise standard romanization. Keep it short."))

    # --- memory records (source-language lines: English, original kept by the page)
    pending = sorted({t for t in
                      [n["text"] for n in graphs["affiliation"]["nodes"]]
                      + [m["text"] for m in graphs["trilayer"]["mems"]]
                      if _has_cjk(t) and t not in texts})
    for k in range(0, len(pending), BATCH):
        chunk = {str(k + n): t for n, t in enumerate(pending[k:k + BATCH])}
        out = await _batch(
            llm, chunk,
            "Translate each memory record into concise English. These are "
            "records from a story-world simulation: keep every concrete "
            "particular (names, places, objects, numbers, titles, the target "
            "and outcome of an action), use the conventional English names of "
            "characters and places, and do not add or drop information.")
        for n, eng in out.items():
            if n in chunk:
                texts[chunk[n]] = eng
        print(f"  {run_dir}: {len(texts)}/{len(pending) + len(texts) - len(out)} texts", flush=True)

    json.dump(cache, open(tpath, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{run_dir}: {len(agents)} agents, {len(texts)} texts -> {tpath}", flush=True)


async def main(dirs):
    llm, _ = _build_llm_and_embed("config_flash.json")
    for d in dirs:
        await translate_dir(d, llm)


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1:] or DEFAULT_DIRS))
