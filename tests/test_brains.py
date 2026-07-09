from society.actions import Action
from society.brains.rule_brain import RuleBrain
from society.brains.retrieval_brain import RetrievalBrain
from society.brains.llm_brain import LLMBrain
from tests.helpers import FakeLLM


async def test_rule_brain_default_and_custom():
    assert (await RuleBrain().decide({})).name == "wait"
    rb = RuleBrain(fn=lambda v: Action("noop"))
    assert (await rb.decide({})).name == "noop"
    assert "推门" in RuleBrain().handle_act_on("alice", "推门", {}) or "alice" in RuleBrain().handle_act_on("alice", "推门", {})


async def test_retrieval_brain_retrieve_and_idle():
    rb = RetrievalBrain("石头记开篇。\n\n宝玉衔玉而生。\n\n黛玉进贾府。")
    assert (await rb.decide({})).name == "wait"
    out = rb.retrieve("宝玉 衔玉")
    assert "宝玉衔玉而生" in out


async def test_llm_brain_parses_action_and_injects_skill():
    llm = FakeLLM(responses=['{"action": "say", "params": {"targets": ["b"], "content": "hi"}}'])
    b = LLMBrain(llm, profile="你是黛玉", language="zh")
    a = await b.decide({"tick": 1, "goals": []})
    assert a.name == "say" and a.params["targets"] == ["b"]
    bucket, prompt = llm.calls[0][0], llm.calls[0][1]
    assert bucket == "decide"
    sys = llm.calls[0][2] if len(llm.calls[0]) > 2 else ""
    # FakeLLM must record system too: calls entries are (bucket, prompt, system)
    assert "你是黛玉" in sys and "pop_message" in sys   # skill内容注入


async def test_llm_brain_retries_then_noop():
    llm = FakeLLM(responses=["not json", "still bad", "nope"])
    b = LLMBrain(llm, profile="p")
    a = await b.decide({})
    assert a.name == "noop" and len(llm.calls) == 3
