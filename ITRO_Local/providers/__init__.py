# providers/__init__.py

from providers.qwen_provider import QwenProvider

AVAILABLE_PROVIDERS = {
    "1": QwenProvider,
}

PROVIDER_MENU = [
    ("1", "Qwen (Local)"),
]