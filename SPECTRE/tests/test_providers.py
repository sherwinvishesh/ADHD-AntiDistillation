from providers import AVAILABLE_PROVIDERS, PROVIDER_MENU, resolve_provider_key, get_provider


def test_registry_has_exactly_two_providers():
    assert set(AVAILABLE_PROVIDERS.keys()) == {"1", "2"}


def test_provider_menu_matches_registry_keys():
    assert {k for k, _ in PROVIDER_MENU} == set(AVAILABLE_PROVIDERS.keys())


def test_resolve_provider_key_aliases():
    assert resolve_provider_key("claude") == "1"
    assert resolve_provider_key("anthropic") == "1"
    assert resolve_provider_key("gemini") == "2"


def test_resolve_provider_key_numeric_passthrough():
    assert resolve_provider_key("1") == "1"
    assert resolve_provider_key("2") == "2"


def test_resolve_provider_key_case_insensitive():
    assert resolve_provider_key("CLAUDE") == "1"
    assert resolve_provider_key("  Gemini  ") == "2"


def test_resolve_provider_key_unknown_returns_none():
    assert resolve_provider_key("not-a-real-provider") is None
    assert resolve_provider_key("") is None
    assert resolve_provider_key(None) is None


def test_get_provider_instantiates_correct_class():
    assert get_provider("claude").name.startswith("Anthropic")
    assert get_provider("gemini").name.startswith("Google Gemini")


def test_get_provider_raises_on_bad_input():
    try:
        get_provider("not-a-real-provider")
        assert False, "expected ValueError"
    except ValueError:
        pass
