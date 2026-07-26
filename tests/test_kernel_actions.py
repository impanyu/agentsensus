import uuid
from society.actions import Action
from society.agent import Agent
from society.brains.rule_brain import RuleBrain
from society.brains.retrieval_brain import RetrievalBrain
from society.events import EventLog
from society.kernel import Kernel
from society.ltm import SharedMemory
from society.stm import STM
from society.worldmap import WorldMap
from tests.helpers import FakeLLM, afake_embed


def build(agents, llm=None, shared=None, edges=None):
    envs = [a.id for a in agents if a.kind == "environment"]
    return Kernel({a.id: a for a in agents},
                  WorldMap(envs, edges=edges, default_distance=4),
                  EventLog(None), shared_memory=shared, llm=llm)


def char(aid, loc):
    return Agent(aid, "character", RuleBrain(), STM(status={"location": loc}))


async def test_say_cross_location_now_succeeds_after_distance_delay():
    """Task 3 (unified say): cross-location targets are no longer rejected
    -- there is no co-location gate any more. A remote `say` is routed
    through `route()` and delivered after a worldmap-distance delay (a
    "letter"), instead of instantly like a same-room utterance."""
    a, b = char("a", "hall"), char("b", "garden")
    k = build([a, b, Agent("hall", "environment", RuleBrain(), STM()),
               Agent("garden", "environment", RuleBrain(), STM())])
    r = await k.execute(a, Action("say", {"targets": ["b"], "content": "hi"}))
    assert r.ok is True

    # Not yet delivered: build()'s WorldMap is fully-connected with
    # default_distance=4, so hall->garden is a 4-tick delay.
    k._deliver_due()
    assert k.conversations.read("b", "a", k=10) == []

    k.tick += 4
    k._deliver_due()
    msgs = k.conversations.read("b", "a", k=10)
    assert len(msgs) == 1 and msgs[0]["content"] == "hi"

    r2 = await k.execute(a, Action("say", {"targets": ["ghost"], "content": "hi"}))
    assert r2.ok is False


async def test_observe_environment_lists_occupants():
    a, b = char("a", "hall"), char("b", "hall")
    k = build([a, b, Agent("hall", "environment", RuleBrain(), STM(status={"desc": "大厅"}))])
    r = await k.execute(a, Action("observe", {"target": "hall"}))
    assert r.ok and r.data["kind"] == "environment"
    assert [o["id"] for o in r.data["occupants"]] == ["b"]


async def test_observe_character_requires_colocation():
    a, b = char("a", "hall"), char("b", "garden")
    k = build([a, b, Agent("hall", "environment", RuleBrain(), STM()),
               Agent("garden", "environment", RuleBrain(), STM())])
    assert (await k.execute(a, Action("observe", {"target": "b"}))).ok is False


async def test_read_info_carrier_returns_target_owner_recall_synchronously():
    """Task R (revert of S2): read is SYNCHRONOUS -- info_carriers are
    passive, function-driven agents with no brain turn of their own, so the
    kernel retrieves the carrier's OWN memories (via
    SharedMemory.recall_of) and returns them in the SAME tick, with no
    Message/inbox round trip at all."""
    shared = SharedMemory(afake_embed, llm=None, collection_name=f"t_{uuid.uuid4().hex[:8]}")
    a = char("a", "hall")
    book = Agent("book", "info_carrier", RetrievalBrain("宝玉衔玉而生。"), STM(status={"location": "hall"}))
    k = build([a, book, Agent("hall", "environment", RuleBrain(), STM())], shared=shared)

    await shared.remember_atomic(["book"], "宝玉衔玉而生", source="sediment")

    r = await k.execute(a, Action("read", {"target": "book", "query": "宝玉"}))
    assert r.ok
    assert r.data and r.data[0]["text"] == "宝玉衔玉而生"
    assert k._pending == []    # no Message ever sent
    k._deliver_due()
    assert k._pending == []


