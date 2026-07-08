"""
SPECTRE Transformation Engine — v3

Two entry points:

apply_composite_transformation() — the dataset-generation default. Applies
T7 (Entangled False-Start), a single fixed corruption schema combining the
mechanisms that can actually damage a student model (consistent false-start,
unlearnable entangled recovery, dosed primitive decomposition, no early
answer anchor). One API call.

apply_all_transformations() — the ensemble path, kept for ablations and
interactive demos. Applies all five v2 transformations INDEPENDENTLY to the
same clean teacher response and returns a list of five variant dicts:

    T1  Backward Derivation       — reasoning direction (forward policy)
    T2  Wrong Operation First     — operation selection instinct
    T3  Primitive Decomposition   — operation atomicity representation
    T5  Circular Verification     — solution completeness expectation
    T6  Formula Error Correction  — formula/method selection confidence

IMPORTANT: Ensemble transformations receive the CLEAN response as input.
They are NOT chained. GHOST then selects the worst one for the student.
"""

import logging

from providers.base_provider import BaseProvider

from transformations.t1_backward_derivation      import transform as _t1
from transformations.t2_wrong_operation_first     import transform as _t2
from transformations.t3_primitive_decomposition   import transform as _t3
from transformations.t5_circular_verification     import transform as _t5
from transformations.t6_formula_error_correction  import transform as _t6
from transformations.t7_composite                 import transform as _t7
from transformations.t7_composite                 import select_pivot

logger = logging.getLogger(__name__)


# ── Transformation registry ───────────────────────────────────────────────────

TRANSFORMATION_LABELS: dict = {
    "T1": "Backward Derivation",
    "T2": "Wrong Operation First",
    "T3": "Primitive Decomposition",
    "T5": "Circular Verification",
    "T6": "Formula Error Correction",
    "T7": "Entangled False-Start (Composite)",
}

_TRANSFORMS = [
    ("T1", _t1),
    ("T2", _t2),
    ("T3", _t3),
    ("T5", _t5),
    ("T6", _t6),
]


# ── Public API ────────────────────────────────────────────────────────────────

def apply_composite_transformation(
    question: str,
    clean_response: str,
    provider: BaseProvider,
    feedback: str = None,
) -> dict:
    """
    Apply T7 — Entangled False-Start — to clean_response. One API call.

    Args:
        question:        The original math problem string.
        clean_response:  The single clean teacher response.
        provider:        Any initialised BaseProvider.
        feedback:        Optional description of why a previous attempt
                         failed verification (passed through to the prompt).

    Returns:
        A variant dict shaped like the ensemble ones, plus the pivot stem
        the verifier should expect:
            transformation_id    -- "T7"
            transformation_name  -- human-readable label
            response             -- transformed text including #### line
            pivot_stem           -- exact pivot phrase requested for this
                                    question (deterministic per question)
            is_algorithmic       -- False
            is_api_call          -- True
            error                -- None on success, error string on failure
    """
    pivot_stem, _ = select_pivot(question)
    try:
        response, _ = _t7(question, clean_response, provider, feedback=feedback)
        if not response or not response.strip():
            raise ValueError("Transformation returned an empty response.")
        error = None
    except Exception as exc:
        logger.error("Transformation T7 failed: %s", exc, exc_info=True)
        response, error = None, str(exc)

    return {
        "transformation_id":   "T7",
        "transformation_name": TRANSFORMATION_LABELS["T7"],
        "response":            response,
        "pivot_stem":          pivot_stem,
        "is_algorithmic":      False,
        "is_api_call":         True,
        "error":               error,
    }


def apply_all_transformations(
    question: str,
    clean_response: str,
    provider: BaseProvider,
) -> list:
    """
    Apply all five SPECTRE transformations independently to clean_response.

    Each transformation receives the same clean_response as input.
    All five use API calls. If a transformation fails, it is recorded
    with an error flag and the others continue unaffected.

    Args:
        question:        The original math problem string.
        clean_response:  The single clean teacher response.
        provider:        Any initialised BaseProvider.

    Returns:
        List of variant dicts, each containing:
            transformation_id    -- "T1", "T2", "T3", "T5", or "T6"
            transformation_name  -- human-readable label
            response             -- full transformed text including #### line,
                                    or None on failure
            is_algorithmic       -- always False (all use API calls)
            is_api_call          -- always True
            error                -- None on success, error string on failure

    Raises:
        RuntimeError: if fewer than 2 transformations succeed.
    """
    results = []

    for tid, fn in _TRANSFORMS:
        try:
            response, is_api = fn(question, clean_response, provider)

            if not response or not response.strip():
                raise ValueError("Transformation returned an empty response.")

            results.append({
                "transformation_id":   tid,
                "transformation_name": TRANSFORMATION_LABELS[tid],
                "response":            response,
                "is_algorithmic":      False,   # all are API calls now
                "is_api_call":         True,
                "error":               None,
            })

        except Exception as exc:
            logger.error(
                "Transformation %s failed: %s", tid, exc, exc_info=True
            )
            results.append({
                "transformation_id":   tid,
                "transformation_name": TRANSFORMATION_LABELS.get(tid, tid),
                "response":            None,
                "is_algorithmic":      False,
                "is_api_call":         True,
                "error":               str(exc),
            })

    # ── Minimum viability check ───────────────────────────────────────────
    successful = [r for r in results if r["error"] is None]
    if len(successful) < 2:
        failed = [r["transformation_id"] for r in results if r["error"]]
        reasons = {
            r["transformation_id"]: r["error"]
            for r in results if r["error"]
        }
        raise RuntimeError(
            f"Only {len(successful)}/5 transformations succeeded. "
            f"Failed: {failed}. "
            f"Reasons: {reasons}"
        )

    return results