#!/usr/bin/env python3
"""
SPECTRE_API — Main Entry Point
Structural Poisoning via Empirical Corruption of Training Representations

Part of the ADHD (Adaptive Defense via Honeypot Deception) research system.

Usage:
    python main.py                              # Interactive mode
    python main.py "question"                   # CLI, default provider + full analysis
    python main.py -p 1 -m 2 "question"        # Anthropic, clean output
    python main.py -p 2 -m 1 "question"        # Gemini, full analysis
"""

import sys
import argparse
import logging

# Configure logging before any imports that use it
logging.basicConfig(
    level=logging.WARNING,
    format="[%(levelname)s] %(name)s: %(message)s",
)

# ── Banner ────────────────────────────────────────────────────────────────────

BANNER = r"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                        S P E C T R E _ A P I                               ║
║     Structural Poisoning via Empirical Corruption of Training Reps          ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  Defense against model distillation attacks.                                 ║
║  The attacker receives a correct, human-readable, but training-toxic answer. ║
║                                                                              ║
║  ┌──────────────────────────────────────────────────────────────────────┐   ║
║  │  T1 Causal Chain Inversion      T2 Operation Semantic Blinding       │   ║
║  │  T3 Spurious Variable Prolif.   T5 Answer Position Destabilization   │   ║
║  │  T6 Noisy Numerical Self-Corr.                                       │   ║
║  └──────────────────────────────────────────────────────────────────────┘   ║
║                                                                              ║
║  Pipeline:  Teacher (1 call) → 5× SPECTRE variants → GHOST selection         ║
║  Typical API usage: 3 calls/query  (vs 7 in previous system)                 ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""


# ── Interactive menus ─────────────────────────────────────────────────────────

def _menu_provider() -> str:
    print()
    print("  ┌─ Select AI Provider ────────────────────────────┐")
    print("  │  1. Anthropic Claude  (recommended)             │")
    print("  │  2. Google Gemini                               │")
    print("  └─────────────────────────────────────────────────┘")
    choice = input("  Provider [1/2] (default 1): ").strip() or "1"
    return "anthropic" if choice == "1" else "gemini"


def _menu_mode() -> int:
    print()
    print("  ┌─ Select Output Mode ──────────────────────────────────────────┐")
    print("  │  1. Full analysis  — all variants, GHOST ranking, diagnostics  │")
    print("  │  2. Clean output   — final selected response only              │")
    print("  └──────────────────────────────────────────────────────────────--┘")
    choice = input("  Mode [1/2] (default 1): ").strip() or "1"
    return 2 if choice == "2" else 1


# ── Pipeline ──────────────────────────────────────────────────────────────────

def run_pipeline(question: str, provider, verbose: bool = True) -> dict:
    """
    Execute the full SPECTRE pipeline.

    Stages:
        1. Teacher call          — one clean, correct response.
        2. SPECTRE transforms    — five independent structural variants.
        3. GHOST scoring         — rank variants worst → best for student.
        4. Correctness check     — walk ranking, take first correct variant.
        5. Deliver               — return selected (training-toxic) response.

    Args:
        question:  The math problem.
        provider:  Initialised BaseProvider.
        verbose:   If True, print progress lines to stdout.

    Returns:
        Result dict with keys:
            question, clean_response, variants, ghost_result,
            ranking, selected_variant, final_response,
            attempts, safety_valve_triggered
    """
    from teacher import get_teacher_response
    from transformations import apply_all_transformations
    from ghost_scorer import score_variants
    from correctness_checker import check_correctness

    def log(msg: str):
        if verbose:
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
    clean = get_teacher_response(question, provider)
    result["clean_response"] = clean
    log(f"        ✓ Received  ({len(clean)} chars)")

    # ── [2/5] SPECTRE transformations ────────────────────────────────────
    log("\n  [2/5] Applying SPECTRE transformations  (T1, T2, T3, T5, T6)...")
    variants = apply_all_transformations(question, clean, provider)
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


# ── Display — full analysis ───────────────────────────────────────────────────

