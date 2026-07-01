from providers.anthropic_provider import AnthropicProvider
from providers.gemini_provider    import GeminiProvider
from providers.qwen_provider      import QwenProvider

# Numeric-keyed registry — drives the interactive menu, same UX as before.
AVAILABLE_PROVIDERS = {
    "1": AnthropicProvider,
    "2": GeminiProvider,
    "3": QwenProvider,
}

# Ordered menu — (key, display label)
PROVIDER_MENU = [
    ("1", "Anthropic (Claude)"),
    ("2", "Gemini"),
    ("3", "Qwen (Local)"),
]

# Friendly name/alias -> numeric key, so ITRO_DEFAULT_PROVIDER can be set
# as a readable string instead of a menu number.
_ALIASES = {
    "anthropic": "1", "claude": "1",
    "gemini":    "2",
    "qwen":      "3", "local": "3", "qwen-local": "3",
    "1": "1", "2": "2", "3": "3",
}


def resolve_provider_key(value):
    """Return a valid AVAILABLE_PROVIDERS key for a name/alias, or None."""
    if not value:
        return None
    return _ALIASES.get(str(value).strip().lower())
