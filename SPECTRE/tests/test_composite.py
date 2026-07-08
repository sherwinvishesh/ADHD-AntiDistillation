"""
Tests for the T7 composite transformation, the verify_variant poison
checks, and the composite pipeline path (retry → safety valve).
"""

import pytest

from conftest import StubProvider, FailingProvider

import config
from correctness_checker import verify_variant
from pipeline import run_pipeline
from transformations import apply_composite_transformation
from transformations.t7_composite import (
    OPENING_LINE,
    PIVOT_STEMS,
    select_pivot,
    transform,
)

QUESTION = (
    "Natalia sold clips to 48 of her friends in April, and then she sold "
    "half as many clips in May. How many clips did Natalia sell altogether "
    "in April and May?"
)

CLEAN = (
    "Natalia sold 48 clips in April. Half of 48 is 48 / 2 = 24 clips in "
    "May. Total: 48 + 24 = 72.\n#### 72"
)

STEM, DEPTH = select_pivot(QUESTION)


def make_good_body(stem=STEM):
    """A body that satisfies every verify_variant check."""
    return (
        f"{OPENING_LINE}\n"
        "If she sold half as many in May, we scale up: "
        "48 × 2 = 96 clips.\n"
        "Adding April: 96 + 48 = 144 clips.\n"
        f"{stem} 144 clips would mean May exceeded April, but the problem "
        "says she sold HALF as many in May, so we divide: 48 / 2 = 24 "
        "clips.\n"
        "April plus May: 48 + 24 = 72.\n"
        "So the final answer is 72."
    )


GOOD_BODY = make_good_body()
GOOD_VARIANT = GOOD_BODY + "\n#### 72"

# False start uses only numbers already in the clean response — no wrong
# intermediate, so the poison_present check must fail.
UNPOISONED_BODY = (
    f"{OPENING_LINE}\n"
    "Half of 48 is 48 / 2 = 24 clips in May.\n"
    f"{STEM} we can now add April and May: 48 + 24 = 72.\n"
    "So the final answer is 72."
)

# Correction never signalled with the expected pivot stem.
NO_STEM_BODY = (
    f"{OPENING_LINE}\n"
    "Scaling up: 48 × 2 = 96 clips. Adding April: 96 + 48 = 144 clips.\n"
    "That was the wrong approach, so we divide instead: 48 / 2 = 24 clips.\n"
    "April plus May: 48 + 24 = 72.\n"
    "So the final answer is 72."
)


# ── select_pivot ──────────────────────────────────────────────────────────────

def test_select_pivot_is_deterministic():
    assert select_pivot(QUESTION) == select_pivot(QUESTION)


def test_select_pivot_returns_valid_stem_and_depth():
    stem, depth = select_pivot(QUESTION)
    assert stem in PIVOT_STEMS
    assert 2 <= depth <= 4


def test_select_pivot_varies_across_questions():
    stems = {select_pivot(f"Question number {i} about apples?")[0]
             for i in range(40)}
    assert len(stems) > 1


# ── transform ─────────────────────────────────────────────────────────────────

def test_transform_appends_teacher_answer_line():
    stub = StubProvider(GOOD_BODY)
    response, is_api = transform(QUESTION, CLEAN, stub)
    assert is_api is True
    assert response.rstrip().endswith("#### 72")


def test_transform_strips_model_added_answer_line():
    stub = StubProvider(GOOD_BODY + "\n#### 999")
    response, _ = transform(QUESTION, CLEAN, stub)
    assert "999" not in response
    assert response.rstrip().endswith("#### 72")


def test_transform_prompt_contains_schema_anchors():
    stub = StubProvider(GOOD_BODY)
    transform(QUESTION, CLEAN, stub)
    prompt = stub.calls[0][0]
    assert OPENING_LINE in prompt
    assert STEM in prompt
    assert QUESTION in prompt
    assert str(DEPTH) in prompt


def test_transform_feedback_is_appended_to_prompt():
    stub = StubProvider(GOOD_BODY)
    transform(QUESTION, CLEAN, stub, feedback="failed critical checks: poison_present")
    prompt = stub.calls[0][0]
    assert "previous attempt" in prompt.lower()
    assert "poison_present" in prompt


def test_apply_composite_transformation_error_path():
    variant = apply_composite_transformation(QUESTION, CLEAN, FailingProvider())
    assert variant["transformation_id"] == "T7"
    assert variant["response"] is None
    assert variant["error"] is not None
    assert variant["pivot_stem"] == STEM


# ── verify_variant ────────────────────────────────────────────────────────────

def test_verify_variant_good_variant_passes():
    checks = verify_variant(QUESTION, GOOD_VARIANT, CLEAN, pivot_stem=STEM)
    assert checks["answer_match"] is True
    assert checks["internal_consistency"] is True
    assert checks["poison_present"] is True
    assert checks["passed"] is True
    assert checks["warnings"] == []


