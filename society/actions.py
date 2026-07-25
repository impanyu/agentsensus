from dataclasses import dataclass, field


@dataclass
class Action:
    """Represents an action that an agent can take."""
    name: str
    params: dict = field(default_factory=dict)


@dataclass
class ActionResult:
    """Result of executing an action."""
    ok: bool
    data: object = None
    error: str | None = None

    def to_dict(self) -> dict:
        """Convert ActionResult to dictionary."""
        return {
            "ok": self.ok,
            "data": self.data,
            "error": self.error
        }


@dataclass
class Message:
    """Message sent between agents.

    `wake` controls whether this message, by itself, is allowed to make a
    sleeping recipient eligible (Kernel.is_eligible) and to clear a
    recipient's `waiting_until` on delivery (Kernel.deliver_pending).
    Defaults to True so say/gesture/system/arrival messages behave exactly
    as before wake was introduced. `broadcast` is the only action that
    lets the sender set this to False.
    """
    id: str
    sender: str
    recipients: list
    kind: str
    content: str
    tick_sent: int
    correlation_id: str | None = None
    wake: bool = True

    def to_dict(self) -> dict:
        """Convert Message to dictionary."""
        return {
            "id": self.id,
            "sender": self.sender,
            "recipients": self.recipients,
            "kind": self.kind,
            "content": self.content,
            "tick_sent": self.tick_sent,
            "correlation_id": self.correlation_id,
            "wake": self.wake
        }


# Synchronous actions (complete in same tick)
SYNC_ACTIONS: set[str] = {
    "pop_message",
    "peek_inbox",
    "think",
    "conclude",
    "push_goal",
    "pop_goal",
    "replace_goal",
    "update_status",
    "remove_status",
    "remember",
    "recall",
    "forget",
    "revise_memory",
    "observe",
    "move",
    "wait",
    "noop",
    "add_affiliated",
    "remove_affiliated",
    "set_affiliated",
    "get_affiliated"
}

# Asynchronous actions (may take multiple ticks)
ASYNC_ACTIONS: set[str] = {
    "say",
    "gesture",
    "act_on",
    "broadcast",
    # Task S2 (unified-agent architecture): `read` no longer synchronously
    # calls brain.retrieve() -- it queues a Message into the target
    # info_carrier's own inbox (Kernel._execute_read), answered on the
    # carrier's own next tick, exactly like say/gesture/act_on.
    "read"
}

# Required parameters for each action
REQUIRED_PARAMS: dict[str, list[str]] = {
    "pop_message": [],
    "peek_inbox": [],
    "think": ["question"],
    "conclude": ["text"],
    "push_goal": ["text"],
    "pop_goal": [],
    "replace_goal": ["text"],
    "update_status": ["key", "value"],
    "remove_status": ["key"],
    "remember": ["text"],
    "recall": ["query"],
    "forget": ["memory_id"],
    "revise_memory": ["memory_id", "new_text"],
    "observe": ["target"],
    "read": ["target", "query"],
    "move": ["destination"],
    "wait": [],
    "noop": [],
    # {targets, content} is the uniform shape for every message-like
    # action (say/gesture/broadcast/act_on): exactly the same two keys,
    # no special cases. act_on's `targets` must contain exactly one
    # co-located environment id (enforced by the kernel, not here).
    "say": ["targets", "content"],
    "gesture": ["targets", "content"],
    "act_on": ["targets", "content"],
    "broadcast": ["targets", "content"],
    "add_affiliated": ["memory_id", "affiliated"],
    "remove_affiliated": ["memory_id", "affiliated"],
    "set_affiliated": ["memory_id", "affiliated"],
    "get_affiliated": ["memory_id"]
}


def validate_action(action: Action) -> str | None:
    """Validate an action.

    Returns None if valid, otherwise returns an error string.
    Validates:
    - Action name exists
    - All required parameters are present
    - targets parameter is a list (if present)
    - update_status doesn't use reserved key "location"
    """
    # Check if action name is known
    all_actions = SYNC_ACTIONS | ASYNC_ACTIONS
    if action.name not in all_actions:
        return f"Unknown action: {action.name}"

    # Check required parameters
    required = REQUIRED_PARAMS.get(action.name, [])
    for param in required:
        if param not in action.params:
            return f"Missing required parameter '{param}' for action '{action.name}'"

    # Special validation for targets parameter
    if "targets" in action.params:
        if not isinstance(action.params["targets"], list):
            return f"Parameter 'targets' must be a list for action '{action.name}'"

    # Special validation for update_status
    if action.name == "update_status" and action.params.get("key") == "location":
        return "Cannot use 'location' as a key in update_status (reserved)"

    return None


def parse_action(obj: dict) -> Action:
    """Parse a dictionary to an Action object.

    Expected format: {"action": name, "params": {...}}

    Raises ValueError if:
    - "action" key is missing
    - Action validation fails
    """
    if "action" not in obj:
        raise ValueError("Missing 'action' key in action dict")

    action_name = obj["action"]
    params = obj.get("params", {})

    action = Action(name=action_name, params=params)

    # Validate the action
    error = validate_action(action)
    if error:
        raise ValueError(error)

    return action
