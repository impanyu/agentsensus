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


async def test_say_rejects_cross_location():
    a, b = char("a", "hall"), char("b", "garden")
    k = build([a, b, Agent("hall", "environment", RuleBrain(), STM()),
               Agent("garden", "environment", RuleBrain(), STM())])
    r = await k.execute(a, Action("say", {"targets": ["b"], "content": "hi"}))
    assert r.ok is False and "b" in r.error
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


async def test_read_info_carrier_queues_message_async():
    """Task S2: read is async-only -- the kernel no longer calls
    brain.retrieve() synchronously. It queues a Message(kind="read",
    content=query, wake=True) into the carrier's own inbox; the carrier
    answers on its own next tick (see test_unified_agents.py for the full
    2-3 tick round trip)."""
    a = char("a", "hall")
    book = Agent("book", "info_carrier", RetrievalBrain("宝玉衔玉而生。"), STM(status={"location": "hall"}))
    k = build([a, book, Agent("hall", "environment", RuleBrain(), STM())])
    r = await k.execute(a, Action("read", {"target": "book", "query": "宝玉"}))
    assert r.ok
    assert book.stm.inbox.qsize() == 0    # not delivered yet this tick
    k.deliver_pending()
    assert book.stm.inbox.qsize() == 1
    msg = book.stm.inbox.get_nowait()
    assert msg.kind == "read" and msg.content == "宝玉" and msg.sender == "a" and msg.wake is True


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


async def test_act_on_queues_message_to_env_inbox_async():
    """Task S2: act_on is async-only -- the kernel no longer synchronously
    calls a RuleBrain's handle_act_on. It always queues an act_on
    Message(wake=True) into the target environment's own inbox, exactly
    like say/gesture to any other agent; the environment's own brain reacts
    on its own next tick (see test_unified_agents.py for the full 2-3 tick
    round trip, including a RuleBrain env scripted with `fn` to reply via
    `say`)."""
    a = char("a", "hall")
    env = Agent("hall", "environment", RuleBrain(), STM())
    k = build([a, env])
    r = await k.execute(a, Action("act_on", {"targets": ["hall"], "content": "大门"}))
    assert r.ok
    assert env.stm.inbox.qsize() == 0    # not delivered yet this tick
    k.deliver_pending()                  # public delivery step
    assert a.stm.inbox.qsize() == 0      # the actor gets nothing synchronously
    assert env.stm.inbox.qsize() == 1
    msg = env.stm.inbox.get_nowait()
    assert msg.kind == "act_on" and msg.content == "大门" and msg.sender == "a" and msg.wake is True
