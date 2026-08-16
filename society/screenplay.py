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

import json
import re

_ACTION_BEAT_NAMES = {"say", "gesture", "think", "conclude", "move", "act_on"}
_MESSAGE_BEAT_KINDS = {"say", "gesture"}

_CONTENT_PARAM_KEYS = ("content", "description", "question", "text")

_SYSTEM_PROMPT = {
    "zh": (
        "你是一位经验丰富的编剧。给定一段按时间顺序排列的事件线索,"
        "请将它们改写为剧本正文,同时满足两条同等重要的要求。\n"
        "第一,完整:每一条事件都必须在剧本中有对应的落点——化为台词、"
        "舞台指示、内心独白或旁白皆可,但不得遗漏、不得合并掉任何一条,"
        "也不得改变其发生顺序。事件中的具体信息(人名、地点、器物、"
        "数目、称谓、行动的对象与结果)必须原样保留,不可含糊带过。"
        "think/conclude 类事件渲染为内心独白或旁白(括号标注,"
        "如“(内心独白)”“(旁白)”)。\n"
        "第二,文学性:必须改写,不得照抄。源事件多为冗长的公文式消息"
        "(编号条款、格式化请示),整段搬进台词即是失败。请把它们拆成人物"
        "真能说出口的话,人物各有声口,舞台指示简练而有画面感,场面有起伏。"
        "语言风格贴合该世界的时代与气质。\n"
        "硬性格式(违反即不合格):①单句台词不超过 60 字;②台词内禁止出现"
        "编号(1)、2)、一、二)、项目符号或分条冒号等公文格式;③一条含多个"
        "要点的源事件必须拆成多句台词或多轮对答,可由对方追问、应答、复述"
        "分担;④不得整句照抄源事件措辞。\n"
        "两者的结合:事实一条不少,措辞一句不抄。"
        "直接输出剧本正文,不要输出解释、前后缀或 Markdown 标题。"
    ),
    "en": (
        "You are an experienced screenwriter. Given a chronological list of "
        "events, render them as screenplay text under two equally binding "
        "requirements.\n"
        "First, completeness: every single event must land somewhere in the "
        "scene — as dialogue, a stage direction, inner monologue, or "
        "voice-over — with none dropped, none merged away, and none "
        "reordered. Concrete particulars carried by an event (names, places, "
        "objects, numbers, titles, the target and outcome of an action) must "
        "survive verbatim in substance; do not blur them into generalities. "
        "think/conclude events become inner monologue or voice-over (marked "
        "in parentheses, e.g. \"(inner monologue)\" or \"(voice-over)\").\n"
        "Second, literary quality: you must **rewrite**, never copy the event "
        "text. The source events are mostly long administrative messages "
        "(numbered clauses, formatted requests); pasting one into a line of "
        "dialogue is a failure. Break them into lines a person would actually "
        "speak \u2014 one or two points per line, a long directive split across an "
        "exchange, enumerations turned into speech \u2014 with distinct voices per "
        "character, lines that fit each speaker's station, spare but vivid "
        "stage directions, and a scene that builds rather than lists. Match "
        "the register of the world the events come from.\n"
        "Hard format rules (violating them fails the task): (i) no single line of "
        "dialogue longer than about 40 words; (ii) no numbered clauses, bullets "
        "or memo formatting inside dialogue; (iii) an event carrying several "
        "points must be split across several lines or an exchange, with the "
        "other party questioning, answering or confirming parts of it; (iv) "
        "never reproduce a sentence of the source verbatim.\n"
        "How the two combine: not one fact missing, not one phrase copied. "
        "Output the screenplay text directly, with no explanation, prefix, or "
        "Markdown heading."
    ),
}

