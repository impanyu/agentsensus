import pytest
from society.actions import (Action, ActionResult, Message, SYNC_ACTIONS, ASYNC_ACTIONS,
                             validate_action, parse_action)

def test_action_sets_are_disjoint_and_complete():
    assert SYNC_ACTIONS & ASYNC_ACTIONS == set()
    assert "move" in SYNC_ACTIONS and "say" in ASYNC_ACTIONS
    assert "broadcast" in ASYNC_ACTIONS
    # Task R (revert of S2): act_on/read are answered synchronously by the
    # kernel during the acting character's own apply step (environments/
    # info_carriers are passive, function-driven agents with no brain turn
    # of their own to answer on next tick), so both are SYNC_ACTIONS now.
    assert "read" in SYNC_ACTIONS and "read" not in ASYNC_ACTIONS
    assert "act_on" in SYNC_ACTIONS and "act_on" not in ASYNC_ACTIONS
    assert {"add_affiliated", "remove_affiliated", "set_affiliated", "get_affiliated"} <= SYNC_ACTIONS
    assert len(SYNC_ACTIONS | ASYNC_ACTIONS) == 26

def test_validate_ok_and_missing_param():
    assert validate_action(Action("say", {"targets": ["b"], "content": "hi"})) is None
    err = validate_action(Action("say", {"content": "hi"}))
    assert err and "targets" in err

def test_validate_rejects_unknown_and_reserved_location():
    assert validate_action(Action("fly", {})) is not None
    assert validate_action(Action("update_status", {"key": "location", "value": "x"})) is not None
    assert validate_action(Action("say", {"targets": "b", "content": "hi"})) is not None  # not a list

def test_parse_action_roundtrip_and_errors():
    a = parse_action({"action": "think", "params": {"question": "why"}})
    assert a.name == "think" and a.params["question"] == "why"
    with pytest.raises(ValueError):
        parse_action({"params": {}})
    with pytest.raises(ValueError):
        parse_action({"action": "fly", "params": {}})   # parse validates too

def test_result_and_message_serialization():
    r = ActionResult(ok=False, error="nope")
    assert r.to_dict() == {"ok": False, "data": None, "error": "nope"}
    m = Message(id="1", sender="a", recipients=["b"], kind="say", content="hi", tick_sent=3)
    d = m.to_dict()
    assert d["recipients"] == ["b"] and d["tick_sent"] == 3 and d["correlation_id"] is None
    assert d["wake"] is True   # default wake=True (say behaves exactly as before wake existed)

    quiet = Message(id="2", sender="a", recipients=["b"], kind="broadcast",
                     content="fyi", tick_sent=3, wake=False)
    assert quiet.to_dict()["wake"] is False
