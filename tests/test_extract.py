import json
import os

from society.extract import extract_scenario
from society.scenario import load_scenario
from tests.helpers import FakeLLM

STAGES = {
    "characters": json.dumps(
        [
            {
                "id": "daiyu",
                "name": "林黛玉",
                "profile": "多愁善感",
                "status": {"location": "xiaoxiang", "mood": "忧郁"},
                "goals": ["求真情", "试探宝玉"],
            }
        ],
        ensure_ascii=False,
    ),
    "locations": json.dumps(
        {
            "locations": [
                {"id": "xiaoxiang", "profile": "潇湘馆"},
                {"id": "hengwu", "profile": "蘅芜苑"},
            ],
            "edges": [["xiaoxiang", "hengwu", 5]],
        },
        ensure_ascii=False,
    ),
    "carriers": json.dumps(
        [
            {
                "id": "shitou_ji",
                "profile": "石头记",
                "location": "xiaoxiang",
                "excerpt": "满纸荒唐言",
            }
        ],
        ensure_ascii=False,
    ),
    "memories": json.dumps({"daiyu": ["黛玉葬花", "宝玉赠帕"]}, ensure_ascii=False),
    "kickoff": json.dumps(
        [{"to": ["daiyu"], "kind": "system", "content": "宝玉遣人送帕"}], ensure_ascii=False
    ),
}


def fake(prompt, system=None):
    for key, marker in [
        ("characters", "角色"),
        ("locations", "地点"),
        ("carriers", "信息载体"),
        ("memories", "记忆"),
        ("kickoff", "起始"),
    ]:
        if marker in prompt:
            return STAGES[key]
    return "[]"


async def test_extract_produces_loadable_scenario(tmp_path):
    out = str(tmp_path / "red.yaml")
    cfg = await extract_scenario("……黛玉葬花……", FakeLLM(fn=fake), out, max_agents=10)
    loaded = load_scenario(out)  # must pass the real loader's validation
    ids = {a["id"] for a in loaded["agents"]}
    assert {"daiyu", "xiaoxiang", "hengwu", "shitou_ji"} <= ids
    daiyu = next(a for a in loaded["agents"] if a["id"] == "daiyu")
    assert daiyu["goals"] == ["求真情", "试探宝玉"] and daiyu["seed_memories"] == [
        "黛玉葬花",
        "宝玉赠帕",
    ]
    assert loaded["map"]["edges"] == [["xiaoxiang", "hengwu", 5]]
    corpus = os.path.join(str(tmp_path), "corpora", "shitou_ji.txt")
    assert os.path.exists(corpus) and "满纸荒唐言" in open(corpus, encoding="utf-8").read()
    assert loaded["kickoff"][0]["to"] == ["daiyu"]


async def test_stage_failure_is_skipped_with_warning(tmp_path):
    def flaky(prompt, system=None):
        if "信息载体" in prompt:
            return "not json at all"
        return fake(prompt)

    cfg = await extract_scenario("文本", FakeLLM(fn=flaky), str(tmp_path / "x.yaml"))
    assert cfg["_warnings"] and any("carrier" in w or "信息载体" in w for w in cfg["_warnings"])
    load_scenario(str(tmp_path / "x.yaml"))  # still loadable without carriers
