import ast
import os

from providers import AVAILABLE_PROVIDERS, PROVIDER_MENU, resolve_provider_key


def test_registry_has_exactly_three_providers():
    assert set(AVAILABLE_PROVIDERS.keys()) == {"1", "2", "3"}


def test_provider_menu_matches_registry_keys():
    assert {k for k, _ in PROVIDER_MENU} == set(AVAILABLE_PROVIDERS.keys())


def test_resolve_provider_key_aliases():
    assert resolve_provider_key("claude") == "1"
    assert resolve_provider_key("anthropic") == "1"
    assert resolve_provider_key("gemini") == "2"
    assert resolve_provider_key("qwen") == "3"
    assert resolve_provider_key("local") == "3"
    assert resolve_provider_key("qwen-local") == "3"


def test_resolve_provider_key_numeric_passthrough():
    assert resolve_provider_key("1") == "1"
    assert resolve_provider_key("2") == "2"
    assert resolve_provider_key("3") == "3"


def test_resolve_provider_key_case_insensitive():
    assert resolve_provider_key("CLAUDE") == "1"
    assert resolve_provider_key("  Gemini  ") == "2"


def test_resolve_provider_key_unknown_returns_none():
    assert resolve_provider_key("not-a-real-provider") is None
    assert resolve_provider_key("") is None
    assert resolve_provider_key(None) is None


def test_qwen_provider_has_no_top_level_heavy_imports():
    """
    qwen_provider.py must lazy-import torch/transformers inside methods,
    not at module top level — otherwise every ITRO user (including cloud-
    only ones) would be forced to install the ~GB local-model stack.
    """
    qwen_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "providers", "qwen_provider.py",
    )
    with open(qwen_path) as f:
        tree = ast.parse(f.read(), filename=qwen_path)

    heavy = {"torch", "transformers"}
    top_level_imports = set()
    for node in tree.body:  # only top-level statements, not nested in functions
        if isinstance(node, ast.Import):
            top_level_imports.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            top_level_imports.add(node.module.split(".")[0])

    assert not (top_level_imports & heavy), (
        f"qwen_provider.py imports {top_level_imports & heavy} at module "
        f"top level — these must be lazy-imported inside methods instead."
    )
