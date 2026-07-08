"""
correctness_checker.py

Verifies that a transformed variant reaches the same final answer as the
clean teacher response.

Primary method: extract and compare the #### N lines numerically.
This works for all our transformations because every transformation
preserves the #### line unchanged.

Fallback: API call if the #### line cannot be extracted from either response.

verify_variant() goes further for the composite (T7) path: because the ####
line is appended programmatically from the teacher response, comparing ####
lines alone is a tautology — it can never fail, so it verifies nothing about
the corruption. ITRO Bug 1 showed exactly how a dataset can silently end up
clean while every check passes. verify_variant() therefore also confirms the
poison is actually present, the body is internally consistent with the
answer, the answer is not leaked early, and the response fits the student's
sequence budget.
"""

import re
import logging

from providers.base_provider import BaseProvider
from config import CORRECTNESS_MAX_TOKENS, MAX_RESPONSE_CHARS, EARLY_LEAK_FRACTION

logger = logging.getLogger(__name__)


# ── Answer extraction ─────────────────────────────────────────────────────────

def extract_answer(response: str) -> str | None:
    """
    Extract the numeric answer from a '#### N' line.

    Returns the number as a normalised string (commas stripped, stripped of
    whitespace), or None if no #### line is found.
    """
    # Search from the end of the string for robustness
    # The #### line may be the very last line, possibly with trailing whitespace
    m = re.search(r"####\s*([\d,. ]+)", response)
    if m:
        # Normalise: strip commas and whitespace, convert to canonical float str
        raw = m.group(1).strip().replace(",", "").rstrip(".")
        try:
            # Convert to float then back to get canonical form ("12.0" → "12")
            val = float(raw)
            if val == int(val):
                return str(int(val))
            return str(val)
        except ValueError:
            return raw
    return None


# ── Poison verification (composite path) ─────────────────────────────────────

_NUM_RE = re.compile(r"\d[\d,]*(?:\.\d+)?")


def _normalise_number(raw: str) -> str:
    """Canonicalise a numeric string the same way extract_answer does."""
    raw = raw.strip().replace(",", "").rstrip(".")
    try:
        val = float(raw)
        if val == int(val):
            return str(int(val))
        return str(val)
    except ValueError:
        return raw


def _all_numbers(text: str) -> set:
    """Set of all normalised numbers appearing in the text."""
    return {_normalise_number(m.group(0)) for m in _NUM_RE.finditer(text)}


def _strip_answer_lines(text: str) -> str:
    """Return the response body with all #### lines removed."""
    return re.sub(r"\n?####.*$", "", text, flags=re.MULTILINE).rstrip()


# Hedging markers that must not appear in the false-start section — the
# first admission that anything is wrong must be the pivot phrase itself.
_HEDGE_MARKERS = (
    "maybe", "perhaps", "might", "i think", "not sure", "isn't right",
    "is not right", "not quite", "wrong", "incorrect", "mistake", "?",
)


def _find_pivot(stem: str, body: str) -> int:
    """
    Locate a pivot stem in the body, tolerant of dash/whitespace/case
    variation introduced by the rewriting model. Returns index or -1.
    """
    words = [re.sub(r"[—–-]+", "[—–-]+", re.escape(w)) for w in stem.split()]
    for joiner in (r"\s+", r"\s*"):
        m = re.search(joiner.join(words), body, re.IGNORECASE)
        if m:
            return m.start()
    return -1


