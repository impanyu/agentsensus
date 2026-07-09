from society.actions import Action
from society.brains.base import Brain


class RuleBrain(Brain):
    """A brain driven by plain Python callables instead of an LLM.

    Used for scenario scripting, tests, and as the default brain for
    `environment` agents (which mostly just react to observe/act_on rather
    than take their own turn).
    """

    def __init__(self, fn=None, act_on_fn=None):
        """
        Args:
            fn: Optional callable(view: dict) -> Action used by decide().
                If omitted, decide() always returns Action("wait").
            act_on_fn: Optional callable(actor_id, description, view) -> str
                used by handle_act_on(). If omitted, a default Chinese
                description string is produced.
        """
        self._fn = fn
        self._act_on_fn = act_on_fn

    async def decide(self, view: dict) -> Action:
        """Return fn(view) if configured, otherwise Action("wait")."""
        if self._fn is not None:
            return self._fn(view)
        return Action("wait")

    def handle_act_on(self, actor_id: str, description: str, view: dict) -> str:
        """Handle the passive act_on interface (called by the kernel when
        another agent targets this agent with an `act_on` action).

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
