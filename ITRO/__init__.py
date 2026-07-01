"""
ITRO — Inference-Time Reasoning Obfuscator.

Public API for use as an imported package (e.g. from ITRO_Test):

    import sys, os
    sys.path.insert(0, "<repo root>")
    import ITRO

    provider = ITRO.get_provider("claude")   # or "1", "gemini", "qwen", ...
    provider.check_api_key()
    result = ITRO.run_pipeline("What is 2+2?", provider, mode="clean")

Internally, every module in this package (config.py, providers/, etc.) uses
flat absolute imports (e.g. `from config import ...`) because that's how the
original ITRO_API/ITRO_Local pipelines were written, and porting them
unchanged was lower-risk than rewriting every import statement. Those
imports only resolve if this package's own directory is on sys.path — which
happens automatically when you `cd ITRO && python main.py` (Python adds a
script's own directory to sys.path[0]), but NOT when a sibling package like
ITRO_Test does `import ITRO`. So we do it explicitly here, before importing
any submodule, making both usage styles work identically.
"""

import os
import sys

_ITRO_DIR = os.path.dirname(os.path.abspath(__file__))
if _ITRO_DIR not in sys.path:
    sys.path.insert(0, _ITRO_DIR)

from providers import AVAILABLE_PROVIDERS, PROVIDER_MENU, resolve_provider_key
from pipeline import run_pipeline
import config


def list_providers():
    """Return the ordered (key, label) provider menu."""
    return PROVIDER_MENU


def get_provider(key_or_name):
    """
    Instantiate a provider by numeric key ("1") or friendly name/alias
    ("claude", "gemini", "qwen", "local", ...).

    Raises ValueError if the key/name doesn't resolve to a known provider.
    """
    key = resolve_provider_key(key_or_name)
    if key is None or key not in AVAILABLE_PROVIDERS:
        raise ValueError(
            f"Unknown provider '{key_or_name}'. "
            f"Valid options: {[k for k, _ in PROVIDER_MENU]} "
            f"or their names (claude, gemini, qwen, local, ...)."
        )
    return AVAILABLE_PROVIDERS[key]()


def resolve_default_provider():
    """
    Resolve config.ITRO_DEFAULT_PROVIDER to a valid AVAILABLE_PROVIDERS key,
    or None if unset/unrecognized.
    """
    return resolve_provider_key(config.ITRO_DEFAULT_PROVIDER)


__all__ = [
    "run_pipeline",
    "list_providers",
    "get_provider",
    "resolve_default_provider",
    "AVAILABLE_PROVIDERS",
    "PROVIDER_MENU",
    "config",
]