# Coverage repair (used when `ensure_coverage` is on). The renderer is asked
# to keep every beat, but a long scene can still lose one; these prompts run a
# check-then-repair round so a dropped beat is caught here rather than showing
# up later as a missing event in whatever consumes the screenplay.
_COVERAGE_CHECK = {
    "zh": (
        "下面是一份事件列表和据其写成的剧本。请逐条检查:该事件的实质内容"
        "(人物、动作、对象、结果)是否在剧本中有体现?只要有体现即算覆盖,"
        "措辞不必相同。\n\n事件列表:\n{beats}\n\n剧本:\n{scene}\n\n"
        '严格返回 JSON:{{"missing": [<未被覆盖的事件序号,从1开始>]}}。只返回 JSON。'
    ),
    "en": (
        "Below are an event list and a screenplay written from it. For each "
        "event, check whether its substance (who, the action, its target, its "
        "outcome) appears in the screenplay. Any faithful rendering counts as "
        "covered; the wording need not match.\n\nEvents:\n{beats}\n\n"
        "Screenplay:\n{scene}\n\n"
        'Return STRICT JSON: {{"missing": [<1-based indices of uncovered events>]}}. '
        "Return ONLY the JSON."
    ),
}

_COVERAGE_REPAIR = {
    "zh": (
        "以下剧本遗漏了这些事件:\n{missing}\n\n请重写整幕,把遗漏的事件"
        "补进恰当的位置,保持已有内容的顺序与文学水准,不要新增任何事实。"
        "直接输出重写后的剧本正文。\n\n原剧本:\n{scene}"
    ),
    "en": (
        "The screenplay below is missing these events:\n{missing}\n\n"
        "Rewrite the whole scene, working the missing events into their "
        "proper places, preserving the order and the literary quality of what "
        "is already there, and adding no new facts. Output the rewritten "
        "screenplay text directly.\n\nCurrent screenplay:\n{scene}"
    ),
}

_USER_TEMPLATE = {
    "zh": "场景地点:{location}\n回合范围:{tick_start}–{tick_end}\n\n事件列表:\n{beats}\n",
    "en": "Location: {location}\nRounds: {tick_start}–{tick_end}\n\nEvents:\n{beats}\n",
}

# Target-language render instruction (Deliverable 1). Prepended to the
# constraint when `target_language` differs from `language`: renders the
# screenplay directly in the target language in one pass (never render in
# `language` then machine-translate), grounding on the source-language
# beats and romanizing/rendering names via the `names` mapping.
_TARGET_LANGUAGE_NAMES = {
    "en": "English",
    "zh": "Chinese",
}

_TARGET_LANGUAGE_INSTRUCTION = {
    "en": (
        "Write the screenplay in English, even though the source events "
        "below are in another language. For every character, use the "
        "display name given in the cast list (already romanized / an "
        "English name); if a character has no display name, use standard "
        "romanization of their id. Ground every line strictly in the "
        "source-language beats provided — translate and dramatize them "
        "directly into English in a single pass; do not leave any "
        "non-English text in the output."
    ),
    "zh": (
        "请用中文撰写剧本正文,即使下方的源事件使用了其他语言。"
        "每个角色都使用演员表中给出的显示名称;如果没有显示名称,"
        "则使用其 id 的标准中文译名。所有台词都必须严格基于下方提供的"
        "源语言事件,一次性直接译写为中文,不要在输出中保留任何非中文文本。"
    ),
}


