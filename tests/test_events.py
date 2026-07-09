import json
from society.events import EventLog

def test_append_assigns_monotonic_seq_and_persists(tmp_path):
    p = str(tmp_path / "events.jsonl")
    log = EventLog(p)
    s0 = log.append(0, "action", "alice", {"action": {"name": "noop"}})
    s1 = log.append(0, "message", "kernel", {"content": "hi"})
    s2 = log.append(1, "action", "bob", {"action": {"name": "wait"}})
    assert (s0, s1, s2) == (0, 1, 2)
    lines = [json.loads(l) for l in open(p, encoding="utf-8")]
    assert len(lines) == 3 and lines[2]["tick"] == 1 and lines[2]["agent"] == "bob"
    assert EventLog.load(p) == log.all()

def test_in_memory_mode():
    log = EventLog(None)
    log.append(5, "system", "kernel", {"note": "静止"})
    assert log.all()[0]["tick"] == 5 and log.all()[0]["note"] == "静止"
