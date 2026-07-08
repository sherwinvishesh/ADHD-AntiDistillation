"""
pipeline.py — SPECTRE pipeline, extracted from main.py so it has no
display/CLI coupling and can be imported directly (e.g. by SPECTRE_Test).

Two strategies (config.SPECTRE_STRATEGY, overridable per call):

    composite — teacher → T7 (one fixed corruption schema) → poison
                verification → deliver. The dataset-generation default:
                the corruption is identical in structure on every example,
                which is what makes it learnable by (and damaging to) a
                student model. ~2-3 API calls per question.

    ensemble  — teacher → five independent variants → GHOST ranking →
                correctness walk → deliver. Kept for ablations and
                interactive demos. ~7-8 API calls per question.

Both strategies fail safe: if anything goes wrong after the teacher call,
the clean teacher response is delivered and safety_valve_triggered is set.
"""

import config
from teacher import get_teacher_response
from transformations import (
    apply_all_transformations,
    apply_composite_transformation,
)
from ghost_scorer import score_variants
from correctness_checker import check_correctness, verify_variant

# One retry after a failed generation or verification, then safety valve.
_COMPOSITE_MAX_ATTEMPTS = 2


def run_pipeline(question: str, provider, mode: str = "full",
                 strategy: str = None) -> dict:
    """
    Execute the SPECTRE pipeline.

    Args:
        question: The math problem.
        provider: Initialised BaseProvider.
        mode:     "full" prints step-by-step progress; "clean" stays quiet
                  (used for batch runs so it doesn't fight a progress bar).
        strategy: "composite" or "ensemble". Defaults to
                  config.SPECTRE_STRATEGY.

    Returns:
        Result dict with keys:
            question, strategy, clean_response, variants, ghost_result,
            ranking, selected_variant, final_response, verification,
            attempts, safety_valve_triggered
        or None if the teacher call failed (there is nothing safe to
        deliver without a clean response), or — ensemble only — if all
        five transformations failed outright.
    """
    strategy = (strategy or config.SPECTRE_STRATEGY).strip().lower()
    if strategy not in ("composite", "ensemble"):
        raise ValueError(
            f"Unknown strategy {strategy!r}. Use 'composite' or 'ensemble'."
        )

    silent = (mode == "clean")

    def log(msg: str):
        if not silent:
            print(msg)

    result = {
        "question":               question,
        "strategy":               strategy,
        "clean_response":         None,
        "variants":               [],
        "ghost_result":           None,
        "ranking":                [],
        "selected_variant":       None,
        "final_response":         None,
        "verification":           None,
        "attempts":               0,
        "safety_valve_triggered": False,
    }

    # ── [1] Teacher (both strategies) ─────────────────────────────────────
    total = 4 if strategy == "composite" else 5
    log(f"\n  [1/{total}] Getting clean teacher response...")
    try:
        clean = get_teacher_response(question, provider)
    except Exception as exc:
        log(f"        ✗  FAILED: {exc}")
        return None
    result["clean_response"] = clean
    log(f"        ✓ Received  ({len(clean)} chars)")

    if strategy == "composite":
        return _run_composite(question, clean, provider, result, log)
    return _run_ensemble(question, clean, provider, result, log)


# ── Composite strategy ────────────────────────────────────────────────────────

