"""
Provider registry and factory.
"""

from .base_provider import BaseProvider
from .anthropic_provider import AnthropicProvider
from .gemini_provider import GeminiProvider

# Numeric-keyed registry — drives the interactive menu, same UX as ITRO.
AVAILABLE_PROVIDERS = {
    "1": AnthropicProvider,
    "2": GeminiProvider,
}

# Ordered menu — (key, display label)
PROVIDER_MENU = [
    ("1", "Anthropic Claude"),
    ("2", "Google Gemini"),
]

# Friendly name/alias -> numeric key, so SPECTRE_DEFAULT_PROVIDER can be set
# as a readable string instead of a menu number.
_ALIASES = {
    "anthropic": "1", "claude": "1",
    "gemini":    "2",
    "1": "1", "2": "2",
}


def resolve_provider_key(value):
    """Return a valid AVAILABLE_PROVIDERS key for a name/alias, or None."""
    if not value:
        return None
    return _ALIASES.get(str(value).strip().lower())


def get_provider(key_or_name: str) -> BaseProvider:
    """
    Instantiate a provider by numeric key ("1") or friendly name/alias
    ("anthropic", "claude", "gemini").

    Raises:
        ValueError: If the key/name doesn't resolve to a known provider.
    """
    key = resolve_provider_key(key_or_name)
    if key is None or key not in AVAILABLE_PROVIDERS:
        raise ValueError(
            f"Unknown provider '{key_or_name}'. "
            f"Valid options: {[k for k, _ in PROVIDER_MENU]} "
            f"or their names (anthropic, claude, gemini)."
        )
    return AVAILABLE_PROVIDERS[key]()


__all__ = [
    "BaseProvider", "AnthropicProvider", "GeminiProvider",
    "AVAILABLE_PROVIDERS", "PROVIDER_MENU", "resolve_provider_key", "get_provider",
]
