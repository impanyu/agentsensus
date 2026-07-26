"""Apply per-scenario memory-count thresholds to select the ACTIVE simulated cast.

A character participates in simulation iff it owns MORE than T memories (T chosen
per scenario from its memory-count distribution). Below-threshold characters are
dropped from the agent list but their memories REMAIN in the LTM sidecar (they stay
owners of the shared record — just never scheduled). Environments and info_carriers
are kept as-is. Writes a curated <name>.sim.yaml (original <name>.yaml untouched).

Run: venv/bin/python -m experiments.select_cast
"""
import json
import os
from collections import Counter

import yaml

from society.boundary_state import finalize_boundary_state
from society.history_extract import _split_by_chapters

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SC = os.path.join(BASE, "scenarios")

# per-scenario CHARACTER thresholds (character kept iff memory_count > T)
THRESHOLDS = {
    "three_kingdoms": 50,
    "red_chamber": 100,
    "war_and_peace": 20,
    "russia_ukraine": 3,
}
# per-scenario ENVIRONMENT memory bar (env kept iff it's an active char's location
# OR owns > E memories). Novels: E=0 (>=1 mem) trims well. 俄乌: every timeline
# place has >=1 event memory, so E=5 keeps the real theaters and drops the tail.
ENV_THRESHOLDS = {
    "three_kingdoms": 0,
    "red_chamber": 0,
    "war_and_peace": 0,
    "russia_ukraine": 5,
}


# how many trailing chapters/segments of the sediment span form the boundary
# context, and the sediment chapter count per scenario (mirrors sediment_all.py)
_SEDIMENT_CHAPTERS = {"three_kingdoms": 40, "red_chamber": 40}
_BOUNDARY_TAIL_CHAPTERS = 2
_SOURCE_FILES = {
    "three_kingdoms": ["three_kingdoms_ch01-10.txt", "three_kingdoms_ch11-60.txt"],
    "red_chamber": ["dream_red_chamber_ch01-80.txt"],
}


def boundary_source_tail(name):
    """Raw source text of the last `_BOUNDARY_TAIL_CHAPTERS` chapters of the
    sediment span (with their chapter markers), reused as fallback context.
    Returns "" for scenarios whose source isn't chapter-sliceable here (callers
    then rely on the grounded path + an empty context)."""
    files = _SOURCE_FILES.get(name)
    n = _SEDIMENT_CHAPTERS.get(name)
    if not files or n is None:
        return ""
    src_dir = os.path.join(BASE, "scenarios", "sources")
    parts = []
    for f in files:
        with open(os.path.join(src_dir, f), encoding="utf-8") as fh:
            parts.append(fh.read())
    text = "\n".join(parts)
    chs = _split_by_chapters(text)
    if not chs:
        return ""
    tail = chs[max(0, n - _BOUNDARY_TAIL_CHAPTERS):n]
    return "".join(tail)


def apply_boundary_state(agents, keep_char, finalized):
    """Mutate agent dicts: living -> status.location (when resolved); dead ->
    archived=True. Returns {"archived": int, "relocated": int, "canon": int}."""
    counts = {"archived": 0, "relocated": 0, "canon": 0}
    for a in agents:
        if a.get("kind") != "character" or a["id"] not in keep_char:
            continue
        fin = finalized.get(a["id"])
        if not fin:
            continue
        if fin.get("source") == "canon@boundary":
            counts["canon"] += 1
        if not fin.get("alive", True):
            a["archived"] = True
            # Archived agents are never scheduled/observed (Kernel.is_eligible
            # excludes them), so their location is unused -- and a stale
            # location can dangle if the env-trim below drops that env,
            # which the scenario loader then rejects (status.location must
            # reference a live environment). Drop it so the loader's
            # `loc is not None` guard simply skips archived agents.
            a.get("status", {}).pop("location", None)
            counts["archived"] += 1
            continue
        loc = fin.get("location")
        if loc:  # resolved on-list location; otherwise keep the pre-existing one
            st = a.setdefault("status", {})
            if st.get("location") != loc:
                counts["relocated"] += 1
            st["location"] = loc

    # Any archived character (whether archived this run or already archived in
    # the base scenario) must not carry a status.location: it is never
    # scheduled, and env-trim can remove the env its stale location points to,
    # which would make the scenario fail to load (scenario.py validates
    # location membership for ALL characters, archived included).
    for a in agents:
        if a.get("kind") == "character" and a.get("archived"):
            a.get("status", {}).pop("location", None)
    return counts


