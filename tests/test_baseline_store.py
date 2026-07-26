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


async def test_query_hits_include_stored_embedding():
    r = ChromaRows(afake_embed)
    emb = (await afake_embed(["刘备在新野"]))[0]
    await r.add("m1", "刘备在新野", emb, {"owners": '["liubei"]'})
    hits = await r.query("新野", 5)
    assert hits[0]["embedding"] == pytest.approx(emb)


async def test_query_return_query_embedding_nonempty():
    r = ChromaRows(afake_embed)
    emb = (await afake_embed(["刘备在新野"]))[0]
    await r.add("m1", "刘备在新野", emb, {"owners": '["liubei"]'})
    hits, q_emb = await r.query("新野", 5, return_query_embedding=True)
    assert hits and hits[0]["id"] == "m1"
    assert hits[0]["embedding"] == pytest.approx(emb)
    expected_q_emb = (await afake_embed(["新野"]))[0]
    assert q_emb == pytest.approx(expected_q_emb)


async def test_query_return_query_embedding_on_empty_collection():
    r = ChromaRows(afake_embed)
    hits, q_emb = await r.query("新野", 5, return_query_embedding=True)
    assert hits == []
    assert q_emb is None


async def test_query_default_shape_unchanged_on_empty_collection():
    r = ChromaRows(afake_embed)
    hits = await r.query("新野", 5)
    assert hits == []
