"""Task S2.1: info_carrier placement.

Bug fixed: `_assemble_history_scenario` used to emit every info_carrier
agent with `"status": {}` -- no location, no portable/holder. Kernel
`_is_readable` (society/kernel.py) requires the reader to either share the
carrier's location or have it portable-and-held, so with an empty status
neither is ever true and `read` was permanently unreachable for every
carrier in every real scenario (Hamlet's love_letter/sealed_commission/
gonzago_script, etc).

Fix: `_assign_carrier_placements` runs ONE LLM call (marker
"[carrier-placement]") assigning each carrier a placement, resolved
against the registry's id/name/alias tables; `_assemble_history_scenario`
takes the result via its `carrier_placements` kwarg and emits
status.location/portable/holder onto each carrier agent dict.

No real API calls anywhere -- FakeLLM only.
"""

import json

from society.history_extract import (
    _assemble_history_scenario,
    _assign_carrier_placements,
)
from tests.helpers import FakeLLM

REGISTRY = {
    "characters": [
        {"id": "alice", "name": "甲", "aliases": ["小甲"], "profile": ""},
        {"id": "bob", "name": "乙", "aliases": [], "profile": ""},
    ],
    "locations": [
        {"id": "loc1", "name": "集市", "aliases": [], "profile": ""},
        {"id": "loc2", "name": "书房", "aliases": ["书斋"], "profile": ""},
    ],
    "carriers": [{"id": "letter1", "name": "一封信", "profile": "甲写给乙的信"}],
}


def _registry(**overrides) -> dict:
    reg = json.loads(json.dumps(REGISTRY))  # deep copy
    reg.update(overrides)
    return reg


def _routed(fn):
    def fake(prompt, system=None):
        if "[carrier-placement]" in prompt:
            return fn(prompt)
        return "[]"

    return fake


# ----------------------------------------------------------------------
# 1. Correct placement applied: location by name, portable + holder by id.
# ----------------------------------------------------------------------


async def test_assign_carrier_placements_correct_placement_applied():
    registry = _registry()
    response = json.dumps(
        [{"location": "书房", "portable": True, "holder": "bob"}], ensure_ascii=False
    )
    llm = FakeLLM(fn=_routed(lambda p: response))
    warnings: list[str] = []

    placements = await _assign_carrier_placements(llm, registry, warnings)

    assert placements == {"letter1": {"location": "loc2", "portable": True, "holder": "bob"}}
    assert warnings == []
    assert len(llm.calls) == 1
    assert "[carrier-placement]" in llm.calls[0][1]


async def test_assign_carrier_placements_wires_into_assembly():
    registry = _registry()
    placements = {"letter1": {"location": "loc2", "portable": True, "holder": "bob"}}
    warnings: list[str] = []

    cfg, _carriers = _assemble_history_scenario(
        registry=registry,
        state={},
        scenario_name="s",
        language="zh",
        warnings=warnings,
        carrier_placements=placements,
    )

    carrier_agent = next(a for a in cfg["agents"] if a["kind"] == "info_carrier")
    assert carrier_agent["status"] == {"location": "loc2"}
    assert carrier_agent["portable"] is True
    assert carrier_agent["holder"] == "bob"


def test_assemble_without_carrier_placements_kwarg_keeps_old_empty_status():
    """Default `carrier_placements=None` reproduces the pre-fix behavior,
    so the many direct callers in tests/test_history_locations.py that
    don't pass it (and don't care about carriers) are unaffected."""
    registry = _registry()
    warnings: list[str] = []

    cfg, _carriers = _assemble_history_scenario(
        registry=registry, state={}, scenario_name="s", language="zh", warnings=warnings
    )

    carrier_agent = next(a for a in cfg["agents"] if a["kind"] == "info_carrier")
    assert carrier_agent["status"] == {}
    assert "portable" not in carrier_agent
    assert "holder" not in carrier_agent


# ----------------------------------------------------------------------
# 2. Malformed reply -> fallback to first environment id + portable=False,
#    with a warning. Covers: non-JSON, JSON-but-not-a-list, and a
#    per-item unresolvable location.
# ----------------------------------------------------------------------


async def test_assign_carrier_placements_non_json_reply_falls_back_with_warning():
    registry = _registry()
    llm = FakeLLM(fn=_routed(lambda p: "not json at all"))
    warnings: list[str] = []

    placements = await _assign_carrier_placements(llm, registry, warnings)

    assert placements == {"letter1": {"location": "loc1", "portable": False, "holder": None}}
    assert any("carrier placement" in w for w in warnings)


