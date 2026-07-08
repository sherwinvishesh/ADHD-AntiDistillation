import importlib

import config
from providers import resolve_provider_key


def test_default_provider_unset(monkeypatch):
    monkeypatch.delenv("SPECTRE_DEFAULT_PROVIDER", raising=False)
    reloaded = importlib.reload(config)
    assert reloaded.SPECTRE_DEFAULT_PROVIDER is None


def test_default_provider_blank_normalizes_to_none(monkeypatch):
    monkeypatch.setenv("SPECTRE_DEFAULT_PROVIDER", "   ")
    reloaded = importlib.reload(config)
    assert reloaded.SPECTRE_DEFAULT_PROVIDER is None


def test_default_provider_set(monkeypatch):
    monkeypatch.setenv("SPECTRE_DEFAULT_PROVIDER", "claude")
    reloaded = importlib.reload(config)
    assert reloaded.SPECTRE_DEFAULT_PROVIDER == "claude"
    monkeypatch.delenv("SPECTRE_DEFAULT_PROVIDER", raising=False)
    importlib.reload(config)


def test_resolve_default_provider_valid(monkeypatch):
    monkeypatch.setattr(config, "SPECTRE_DEFAULT_PROVIDER", "gemini")
    assert resolve_provider_key(config.SPECTRE_DEFAULT_PROVIDER) == "2"


def test_resolve_default_provider_invalid(monkeypatch):
    monkeypatch.setattr(config, "SPECTRE_DEFAULT_PROVIDER", "not-a-real-provider")
    assert resolve_provider_key(config.SPECTRE_DEFAULT_PROVIDER) is None


def test_resolve_default_provider_case_insensitive(monkeypatch):
    monkeypatch.setattr(config, "SPECTRE_DEFAULT_PROVIDER", "CLAUDE")
    assert resolve_provider_key(config.SPECTRE_DEFAULT_PROVIDER) == "1"


def test_resolve_default_provider_unset_is_none(monkeypatch):
    monkeypatch.setattr(config, "SPECTRE_DEFAULT_PROVIDER", None)
    assert resolve_provider_key(config.SPECTRE_DEFAULT_PROVIDER) is None


def test_strategy_defaults_to_composite(monkeypatch):
    monkeypatch.delenv("SPECTRE_STRATEGY", raising=False)
    reloaded = importlib.reload(config)
    assert reloaded.SPECTRE_STRATEGY == "composite"


def test_strategy_env_override(monkeypatch):
    monkeypatch.setenv("SPECTRE_STRATEGY", "  Ensemble ")
    reloaded = importlib.reload(config)
    assert reloaded.SPECTRE_STRATEGY == "ensemble"
    monkeypatch.delenv("SPECTRE_STRATEGY", raising=False)
    importlib.reload(config)


def test_poison_verification_knobs_exist():
    assert config.COMPOSITE_MAX_TOKENS > 0
    assert config.MAX_RESPONSE_CHARS > 0
    assert 0.0 < config.EARLY_LEAK_FRACTION < 1.0


def test_transformation_labels_match_registry():
    import transformations
    assert config.TRANSFORMATION_LABELS == transformations.TRANSFORMATION_LABELS
    assert "T7" in config.TRANSFORMATION_LABELS
