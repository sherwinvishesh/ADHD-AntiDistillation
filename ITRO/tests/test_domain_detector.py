from conftest import StubProvider
from domain_detector import (
    detect_domain,
    get_domain_label,
    _hard_rule_detect,
    _normalize_category,
)


# ── Hard rule: code ──────────────────────────────────────────

def test_hard_rule_code_from_response_fence():
    response = "```python\ndef add(a, b):\n    return a + b\n```"
    assert _hard_rule_detect("How do I write a function?", response) == "code"


def test_detect_domain_code_needs_no_provider():
    response = "```python\ndef add(a, b):\n    return a + b\n```"
    assert detect_domain("write a function", response, provider=None) == "code"


# ── Hard rule: math via unicode symbols ──────────────────────

def test_hard_rule_math_computation_via_symbol():
    assert _hard_rule_detect("Compute ∫ x dx from 0 to 1", "") == "math_computation"


def test_hard_rule_math_proof_via_symbol_plus_proof_language():
    query = "Prove that ∫ x dx converges for this interval"
    assert _hard_rule_detect(query, "") == "math_proof"


def test_hard_rule_math_proof_via_language_only():
    query = "Prove that by induction this theorem holds, formally derive it"
    assert _hard_rule_detect(query, "") == "math_proof"


# ── Ambiguous cases defer to the LLM ──────────────────────────

def test_hard_rule_returns_none_for_ambiguous_query():
    assert _hard_rule_detect("Why does convection occur in fluids?", "") is None


def test_detect_domain_falls_back_to_factual_recall_with_no_provider():
    result = detect_domain("Why does convection occur in fluids?", "", provider=None)
    assert result == "factual_recall"


# ── LLM classification path ───────────────────────────────────

def test_detect_domain_uses_llm_when_hard_rule_unsure():
    stub = StubProvider("scientific")
    result = detect_domain(
        "Why does convection occur in fluids?", "", provider=stub
    )
    assert result == "scientific"
    assert stub.call_count == 1


def test_detect_domain_normalizes_llm_alias_output():
    stub = StubProvider("Math.")
    result = detect_domain(
        "Why does convection occur in fluids?", "", provider=stub
    )
    assert result == "math_computation"


def test_detect_domain_falls_back_on_llm_exception(failing_provider):
    result = detect_domain(
        "Why does convection occur in fluids?", "", provider=failing_provider
    )
    assert result == "factual_recall"


# ── _normalize_category ───────────────────────────────────────

def test_normalize_category_exact():
    assert _normalize_category("code") == "code"


def test_normalize_category_alias():
    assert _normalize_category("logic") == "logical_argument"


def test_normalize_category_unrecognizable_defaults_to_factual_recall():
    assert _normalize_category("xyz_totally_unknown") == "factual_recall"


# ── Domain labels ─────────────────────────────────────────────

def test_get_domain_label_known():
    assert get_domain_label("math_proof") == "Math (Proof/Derivation)"


def test_get_domain_label_unknown_passthrough():
    assert get_domain_label("not_a_domain") == "not_a_domain"
