from society.conversations import Thread, ConversationStore


def _m(sender, content, tick=0, kind="say"):
    return {"sender": sender, "kind": kind, "content": content, "tick": tick}


def test_thread_append_unread_read():
    t = Thread("bob", kind="character")
    t.append(_m("bob", "hi"))
    t.append(_m("bob", "there"))
    assert t.unread == 2 and len(t.messages) == 2
    assert t.recent(1) == [_m("bob", "there")]
    t.mark_read()
    assert t.unread == 0


def test_store_record_both_sides_and_roster():
    s = ConversationStore()
    s.record("alice", "bob", _m("bob", "hi"), unread_delta=1, kind="character")
    s.record("bob", "alice", _m("bob", "hi"), unread_delta=0, kind="character")
    agents = {"bob": type("A", (), {"kind": "character", "name": "Bob"})(),
              "carol": type("A", (), {"kind": "character", "name": "Carol"})()}
    roster = s.roster("alice", colocated_ids={"bob", "carol"}, agents=agents)
    by = {r["other"]: r for r in roster}
    assert by["bob"]["unread"] == 1 and by["bob"]["colocated"] is True
    assert by["bob"]["last_preview"].startswith("hi")
    # carol: co-located but no thread yet -> present with unread 0
    assert by["carol"]["unread"] == 0 and by["carol"]["colocated"] is True


def test_store_read_marks_read_and_export_restore():
    s = ConversationStore()
    s.record("alice", "bob", _m("bob", "hi"))
    assert s.read("alice", "bob", k=10)[0]["content"] == "hi"
    # read marks it read
    assert s.roster("alice", set(), {"bob": type("A", (), {"kind": "character"})()})[0]["unread"] == 0
    s2 = ConversationStore(); s2.restore(s.export())
    assert s2.read("alice", "bob")[0]["content"] == "hi"
