"""Continuation-quality scoring for all four worlds, one protocol.

Each world is judged from its rendered screenplay (see
experiments/screenplay_for_scoring.py) over its full run, against a reference
span held out of sedimentation:

    Three Kingdoms  g20+g40+g60+g80   chapters 41-60 held out
    Red Chamber     rc10+rc40+rc60+rc80   chapters 41-80 held out
    Russia-Ukraine  ru10+ru20+ru40    timeline from 2024-05 held out
    Hamlet          hl20+hl30+hl40    Acts 4-5 held out

Three metrics, each scored RUN_REPEAT times and reported mean/std:
  grounding   fraction of the run's own events judged consistent with the
              world's canon (a plausible in-character action that did not
              literally happen still counts; only contradictions and
              inventions fail)
  trajectory  agreement of each principal's arc with the arc extracted from
              the held-out span
  narrative   coherence / distinctiveness / drama / fidelity, 1-5

Run:  RUN_REPEAT=3 venv/bin/python -m experiments.score_all [world ...]
      worlds: three_kingdoms red_chamber russia_ukraine hamlet
"""
import asyncio
import json
import os
import sys

os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); sys.path.insert(0, ".")

from society import evaluation as ev
from society.history_extract import _split_by_chapters
from society.run import _build_llm_and_embed
from experiments.score_fidelity import _mean_std
from experiments.screenplay_for_scoring import screenplay_text

BACKENDS = ["consensus", "generative_agents", "g_memory", "collaborative"]
REPEAT = int(os.environ.get("RUN_REPEAT", "3"))
MAX_EVENTS = int(os.environ.get("GROUNDING_MAX_EVENTS", "80"))
SRC = "scenarios/sources"


def _chapters(files):
    text = "\n".join(open(f"{SRC}/{f}", encoding="utf-8").read() for f in files)
    return _split_by_chapters(text)


def _three_kingdoms_reference():
    return _chapters(["three_kingdoms_ch01-10.txt",
                      "three_kingdoms_ch11-60.txt"])[40:60]


def _red_chamber_reference():
    return _chapters(["dream_red_chamber_ch01-80.txt"])[40:80]


def _hamlet_reference():
    text = open(f"{SRC}/hamlet.txt", encoding="utf-8").read()
    return [text[text.index("ACT IV"):]]


def _russia_ukraine_reference():
    keep = [l.rstrip("\n") for l in open(f"{SRC}/russia_ukraine_timeline.txt", encoding="utf-8")
            if len(l[:10]) == 10 and l[4] == "-" and l[:10] >= "2024-05-01"]
    return ["\n".join(keep)]


WORLDS = {
    "three_kingdoms": {
        "stages": ["g20", "g40", "g60", "g80"],
        "out": "runs/results_g80.json",
        "canon": "the classical Chinese novel 三国演义 (Romance of the Three Kingdoms)",
        "reference": _three_kingdoms_reference,
        "arcs": ["liubei", "guanyu", "zhangfei", "zhugeliang", "zhaoyun",
                 "caocao", "sunquan", "zhouyu", "simayi", "xiahoudun"],
    },
    "red_chamber": {
        "stages": ["rc10", "rc40", "rc60", "rc80"],
        "out": "runs/results_rc80.json",
        "canon": "the classical Chinese novel 红楼梦 (Dream of the Red Chamber)",
        "reference": _red_chamber_reference,
        "arcs": ["jiabaoyu", "lindaiyu", "xuebaochai", "wangxifeng", "jiamu",
                 "jiazheng", "wangfuren", "jiatanchun", "shixiangyun", "liwan"],
    },
    "russia_ukraine": {
        "stages": ["ru10", "ru20", "ru40"],
        "out": "runs/results_ru40.json",
        "canon": "the real-world Russia-Ukraine conflict (the simulation continues "
                 "the timeline beyond its 2024-04 boundary)",
        "reference": _russia_ukraine_reference,
        "arcs": ["putin", "zelenskyy", "zaluzhnyi", "syrskyi", "budanov",
                 "stoltenberg", "sobyanin", "yermak", "sbu", "black_sea_fleet"],
    },
    "hamlet": {
        "stages": ["hl20", "hl30", "hl40"],
        "out": "runs/results_hl40.json",
        "canon": "Shakespeare's Hamlet",
        "reference": _hamlet_reference,
        "arcs": ["hamlet", "claudius", "gertrude", "ophelia", "laertes",
                 "horatio", "marcellus", "rosencrantz", "guildenstern", "fortinbras"],
    },
}


ARC_CHUNK = int(os.environ.get("ARC_CHUNK_CHARS", "100000"))