# Hard grounding constraints (Task: no hallucination). Prepended to every
# scene's user prompt so the LLM cannot invent characters/locations/events
# beyond what the logged run actually produced.
_CONSTRAINT_TEMPLATE = {
    "zh": (
        "你只能使用以下角色(格式为「显示名 [id]」,剧本中一律写显示名,禁止出现 id):{cast}。场景地点:{location}。"
        "绝对禁止虚构任何未列出的角色、未出现的地点或未发生的事件。"
        "每句对白和动作都必须对应所给的实际事件记录,可以润色语言表达,"
        "但不可改变事实、不可增加情节。think/conclude 渲染为内心独白。"
    ),
    "en": (
        "You may only use the following characters, given as \"name [id]\" \u2014 "
        "always write the name, never the id: {cast}. Scene location: "
        "{location}. It is strictly forbidden to invent any character not "
        "listed, any location that did not appear, or any event that did "
        "not happen. Every line of dialogue and every action must "
        "correspond to the actual event record provided — you may polish "
        "the wording, but you must not change the facts or add plot. "
        "Render think/conclude as inner monologue."
    ),
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
        return f"[round {tick}] {speaker}{target_str} {name}: {content}"

    # message beat
    message = event.get("message", {})
    sender = message.get("sender")
    recipient = event.get("recipient")
    msg_kind = message.get("kind")
    content = message.get("content")
    return f"[round {tick}] {sender} -> {recipient} {msg_kind}: {content}"


def _sort_key(event: dict):
    return (event.get("tick", 0), event.get("seq", 0))


def _split_scenes(beats: list[dict], scene_gap: int) -> list[dict]:
    """Group sorted beats into scenes: one place, one stretch of time.

    Beats are bucketed by location first and only then cut on time, because a
    round applies actions in every location at once -- splitting the
    chronological stream on each location change turned a run into hundreds of
    one-beat "scenes". Within a location a new scene starts when the gap to the
    previous beat there exceeds `scene_gap`. Scenes are returned in the order
    they begin, so the screenplay still reads forwards. Message beats carry no
    location and inherit the last one seen.
    """
    current_location = None
    by_location: dict = {}
    for beat in beats:
        loc = beat.get("location")
        if loc is not None:
            current_location = loc
        by_location.setdefault(current_location, []).append(beat)

    scenes = []
    for location, located in by_location.items():
        scene = None
        prev_tick = None
        for beat in sorted(located, key=_sort_key):
            tick = beat.get("tick", 0)
            if scene is None or (prev_tick is not None and tick - prev_tick > scene_gap):
                scene = {"location": location, "beats": [],
                         "tick_start": tick, "tick_end": tick}
                scenes.append(scene)
            scene["beats"].append(beat)
            scene["tick_end"] = tick
            prev_tick = tick

    scenes.sort(key=lambda s: (s["tick_start"], str(s["location"] or "")))
    return scenes

    return scenes


def _scene_cast(scene: dict) -> list[str]:
    """The unique agent ids that actually appear in `scene`'s beats: the
    actor (or sender) plus any say/gesture/act_on targets. This is the
    "allowed cast" a scene's constraint prompt is built from, so the LLM
    has no cover to invent a character that never showed up in the log.
    """
    ids: set[str] = set()
    for beat in scene["beats"]:
        if beat.get("kind") == "action":
            ids.add(beat.get("agent"))
            params = beat.get("action", {}).get("params", {}) or {}
            targets = params.get("targets")
            if isinstance(targets, list):
                ids.update(targets)
            target = params.get("target")
            if isinstance(target, str):
                ids.add(target)
        else:
            message = beat.get("message", {})
            ids.add(message.get("sender"))
            recipient = beat.get("recipient")
            if recipient is not None:
                ids.add(recipient)
    ids.discard(None)
    return sorted(ids)


def _format_cast(cast_ids: list[str], names: dict | None) -> str:
    names = names or {}
    parts = []
    for cid in cast_ids:
        display_name = names.get(cid)
        # "display name [id]" rather than "id(display name)": the renderer kept
        # echoing whichever token came first, and the screenplay must speak the
        # name, not the identifier.
        parts.append(f"{display_name} [{cid}]" if display_name else cid)
    return ", ".join(parts)


def _utterance_key(event: dict):
    """Identity of the utterance a beat represents, or None if it is unique.

    The kernel logs one `say`/`gesture` as an action event AND one message
    event per recipient, so a line spoken to three agents arrives as four
    beats carrying the same words. They are the same story moment; feeding all
    four to the screenwriter (which is instructed to give every beat a place)
    would make it write the line four times.
    """
    tick = event.get("tick")
    if event.get("kind") == "action":
        action = event.get("action", {}) or {}
        if action.get("name") not in _MESSAGE_BEAT_KINDS:
            return None
        params = action.get("params", {}) or {}
        content = params.get("content") or params.get("description") or ""
        return (tick, event.get("agent"), action.get("name"), str(content).strip())
    message = event.get("message", {}) or {}
    return (tick, message.get("sender"), message.get("kind"),
            str(message.get("content") or "").strip())


def _dedupe(beats: list[dict]) -> list[dict]:
    """Drop repeat beats of one utterance, keeping the first occurrence."""
    seen, out = set(), []
    for e in beats:
        key = _utterance_key(e)
        if key is not None:
            if key in seen:
                continue
            seen.add(key)
        out.append(e)
    return out


def _clean_rendered(text: str, ids, location=None, names=None) -> str:
    """Tidy one rendered scene.

    Drops leading lines that merely echo the prompt's scene header (including a
    bare location id), and strips the "[agent_id]" the renderer tends to carry
    over from the cast list, which is given as "Name [id]" precisely so the id
    is not spoken.
    """
    names = names or {}
    ids = [i for i in (ids or []) if i]
    if ids:
        text = re.sub(r"\s*\[(" + "|".join(re.escape(i) for i in ids) + r")\]", "", text)
        # ids that leaked into the prose: the beats name agents by id, and the
        # renderer sometimes carries one through. Only substitute ids long
        # enough to be unambiguous as whole words ("un", "eu" would be words).
        subs = {i: names.get(i) for i in ids if len(i) >= 4 and names.get(i)}
        if subs:
            pattern = re.compile(r"\b(" + "|".join(re.escape(i) for i in subs) + r")\b")
            text = pattern.sub(lambda m: subs[m.group(1)], text)
    lines = text.lstrip().split("\n")
    drop = ("场景地点", "回合范围", "事件列表", "Location:", "Rounds:", "Events:",
            "Scene at", "（场景", "(场景", "场景:", "Scene:")
    echoes = {str(location or "").strip(), "（场景·" + str(location or "") + "）"}
    while lines and (not lines[0].strip()
                     or lines[0].strip().startswith(drop)
                     or lines[0].strip() in echoes):
        lines.pop(0)
    return "\n".join(lines).strip()


async def _repair_coverage(rendered, beats, beat_lines, llm, language, system_prompt):
    """Ask whether any beat is missing from `rendered`; if so, rewrite once.

    One check call and at most one repair call per scene. A malformed or
    unparseable check reply is treated as "nothing missing" -- the scene keeps
    its original text rather than being rewritten on a guess.
    """
    check = _COVERAGE_CHECK.get(language, _COVERAGE_CHECK["en"]).format(
        beats="\n".join(f"{i}. {line}" for i, line in
                         enumerate(beat_lines.split("\n"), start=1)),
        scene=rendered,
    )
    reply = await llm.chat(check, system=None, bucket="screenplay_coverage")
    missing_idx = _parse_missing(reply, len(beats))
    if not missing_idx:
        return rendered

    lines = beat_lines.split("\n")
    missing_text = "\n".join(lines[i - 1] for i in missing_idx)
    repair = _COVERAGE_REPAIR.get(language, _COVERAGE_REPAIR["en"]).format(
        missing=missing_text, scene=rendered
    )
    repaired = await llm.chat(repair, system=system_prompt, bucket="screenplay_coverage")
    return repaired.strip() or rendered


def _parse_missing(reply, n_beats):
    """1-based beat indices the coverage check reported as missing."""
    text = (reply or "").strip()
    if text.startswith("```"):
        text = text.strip("`")
        text = text[text.find("{"):] if "{" in text else text
    try:
        data = json.loads(text[text.index("{"):text.rindex("}") + 1])
    except (ValueError, TypeError):
        return []
    raw = data.get("missing") if isinstance(data, dict) else None
    if not isinstance(raw, list):
        return []
    out = []
    for v in raw:
        try:
            i = int(v)
        except (TypeError, ValueError):
            continue
        if 1 <= i <= n_beats:
            out.append(i)
    return sorted(set(out))


async def generate_screenplay(
    events: list[dict],
    llm,
    out_path: str | None = None,
    language: str = "zh",
    scene_gap: int = 5,
    names: dict | None = None,
    target_language: str | None = None,
    ensure_coverage: bool = True,
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
        names: Optional {agent_id: display_name} map (events themselves
            carry no display names). When given, the per-scene cast line
            shows "id(display_name)" so the LLM can use natural names
            while the grounding constraint still keys off real ids.
        target_language: Optional language code (e.g. "en"). When None
            (default), behaves exactly as before -- the screenplay is
            rendered in `language`. When set and different from
            `language`, the per-scene render prompt instructs the LLM to
            write the screenplay directly in `target_language` in a
            single pass (grounded on the source-language beats, names
            romanized/rendered via `names`) instead of rendering in
            `language` and translating afterwards.

    Returns:
        The full screenplay as a markdown string.
    """
    beats = _dedupe(sorted((e for e in events if _is_beat(e)), key=_sort_key))
    scenes = _split_scenes(beats, scene_gap)

    system_prompt = _SYSTEM_PROMPT.get(language, _SYSTEM_PROMPT["en"])
    user_template = _USER_TEMPLATE.get(language, _USER_TEMPLATE["en"])
    constraint_template = _CONSTRAINT_TEMPLATE.get(language, _CONSTRAINT_TEMPLATE["en"])

    # A run's event log can be mixed-language (see the content-language note in
    # society/brains/llm_brain.py): runs made before that directive existed
    # contain memories in a language other than the scenario's. Rendering a
    # screenplay in the scenario's own language is therefore also a
    # normalization step, so the instruction applies whenever a target language
    # is named -- including when it equals `language`.
    target_instruction = ""
    if target_language:
        target_instruction = (
            _TARGET_LANGUAGE_INSTRUCTION.get(
                target_language, _TARGET_LANGUAGE_INSTRUCTION["en"]
            )
            + "\n\n"
        )

    blocks = []
    for i, scene in enumerate(scenes, start=1):
        beat_lines = "\n".join(_beat_line(b) for b in scene["beats"])
        cast_str = _format_cast(_scene_cast(scene), names)
        constraint = constraint_template.format(cast=cast_str, location=scene["location"])
        prompt = target_instruction + constraint + "\n\n" + user_template.format(
            location=scene["location"],
            tick_start=scene["tick_start"],
            tick_end=scene["tick_end"],
            beats=beat_lines,
        )
        rendered = await llm.chat(prompt, system=system_prompt, bucket="screenplay")
        if ensure_coverage:
            rendered = await _repair_coverage(
                rendered, scene["beats"], beat_lines, llm, language, system_prompt
            )

        place = (names or {}).get(scene["location"], scene["location"])
        span = f"{scene['tick_start']}–{scene['tick_end']}"
        # the header follows the language the screenplay is written in, which is
        # the target when one is named, not the world's own language
        out_lang = target_language or language
        header = (f"## 第{i}幕 · {place} · 回合 {span}" if out_lang == "zh"
                  else f"## Scene {i} · {place} · rounds {span}")
        # the renderer sometimes echoes the prompt's location/round header back
        # as its first line; the block already has one.
        rendered = _clean_rendered(rendered, list((names or {}).keys()), scene["location"], names)
        blocks.append(f"{header}\n\n{rendered}\n")

    markdown = "\n".join(blocks)

    if out_path:
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(markdown)

    return markdown