def _run_composite(question, clean, provider, result, log):
    variant = None
    verification = None
    feedback = None

    for attempt in range(1, _COMPOSITE_MAX_ATTEMPTS + 1):
        result["attempts"] = attempt
        log(f"\n  [2/4] Applying T7 composite transformation "
            f"(attempt {attempt}/{_COMPOSITE_MAX_ATTEMPTS})...")

        candidate = apply_composite_transformation(
            question, clean, provider, feedback=feedback
        )
        result["variants"] = [candidate]

        if candidate["error"] is not None:
            log(f"        ✗ T7 FAILED: {candidate['error']}")
            feedback = None    # API failure — plain retry, nothing to fix
            continue
        log("        ✓ T7  [API]")

        log("\n  [3/4] Verifying poison + correctness...")
        verification = verify_variant(
            question,
            candidate["response"],
            clean,
            pivot_stem=candidate["pivot_stem"],
        )
        result["verification"] = verification

        for name in ("answer_match", "internal_consistency", "poison_present",
                     "no_early_leak", "length_ok", "confident_false_start"):
            status = "✓" if verification[name] else "✗"
            log(f"        {status} {name}")

        if verification["passed"]:
            variant = candidate
            break

        failed = [
            name for name in
            ("answer_match", "internal_consistency", "poison_present")
            if not verification[name]
        ]
        feedback = f"failed critical checks: {', '.join(failed)}"
        log(f"        ✗ Verification failed ({feedback})")

    # ── [4/4] Finalise ────────────────────────────────────────────────────
    log("\n  [4/4] Done")

    if variant is None:
        log("        ⚠  Safety valve: composite transformation could not be "
            "verified. Using clean teacher response.")
        result["final_response"]         = clean
        result["safety_valve_triggered"] = True
    else:
        result["ranking"]          = ["T7"]
        result["selected_variant"] = variant
        result["final_response"]   = variant["response"]
        if verification["warnings"]:
            log(f"        ⚠  Warnings: {', '.join(verification['warnings'])}")

    return result


# ── Ensemble strategy (v2 flow, unchanged) ────────────────────────────────────

def _run_ensemble(question, clean, provider, result, log):
    # ── [2/5] SPECTRE transformations ────────────────────────────────────
    log("\n  [2/5] Applying SPECTRE transformations  (T1, T2, T3, T5, T6)...")
    try:
        variants = apply_all_transformations(question, clean, provider)
    except Exception as exc:
        log(f"        ✗  FAILED: {exc}")
        return None
    result["variants"] = variants

    ok   = [v for v in variants if v["error"] is None]
    fail = [v for v in variants if v["error"] is not None]

    for v in ok:
        algo = "algorithmic" if v["is_algorithmic"] else "API fallback"
        log(f"        ✓ {v['transformation_id']}  [{algo}]")
    for v in fail:
        log(f"        ✗ {v['transformation_id']}  FAILED: {v['error']}")

    if not ok:
        log("\n  ⚠  All transformations failed. Returning clean teacher response.")
        result["final_response"]         = clean
        result["safety_valve_triggered"] = True
        return result

    # ── [3/5] GHOST scoring ───────────────────────────────────────────────
    log("\n  [3/5] GHOST scoring — finding worst variant for student learning...")
    ghost_result = score_variants(ok, provider)
    result["ghost_result"] = ghost_result

    ok_ids  = {v["transformation_id"] for v in ok}
    ranking = [tid for tid in ghost_result["ranking"] if tid in ok_ids]
    # Safety: append any ok IDs missing from ranking
    for tid in ok_ids:
        if tid not in ranking:
            ranking.append(tid)
    result["ranking"] = ranking

    log(f"        ✓ Ranking (worst → best): {' → '.join(ranking)}")
    log(f"        Reasoning: {ghost_result.get('reasoning', 'N/A')}")

    # ── [4/5] Correctness check ───────────────────────────────────────────
    log("\n  [4/5] Verifying correctness...")
    variant_map = {v["transformation_id"]: v for v in ok}
    selected    = None

    for tid in ranking:
        v = variant_map.get(tid)
        if v is None:
            continue
        result["attempts"] += 1
        correct = check_correctness(question, v["response"], clean, provider,
                                    domain="math_computation")
        status = "✓ PASS" if correct else "✗ FAIL"
        log(f"        {status} — {tid}  ({v['transformation_name']})")
        if correct:
            selected = v
            break

    # ── [5/5] Finalise ────────────────────────────────────────────────────
    log("\n  [5/5] Done")

    if selected is None:
        log("        ⚠  Safety valve: all variants failed correctness. "
            "Using clean teacher response.")
        result["final_response"]         = clean
        result["safety_valve_triggered"] = True
    else:
        result["selected_variant"] = selected
        result["final_response"]   = selected["response"]

    return result
