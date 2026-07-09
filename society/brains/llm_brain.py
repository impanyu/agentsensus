import json
import os

from society.actions import Action, parse_action
from society.brains.base import Brain

SKILL_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "skills"))

_MAX_ATTEMPTS = 3

_FORMAT_INSTRUCTIONS = {
    "zh": (
        "\n\n## 输出格式(严格遵守)\n"
        "你每次只能返回一个 action。只允许输出一个 JSON 对象,禁止输出任何多余文字、"
        "解释、前后缀或 Markdown 代码块标记(如 ```)。\n"
        "严格格式: {\"action\": \"<action名>\", \"params\": {...}}\n"
    ),
    "en": (
        "\n\n## Output Format (follow strictly)\n"
        "You may only return a single action per turn. Respond with ONLY a "
        "single JSON object — no extra text, no explanation, no surrounding "
        "prose, no Markdown code fences (```).\n"
        "Strict format: {\"action\": \"<action name>\", \"params\": {...}}\n"
    ),
}

_RETRY_TEMPLATE = {
    "zh": "\n\n[系统提示:上一次输出解析失败,原因: {error}。请严格按照输出格式只返回一个 JSON 对象。]",
    "en": "\n\n[System note: the previous reply failed to parse, reason: {error}. "
          "Reply with ONLY a single JSON object, following the output format strictly.]",
}


class LLMBrain(Brain):
    """A brain that delegates decision-making to an LLM.

    The system prompt is built once at construction time from the agent's
    profile, the actions skill document for the configured language (plus
    any scenario-specific extra_skill text), and a strict output-format
    instruction. decide() sends the STM view as the user prompt and parses
    the reply into an Action, retrying (with the parse error appended to
    the prompt) up to two more times before giving up.
    """

    def __init__(self, llm, profile: str, language: str = "zh", extra_skill: str = ""):
        """
        Args:
            llm: Async chat client duck-typing LLMClient/FakeLLM
                (`await llm.chat(prompt, system=..., bucket=...) -> str`).
            profile: Free-text character/role profile injected first in the
                system prompt.
            language: "zh" or "en"; selects which actions skill md to load
                from SKILL_DIR (actions_skill_{language}.md).
            extra_skill: Optional scenario-specific skill text appended
                after the base skill document.
        """
        self.llm = llm
        self.profile = profile
        self.language = language
        self.extra_skill = extra_skill
        self._skill_text = self._load_skill(language)
        self.system_prompt = self._build_system_prompt()

    @staticmethod
    def _load_skill(language: str) -> str:
        path = os.path.join(SKILL_DIR, f"actions_skill_{language}.md")
        with open(path, "r", encoding="utf-8") as f:
            return f.read()

    def _build_system_prompt(self) -> str:
        format_instructions = _FORMAT_INSTRUCTIONS.get(self.language, _FORMAT_INSTRUCTIONS["en"])
        parts = [self.profile, self._skill_text]
        if self.extra_skill:
            parts.append(self.extra_skill)
        return "\n\n".join(p for p in parts if p) + format_instructions

    @staticmethod
    def _extract_json_obj(text: str) -> dict:
        """Extract and parse the first balanced {...} block in text,
        tolerating surrounding prose or Markdown code fences.
        """
        start = text.find("{")
        if start == -1:
            raise ValueError(f"no JSON object found in reply: {text!r}")

        depth = 0
        for i in range(start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    candidate = text[start:i + 1]
                    try:
                        obj = json.loads(candidate)
                    except json.JSONDecodeError as e:
                        raise ValueError(f"invalid JSON: {e}") from e
                    if not isinstance(obj, dict):
                        raise ValueError(f"JSON object expected, got: {type(obj).__name__}")
                    return obj
        raise ValueError(f"unterminated JSON object in reply: {text!r}")

    async def decide(self, view: dict) -> Action:
        """Ask the LLM to decide the next action for `view`.

        Sends up to _MAX_ATTEMPTS chat calls (bucket="decide"); each retry
        appends the previous parse error to the user prompt. Falls back to
        Action("noop", {"note": "decide-parse-failed"}) if every attempt
        fails to parse into a valid Action.
        """
        base_prompt = json.dumps(view, ensure_ascii=False)
        retry_template = _RETRY_TEMPLATE.get(self.language, _RETRY_TEMPLATE["en"])
        last_error = None

        for _ in range(_MAX_ATTEMPTS):
            prompt = base_prompt
            if last_error is not None:
                prompt += retry_template.format(error=last_error)

            reply = await self.llm.chat(prompt, system=self.system_prompt, bucket="decide")

            try:
                obj = self._extract_json_obj(reply)
                return parse_action(obj)
            except ValueError as e:
                last_error = str(e)
                continue

        return Action("noop", {"note": "decide-parse-failed"})
