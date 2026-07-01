import pytest

from conftest import StubProvider
from tau_system import (
    compute_tau,
    get_tau_label,
    _fast_estimate,
    _parse_scores,
    _llm_score,
    DOMAIN_BOUNDS,
)


# ── _fast_estimate ─────────────────────────────────────────────

def test_fast_estimate_trivial_signal_hits_domain_floor():
    tau = _fast_estimate("What is the capital of France?", "factual_recall")
    floor, _ = DOMAIN_BOUNDS["factual_recall"]
    assert tau == max(0.08, floor)


def test_fast_estimate_maximal_signal_hits_domain_ceiling():
    tau = _fast_estimate("Evaluate ∫ x^2 dx", "math_computation")
    _, ceiling = DOMAIN_BOUNDS["math_computation"]
    assert tau == min(0.92, ceiling)


def test_fast_estimate_short_factual_query():
    assert _fast_estimate("Tallest mountain today", "factual_recall") == 0.08


def test_fast_estimate_ambiguous_returns_none():
    query = "Explain the causes of World War 1 in detail"
    assert _fast_estimate(query, "scientific") is None


# ── compute_tau: domain clipping + weighted combination ───────

def test_compute_tau_clips_to_domain_ceiling():
    stub = StubProvider(
        '{"reasoning_depth": 1.0, "generalizability": 1.0, '
        '"expert_density": 1.0, "frontier_dependency": 1.0}'
    )
    query = "Describe the government structure of ancient Rome in detail"
    tau = compute_tau(query, domain="factual_recall", provider=stub)
    _, ceiling = DOMAIN_BOUNDS["factual_recall"]
    assert tau == pytest.approx(ceiling)


def test_compute_tau_weighted_combination_arithmetic():
    stub = StubProvider(
        '{"reasoning_depth": 0.4, "generalizability": 0.6, '
        '"expert_density": 0.2, "frontier_dependency": 0.8}'
    )
    query = "Describe the government structure of ancient Rome in detail"
    tau = compute_tau(query, domain="code", provider=stub)
    expected = 0.35 * 0.4 + 0.30 * 0.6 + 0.20 * 0.2 + 0.15 * 0.8
    assert tau == pytest.approx(expected)


def test_compute_tau_no_provider_falls_back_to_domain_midpoint():
    query = "Consider the following argument and evaluate its structure in depth"
    tau = compute_tau(query, domain="logical_argument", provider=None)
    floor, ceiling = DOMAIN_BOUNDS["logical_argument"]
    assert tau == pytest.approx((floor + ceiling) / 2.0)


def test_compute_tau_never_raises_on_llm_failure(failing_provider):
    query = "Describe the government structure of ancient Rome in detail"
    tau = compute_tau(query, domain="analytical", provider=failing_provider)
    floor, ceiling = DOMAIN_BOUNDS["analytical"]
    assert tau == pytest.approx((floor + ceiling) / 2.0)


# ── _llm_score retry loop ──────────────────────────────────────

def test_llm_score_retries_on_malformed_json():
    stub = StubProvider([
        "not valid json at all",
        '{"reasoning_depth": 0.5, "generalizability": 0.5, '
        '"expert_density": 0.5, "frontier_dependency": 0.5}',
    ])
    scores = _llm_score("some query", "analytical", stub)
    assert scores is not None
    assert scores["reasoning_depth"] == 0.5
    assert stub.call_count == 2


def test_llm_score_gives_up_after_max_retries():
    stub = StubProvider(["garbage", "garbage", "garbage"])
    scores = _llm_score("some query", "analytical", stub, max_retries=3)
    assert scores is None
    assert stub.call_count == 3


# ── _parse_scores ───────────────────────────────────────────────

def test_parse_scores_strips_markdown_fences():
    raw = (
        "```json\n"
        '{"reasoning_depth": 0.3, "generalizability": 0.4, '
        '"expert_density": 0.2, "frontier_dependency": 0.6}\n'
        "```"
    )
    scores = _parse_scores(raw)
    assert scores["reasoning_depth"] == 0.3
    assert scores["frontier_dependency"] == 0.6


def test_parse_scores_regex_fallback_on_invalid_json():
    raw = (
        'Sure, here you go: "reasoning_depth": 0.3, "generalizability": 0.4, '
        '"expert_density": 0.2, "frontier_dependency": 0.6 — hope that helps!'
    )
    scores = _parse_scores(raw)
    assert scores is not None
    assert scores["reasoning_depth"] == 0.3
    assert scores["expert_density"] == 0.2


def test_parse_scores_returns_none_when_unparseable():
    assert _parse_scores("completely unrelated text with no scores") is None


# ── get_tau_label boundaries ────────────────────────────────────

@pytest.mark.parametrize("tau,label", [
    (0.0,  "minimal"),
    (0.19, "minimal"),
    (0.20, "mild"),
    (0.39, "mild"),
    (0.40, "moderate"),
    (0.59, "moderate"),
    (0.60, "heavy"),
    (0.79, "heavy"),
    (0.80, "maximum"),
    (1.0,  "maximum"),
])
def test_get_tau_label_boundaries(tau, label):
    assert get_tau_label(tau) == label
