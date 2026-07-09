import pytest
from society.llm import LLMClient, BudgetExceeded


def make_client(**kw):
    async def transport(payload):
        return {"choices": [{"message": {"content": "ok:" + payload["messages"][-1]["content"]}}],
                "usage": {"total_tokens": 7}}
    kw.setdefault("backoff_base", 0.0)
    return LLMClient("k", "http://x", "m", transport=transport, **kw)


async def test_chat_returns_content_and_counts_buckets():
    c = make_client()
    out = await c.chat("hello", bucket="think")
    assert out == "ok:hello"
    u = c.usage()
    assert u["think"]["calls"] == 1 and u["think"]["tokens"] == 7
    assert u["_total"]["calls"] == 1


async def test_budget_max_calls_enforced():
    c = make_client(max_calls=1)
    await c.chat("a")
    with pytest.raises(BudgetExceeded):
        await c.chat("b")


async def test_retry_then_success():
    attempts = {"n": 0}

    async def flaky(payload):
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise RuntimeError("boom")
        return {"choices": [{"message": {"content": "done"}}], "usage": {}}

    c = LLMClient("k", "http://x", "m", transport=flaky, retries=3, backoff_base=0.0)
    assert await c.chat("x") == "done"
    assert attempts["n"] == 3


async def test_fakes_are_deterministic():
    from tests.helpers import FakeLLM, fake_embed
    f = FakeLLM(responses=["r1", "r2"])
    assert await f.chat("p") == "r1" and await f.chat("p") == "r2"
    assert f.calls[0][1] == "p"
    assert fake_embed(["同一句"]) == fake_embed(["同一句"])
    assert fake_embed(["a"]) != fake_embed(["b"])
