import pytest
from society.boundary_state import gather_timeline, finalize_boundary_state
from tests.helpers import FakeLLM


def _mem(text, owners, so):
    return {"text": text, "owners": owners, "meta": {"story_order": so}}


def test_gather_timeline_owned_sorted_and_capped():
    mems = [
        _mem("b", ["x"], 20), _mem("a", ["x"], 10),
        _mem("other", ["y"], 5), _mem("c", ["x", "z"], 30),
    ]
    assert gather_timeline(mems, "x") == ["a", "b", "c"]        # owned by x, story order
    assert gather_timeline(mems, "y") == ["other"]
    # cap keeps the LATEST max_mem
    big = [_mem(str(i), ["x"], i) for i in range(300)]
    tl = gather_timeline(big, "x", max_mem=200)
    assert len(tl) == 200 and tl[0] == "100" and tl[-1] == "299"


async def test_grounded_death_from_timeline():
    mems = [_mem("何进入宫", ["hejin"], 1), _mem("何进被十常侍所杀", ["hejin"], 2)]
    llm = FakeLLM(fn=lambda p, s=None: '{"alive": false, "location": "", "determinable": true}')
    out = await finalize_boundary_state(mems, ["hejin"], {"luoyang"}, llm=llm, boundary_context="ctx")
    assert out["hejin"]["alive"] is False and out["hejin"]["source"] == "memory"


async def test_grounded_location_from_timeline():
    mems = [_mem("曹操在许昌议事", ["caocao"], 5)]
    llm = FakeLLM(fn=lambda p, s=None: '{"alive": true, "location": "xuchang", "determinable": true}')
    out = await finalize_boundary_state(mems, ["caocao"], {"xuchang", "luoyang"}, llm=llm, boundary_context="ctx")
    assert out["caocao"] == {"alive": True, "location": "xuchang", "source": "memory"}


async def test_inconclusive_timeline_triggers_canon_fallback():
    mems = [_mem("某无关记忆", ["liubei"], 1)]
    def fn(prompt, system=None):
        if "determinable" in prompt:               # grounded call
            return '{"alive": true, "location": "", "determinable": false}'
        return '{"alive": true, "location": "xinye"}'  # fallback call
    out = await finalize_boundary_state(mems, ["liubei"], {"xinye"}, llm=FakeLLM(fn=fn), boundary_context="第40回 …")
    assert out["liubei"] == {"alive": True, "location": "xinye", "source": "canon@boundary"}


async def test_off_list_location_becomes_none():
    mems = [_mem("x", ["a"], 1)]
    def fn(prompt, system=None):
        if "determinable" in prompt:
            return '{"alive": true, "location": "nowhere", "determinable": true}'
        return '{"alive": true, "location": "stillnowhere"}'   # fallback also off-list
    out = await finalize_boundary_state(mems, ["a"], {"xuchang"}, llm=FakeLLM(fn=fn), boundary_context="ctx")
    assert out["a"]["location"] is None and out["a"]["alive"] is True


async def test_no_timeline_goes_straight_to_fallback():
    def fn(prompt, system=None):
        return '{"alive": true, "location": "jiangdong"}'
    out = await finalize_boundary_state([], ["sunquan"], {"jiangdong"}, llm=FakeLLM(fn=fn), boundary_context="ctx")
    assert out["sunquan"]["source"] == "canon@boundary" and out["sunquan"]["location"] == "jiangdong"


from experiments.select_cast import apply_boundary_state


def test_apply_sets_location_and_archives_dead():
    agents = [
        {"id": "caocao", "kind": "character", "status": {"location": "hedong"}},
        {"id": "hejin", "kind": "character", "status": {"location": "hedong"}},
        {"id": "liubei", "kind": "character", "status": {"location": "xinye"}},
        {"id": "lijue", "kind": "character", "archived": True, "status": {"location": "shanzhong"}},
        {"id": "xuchang", "kind": "environment"},
    ]
    finalized = {
        "caocao": {"alive": True, "location": "xuchang", "source": "memory"},
        "hejin": {"alive": False, "location": None, "source": "memory"},
        "liubei": {"alive": True, "location": None, "source": "canon@boundary"},  # unresolved -> keep prior
        # pre-archived (from prior sedimentation) + a false-negative "alive=True"
        # from finalize_boundary_state -- must NOT be resurrected, but its
        # dangling location must still be cleared.
        "lijue": {"alive": True, "location": None, "source": "canon@boundary"},
    }
    counts = apply_boundary_state(agents, {"caocao", "hejin", "liubei", "lijue"}, finalized)
    byid = {a["id"]: a for a in agents}
    assert byid["caocao"]["status"]["location"] == "xuchang"      # relocated
    assert byid["hejin"].get("archived") is True                 # dead archived
    assert "location" not in byid["hejin"].get("status", {})     # dangling location cleared
    assert byid["liubei"]["status"]["location"] == "xinye"       # unresolved -> unchanged
    assert byid["lijue"].get("archived") is True                 # stays archived (not resurrected)
    assert "location" not in byid["lijue"].get("status", {})     # dangling location cleared, even though "alive"
    assert counts["archived"] == 1 and counts["relocated"] == 1


async def test_prompts_are_conservative_and_novel_anchored():
    # grounded prompt must instruct conservative death (explicit-only);
    # fallback prompt must anchor to the novel, not real-world history.
    prompts = []
    def fn(prompt, system=None):
        prompts.append(prompt)
        if "determinable" in prompt:                       # grounded call
            return '{"alive": true, "location": "", "determinable": false}'
        return '{"alive": true, "location": "loc"}'          # fallback call
    mems = [{"text": "x", "owners": ["a"], "meta": {"story_order": 1}}]
    await finalize_boundary_state(
        mems, ["a"], {"loc"}, llm=FakeLLM(fn=fn), boundary_context="第四十回 …")
    grounded = next(p for p in prompts if "determinable" in p)
    fallback = next(p for p in prompts if "determinable" not in p)
    assert "EXPLICITLY" in grounded and "alive=false ONLY if" in grounded
    assert "WORK ITSELF" in fallback and "history" in fallback
