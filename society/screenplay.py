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
        "你是一位编剧。下面给出一场戏里按发生顺序编号的事件,请逐条把每条事件"
        "改写成剧本文字。\n"
        "改写要求:①用人物真能说出口的话,单句不超过 60 字;②禁止编号、项目符号"
        "或公文分条格式;③一条含多个要点的事件可拆成同一人的连续数句;"
        "④不得整句照抄原文措辞;⑤事件里的具体信息(人名、地点、器物、数目、"
        "称谓、动作的对象与结果)必须保留。\n"
        "字段名要写成人话:move 事件的 eta 是预计到达的**回合数**(如""「预计回合 33 到位」),不要照搬 eta;delivered 之类的投递计数不必出现。\n"
        "不得增加事件中没有的内容:不替任何人添加追问、应答或过渡句,不虚构"
        "动作、情绪或情节。\n"
        '严格返回 JSON:{{"1": ["台词或舞台指示", ...], "2": [...], ...}},'
        "键为事件编号,值为该条事件改写成的一到数行文字。只返回 JSON。"
    ),
    "en": (
        "You are a screenwriter. Below are the events of one scene, numbered in "
        "the order they happened. Rewrite each event as screenplay text.\n"
        "How to rewrite: (i) lines a person would actually speak, none longer "
        "than about 40 words; (ii) no numbered clauses, bullets or memo "
        "formatting; (iii) an event carrying several points may become several "
        "consecutive lines for that same speaker; (iv) never reproduce a "
        "sentence of the source verbatim; (v) keep every concrete particular "
        "the event carries (names, places, objects, numbers, titles, the target "
        "and outcome of an action).\n"
        "Render field names as prose: a move event's eta is the round it "
        "arrives (\"in place by round 33\"), never \"eta: 33\"; delivery counts "
        "need not appear at all.\n"
        "Add nothing the event does not contain: no invented questions, "
        "answers or connective lines for anyone, no invented action, feeling or "
        "plot.\n"
        'Return STRICT JSON: {{"1": ["line", ...], "2": [...], ...}} keyed by '
        "event number, each value the one or more lines that event becomes. "
        "Return ONLY the JSON."
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
        "可以说话的角色只有(格式为「显示名 [id]」,剧本中一律写显示名,禁止出现 id):{cast}。"
        "以下是场景中出现的地点与信息载体:{silent}。它们从不开口——与它们相关的内容一律写成旁白或舞台指示,绝不可给它们台词。场景地点:{location}。"
        "绝对禁止虚构任何未列出的角色、未出现的地点或未发生的事件。"
        "每句对白和动作都必须对应所给的实际事件记录,可以润色语言表达,"
        "但不可改变事实、不可增加情节。think/conclude 渲染为内心独白。"
    ),
    "en": (
        "Only these may speak, given as \"name [id]\" \u2014 always write the name, "
        "never the id: {cast}. "
        "These places and objects also appear: {silent}. They never speak \u2014 render "
        "anything involving them as narration or a stage direction, never as a "
        "line of dialogue. Scene location: "
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


def _split_scenes(beats: list[dict], scene_gap: int, max_span: int = 20) -> list[dict]:
    """Group beats into scenes by proximity in space and time.

    A scene is a run of beats at one location whose neighbours are no more than
    `scene_gap` rounds apart, capped at `max_span` rounds so a slow-burning
    place cannot swallow the whole story. Scenes are then ordered by the round
    they open on, so the screenplay reads forwards.

    Both halves matter. Cutting on pure chronology started a new scene at
    nearly every beat, since one round touches every location at once; grouping
    only by place produced scenes that jumped from round 70 back to round 12.
    Message beats carry no location and inherit the last one seen.
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
            too_far = prev_tick is not None and tick - prev_tick > scene_gap
            too_long = scene is not None and tick - scene["tick_start"] >= max_span
            if scene is None or too_far or too_long:
                scene = {"location": location, "beats": [],
                         "tick_start": tick, "tick_end": tick}
                scenes.append(scene)
            scene["beats"].append(beat)
            scene["tick_end"] = tick
            prev_tick = tick

    scenes.sort(key=lambda s: (s["tick_start"], s["tick_end"], str(s["location"] or "")))
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


def _format_cast(cast_ids: list[str], names: dict | None, kinds: dict | None = None):
    """(speaking cast, silent entities) as display-name lists.

    Environments and information carriers own memories and answer `act_on`/
    `read`, so they appear in a scene's beats -- but the kernel never gives them
    a turn, so they must never be given a line. Handing the renderer one flat
    "characters" list made it write dialogue for a place.
    """
    names, kinds = names or {}, kinds or {}
    speaking, silent = [], []
    for cid in cast_ids:
        label = f"{names[cid]} [{cid}]" if names.get(cid) else cid
        (silent if kinds.get(cid) in ("environment", "info_carrier") else speaking).append(label)
    return ", ".join(speaking), ", ".join(silent)


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


_SPEECH_KINDS = {"say", "gesture"}
_INNER_KINDS = {"think", "conclude"}


def _beat_speaker(beat):
    return beat.get("agent") or (beat.get("message") or {}).get("sender")


def _beat_kind(beat):
    if beat.get("kind") == "action":
        return (beat.get("action") or {}).get("name")
    return (beat.get("message") or {}).get("kind")


def _strip_label(line, labels):
    """Drop a speaker label the model echoed back.

    The beat list it is given reads "N. [kind] Name: content", and the model
    tends to repeat "Name:" (sometimes "Name [id]:") at the head of its line.
    The assembler supplies the label itself, so a second one would double it.
    """
    line = re.sub(r"\s*\[[a-z_]{2,}\]", "", line).strip()
    m = re.match(r"^([^:：]{1,40})[:：]\s*(.*)$", line, flags=re.S)
    if m and m.group(1).strip() in labels:
        return m.group(2).strip()
    return line


def _assemble(scene, rewrites, names, out_lang):
    """Lay out one scene: the log fixes order and speaker, the model supplies words.

    Any beat the model did not return falls back to its own text, so a scene can
    never silently lose an event -- and no passage can be attributed to someone
    who did not produce it, because the label never comes from the model.
    """
    names = names or {}
    labels = {v for v in names.values() if v} | {k for k in names}
    out = []
    for n, beat in enumerate(scene["beats"], start=1):
        lines = rewrites.get(str(n)) or rewrites.get(n)
        if isinstance(lines, str):
            lines = [lines]
        lines = [_strip_label(str(l), labels) for l in (lines or [])]
        lines = [l for l in lines if l]
        if not lines:
            fallback = _beat_content(beat)
            lines = [fallback] if fallback else []
        if not lines:
            continue
        who = names.get(_beat_speaker(beat), _beat_speaker(beat))
        kind = _beat_kind(beat)
        if kind in _SPEECH_KINDS:
            body = "\n".join(str(l).strip() for l in lines)
        else:
            # a non-speech beat is a stage direction: parenthesised, and marked
            # as inner speech when that is what it was. The renderer often
            # returns it already wrapped and already naming the actor, which
            # produced "(Rosencrantz, (Rosencrantz moves ...))".
            text = " ".join(str(l).strip() for l in lines)
            while text.startswith("(") and text.endswith(")"):
                text = text[1:-1].strip()
            if who and text.lower().startswith(str(who).lower()):
                text = text[len(str(who)):].lstrip(" ,，:：").strip()
            mark = "inner monologue: " if kind in _INNER_KINDS else ""
            body = f"({mark}{text})"
        # every beat is one labelled block, so a reader can see which agent
        # produced it and where one action ends and the next begins
        out.append(f"{who}:\n{body}")

    return "\n\n".join(out)


def _beat_content(beat):
    """Everything a beat carries, as one line.

    Both halves matter: a `think` beat's question is the prompt to itself and
    its result is the conclusion reached, and a scene that shows only the
    question loses what the agent actually decided.
    """
    if beat.get("kind") == "action":
        params = (beat.get("action") or {}).get("params") or {}
        pieces = [str(params[k]) for k in _CONTENT_PARAM_KEYS if params.get(k)]
        data = (beat.get("result") or {}).get("data")
        if data:
            pieces.append(str(data))
        return " | ".join(pieces)
    return str((beat.get("message") or {}).get("content") or "")


def _parse_rewrites(reply):
    """The {beat number: lines} object the renderer returns, or {} if unusable."""
    text = (reply or "").strip()
    if text.startswith("```"):
        text = text.strip("`")
        text = text[text.find("{"):] if "{" in text else text
    try:
        data = json.loads(text[text.index("{"):text.rindex("}") + 1])
    except (ValueError, TypeError):
        return {}
    return data if isinstance(data, dict) else {}


async def generate_screenplay(
    events: list[dict],
    llm,
    out_path: str | None = None,
    language: str = "zh",
    scene_gap: int = 5,
    names: dict | None = None,
    target_language: str | None = None,
    ensure_coverage: bool = True,
    kinds: dict | None = None,
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
        scene_gap: Max rounds between neighbouring beats of one scene.
        kinds: Optional {agent_id: kind} map ("character" / "environment" /
            "info_carrier"). Environments and information carriers appear in
            beats (they are act_on/read targets) but never take a turn, so they
            are listed to the renderer as entities that must not be given
            dialogue.
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
        beat_lines = "\n".join(
            f"{n}. [{_beat_kind(b)}] {(names or {}).get(_beat_speaker(b), _beat_speaker(b))}: "
            f"{_beat_content(b)}"
            for n, b in enumerate(scene["beats"], start=1))
        cast_str, silent_str = _format_cast(_scene_cast(scene), names, kinds)
        place = (names or {}).get(scene["location"], scene["location"])
        constraint = constraint_template.format(cast=cast_str, silent=silent_str or "-",
                                                location=place)
        prompt = target_instruction + constraint + "\n\n" + user_template.format(
            location=place,
            tick_start=scene["tick_start"],
            tick_end=scene["tick_end"],
            beats=beat_lines,
        )
        reply = await llm.chat(prompt, system=system_prompt, bucket="screenplay")
        rewrites = _parse_rewrites(reply)
        missing = [n for n in range(1, len(scene["beats"]) + 1)
                   if not (rewrites.get(str(n)) or rewrites.get(n))]
        if missing and ensure_coverage:
            retry = await llm.chat(
                prompt + "\n\nOnly these event numbers are still needed: "
                + ", ".join(map(str, missing)),
                system=system_prompt, bucket="screenplay_coverage")
            for k, v in _parse_rewrites(retry).items():
                rewrites.setdefault(str(k), v)

        span = f"{scene['tick_start']}–{scene['tick_end']}"
        out_lang = target_language or language
        header = (f"## 第{i}幕 · {place} · 回合 {span}" if out_lang == "zh"
                  else f"## Scene {i} · {place} · rounds {span}")
        blocks.append(f"{header}\n\n{_assemble(scene, rewrites, names, out_lang)}\n")

    markdown = "\n".join(blocks)

    if out_path:
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(markdown)

    return markdown
