import pytest

from society.baseline_store import ChromaRows
from tests.helpers import afake_embed


async def test_add_get_query_roundtrip():
    r = ChromaRows(afake_embed)
    emb = (await afake_embed(["刘备在新野"]))[0]
    await r.add("m1", "刘备在新野", emb, {"owners": '["liubei"]'})
    got = r.get("m1")
    assert got["text"] == "刘备在新野" and got["metadata"]["owners"] == '["liubei"]'
    assert r.count() == 1
    hits = await r.query("新野", 5)
    assert hits and hits[0]["id"] == "m1"
