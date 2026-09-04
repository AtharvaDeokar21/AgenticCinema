from abc import ABC, abstractmethod
from typing import Any


class BaseAgent(ABC):
    """Base interface for all Agentic Cinema agents."""

    name: str

    @abstractmethod
    async def run(self, input_data: Any) -> Any:
        """Execute the agent workflow."""
        raise NotImplementedError