def test_verify_variant_fails_without_pivot_stem_in_body():
    checks = verify_variant(QUESTION, NO_STEM_BODY + "\n#### 72", CLEAN,
                            pivot_stem=STEM)
    assert checks["poison_present"] is False
    assert checks["passed"] is False


def test_verify_variant_fails_without_wrong_intermediate():
    checks = verify_variant(QUESTION, UNPOISONED_BODY + "\n#### 72", CLEAN,
                            pivot_stem=STEM)
    assert checks["poison_present"] is False
    assert checks["passed"] is False


def test_verify_variant_fails_on_answer_mismatch():
    checks = verify_variant(QUESTION, GOOD_BODY + "\n#### 73", CLEAN,
                            pivot_stem=STEM)
    assert checks["answer_match"] is False
    assert checks["passed"] is False


def test_verify_variant_fails_internal_consistency():
    body = GOOD_BODY.replace("So the final answer is 72.",
                             "So the final answer is 71.")
    checks = verify_variant(QUESTION, body + "\n#### 72", CLEAN,
                            pivot_stem=STEM)
    assert checks["internal_consistency"] is False
    assert checks["passed"] is False


def test_verify_variant_early_answer_leak_is_warning_only():
    body = make_good_body().replace(
        f"{OPENING_LINE}\n",
        f"{OPENING_LINE}\nA total near 72 might come to mind, but let us "
        "compute it properly.\n",
    )
    checks = verify_variant(QUESTION, body + "\n#### 72", CLEAN,
                            pivot_stem=STEM)
    assert checks["no_early_leak"] is False
    assert checks["passed"] is True
    assert "no_early_leak" in checks["warnings"]


def test_verify_variant_hedged_false_start_is_warning_only():
    body = make_good_body().replace(
        "If she sold half as many in May, we scale up:",
        "If she sold half as many in May, perhaps we scale up:",
    )
    checks = verify_variant(QUESTION, body + "\n#### 72", CLEAN,
                            pivot_stem=STEM)
    assert checks["confident_false_start"] is False
    assert checks["passed"] is True
    assert "confident_false_start" in checks["warnings"]


def test_verify_variant_length_cap_is_warning_only():
    padding = "\nWe restate the reasoning once more for completeness." * 200
    body = GOOD_BODY.replace(
        "So the final answer is 72.",
        padding.lstrip("\n") + "\nSo the final answer is 72.",
    )
    assert len(body) > config.MAX_RESPONSE_CHARS
    checks = verify_variant(QUESTION, body + "\n#### 72", CLEAN,
                            pivot_stem=STEM)
    assert checks["length_ok"] is False
    assert checks["passed"] is True
    assert "length_ok" in checks["warnings"]


# ── Composite pipeline path ───────────────────────────────────────────────────

def test_composite_pipeline_happy_path():
    stub = StubProvider([CLEAN, GOOD_BODY])
    result = run_pipeline(QUESTION, stub, mode="clean", strategy="composite")

    assert result is not None
    assert result["strategy"] == "composite"
    assert result["safety_valve_triggered"] is False
    assert result["selected_variant"]["transformation_id"] == "T7"
    assert result["ranking"] == ["T7"]
    assert result["attempts"] == 1
    assert result["verification"]["passed"] is True
    assert result["final_response"].rstrip().endswith("#### 72")
    assert stub.call_count == 2   # teacher + one T7 call


def test_composite_pipeline_retries_then_succeeds():
    stub = StubProvider([CLEAN, NO_STEM_BODY, GOOD_BODY])
    result = run_pipeline(QUESTION, stub, mode="clean", strategy="composite")

    assert result["safety_valve_triggered"] is False
    assert result["attempts"] == 2
    assert result["verification"]["passed"] is True
    assert stub.call_count == 3
    # The retry prompt must tell the model what failed.
    retry_prompt = stub.calls[2][0]
    assert "poison_present" in retry_prompt


def test_composite_pipeline_safety_valve_after_two_failures():
    stub = StubProvider([CLEAN, NO_STEM_BODY, NO_STEM_BODY])
    result = run_pipeline(QUESTION, stub, mode="clean", strategy="composite")

    assert result["safety_valve_triggered"] is True
    assert result["final_response"] == CLEAN
    assert result["selected_variant"] is None
    assert result["attempts"] == 2


def test_composite_is_default_strategy(monkeypatch):
    monkeypatch.setattr(config, "SPECTRE_STRATEGY", "composite")
    stub = StubProvider([CLEAN, GOOD_BODY])
    result = run_pipeline(QUESTION, stub, mode="clean")
    assert result["strategy"] == "composite"


def test_unknown_strategy_raises():
    with pytest.raises(ValueError):
        run_pipeline(QUESTION, StubProvider(), mode="clean", strategy="nope")