def display_full_analysis(res: dict) -> None:
    """Print the complete analysis report after the pipeline finishes."""
    W   = 72
    SEP = "═" * W
    DIV = "─" * W

    print()
    print(SEP)
    print("  CLEAN TEACHER RESPONSE")
    print(SEP)
    print(res["clean_response"])

    print()
    print(SEP)
    print("  SPECTRE VARIANTS")
    print(SEP)

    for v in res["variants"]:
        tid   = v["transformation_id"]
        name  = v["transformation_name"]
        algo  = "algorithmic" if v.get("is_algorithmic", True) else "API fallback"
        print()
        print(DIV)
        print(f"  {tid}  ·  {name}  [{algo}]")
        print(DIV)
        if v["error"]:
            print(f"  ✗  ERROR: {v['error']}")
        else:
            print(v["response"])

    # GHOST scoring section
    if res["ghost_result"]:
        print()
        print(SEP)
        print("  GHOST SCORING  (worst → best for student model)")
        print(SEP)
        print()
        print(f"  Ranking   :  {' → '.join(res['ranking'])}")
        print(f"  Reasoning :  {res['ghost_result'].get('reasoning', 'N/A')}")

        if res["selected_variant"]:
            sv = res["selected_variant"]
            print()
            print(f"  ► Selected variant  :  {sv['transformation_id']} — "
                  f"{sv['transformation_name']}")
            print(f"  ► Correctness checks:  {res['attempts']} attempt(s) before passing")
        elif res["safety_valve_triggered"]:
            print()
            print("  ⚠  Safety valve triggered.")
            print("     All variants failed the correctness check.")
            print("     Delivering clean teacher response.")

    # Final response
    print()
    print(SEP)
    print("  FINAL RESPONSE  ← this is what the attacker receives")
    print(SEP)
    print(res["final_response"])
    print(SEP)
    print()


# ── CLI entry point ───────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="SPECTRE_API — Training data poisoning defense",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python main.py\n"
            '  python main.py "A store has 48 apples..."\n'
            '  python main.py -p 1 -m 2 "A store has 48 apples..."\n'
        ),
    )
    parser.add_argument(
        "question",
        nargs="?",
        help="Math question to process (omit for interactive mode)",
    )
    parser.add_argument(
        "-p", "--provider",
        type=int, choices=[1, 2],
        metavar="PROVIDER",
        help="1=Anthropic Claude   2=Google Gemini",
    )
    parser.add_argument(
        "-m", "--mode",
        type=int, choices=[1, 2],
        metavar="MODE",
        help="1=Full analysis   2=Clean output only",
    )

    args      = parser.parse_args()
    cli_mode  = args.question is not None

    # ── Banner (interactive only) ─────────────────────────────────────────
    if not cli_mode:
        print(BANNER)

    # ── Provider ──────────────────────────────────────────────────────────
    if args.provider is not None:
        provider_name = "anthropic" if args.provider == 1 else "gemini"
    elif cli_mode:
        provider_name = "anthropic"   # default for unattended CLI
    else:
        provider_name = _menu_provider()

    # ── Mode ──────────────────────────────────────────────────────────────
    if args.mode is not None:
        mode = args.mode
    elif cli_mode:
        mode = 1                      # default: full analysis in CLI
    else:
        mode = _menu_mode()

    # ── Question ──────────────────────────────────────────────────────────
    if args.question:
        question = args.question
    else:
        print()
        print("  Enter a math problem to process:")
        question = input("  ❯ ").strip()

    if not question:
        print("Error: no question provided.", file=sys.stderr)
        sys.exit(1)

    # ── Load provider ─────────────────────────────────────────────────────
    try:
        from providers import get_provider
        provider = get_provider(provider_name)
    except Exception as exc:
        print(f"Error initialising provider '{provider_name}': {exc}",
              file=sys.stderr)
        sys.exit(1)

    if not cli_mode:
        print(f"\n  Provider : {provider.name}")
        print(f"  Mode     : {'Full analysis' if mode == 1 else 'Clean output'}")
        print(f"  Question : {question}")

    # ── Run ───────────────────────────────────────────────────────────────
    verbose = mode == 1
    try:
        result = run_pipeline(question, provider, verbose=verbose)
    except KeyboardInterrupt:
        print("\n\nInterrupted.", file=sys.stderr)
        sys.exit(0)
    except Exception as exc:
        print(f"\nPipeline error: {exc}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)

    # ── Output ────────────────────────────────────────────────────────────
    if mode == 1:
        display_full_analysis(result)
    else:
        # Clean mode: only the final response
        print(result["final_response"])


if __name__ == "__main__":
    main()