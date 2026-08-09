from society.screenplay import generate_screenplay
from tests.helpers import FakeLLM

EVENTS = [
 {"seq": 0, "tick": 0, "kind": "action", "agent": "amy",
  "action": {"name": "say", "params": {"targets": ["ben"], "content": "走吧"}},
  "result": {"ok": True}, "location": "hall"},
 {"seq": 1, "tick": 1, "kind": "action", "agent": "ben",
  "action": {"name": "think", "params": {"question": "去哪"}},
  "result": {"ok": True, "data": "还是花园好"}, "location": "hall"},
 {"seq": 2, "tick": 9, "kind": "action", "agent": "amy",
  "action": {"name": "gesture", "params": {"targets": ["ben"], "description": "指向花园"}},
  "result": {"ok": True}, "location": "garden"},
]


async def test_scene_split_and_render(tmp_path):
    calls = []
    def fn(prompt, system=None):
        calls.append(prompt)
        return f"（第{len(calls)}场渲染文本）"
    llm = FakeLLM(fn=fn)
    out = str(tmp_path / "sp.md")
    md = await generate_screenplay(EVENTS, llm, out_path=out, scene_gap=5,
                                   ensure_coverage=False)
    assert len(calls) == 2                      # hall scene + garden scene (location change & gap)
    assert "第1幕" in md and "hall" in md and "garden" in md
    assert "（第1场渲染文本）" in md and open(out, encoding="utf-8").read() == md
    assert "走吧" in calls[0] and "还是花园好" in calls[0]   # beats reach the LLM


async def test_noop_and_failed_actions_excluded():
    evs = EVENTS + [{"seq": 3, "tick": 9, "kind": "action", "agent": "amy",
                     "action": {"name": "noop", "params": {}}, "result": {"ok": True},
                     "location": "garden"},
                    {"seq": 4, "tick": 9, "kind": "action", "agent": "amy",
                     "action": {"name": "say", "params": {"targets": ["x"], "content": "?"}},
                     "result": {"ok": False, "error": "x not here"}, "location": "garden"}]
    llm = FakeLLM(fn=lambda p, s=None: "ok")
    await generate_screenplay(evs, llm)
    joined = "".join(c[1] for c in llm.calls)
    assert "noop" not in joined and "not here" not in joined


async def test_render_prompt_contains_cast_and_constraints():
    calls = []

    def fn(prompt, system=None):
        calls.append(prompt)
        return "ok"

    llm = FakeLLM(fn=fn)
    await generate_screenplay(EVENTS, llm, scene_gap=5)

    hall_prompt = calls[0]
    assert "amy" in hall_prompt and "ben" in hall_prompt
    assert "禁止虚构" in hall_prompt
    assert "ghost_agent" not in hall_prompt


async def test_names_mapping_reaches_prompt():
    calls = []

    def fn(prompt, system=None):
        calls.append(prompt)
        return "ok"

    llm = FakeLLM(fn=fn)
    await generate_screenplay(EVENTS, llm, scene_gap=5, names={"amy": "艾米"})

    assert "艾米" in calls[0]


async def test_screenplay_target_language():
    calls = []

    def fn(prompt, system=None):
        calls.append(prompt)
        return "the rendered english screenplay"

    llm = FakeLLM(fn=fn)
    md = await generate_screenplay(
        EVENTS,
        llm,
        language="zh",
        target_language="en",
        scene_gap=5,
        names={"amy": "Amy", "ben": "Ben"},
    )

    hall_prompt = calls[0]
    # instructs English rendering
    assert "English" in hall_prompt
    # still carries the grounding constraint (zh constraint template, since
    # language="zh" -- only the render target changes)
    assert "禁止虚构" in hall_prompt
    # names mapping still reaches the prompt for romanization
    assert "Amy" in hall_prompt
    # returned markdown is exactly the fake's rendered text
    assert "the rendered english screenplay" in md


async def test_screenplay_target_language_none_is_noop():
    calls = []

    def fn(prompt, system=None):
        calls.append(prompt)
        return "ok"

    llm = FakeLLM(fn=fn)
    await generate_screenplay(EVENTS, llm, language="zh", scene_gap=5)

    assert "English" not in calls[0]


async def test_screenplay_target_language_same_as_language_is_noop():
    calls = []

    def fn(prompt, system=None):
        calls.append(prompt)
        return "ok"

    llm = FakeLLM(fn=fn)
    await generate_screenplay(
        EVENTS, llm, language="zh", target_language="zh", scene_gap=5
    )

    assert "English" not in calls[0]


async def test_coverage_pass_no_repair_when_nothing_missing():
    """One render + one check per scene; a clean check adds no repair call."""
    calls = []
    def fn(prompt, system=None):
        calls.append(prompt)
        return '{"missing": []}' if "missing" in prompt else "SCENE"
    llm = FakeLLM(fn=fn)
    md = await generate_screenplay(EVENTS, llm, scene_gap=5)
    assert len(calls) == 4          # 2 scenes x (render + check), no repair
    assert "SCENE" in md


async def test_coverage_pass_repairs_a_dropped_beat():
    """A beat reported missing triggers exactly one rewrite, which is kept."""
    calls = []
    def fn(prompt, system=None):
        calls.append(prompt)
        if '"missing"' in prompt:            # the coverage-check prompt
            return '{"missing": [1]}'
        if "遗漏" in prompt or "is missing these events" in prompt:
            return "REPAIRED"
        return "SCENE"
    llm = FakeLLM(fn=fn)
    md = await generate_screenplay(EVENTS[:2], llm, scene_gap=5)
    assert "REPAIRED" in md and "SCENE" not in md
    assert len(calls) == 3          # render + check + one repair


async def test_unparseable_coverage_reply_keeps_original_scene():
    """A garbled check reply must not trigger a speculative rewrite."""
    def fn(prompt, system=None):
        return "sorry, I cannot" if '"missing"' in prompt else "SCENE"
    llm = FakeLLM(fn=fn)
    md = await generate_screenplay(EVENTS[:2], llm, scene_gap=5)
    assert "SCENE" in md


async def test_one_utterance_is_one_beat():
    """A say logged as an action plus one message per recipient is one beat.

    The kernel emits both forms; feeding all of them to a screenwriter that is
    told to place every beat would make it write the same line several times.
    """
    say = {"seq": 0, "tick": 3, "kind": "action", "agent": "amy", "location": "hall",
           "action": {"name": "say", "params": {"targets": ["ben", "cid"], "content": "撤"}},
           "result": {"ok": True}}
    msg = lambda seq: {"seq": seq, "tick": 3, "kind": "message", "location": "hall",
                       "message": {"kind": "say", "sender": "amy",
                                   "recipients": ["ben", "cid"], "content": "撤"}}
    evs = [say, msg(1), msg(2)]
    prompts = []
    llm = FakeLLM(fn=lambda p, s=None: prompts.append(p) or "SCENE")
    await generate_screenplay(evs, llm, scene_gap=5, ensure_coverage=False)
    assert prompts[0].count("撤") == 1
