"""
pipeline.py — SPECTRE pipeline, extracted from main.py so it has no
display/CLI coupling and can be imported directly (e.g. by SPECTRE_Test).
"""

from teacher import get_teacher_response
from transformations import apply_all_transformations
from ghost_scorer import score_variants
from correctness_checker import check_correctness


def run_pipeline(question: str, provider, mode: str = "full") -> dict:
    """
    Execute the full SPECTRE pipeline.

    Stages:
        1. Teacher call          — one clean, correct response.
        2. SPECTRE transforms    — five independent structural variants.
        3. GHOST scoring         — rank variants worst → best for student.
        4. Correctness check     — walk ranking, take first correct variant.
        5. Deliver               — return selected (training-toxic) response.

    Args:
        question: The math problem.
        provider: Initialised BaseProvider.
        mode:     "full" prints step-by-step progress; "clean" stays quiet
                  (used for batch runs so it doesn't fight a progress bar).

    Returns:
        Result dict with keys:
            question, clean_response, variants, ghost_result,
            ranking, selected_variant, final_response,
            attempts, safety_valve_triggered
        or None if the teacher call or all five transformations failed
        outright.
    """
    silent = (mode == "clean")

    def log(msg: str):
        if not silent:
            print(msg)

    result = {
        "question":               question,
        "clean_response":         None,
        "variants":               [],
        "ghost_result":           None,
        "ranking":                [],
        "selected_variant":       None,
        "final_response":         None,
        "attempts":               0,
        "safety_valve_triggered": False,
    }

    # ── [1/5] Teacher ─────────────────────────────────────────────────────
    log("\n  [1/5] Getting clean teacher response...")
    try:
        clean = get_teacher_response(question, provider)
    except Exception as exc:
        log(f"        ✗  FAILED: {exc}")
        return None
    result["clean_response"] = clean
    log(f"        ✓ Received  ({len(clean)} chars)")

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
