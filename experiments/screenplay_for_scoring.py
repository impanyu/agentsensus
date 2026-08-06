"""Rendered-screenplay source text for continuation-quality scoring.

Scoring reads the run's **screenplay**, not its raw event log. Two reasons:

1. Language. A run's event log can be mixed-language (see the content-language
   note in society/brains/llm_brain.py) -- Russia-Ukraine's was 12% Chinese and
   2% Russian, Hamlet's 62% Chinese. `generate_screenplay` renders into the
   scenario's own language in one grounded pass, so the judge sees one language
   regardless of what the agents happened to emit.
2. Size and form. The raw 40-tick Russia-Ukraine transcript is ~1.6M chars --
   far past the judge's context window, previously handled by truncating each
   message and sampling lines. The screenplay is scene-organized and an order
   of magnitude smaller, so the judge sees a coherent whole rather than a
   sampled fragment.

The rendered screenplay is cached per backend at
`runs/<last_stage>_<backend>/screenplay_scoring.md`; delete that file to force
a re-render.
"""
import json
import os

from society.events import EventLog
from society.scenario import load_scenario
from society.screenplay import generate_screenplay

CACHE_NAME = "screenplay_scoring.md"


def scenario_of(run_dir: str) -> str:
    """Scenario file a run came from; resumed runs record a suffixed string."""
    with open(os.path.join(run_dir, "result.json"), encoding="utf-8") as f:
        path = (json.load(f) or {}).get("scenario")
    if not path:
        raise SystemExit(f"{run_dir}: result.json has no 'scenario' field")
    return path.split(" (")[0].strip()


def combined_events(run_dirs: list[str]) -> list[dict]:
    """Event log of a multi-stage run, in stage order."""
    events = []
    for rd in run_dirs:
        p = os.path.join(rd, "events.jsonl")
        if os.path.exists(p):
            events.extend(EventLog.load(p))
    return events


async def screenplay_text(run_dirs: list[str], llm, *, force: bool = False) -> str:
    """Screenplay for one backend's full run, rendered in the scenario language.

    `run_dirs` are the run's stages in order (e.g. ru10/ru20/ru40 for one
    backend); the screenplay is rendered once over their concatenated event
    logs and cached in the last stage's directory.
    """
    last = run_dirs[-1]
    cache = os.path.join(last, CACHE_NAME)
    if os.path.exists(cache) and not force:
        with open(cache, encoding="utf-8") as f:
            return f.read()

    cfg = load_scenario(scenario_of(last))
    language = cfg.get("language", "zh")
    names = {a["id"]: a.get("name") for a in cfg.get("agents", []) if a.get("id")}
    events = combined_events(run_dirs)
    text = await generate_screenplay(
        events, llm, out_path=cache, language=language, names=names,
        target_language=language,
    )
    return text
