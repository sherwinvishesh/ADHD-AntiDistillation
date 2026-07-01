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