def _pack(segments, budget=ARC_CHUNK):
    """Group reference segments (chapters, or one blob) into context-sized chunks.

    Chunks are evenly sized rather than greedily filled, so no chunk is a
    scrap: a 101k-character span becomes two halves, not 94k plus 7k. A single
    segment is never split -- a chapter is the smallest unit of arc.
    """
    total = sum(len(s) for s in segments)
    target = total / max(1, -(-total // budget))
    chunks, cur = [], ""
    for seg in segments:
        if cur and len(cur) + len(seg) / 2 > target:
            chunks.append(cur); cur = ""
        cur += seg
    return chunks + ([cur] if cur else [])


async def _condense(name, pieces, llm):
    """One arc paragraph out of the per-chunk paragraphs for one character."""
    prompt = ("Below are descriptions of one character's arc, each taken from a "
              "different stretch of the same narrative, in order.\n\n"
              + "\n\n".join(pieces) +
              f"\n\nWrite ONE paragraph describing {name}'s arc across the whole "
              "stretch: behaviour, goals, relationships, how they change. Return "
              "only the paragraph.")
    return (await llm.chat(prompt, system=None, bucket="eval_extract_arcs")).strip()


async def gold_arcs(segments, characters, llm):
    """`ev.extract_arcs` over a reference too long for one call.

    Red Chamber's held-out span is 313k characters of Chinese -- past the
    judge's context window -- so the span is extracted chapter-group by
    chapter-group and each character's paragraphs are condensed into one arc.
    """
    chunks = _pack(segments)
    if len(chunks) == 1:
        return await ev.extract_arcs(chunks[0], characters, llm)
    parts = await asyncio.gather(*[ev.extract_arcs(c, characters, llm) for c in chunks])
    out = {}
    for c in characters:
        got = [p.get(c, "").strip() for p in parts if p.get(c, "").strip()]
        out[c] = await _condense(c, got, llm) if len(got) > 1 else (got[0] if got else "")
    print(f"    gold arcs from {len(chunks)} chunks", flush=True)
    return out


async def _judge_one(event_text, canon, judge):
    prompt = (
        f"Below is an event taken from a SIMULATED continuation of {canon}. "
        "Judge whether this event is GROUNDED in that world: the characters, "
        "institutions and places exist there, their identities, roles and "
        "allegiances match, and the event is plausible within it (NOT a "
        "contradiction of the canon, a wrong-side or wrong-role error, or an "
        "invention of people, places or capabilities that do not exist). A "
        "plausible in-character action that simply is not a literal event of "
        "the source still counts as GROUNDED; only canon-violating or "
        "fabricated events are NOT grounded.\n\n"
        f"Event: {event_text}\n\n"
        'Return STRICT JSON: {"grounded": true/false, "why": "<short>"}. '
        "Return ONLY the JSON."
    )
    reply = await judge.chat(prompt, system=None, bucket="eval_judge")
    parsed = ev._parse_json(reply, default={"grounded": False, "why": ""})
    if not isinstance(parsed, dict):
        parsed = {"grounded": False}
    return bool(parsed.get("grounded", False))


async def grounding_rate(text, canon, judge, max_events=MAX_EVENTS):
    for attempt in range(3):
        events = await ev.extract_events(text, judge, max_events=max_events)
        if events:
            break
        print(f"    event extraction returned nothing (attempt {attempt + 1})", flush=True)
    if not events:
        return {"rate": None, "n": 0}
    verdicts = await asyncio.gather(*[
        _judge_one(e.get("event", ""), canon, judge) for e in events])
    n = len(verdicts)
    return {"rate": sum(verdicts) / n if n else 0.0, "n": n}


async def score_world(name, spec, llm):
    print(f"=== {name}: extracting gold arcs", flush=True)
    gold = await gold_arcs(spec["reference"](), spec["arcs"], llm)
    print(f"=== {name}: {len(gold)} arcs | repeat={REPEAT}", flush=True)
    results = {}
    for backend in BACKENDS:
        dirs = [f"runs/{s}_{backend}" for s in spec["stages"]]
        text = await screenplay_text(dirs, llm)
        runs = []
        for _ in range(REPEAT):
            gr = await grounding_rate(text, spec["canon"], llm)
            tj = await ev.trajectory_consistency(gold, text, llm)
            nq = await ev.narrative_quality(text, llm)
            runs.append({"grnd": gr["rate"], "grnd_n": gr["n"],
                         "traj": tj["mean"], "narr": nq["overall"]})
        # a repeat whose extraction failed carries no grounding number; it is
        # dropped rather than averaged in as a zero
        agg = {k: dict(zip(("mean", "std"),
                           _mean_std([r[k] for r in runs if r[k] is not None])))
               for k in ("grnd", "traj", "narr")}
        agg["grnd_n"] = sum(r["grnd_n"] for r in runs) / len(runs)
        results[backend] = {"agg": agg, "runs": runs, "chars": len(text)}
        print(f"{name}/{backend}: grounding {agg['grnd']['mean']:.2f}±{agg['grnd']['std']:.2f} "
              f"(n≈{agg['grnd_n']:.0f}) | traj {agg['traj']['mean']:.2f}±{agg['traj']['std']:.2f} "
              f"| narr {agg['narr']['mean']:.2f}±{agg['narr']['std']:.2f}", flush=True)
    json.dump(results, open(spec["out"], "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(f"=== {name} -> {spec['out']}", flush=True)


async def main(names):
    llm, _ = _build_llm_and_embed("config_flash.json")
    for n in names:
        await score_world(n, WORLDS[n], llm)


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1:] or list(WORLDS)))