async def test_read_rejects_non_carrier_and_non_readable():
    a, b = char("a", "hall"), char("b", "garden")
    book = Agent("book", "info_carrier", RetrievalBrain("宝玉衔玉而生。"), STM(status={"location": "garden"}))
    k = build([a, b, book, Agent("hall", "environment", RuleBrain(), STM()),
               Agent("garden", "environment", RuleBrain(), STM())])
    # not an info_carrier at all
    r1 = await k.execute(a, Action("read", {"target": "b", "query": "宝玉"}))
    assert r1.ok is False
    # info_carrier exists but isn't co-located with (or held by) the reader
    r2 = await k.execute(a, Action("read", {"target": "book", "query": "宝玉"}))
    assert r2.ok is False


async def test_move_sets_transit_and_arrival():
    a = char("a", "hall")
    k = build([a, Agent("hall", "environment", RuleBrain(), STM()),
               Agent("garden", "environment", RuleBrain(), STM())],
              edges=[("hall", "garden", 2)])
    r = await k.execute(a, Action("move", {"destination": "garden"}))
    assert r.ok and a.transit == {"dest": "garden", "arrive_at": 2}   # tick=0 + distance 2
    assert "a" not in k.presence.get("hall", set())
    await k.run(max_ticks=5)                                          # arrival processed
    assert a.location() == "garden" and a.transit is None
    arrival_events = [e for e in k.event_log.all()
                       if e["kind"] == "system" and e.get("event") == "arrival"]
    assert any(e["agent"] == "a" and e["dest"] == "garden" for e in arrival_events)


async def test_move_rejects_unconnected_or_nonenv():
    a = char("a", "hall")
    k = build([a, Agent("hall", "environment", RuleBrain(), STM()),
               Agent("tower", "environment", RuleBrain(), STM())],
              edges=[("hall", "tower", 3)])
    assert (await k.execute(a, Action("move", {"destination": "a"}))).ok is False
    k2 = build([char("x", "hall"), Agent("hall", "environment", RuleBrain(), STM()),
                Agent("far", "environment", RuleBrain(), STM())], edges=[])
    # fully_connected default True → give explicit non-connected map:
    from society.worldmap import WorldMap as WM
    k2.worldmap = WM(["hall", "far"], edges=[], fully_connected=False)
    assert (await k2.execute(k2.agents["x"], Action("move", {"destination": "far"}))).ok is False


async def test_memory_actions_roundtrip():
    shared = SharedMemory(afake_embed, llm=None, collection_name=f"t_{uuid.uuid4().hex[:8]}")
    a = char("a", "hall")
    k = build([a, Agent("hall", "environment", RuleBrain(), STM())], shared=shared)
    r = await k.execute(a, Action("remember", {"text": "花园着火"}))
    assert r.ok and r.data[0]["text"] == "花园着火"
    r2 = await k.execute(a, Action("recall", {"query": "花园着火"}))
    assert r2.ok and r2.data[0]["text"] == "花园着火"
    r3 = await k.execute(a, Action("forget", {"memory_id": r.data[0]["id"]}))
    assert r3.ok
    assert (await k.execute(a, Action("recall", {"query": "花园"}))).data == []


async def test_think_uses_llm_bucket():
    llm = FakeLLM(responses=["结论:该走了"])
    a = char("a", "hall")
    k = build([a, Agent("hall", "environment", RuleBrain(), STM())], llm=llm)
    r = await k.execute(a, Action("think", {"question": "下一步?"}))
    assert r.ok and "结论" in r.data and llm.calls[0][0] == "think"


async def test_act_on_deposits_env_owned_memory_synchronously():
    """Task R (revert of S2): act_on is SYNCHRONOUS -- environments are
    passive, function-driven agents with no brain turn of their own, so the
    kernel deposits an env-owned memory (source="act_on") and returns
    immediately, with no Message/inbox round trip at all."""
    shared = SharedMemory(afake_embed, llm=None, collection_name=f"t_{uuid.uuid4().hex[:8]}")
    a = char("a", "hall")
    env = Agent("hall", "environment", RuleBrain(), STM())
    k = build([a, env], shared=shared)
    r = await k.execute(a, Action("act_on", {"targets": ["hall"], "content": "大门"}))
    assert r.ok
    assert r.data == {"env": "hall", "recorded": "大门"}
    assert k._pending == []
    k._deliver_due()
    assert k._pending == []    # no Message ever sent

    recorded = await shared.recall_of("hall", "大门", top_k=5)
    assert recorded and recorded[0]["text"] == "大门"
