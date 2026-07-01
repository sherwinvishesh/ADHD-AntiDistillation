from conftest import StubProvider
from correctness_checker import (
    check_correctness,
    _normalize_number,
    _llm_semantic_match,
)


# ── _normalize_number ────────────────────────────────────────

def test_normalize_number_strips_commas():
    assert _normalize_number("1,000") == "1000"


def test_normalize_number_strips_trailing_zeros():
    assert _normalize_number("4.00") == "4"


def test_normalize_number_keeps_meaningful_decimals():
    assert _normalize_number("3.14") == "3.14"


def test_normalize_number_strips_whitespace():
    assert _normalize_number(" 5 ") == "5"


def test_normalize_number_non_numeric_lowercased_passthrough():
    assert _normalize_number("ABC") == "abc"


# ── math_computation: exact numeric match ─────────────────────

def test_check_correctness_math_exact_match_passes():
    stub = StubProvider(["42", "42"])
    is_correct, orig, obfu = check_correctness(
        "The answer is 42.", "After some detours, 42.", "math_computation", stub
    )
    assert is_correct is True
    assert orig == "42" and obfu == "42"


def test_check_correctness_math_mismatch_fails():
    stub = StubProvider(["42", "43"])
    is_correct, orig, obfu = check_correctness(
        "The answer is 42.", "After some detours, 43.", "math_computation", stub
    )
    assert is_correct is False


def test_check_correctness_math_normalizes_before_comparing():
    stub = StubProvider(["4", "4.00"])
    is_correct, _, _ = check_correctness(
        "The answer is 4.", "The answer is 4.00.", "math_computation", stub
    )
    assert is_correct is True


# ── non-math domains: LLM semantic match ──────────────────────

def test_check_correctness_semantic_match_pass():
    stub = StubProvider([
        "Shakespeare wrote Hamlet",
        "Hamlet was written by Shakespeare",
        "YES",
    ])
    is_correct, orig, obfu = check_correctness(
        "Shakespeare wrote Hamlet.",
        "Hamlet was authored by William Shakespeare.",
        "factual_recall",
        stub,
    )
    assert is_correct is True
    assert orig == "Shakespeare wrote Hamlet"
    assert obfu == "Hamlet was written by Shakespeare"


def test_check_correctness_semantic_match_fail():
    stub = StubProvider([
        "Shakespeare wrote Hamlet",
        "Marlowe wrote Hamlet",
        "NO",
    ])
    is_correct, _, _ = check_correctness(
        "Shakespeare wrote Hamlet.",
        "Marlowe wrote Hamlet.",
        "factual_recall",
        stub,
    )
    assert is_correct is False


# ── extraction failure triggers the safety valve ──────────────

def test_check_correctness_extraction_failure_triggers_safety_valve(failing_provider):
    is_correct, orig, obfu = check_correctness(
        "some real response", "some obfuscated response",
        "factual_recall", failing_provider,
    )
    assert is_correct is False
    assert "extraction_failed" in orig


# ── semantic match fails open on exception ────────────────────

def test_llm_semantic_match_fails_open_on_exception(failing_provider):
    assert _llm_semantic_match("a", "b", failing_provider) is True


# ── check_correctness never raises ────────────────────────────

def test_check_correctness_never_raises_with_broken_provider():
    is_correct, orig, obfu = check_correctness(
        "real", "obfuscated", "factual_recall", None
    )
    assert is_correct is False
