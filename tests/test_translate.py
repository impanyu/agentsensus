import os
import json
import subprocess
import sys
import warnings

from society.translate import to_bilingual_table, translate_entries
from tests.helpers import FakeLLM

ENTRIES = [
    {"id": "e1", "text": "刘备三顾茅庐", "owners": ["liubei"], "meta": {"tick": 1}},
    {"id": "e2", "text": "关羽张飞结拜", "owners": ["guanyu", "zhangfei"], "meta": {"tick": 2}},
]


async def test_translate_entries_adds_text_en():
    llm = FakeLLM(
        responses=[
            json.dumps(["Liu Bei visits the thatched cottage three times", "Guan Yu and Zhang Fei swear brotherhood"])
        ]
    )

    out = await translate_entries(ENTRIES, llm, target_language="en")

    assert len(out) == 2
    assert out[0]["text_en"] == "Liu Bei visits the thatched cottage three times"
    assert out[1]["text_en"] == "Guan Yu and Zhang Fei swear brotherhood"
    # originals untouched
    assert out[0]["text"] == "刘备三顾茅庐"
    assert out[1]["text"] == "关羽张飞结拜"
    assert ENTRIES[0].get("text_en") is None  # source list not mutated
    # owners/meta preserved
    assert out[0]["owners"] == ["liubei"]
    assert out[1]["owners"] == ["guanyu", "zhangfei"]
    assert out[0]["meta"] == {"tick": 1}

    table = to_bilingual_table(out, lang="en")
    assert table == [
        {
            "id": "e1",
            "source": "刘备三顾茅庐",
            "translation": "Liu Bei visits the thatched cottage three times",
            "owners": ["liubei"],
        },
        {
            "id": "e2",
            "source": "关羽张飞结拜",
            "translation": "Guan Yu and Zhang Fei swear brotherhood",
            "owners": ["guanyu", "zhangfei"],
        },
    ]


async def test_translate_entries_batches():
    calls = []

    def fn(prompt, system=None):
        calls.append(prompt)
        return json.dumps(["x"])

    llm = FakeLLM(fn=fn)
    out = await translate_entries(ENTRIES[:1], llm, target_language="en", batch_size=1)
    assert len(calls) == 1
    assert out[0]["text_en"] == "x"


async def test_translate_entries_falls_back_on_parse_failure():
    # batch reply is not valid JSON -> falls back to per-entry translation
    llm = FakeLLM(responses=["not json at all", "Translated one", "Translated two"])

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        out = await translate_entries(ENTRIES, llm, target_language="en", batch_size=25)

    assert out[0]["text_en"] == "Translated one"
    assert out[1]["text_en"] == "Translated two"
    assert any("fall" in str(w.message).lower() for w in caught)


async def test_translate_entries_leaves_empty_with_warning_on_total_failure():
    class BrokenLLM:
        async def chat(self, prompt, system=None, bucket="decide"):
            if "Translate each" in prompt:
                return "still not json"
            raise RuntimeError("boom")

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        out = await translate_entries(ENTRIES[:1], BrokenLLM(), target_language="en")

    assert out[0]["text_en"] == ""
    assert any("could not translate" in str(w.message) for w in caught)


def test_cli_help_works():
    result = subprocess.run(
        [sys.executable, "-m", "society.translate", "--help"],
        capture_output=True,
        text=True,
        cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    )
    assert result.returncode == 0
    assert "--ltm" in result.stdout
    assert "--out" in result.stdout
    assert "--lang" in result.stdout
