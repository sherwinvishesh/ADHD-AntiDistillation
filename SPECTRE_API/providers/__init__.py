"""
Provider registry and factory.
"""

from .base_provider import BaseProvider
from .anthropic_provider import AnthropicProvider


def get_provider(provider_name: str) -> BaseProvider:
    """
    Instantiate and return a provider by name.

    Args:
        provider_name: "anthropic" or "gemini" (case-insensitive).

    Returns:
        An initialised BaseProvider instance.

    Raises:
        ValueError: If the provider name is unknown.
    """
    name = provider_name.lower()
    if name == "anthropic":
        return AnthropicProvider()
    elif name == "gemini":
        from .gemini_provider import GeminiProvider
        return GeminiProvider()
    else:
        raise ValueError(
            f"Unknown provider '{provider_name}'. Valid options: anthropic, gemini"
        )


__all__ = ["BaseProvider", "AnthropicProvider", "get_provider"]