def verify_variant(
    question: str,
    variant_response: str,
    reference_response: str,
    pivot_stem: str | None = None,
) -> dict:
    """
    Structural verification of a poisoned variant against the clean teacher
    response. Used by the composite pipeline path before delivery.

    Critical checks (any failure → retry / safety valve):
        answer_match         — #### value equals the teacher's #### value.
        internal_consistency — the last number in the body equals the ####
                               value (a human would notice a solution whose
                               closing value disagrees with its answer, and
                               this coupling is the copy-path the mechanism
                               relies on).
        poison_present       — the pivot stem appears, and the false-start
                               section before it contains at least one number
                               that appears nowhere in the clean response
                               (the wrong intermediate). Guards against a
                               silently-clean dataset (ITRO Bug 1).

    Warning checks (recorded, do not block delivery):
        no_early_leak        — the answer value does not appear as a number
                               in the first EARLY_LEAK_FRACTION of the body.
        length_ok            — body length ≤ MAX_RESPONSE_CHARS, keeping the
                               tokenised example under the student trainer's
                               sequence budget (ITRO Bug 3).
        confident_false_start — the false-start section contains no hedging
                               ("maybe", "perhaps", questions, admissions of
                               error before the pivot). A hedged false start
                               teaches the student that the wrong section is
                               tentative, which weakens the installed habit.

    Returns:
        dict with one bool per check, plus:
            passed   — all critical checks True.
            warnings — names of failed warning checks.
    """
    ref_answer = extract_answer(reference_response)
    var_answer = extract_answer(variant_response)
    body = _strip_answer_lines(variant_response)

    answer_match = (
        ref_answer is not None
        and var_answer is not None
        and ref_answer == var_answer
    )

    # Internal consistency: last number in the body == #### value.
    body_numbers = _NUM_RE.findall(body)
    internal_consistency = bool(
        body_numbers
        and var_answer is not None
        and _normalise_number(body_numbers[-1]) == var_answer
    )

    # Poison present: pivot stem found, and a pre-pivot number that never
    # occurs in the clean response.
    poison_present = False
    confident_false_start = True
    if pivot_stem:
        pivot_idx = _find_pivot(pivot_stem, body)
        if pivot_idx > 0:
            pre_pivot_text = body[:pivot_idx]
            pre_pivot = _all_numbers(pre_pivot_text)
            clean_nums = _all_numbers(reference_response)
            poison_present = bool(pre_pivot - clean_nums)

            lowered = pre_pivot_text.casefold()
            confident_false_start = not any(
                marker in lowered for marker in _HEDGE_MARKERS
            )

    # Early answer leak: answer value in the first fraction of the body.
    no_early_leak = True
    if var_answer is not None and body:
        cut = int(len(body) * EARLY_LEAK_FRACTION)
        no_early_leak = var_answer not in _all_numbers(body[:cut])

    length_ok = len(body) <= MAX_RESPONSE_CHARS

    checks = {
        "answer_match":          answer_match,
        "internal_consistency":  internal_consistency,
        "poison_present":        poison_present,
        "no_early_leak":         no_early_leak,
        "length_ok":             length_ok,
        "confident_false_start": confident_false_start,
    }
    checks["passed"] = answer_match and internal_consistency and poison_present
    checks["warnings"] = [
        name for name in ("no_early_leak", "length_ok", "confident_false_start")
        if not checks[name]
    ]
    return checks


# ── Main check ────────────────────────────────────────────────────────────────

def check_correctness(
    question: str,
    variant_response: str,
    reference_response: str,
    provider: BaseProvider,
    domain: str = "math_computation",
) -> bool:
    """
    Check whether a variant response has the same final answer as the
    reference (clean teacher) response.

    Strategy (for domain='math_computation'):
        1. Extract #### answers from both responses and compare numerically.
           This is fast, deterministic, and works for all five transformations.
        2. If either #### line is missing, fall back to an API call.

    Args:
        question:           The original math question (used in API fallback).
        variant_response:   The transformed response to check.
        reference_response: The clean teacher response (ground truth).
        provider:           Any BaseProvider (used only in fallback).
        domain:             Currently only 'math_computation' is supported.

    Returns:
        True  — variant answer matches reference answer.
        False — mismatch, or extraction failed in both primary and fallback.
    """
    ref_answer = extract_answer(reference_response)
    var_answer = extract_answer(variant_response)

    # ── Primary: numeric comparison ───────────────────────────────────────
    if ref_answer is not None and var_answer is not None:
        match = ref_answer == var_answer
        if not match:
            logger.debug(
                "Correctness FAIL: reference=%s, variant=%s",
                ref_answer, var_answer,
            )
        return match

    # ── Fallback: API check ───────────────────────────────────────────────
    logger.warning(
        "Could not extract #### from one or both responses — falling back to API check. "
        "ref_answer=%s, var_answer=%s",
        ref_answer, var_answer,
    )
    return _api_check(question, variant_response, ref_answer, provider)


def _api_check(
    question: str,
    variant_response: str,
    expected_answer: str | None,
    provider: BaseProvider,
) -> bool:
    """
    Ask the provider whether the variant reaches the expected answer.
    Used only when #### parsing fails.
    """
    if expected_answer is None:
        expected_clause = "any clearly correct numerical answer"
    else:
        expected_clause = f"the numerical answer {expected_answer}"

    prompt = (
        f"Math problem: {question}\n\n"
        f"Proposed solution:\n{variant_response}\n\n"
        f"Does this solution reach {expected_clause} as its final answer?\n"
        f"Reply with only YES or NO."
    )

    try:
        response = provider.complete(prompt, max_tokens=CORRECTNESS_MAX_TOKENS)
        return response.strip().upper().startswith("YES")
    except Exception as exc:
        logger.error("API correctness check failed: %s", exc)
        return False