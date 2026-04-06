from providers.anthropic_provider import AnthropicProvider
from providers.gemini_provider    import GeminiProvider

AVAILABLE_PROVIDERS = {
    "1": AnthropicProvider,
    "2": GeminiProvider,
}

PROVIDER_MENU = [
    ("1", "Anthropic (Claude)"),
    ("2", "Gemini"),
]