async def test_assign_carrier_placements_json_object_not_array_falls_back_with_warning():
    registry = _registry()
    llm = FakeLLM(fn=_routed(lambda p: json.dumps({"oops": "not a list"})))
    warnings: list[str] = []

    placements = await _assign_carrier_placements(llm, registry, warnings)

    assert placements == {"letter1": {"location": "loc1", "portable": False, "holder": None}}
    assert any("carrier placement" in w for w in warnings)


async def test_assign_carrier_placements_unresolvable_location_falls_back_with_warning():
    registry = _registry()
    response = json.dumps([{"location": "atlantis", "portable": False}], ensure_ascii=False)
    llm = FakeLLM(fn=_routed(lambda p: response))
    warnings: list[str] = []

    placements = await _assign_carrier_placements(llm, registry, warnings)

    assert placements == {"letter1": {"location": "loc1", "portable": False, "holder": None}}
    assert any("unresolvable location" in w for w in warnings)


async def test_assign_carrier_placements_short_reply_falls_back_per_missing_item():
    """Reply shorter than the carrier list -- the missing tail carrier(s)
    fall back individually rather than crashing on an index error."""
    registry = _registry(
        carriers=[
            {"id": "letter1", "name": "一封信", "profile": ""},
            {"id": "letter2", "name": "第二封信", "profile": ""},
        ]
    )
    response = json.dumps([{"location": "loc1", "portable": False}], ensure_ascii=False)
    llm = FakeLLM(fn=_routed(lambda p: response))
    warnings: list[str] = []

    placements = await _assign_carrier_placements(llm, registry, warnings)

    assert placements["letter1"] == {"location": "loc1", "portable": False, "holder": None}
    assert placements["letter2"] == {"location": "loc1", "portable": False, "holder": None}
    assert any("letter2" in w for w in warnings)


# ----------------------------------------------------------------------
# 3. Holder resolution: by alias, and dropped-but-not-fatal when
#    unresolvable.
# ----------------------------------------------------------------------


async def test_assign_carrier_placements_holder_resolved_by_alias():
    registry = _registry()
    response = json.dumps(
        [{"location": "loc1", "portable": True, "holder": "小甲"}], ensure_ascii=False
    )
    llm = FakeLLM(fn=_routed(lambda p: response))
    warnings: list[str] = []

    placements = await _assign_carrier_placements(llm, registry, warnings)

    assert placements["letter1"] == {"location": "loc1", "portable": True, "holder": "alice"}
    assert warnings == []


async def test_assign_carrier_placements_unresolvable_holder_dropped_not_fatal():
    """An unresolvable holder ref does not fall back the whole carrier --
    location/portable from the reply are kept, holder just drops to None,
    with a (non-fatal) warning."""
    registry = _registry()
    response = json.dumps(
        [{"location": "loc1", "portable": True, "holder": "nobody-such-character"}],
        ensure_ascii=False,
    )
    llm = FakeLLM(fn=_routed(lambda p: response))
    warnings: list[str] = []

    placements = await _assign_carrier_placements(llm, registry, warnings)

    assert placements["letter1"] == {"location": "loc1", "portable": True, "holder": None}
    assert any("holder" in w and "dropped" in w for w in warnings)


async def test_assign_carrier_placements_no_holder_given_stays_none():
    registry = _registry()
    response = json.dumps([{"location": "loc1", "portable": False}], ensure_ascii=False)
    llm = FakeLLM(fn=_routed(lambda p: response))
    warnings: list[str] = []

    placements = await _assign_carrier_placements(llm, registry, warnings)

    assert placements["letter1"]["holder"] is None
    assert warnings == []


# ----------------------------------------------------------------------
# 4. Edge cases: no carriers (no LLM call), zero environments (warn, {}).
# ----------------------------------------------------------------------


async def test_assign_carrier_placements_no_carriers_is_noop():
    registry = _registry(carriers=[])
    llm = FakeLLM(fn=lambda p, system=None: "[]")
    warnings: list[str] = []

    placements = await _assign_carrier_placements(llm, registry, warnings)

    assert placements == {}
    assert llm.calls == []
    assert warnings == []


async def test_assign_carrier_placements_zero_environments_warns_and_returns_empty():
    registry = _registry(locations=[])
    llm = FakeLLM(fn=lambda p, system=None: "[]")
    warnings: list[str] = []

    placements = await _assign_carrier_placements(llm, registry, warnings)

    assert placements == {}
    assert llm.calls == []  # no environments to place into -- no point calling the LLM
    assert any("zero environments" in w for w in warnings)
