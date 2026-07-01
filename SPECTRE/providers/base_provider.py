"""
Abstract base class for all AI providers.
"""

from abc import ABC, abstractmethod


class BaseProvider(ABC):
    """Base interface every provider must implement."""

    @abstractmethod
    def check_api_key(self):
        """Validate the required env var is set, exit cleanly if missing."""

    @abstractmethod
    def complete(self, prompt: str, max_tokens: int = 1024, system: str = None) -> str:
        """
        Send a prompt to the model and return the text response.

        Args:
            prompt:     The user message / prompt text.
            max_tokens: Maximum tokens to generate.
            system:     Optional system prompt.

        Returns:
            The model's text response as a plain string.
        """

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable provider name for display."""