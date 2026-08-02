"""Measure remember/recall latency for a PAST stage by replaying its logged
operations against the store state that stage actually started from.

This is a MEASUREMENT, not a synthesis: the ops (same agent, same text/query,
same order) come from the stage's own events.jsonl, and the starting store is
the real checkpoint the stage resumed from (the sediment restore for the first
stage). Each replayed call is timed the same way the live instrumentation
times it. Output: runs/<stage>_<backend>/mem_ops_replay.jsonl with
{"op","tick","agent","s","replay":true} per line -- kept in a separate file
from live mem_ops.jsonl so provenance stays explicit.

Caveat (disclosed): for the first stage, GA/G-Memory replay stores lack their
prime by-products (reflection/insight rows, ~3-5% of rows); later stages use
exact checkpoints.

Usage: replay_mem_latency.py <backend> <stage g20|g40|g60>
"""
import os
import sys
import json
import time
import asyncio

os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); sys.path.insert(0, ".")

from society.baselines import make_memory
from society.run import _build_llm_and_embed
from society.scenario import load_scenario

BACKEND = sys.argv[1]
STAGE = sys.argv[2]
PREV = {"g20": None, "g40": "g20", "g60": "g40"}[STAGE]
OUT_DIR = f"runs/{STAGE}_{BACKEND}"


async def start_entries():
    """The LTM rows the stage started from."""
    if PREV is None:
        cfg = load_scenario("scenarios/three_kingdoms.sim.yaml")
        path = os.path.join(cfg.get("_dir", "."), cfg["ltm_file"])
        return json.load(open(path, encoding="utf-8"))
    ck = json.load(open(f"runs/{PREV}_{BACKEND}/checkpoints/ckpt_final.json", encoding="utf-8"))
    return ck["ltm"]


async def main():
    llm, embed = _build_llm_and_embed("config_flash.json")
    mem = make_memory(BACKEND, embed, llm=llm, max_tokens=50,
                      collection_name=f"replay_{STAGE}_{BACKEND}")
    entries = await start_entries()
    await mem.restore(entries)
    print(f"[{BACKEND}/{STAGE}] start store: {mem.stats()['total']} rows", flush=True)

    ops = []
    for line in open(f"{OUT_DIR}/events.jsonl", encoding="utf-8"):
        e = json.loads(line)
        if e.get("kind") != "action":
            continue
        a = e.get("action") or {}
        if a.get("name") in ("remember", "recall"):
            ops.append((e["tick"], e["agent"], a["name"], a.get("params") or {}))

    recs = []
    for tick, agent, name, params in ops:          # sequential: store evolves as it did
        t0 = time.monotonic()
        if name == "remember":
            await mem.remember(agent, params.get("text", ""), tick)
        else:
            await mem.recall(agent, params.get("query", ""), params.get("top_k", 5))
        recs.append({"op": name, "tick": tick, "agent": agent,
                     "s": time.monotonic() - t0, "replay": True})

    with open(f"{OUT_DIR}/mem_ops_replay.jsonl", "w", encoding="utf-8") as f:
        for r in recs:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    n_rem = sum(1 for r in recs if r["op"] == "remember")
    print(f"[{BACKEND}/{STAGE}] replayed {len(recs)} ops ({n_rem} remember, "
          f"{len(recs)-n_rem} recall) -> {OUT_DIR}/mem_ops_replay.jsonl", flush=True)


asyncio.run(main())
