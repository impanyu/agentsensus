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
    md = await generate_screenplay(EVENTS, llm, out_path=out, scene_gap=5)
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
