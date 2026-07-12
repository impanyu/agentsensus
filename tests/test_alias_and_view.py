from society.actions import Action
from society.agent import Agent
from society.brains.rule_brain import RuleBrain
from society.events import EventLog
from society.kernel import Kernel
from society.stm import STM
from society.worldmap import WorldMap


def char(aid, loc, name=None, fn=None, goals=None):
    stm = STM(status={"location": loc}, goals=goals or [])
    return Agent(aid, "character", RuleBrain(fn=fn), stm, name=name)


def env(aid, name=None):
    return Agent(aid, "environment", RuleBrain(), STM(), name=name)


def build(agents, edges=None):
    envs = [a.id for a in agents if a.kind == "environment"]
    return Kernel(
        {a.id: a for a in agents},
        WorldMap(envs, edges=edges, default_distance=3),
        EventLog(None),
    )


async def test_alias_resolves_chinese_names():
    liubei = char("liubei", "xiakou")
    sunquan = char("sunquan", "xiakou", name="孙权")
    k = build([liubei, sunquan, env("xiakou")])

    r = await k.execute(liubei, Action("say", {"targets": ["孙权"], "content": "请速速发兵"}))

    assert r.ok is True
    assert len(k._pending) == 1
    assert k._pending[0].recipients == ["sunquan"]


async def test_move_resolves_env_name():
    liubei = char("liubei", "chaisang")
    xiakou = env("xiakou", name="夏口")
    chaisang = env("chaisang")
    k = build([liubei, xiakou, chaisang], edges=[("chaisang", "xiakou", 3)])

    r = await k.execute(liubei, Action("move", {"destination": "夏口"}))

    assert r.ok is True
    assert liubei.transit is not None and liubei.transit["dest"] == "xiakou"


async def test_view_contains_colocated_and_locations():
    captured = {}

    def stash(view):
        captured["view"] = view
        return Action("wait")

    liubei = char("liubei", "xiakou", fn=stash)
    sunquan = char("sunquan", "xiakou", name="孙权")
    chaisang = env("chaisang", name="柴桑")
    xiakou = env("xiakou", name="夏口")
    k = build([liubei, sunquan, chaisang, xiakou])

    action, brain_error = await k._decide(liubei)

    assert brain_error is None
    view = captured["view"]

    colocated = view["colocated"]
    assert [c["id"] for c in colocated] == ["sunquan"]
    assert colocated[0]["kind"] == "character"
    assert colocated[0]["name"] == "孙权"
    assert all(c["id"] != "liubei" for c in colocated)

    known = {loc["id"]: loc["name"] for loc in view["known_locations"]}
    assert known == {"chaisang": "柴桑", "xiakou": "夏口"}


async def test_unknown_ref_still_errors():
    liubei = char("liubei", "xiakou")
    k = build([liubei, env("xiakou")])

    r = await k.execute(liubei, Action("say", {"targets": ["不存在的人"], "content": "hi"}))

    assert r.ok is False
    assert "不存在的人" in r.error
