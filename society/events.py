import json
from pathlib import Path


class EventLog:
    """Event log with global monotonic sequence and optional file persistence."""

    def __init__(self, path: str | None):
        """
        Initialize EventLog.

        Args:
            path: Path to JSONL file for persistence, or None for in-memory only.
        """
        self.path = path
        self._events = []
        self._seq_counter = 0

    def append(self, tick: int, kind: str, agent: str, payload: dict) -> int:
        """
        Append an event to the log.

        Args:
            tick: Tick number.
            kind: Event kind (action, message, system).
            agent: Agent name.
            payload: Additional event data.

        Returns:
            Global monotonic sequence number (0-based).
        """
        seq = self._seq_counter
        self._seq_counter += 1

        # Build event dict
        event = {
            "seq": seq,
            "tick": tick,
            "kind": kind,
            "agent": agent,
            **payload,
        }

        # Store in memory
        self._events.append(event)

        # Persist to file if path is set
        if self.path:
            with open(self.path, "a", encoding="utf-8") as f:
                json.dump(event, f, ensure_ascii=False)
                f.write("\n")

        return seq

    def all(self) -> list[dict]:
        """
        Get all events.

        Returns:
            List of event dicts, each with seq, tick, kind, agent, **payload.
        """
        return self._events

    @staticmethod
    def load(path: str) -> list[dict]:
        """
        Load events from a JSONL file.

        Args:
            path: Path to JSONL file.

        Returns:
            List of event dicts.
        """
        events = []
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    events.append(json.loads(line))
        return events
