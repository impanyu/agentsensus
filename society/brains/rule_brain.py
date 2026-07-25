from society.actions import Action
from society.brains.base import Brain


class RuleBrain(Brain):
    """A brain driven by plain Python callables instead of an LLM.

    Used for scenario scripting and tests. Environment agents in the sim
    path get an LLMBrain by default (Task S2, unified-agent architecture);
    RuleBrain is kept for direct construction convenience (e.g. a scripted
    environment brain in tests) rather than being the kernel's default.
    """

    def __init__(self, fn=None, act_on_fn=None):
        """
        Args:
            fn: Optional callable(view: dict) -> Action used by decide().
                If omitted, decide() always returns Action("wait").
            act_on_fn: Optional callable(actor_id, description, view) -> str.
                Not called by the kernel (see `handle_act_on` below) --
                kept only so callers constructing a RuleBrain directly
                (e.g. tests) can still invoke `handle_act_on` themselves.
        """
        self._fn = fn
        self._act_on_fn = act_on_fn

    async def decide(self, view: dict) -> Action:
        """Return fn(view) if configured, otherwise Action("wait")."""
        if self._fn is not None:
            return self._fn(view)
        return Action("wait")

    def handle_act_on(self, actor_id: str, description: str, view: dict) -> str:
        """Passive act_on handler -- kept for direct-construction
        convenience only. The kernel no longer calls this (Task S2,
        unified-agent architecture): `act_on` now always queues a Message
        into the target's own inbox, handled on its next `decide()` tick,
        exactly like `say`/`gesture` (see Kernel._execute_act_on).

        Args:
            actor_id: id of the agent performing the act_on.
            description: free-text description of what they did.
            view: this agent's current STM view (for act_on_fn to inspect).

        Returns:
            A result string describing the outcome of the act_on.
        """
        if self._act_on_fn is not None:
            return self._act_on_fn(actor_id, description, view)
        return f"{actor_id} 对环境做了: {description}"
