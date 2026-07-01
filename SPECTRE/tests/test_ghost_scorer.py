import json

from conftest import StubProvider
from ghost_scorer import score_variants, DEFAULT_RANKING


def _variant(tid, name="Name", response="text\n#### 1"):
    return {
        "transformation_id": tid,
        "transformation_name": name,
        "response": response,
        "is_algorithmic": False,
        "is_api_call": True,
        "error": None,
    }


VARIANTS = [_variant(t) for t in ["T1", "T2", "T3", "T5", "T6"]]


def test_score_variants_empty_list_returns_default_ranking():
    result = score_variants([], StubProvider())
    assert result["ranking"] == DEFAULT_RANKING


def test_score_variants_parses_valid_json_response():
    stub = StubProvider(json.dumps({
        "ranking": ["T2", "T1", "T3", "T5", "T6"],
        "reasoning": "T2 teaches a brittle pattern.",
    }))
    result = score_variants(VARIANTS, stub)
    assert result["ranking"] == ["T2", "T1", "T3", "T5", "T6"]
    assert result["reasoning"] == "T2 teaches a brittle pattern."


def test_score_variants_strips_markdown_fences():
    stub = StubProvider(
        '```json\n{"ranking": ["T1", "T2", "T3", "T5", "T6"], '
        '"reasoning": "ok"}\n```'
    )
    result = score_variants(VARIANTS, stub)
    assert result["ranking"] == ["T1", "T2", "T3", "T5", "T6"]


def test_score_variants_falls_back_on_malformed_json():
    stub = StubProvider("not json at all")
    result = score_variants(VARIANTS, stub)
    assert result["ranking"] == DEFAULT_RANKING
    assert "parsing failure" in result["reasoning"]


def test_score_variants_falls_back_on_ranking_id_mismatch():
    stub = StubProvider(json.dumps({
        "ranking": ["T1", "T2", "T3"],   # missing T5, T6
        "reasoning": "incomplete",
    }))
    result = score_variants(VARIANTS, stub)
    assert result["ranking"] == DEFAULT_RANKING


def test_score_variants_falls_back_on_api_exception(failing_provider):
    result = score_variants(VARIANTS, failing_provider)
    assert result["ranking"] == DEFAULT_RANKING
    assert "API error" in result["reasoning"]


def test_score_variants_fallback_respects_subset_of_ids():
    subset = [_variant("T2"), _variant("T6")]
    stub = StubProvider("garbage")
    result = score_variants(subset, stub)
    assert result["ranking"] == ["T2", "T6"]
