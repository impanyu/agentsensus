"""Per-agent goal-stack records, read out of a run's event log.

Goal pursuit is the one continuation-quality metric that cannot be scored
from the screenplay: pushing a goal is not something anybody sees happen.
This rebuilds, for each agent, the interleaving of

    what it declared it was trying to do  (push_goal / pop_goal / replace_goal)
    what it then did                      (say, move, act_on, remember, ...)

as one chronological block of text per agent, which
`society.evaluation.goal_pursuit` judges.

Used by experiments/score_all.py; runnable alone to eyeball one agent:
    venv/bin/python -m experiments.goal_timeline runs/hl40_consensus hamlet
"""
import json
import os
import sys

os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); sys.path.insert(0, ".")

from society.events import EventLog

GOAL_OPS = {"push_goal", "pop_goal", "replace_goal"}
# a line of the record is one action; long content is cut to keep a whole
# agent's run inside the judge's window without sampling any action away
CONTENT = 220
MAX_LINES = int(os.environ.get("GOAL_MAX_LINES", "160"))


def _params_text(name, params, result):
    if name == "move":
        return str(params.get("destination", ""))
    bits = []
    for key in ("content", "text", "question", "query", "target", "targets"):
        v = params.get(key)
        if v:
            bits.append(", ".join(v) if isinstance(v, list) else str(v))
    if name == "pop_goal" and isinstance(result, str):
        bits.append(result)
    out = " | ".join(bits)
    return out[:CONTENT] + ("..." if len(out) > CONTENT else "")


def timeline(events, agent):
    """One agent's goal operations and actions, in time order."""
    stack, lines = [], []
    for e in events:
        if e.get("kind") != "action" or e.get("agent") != agent:
            continue
        act = e.get("action") or {}
        name = act.get("name", "")
        res = (e.get("result") or {})
        if not res.get("ok", True):
            continue
        params = act.get("params") or {}
        text = _params_text(name, params, res.get("data"))
        t = e.get("tick", 0)
        if name == "push_goal":
            stack.append(text)
            lines.append(f"[round {t}] GOAL pushed: {text}")
        elif name == "replace_goal":
            if stack:
                stack[-1] = text
            else:
                stack.append(text)
            lines.append(f"[round {t}] GOAL replaced with: {text}")
        elif name == "pop_goal":
            done = stack.pop() if stack else text
            lines.append(f"[round {t}] GOAL popped (considered done/abandoned): {done}")
        else:
            top = stack[-1] if stack else "(none)"
            lines.append(f"[round {t}] {name}: {text}   <goal on top: {top}>")
    if len(lines) > MAX_LINES:  # keep the head and tail of a very long run
        half = MAX_LINES // 2
        lines = lines[:half] + [f"... ({len(lines) - MAX_LINES} lines omitted) ..."] + lines[-half:]
    return "\n".join(lines)


def timelines(run_dirs, agents):
    events = []
    for d in run_dirs:
        p = os.path.join(d, "events.jsonl")
        if os.path.exists(p):
            events.extend(EventLog.load(p))
    events.sort(key=lambda e: (e.get("tick", 0), e.get("seq", 0)))
    return {a: timeline(events, a) for a in agents}


def stack_stats(run_dirs):
    """How often agents act with nothing on their goal stack.

    The judged goal-pursuit score can only be read next to this: if agents
    rarely hold a goal at all, a high score would mean little. Deterministic,
    no LLM.
    """
    events = []
    for d in run_dirs:
        p = os.path.join(d, "events.jsonl")
        if os.path.exists(p):
            events.extend(EventLog.load(p))
    events.sort(key=lambda e: (e.get("tick", 0), e.get("seq", 0)))
    stacks, acted, empty, pushed = {}, 0, 0, 0
    for e in events:
        if e.get("kind") != "action" or not (e.get("result") or {}).get("ok", True):
            continue
        name = (e.get("action") or {}).get("name", "")
        stack = stacks.setdefault(e.get("agent"), [])
        if name == "push_goal":
            stack.append(1); pushed += 1
        elif name == "pop_goal":
            if stack:
                stack.pop()
        elif name == "replace_goal":
            if not stack:
                stack.append(1)
        else:
            acted += 1
            empty += not stack
    return {"actions": acted, "goalless": empty, "pushed": pushed,
            "goalless_pct": 100 * empty / acted if acted else 0.0}


def dump_stack_stats(out="runs/goal_stack_stats.json"):
    """Write the goal-stack statistic for every world and backend."""
    from experiments.score_all import WORLDS, BACKENDS
    stats = {w: {b: stack_stats([f"runs/{s}_{b}" for s in spec["stages"]])
                 for b in BACKENDS}
             for w, spec in WORLDS.items()}
    json.dump(stats, open(out, "w", encoding="utf-8"), indent=1)
    print("wrote", out)
    return stats


if __name__ == "__main__":
    if sys.argv[1:2] == ["--stats"]:
        dump_stack_stats()
    else:
        run, agent = sys.argv[1], sys.argv[2]
        print(timelines([run], [agent])[agent])