def char_mem_counts(ltm, char_ids):
    cnt = Counter()
    for e in ltm:
        for o in e.get("owners", []):
            if o in char_ids:
                cnt[o] += 1
    return cnt


def curate(name, T):
    yml = os.path.join(SC, f"{name}.yaml")
    d = yaml.safe_load(open(yml, encoding="utf-8"))
    ltm = json.load(open(os.path.join(SC, f"{name}.yaml.ltm.json"), encoding="utf-8"))
    agents = d["agents"]
    char_ids = {a["id"] for a in agents if a.get("kind") == "character"}
    cnt = char_mem_counts(ltm, char_ids)

    keep_char = {cid for cid in char_ids if cnt.get(cid, 0) > T}
    dropped = char_ids - keep_char

    # Trim environments: keep an env iff it is an active character's location OR
    # it owns >=1 memory. Drops one-off place names that no active agent uses.
    env_ids = {a["id"] for a in agents if a.get("kind") == "environment"}
    env_mem = char_mem_counts(ltm, env_ids)  # reuse: counts memories owned by each env id

    # Boundary-state finalization: place living cast at canonical boundary
    # locations, archive characters dead by the boundary. Grounded in each
    # character's memory timeline; canon fallback anchored to the source tail.
    import asyncio
    from society.run import _build_llm_and_embed
    llm, _embed = _build_llm_and_embed(os.path.join(BASE, "config_flash.json"))
    finalized = asyncio.run(finalize_boundary_state(
        ltm, sorted(keep_char), env_ids,
        llm=llm, boundary_context=boundary_source_tail(name),
    ))
    bcounts = apply_boundary_state(agents, keep_char, finalized)
    # An archived (dead) character stays a registered agent -- still an owner
    # of its memories, kept in the cast (NOT deleted from `keep_char`/the
    # agent list) but never scheduled (Kernel.is_eligible excludes archived
    # agents). It should not, however, count as an "active location" for the
    # env-trim below, so exclude it from that calculation only.
    active_char = {c for c in keep_char
                   if not any(a["id"] == c and a.get("archived") for a in agents)}

    active_locations = {
        a.get("status", {}).get("location")
        for a in agents
        if a.get("kind") == "character" and a["id"] in active_char
    }
    E = ENV_THRESHOLDS.get(name, 0)
    keep_env = {
        eid for eid in env_ids
        if eid in active_locations or env_mem.get(eid, 0) > E
    }

    def keep_agent(a):
        k = a.get("kind")
        if k == "character":
            return a["id"] in keep_char
        if k == "environment":
            return a["id"] in keep_env
        return True  # info_carriers kept

    kept_agents = [a for a in agents if keep_agent(a)]
    # defensive: filter map edges to kept environments (edges usually empty)
    mp = d.get("map") or {}
    if isinstance(mp, dict) and mp.get("edges"):
        mp["edges"] = [
            e for e in mp["edges"]
            if all(x in keep_env for x in (e[:2] if isinstance(e, (list, tuple)) else []))
        ]
    # clean kickoff: strip dropped ids from `to`, drop now-empty messages
    kickoff = d.get("kickoff") or []
    new_kickoff = []
    for msg in kickoff:
        to = [t for t in (msg.get("to") or []) if t not in dropped]
        if to:
            m = dict(msg)
            m["to"] = to
            new_kickoff.append(m)

    d["agents"] = kept_agents
    d["kickoff"] = new_kickoff
    out = os.path.join(SC, f"{name}.sim.yaml")
    with open(out, "w", encoding="utf-8") as f:
        yaml.safe_dump(d, f, allow_unicode=True, sort_keys=False)

    kinds = Counter(a.get("kind") for a in kept_agents)
    return {
        "name": name, "T": T,
        "chars_total": len(char_ids), "chars_active": len(active_char),
        "chars_dropped": len(dropped),
        "environments": kinds.get("environment", 0),
        "info_carriers": kinds.get("info_carrier", 0),
        "kickoff_msgs": len(new_kickoff),
        "out": os.path.relpath(out, BASE),
        "archived": bcounts["archived"], "relocated": bcounts["relocated"],
        "canon_fallback": bcounts["canon"],
    }


def main():
    import sys
    only = set(sys.argv[1].split(",")) if len(sys.argv) > 1 else None
    for name, T in THRESHOLDS.items():
        if only is not None and name not in only:
            continue
        r = curate(name, T)
        print(json.dumps(r, ensure_ascii=False))


if __name__ == "__main__":
    main()
