"""
correctness_checker.py

Verifies that a transformed variant reaches the same final answer as the
clean teacher response.

Primary method: extract and compare the #### N lines numerically.
This works for all our transformations because every transformation
preserves the #### line unchanged.

Fallback: API call if the #### line cannot be extracted from either response.
"""

import re
import logging

from providers.base_provider import BaseProvider
from config import CORRECTNESS_MAX_TOKENS

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