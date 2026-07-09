"""Screenplay generator (Task 12).

Turns a run's raw event log into a readable markdown screenplay:
1. Filter the event stream down to "beats" worth dramatizing (successful
   say/gesture/think/conclude/move/act_on actions, plus say/gesture
   messages).
2. Split the beats into scenes on location change or a large tick gap.
3. Ask the LLM (once per scene, bucket="screenplay") to pick the
   beats with narrative value and render them as screenplay text.
4. Concatenate the per-scene markdown blocks into the final document.
"""

_ACTION_BEAT_NAMES = {"say", "gesture", "think", "conclude", "move", "act_on"}
_MESSAGE_BEAT_KINDS = {"say", "gesture"}

_CONTENT_PARAM_KEYS = ("content", "description", "question", "text")

_SYSTEM_PROMPT = {
    "zh": (
        "你是一位经验丰富的编剧。给定一段按时间顺序排列的事件线索,"
        "请从中挑选出具有叙事/文学价值的片段,并将其改写为剧本正文:"
        "包含对话与舞台指示;think/conclude 类事件应渲染为内心独白或旁白"
        "(用括号标注,如“(内心独白)”“(旁白)”)。"
        "不需要保留所有事件,略去平淡、重复或无戏剧性的片段。"
        "直接输出剧本正文,不要输出解释、前后缀或 Markdown 标题。"
    ),
    "en": (
        "You are an experienced screenwriter. Given a chronological list of "
        "events, select the beats with narrative/literary value and render "
        "them as screenplay text: dialogue and stage directions; think/"
        "conclude events should be rendered as inner monologue or "
        "voice-over (marked in parentheses, e.g. \"(inner monologue)\" or "
        "\"(voice-over)\"). You do not need to keep every event — drop flat, "
        "repetitive, or undramatic beats. Output the screenplay text "
        "directly, with no explanation, prefix, or Markdown heading."
    ),
}

_USER_TEMPLATE = {
    "zh": "场景地点:{location}\ntick范围:{tick_start}–{tick_end}\n\n事件列表:\n{beats}\n",
    "en": "Location: {location}\nTick range: {tick_start}–{tick_end}\n\nEvents:\n{beats}\n",
}


def _is_beat(event: dict) -> bool:
    """Whether `event` should be kept as a dramatizable beat."""
    kind = event.get("kind")
    if kind == "action":
        result = event.get("result", {})
        if not result.get("ok"):
            return False
        action = event.get("action", {})
        return action.get("name") in _ACTION_BEAT_NAMES
    if kind == "message":
        message = event.get("message", {})
        return message.get("kind") in _MESSAGE_BEAT_KINDS
    return False


def _beat_line(event: dict) -> str:
    """Render one beat as a single readable line for the LLM prompt."""
    tick = event.get("tick")
    if event.get("kind") == "action":
        speaker = event.get("agent")
        action = event.get("action", {})
        name = action.get("name")
        params = action.get("params", {}) or {}
        result = event.get("result", {}) or {}

        pieces = []
        for key in _CONTENT_PARAM_KEYS:
            if key in params and params[key] is not None:
                pieces.append(str(params[key]))
        data = result.get("data")
        if data is not None:
            pieces.append(str(data))
        targets = params.get("targets")
        target_str = f" -> {targets}" if targets else ""
        content = " | ".join(pieces)
        return f"[tick {tick}] {speaker}{target_str} {name}: {content}"

    # message beat
    message = event.get("message", {})
    sender = message.get("sender")
    recipient = event.get("recipient")
    msg_kind = message.get("kind")
    content = message.get("content")
    return f"[tick {tick}] {sender} -> {recipient} {msg_kind}: {content}"


def _sort_key(event: dict):
    return (event.get("tick", 0), event.get("seq", 0))


def _split_scenes(beats: list[dict], scene_gap: int) -> list[dict]:
    """Group sorted beats into scenes.

    A new scene starts when a beat's location differs from the current
    scene's location, or its tick is more than `scene_gap` past the
    previous beat's tick. Message beats (no "location" key) never trigger
    a location change on their own; they inherit the current scene's
    location.
    """
    scenes = []
    scene = None
    scene_location = None
    prev_tick = None

    for beat in beats:
        loc = beat.get("location")
        tick = beat.get("tick", 0)

        tick_jump = prev_tick is not None and (tick - prev_tick) > scene_gap
        loc_change = loc is not None and scene_location is not None and loc != scene_location

        if scene is None or tick_jump or loc_change:
            effective_loc = loc if loc is not None else scene_location
            scene = {
                "location": effective_loc,
                "beats": [],
                "tick_start": tick,
                "tick_end": tick,
            }
            scenes.append(scene)

        if loc is not None:
            scene_location = loc
            scene["location"] = loc

        scene["beats"].append(beat)
        scene["tick_end"] = tick
        prev_tick = tick

    return scenes


async def generate_screenplay(
    events: list[dict],
    llm,
    out_path: str | None = None,
    language: str = "zh",
    scene_gap: int = 5,
) -> str:
    """Turn a run's event log into a markdown screenplay.

    Args:
        events: Raw event dicts from the run's EventLog (action/message/
            system kinds).
        llm: Async chat client duck-typing LLMClient/FakeLLM
            (`await llm.chat(prompt, system=..., bucket=...) -> str`).
        out_path: If given, the resulting markdown is also written there
            (utf-8).
        language: "zh" or "en"; selects the prompt language.
        scene_gap: Max tick gap within one scene before a new scene starts.

    Returns:
        The full screenplay as a markdown string.
    """
    beats = sorted((e for e in events if _is_beat(e)), key=_sort_key)
    scenes = _split_scenes(beats, scene_gap)

    system_prompt = _SYSTEM_PROMPT.get(language, _SYSTEM_PROMPT["en"])
    user_template = _USER_TEMPLATE.get(language, _USER_TEMPLATE["en"])

    blocks = []
    for i, scene in enumerate(scenes, start=1):
        beat_lines = "\n".join(_beat_line(b) for b in scene["beats"])
        prompt = user_template.format(
            location=scene["location"],
            tick_start=scene["tick_start"],
            tick_end=scene["tick_end"],
            beats=beat_lines,
        )
        rendered = await llm.chat(prompt, system=system_prompt, bucket="screenplay")

        header = (
            f"## 第{i}幕 · {scene['location']} · "
            f"tick {scene['tick_start']}–{scene['tick_end']}"
        )
        blocks.append(f"{header}\n\n{rendered}\n")

    markdown = "\n".join(blocks)

    if out_path:
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(markdown)

    return markdown
