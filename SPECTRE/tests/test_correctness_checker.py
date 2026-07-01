from conftest import StubProvider
from correctness_checker import extract_answer, check_correctness, _api_check


# ── extract_answer ──────────────────────────────────────────────

def test_extract_answer_simple_integer():
    assert extract_answer("Some reasoning.\n#### 72") == "72"


def test_extract_answer_strips_commas():
    assert extract_answer("#### 1,000") == "1000"


def test_extract_answer_normalizes_trailing_decimal_zeros():
    assert extract_answer("#### 4.00") == "4"


def test_extract_answer_keeps_meaningful_decimals():
    assert extract_answer("#### 3.14") == "3.14"


def test_extract_answer_missing_line_returns_none():
    assert extract_answer("No answer line here.") is None


def test_extract_answer_tolerates_surrounding_whitespace():
    assert extract_answer("#### 72   \n") == "72"


# ── check_correctness: math_computation exact match ─────────────

def test_check_correctness_math_match_passes():
    ref = "Step 1...\n#### 72"
    var = "Different derivation...\n#### 72"
    assert check_correctness("q", var, ref, provider=None) is True


def test_check_correctness_math_mismatch_fails():
    ref = "Step 1...\n#### 72"
    var = "Different derivation...\n#### 71"
    assert check_correctness("q", var, ref, provider=None) is False


# ── check_correctness: fallback to API when extraction fails ────

def test_check_correctness_falls_back_to_api_when_extraction_fails():
    stub = StubProvider("YES")
    ref = "Step 1...\n#### 72"
    var = "No answer line in this one at all."
    assert check_correctness("q", var, ref, stub) is True
    assert stub.call_count == 1


def test_check_correctness_api_fallback_no_reply_fails():
    stub = StubProvider("NO")
    ref = "Step 1...\n#### 72"
    var = "No answer line in this one at all."
    assert check_correctness("q", var, ref, stub) is False


def test_check_correctness_api_fallback_fails_closed_on_exception(failing_provider):
    ref = "Step 1...\n#### 72"
    var = "No answer line in this one at all."
    assert check_correctness("q", var, ref, failing_provider) is False


# ── _api_check ────────────────────────────────────────────────────

def test_api_check_uses_generic_clause_when_expected_answer_missing():
    stub = StubProvider("YES")
    assert _api_check("q", "some response", None, stub) is True
    prompt = stub.calls[0][0]
    assert "any clearly correct numerical answer" in prompt


def test_api_check_embeds_expected_answer_in_prompt():
    stub = StubProvider("YES")
    _api_check("q", "some response", "72", stub)
    prompt = stub.calls[0][0]
    assert "the numerical answer 72" in prompt
