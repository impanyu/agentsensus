from abc import ABC, abstractmethod

from society.actions import Action


class Brain(ABC):
    """Abstract decision-making strategy for an agent.

    A Brain observes the agent's current STM view and decides the single
    next Action to take. Concrete brains range from simple rule-based
    callables (RuleBrain), through non-LLM keyword retrieval (RetrievalBrain
    for info_carrier agents), to full LLM-driven reasoning (LLMBrain for
    character agents).
    """

    @abstractmethod
    async def decide(self, view: dict) -> Action:
        """Decide the next action given the agent's current STM view.

        Args:
            view: Serialized STM view (FIFO history, goal stack, status
                register, inbox depth/preview, current tick).

        Returns:
            The Action the agent should take this tick.
        """
        raise NotImplementedError
