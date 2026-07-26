"""Per-interlocutor conversation threads (kernel-held), replacing the STM
FIFO inbox. A ConversationStore maps {owner_id: {other_id: Thread}}; a Thread
is an ordered list of lightweight message records with an unread counter.
Pure data structures -- the kernel does routing/delay. See
docs/superpowers/specs/2026-07-26-conversation-threads-design.md."""


class Thread:
    def __init__(self, other_id, kind=None):
        self.other_id = other_id
        self.kind = kind
        self.messages = []
        self.unread = 0

    def append(self, msg, unread_delta=1):
        self.messages.append(dict(msg))
        self.unread += unread_delta

    def mark_read(self):
        self.unread = 0

    def recent(self, k):
        return [dict(m) for m in self.messages[-k:]] if k else [dict(m) for m in self.messages]

    def to_dict(self):
        return {"other_id": self.other_id, "kind": self.kind,
                "messages": [dict(m) for m in self.messages], "unread": self.unread}

    @classmethod
    def from_dict(cls, d):
        t = cls(d["other_id"], d.get("kind"))
        t.messages = [dict(m) for m in d.get("messages", [])]
        t.unread = d.get("unread", 0)
        return t


class ConversationStore:
    def __init__(self):
        self._threads = {}  # owner -> {other -> Thread}

    def _thread(self, owner, other, kind=None):
        owned = self._threads.setdefault(owner, {})
        t = owned.get(other)
        if t is None:
            t = Thread(other, kind)
            owned[other] = t
        elif kind is not None:
            t.kind = kind
        return t

    def record(self, owner, other, msg, *, unread_delta=1, kind=None):
        self._thread(owner, other, kind).append(msg, unread_delta)

    def read(self, owner, other, k=10):
        t = self._threads.get(owner, {}).get(other)
        if t is None:
            return []
        out = t.recent(k)
        t.mark_read()
        return out

    def roster(self, owner, colocated_ids, agents):
        owned = self._threads.get(owner, {})
        rows = {}
        for other, t in owned.items():
            a = agents.get(other)
            rows[other] = {
                "other": other,
                "kind": t.kind or (getattr(a, "kind", None) if a else None),
                "colocated": other in colocated_ids,
                "unread": t.unread,
                "last_preview": (t.messages[-1]["content"][:40] if t.messages else ""),
            }
        for other in colocated_ids:
            if other == owner or other in rows:
                continue
            a = agents.get(other)
            rows[other] = {"other": other, "kind": getattr(a, "kind", None) if a else None,
                           "colocated": True, "unread": 0, "last_preview": ""}
        return sorted(rows.values(), key=lambda r: (-r["unread"], r["other"]))

    def export(self):
        return {o: {k: t.to_dict() for k, t in threads.items()}
                for o, threads in self._threads.items()}

    def restore(self, data):
        self._threads = {o: {k: Thread.from_dict(td) for k, td in threads.items()}
                         for o, threads in (data or {}).items()}
