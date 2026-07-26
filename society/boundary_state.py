"""Boundary-state finalization: for each cast character, determine {alive,
location} at the sediment boundary -- grounded first in the character's own
memory timeline, falling back to the model's canon knowledge anchored to the
raw boundary source-tail. Pure logic; the LLM is injected. See
docs/superpowers/specs/2026-07-26-boundary-state-finalization-design.md."""

import asyncio

from society.evaluation import _parse_json


def gather_timeline(memories, char_id, max_mem=200):
    """Texts of the memories owned by `char_id`, ascending by story_order.
    If more than `max_mem`, keep the LATEST `max_mem` (recent memories set the
    'current' boundary state)."""
    owned = [m for m in memories if char_id in (m.get("owners") or [])]
    owned.sort(key=lambda m: (m.get("meta", {}) or {}).get("story_order", 0))
    texts = [m["text"] for m in owned]
    if len(texts) > max_mem:
        texts = texts[-max_mem:]
    return texts


async def _extract_grounded(char_id, timeline, env_ids, llm):
    joined = "\n".join(f"- {t}" for t in timeline)
    prompt = (
        f"Below are the memories about the character '{char_id}', in narrative "
        "order (earliest first). Based ONLY on what happens to this character in "
        "these memories, determine, as of the LAST memory: is the character "
        "alive, and at which location are they?\n\n"
        f"Memories:\n{joined}\n\n"
        "IMPORTANT — be CONSERVATIVE about death: mark alive=false ONLY if the "
        "memories EXPLICITLY narrate this character's death (killed, executed, "
        "died, etc.). If no death is explicitly shown, the character is alive "
        "(alive=true) — do not infer death from absence, danger, defeat, or your "
        "outside knowledge.\n\n"
        f"Choose location from this list of valid location ids (or \"\" if the "
        f"memories don't say): {sorted(env_ids)}\n\n"
        'Return STRICT JSON: {"alive": true/false, "location": "<location id or '
        'empty string>", "determinable": true/false}. Set determinable=false if '
        "the memories do not make the alive/location state clear. Return ONLY the JSON."
    )
    reply = await llm.chat(prompt, system=None, bucket="boundary_extract")
    return _parse_json(reply, default={"alive": True, "location": "", "determinable": False})


async def _fallback_canon(char_id, boundary_context, env_ids, llm):
    prompt = (
        "The following is the source text at the current point of a story "
        "(near the boundary of what has been narrated so far), including its "
        "chapter/time markers:\n\n"
        f"{boundary_context}\n\n"
        f"At THIS point in the story, is the character '{char_id}' alive, and at "
        "which location are they? Use your knowledge of this work anchored to "
        "the moment shown above.\n\n"
        "IMPORTANT — judge by the WORK ITSELF (this novel/story and its own "
        "timeline), NOT by real-world history or historical death dates. A "
        "character who is still alive in the story AT THIS POINT is alive "
        "(alive=true) even if the historical person they are based on died "
        "earlier. Only mark alive=false if the character has already died within "
        "the story by the moment shown above.\n\n"
        f"Choose location from this list of valid location ids: {sorted(env_ids)}\n\n"
        'Return STRICT JSON: {"alive": true/false, "location": "<location id>"}. '
        "Return ONLY the JSON."
    )
    reply = await llm.chat(prompt, system=None, bucket="boundary_fallback")
    return _parse_json(reply, default={"alive": True, "location": ""})


async def _finalize_one(char_id, memories, env_ids, llm, boundary_context, max_mem):
    timeline = gather_timeline(memories, char_id, max_mem)
    source = "memory"
    if timeline:
        res = await _extract_grounded(char_id, timeline, env_ids, llm)
    else:
        res = {"alive": True, "location": "", "determinable": False}
    alive = bool(res.get("alive", True))
    location = res.get("location") or ""
    determinable = bool(res.get("determinable", False))
    # fall back when the timeline is inconclusive, or a living character has no
    # valid on-list location
    if (not determinable) or (alive and location not in env_ids):
        fb = await _fallback_canon(char_id, boundary_context, env_ids, llm)
        alive = bool(fb.get("alive", alive))
        location = fb.get("location") or location
        source = "canon@boundary"
    if location not in env_ids:
        location = None  # unresolved -> caller keeps prior tracked location
    return {"alive": alive, "location": location, "source": source}


async def finalize_boundary_state(memories, cast, env_ids, *, llm,
                                  boundary_context, max_mem_per_char=200):
    """For each character id in `cast`, return
    {char_id: {"alive": bool, "location": <env id>|None, "source": str}}.
    Per-character LLM work runs concurrently (the client bounds concurrency)."""
    env_ids = set(env_ids)
    results = await asyncio.gather(*[
        _finalize_one(c, memories, env_ids, llm, boundary_context, max_mem_per_char)
        for c in cast
    ])
    return dict(zip(cast, results))
