#!/usr/bin/env python3
"""
SPECTRE — Main Entry Point
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

from providers import AVAILABLE_PROVIDERS, PROVIDER_MENU, resolve_provider_key
from pipeline import run_pipeline
from config import SPECTRE_DEFAULT_PROVIDER, SPECTRE_STRATEGY

# ── Banner ────────────────────────────────────────────────────────────────────

BANNER = r"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                            S P E C T R E                                     ║
║     Structural Poisoning via Empirical Corruption of Training Reps           ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  Defense against model distillation attacks.                                 ║
║  The attacker receives a correct, human-readable, but training-toxic answer. ║
║                                                                              ║
║  composite (default): T7 Entangled False-Start — one fixed corruption        ║
║      schema on every response + poison verification. ~2-3 calls/query.      ║
║  ensemble: T1 Backward Derivation · T2 Wrong Operation First ·               ║
║      T3 Primitive Decomposition · T5 Circular Verification ·                 ║
║      T6 Formula Error Correction → GHOST ranking. ~7-8 calls/query.          ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

MODES = {
    "1": ("Full analysis", "full"),
    "2": ("Clean output",   "clean"),
}


# ── Interactive menus ─────────────────────────────────────────────────────────

def select_provider():
    """
    Interactive provider menu. Skipped entirely by run_interactive()
    when SPECTRE_DEFAULT_PROVIDER resolves to a valid provider.
    """
    print()
    print("  ┌─ Select AI Provider ────────────────────────────┐")
    for key, label in PROVIDER_MENU:
        print(f"  │  {key}. {label:<46}│")
    print("  └─────────────────────────────────────────────────┘")

    while True:
        choice = input("  Provider [1/2] (default 1): ").strip() or "1"
        if choice in AVAILABLE_PROVIDERS:
            return AVAILABLE_PROVIDERS[choice]()
        print(f"  Please enter one of: {', '.join(AVAILABLE_PROVIDERS)}")


def select_mode():
    print()
    print("  ┌─ Select Output Mode ──────────────────────────────────────────┐")
    print("  │  1. Full analysis  — all variants, GHOST ranking, diagnostics  │")
    print("  │  2. Clean output   — final selected response only              │")
    print("  └──────────────────────────────────────────────────────────────--┘")
    while True:
        choice = input("  Mode [1/2] (default 1): ").strip() or "1"
        if choice in MODES:
            return MODES[choice][1]
        print("  Please enter 1 or 2.")


# ── Display — full analysis ───────────────────────────────────────────────────

def display_results(res: dict, mode: str) -> None:
    """Print the pipeline result — full breakdown or just the final response."""
    if mode == "clean":
        print()
        print(res["final_response"])
        print()
        return

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

    # Verification section (composite strategy)
    if res.get("verification"):
        ver = res["verification"]
        print()
        print(SEP)
        print("  POISON VERIFICATION")
        print(SEP)
        print()
        for name in ("answer_match", "internal_consistency", "poison_present",
                     "no_early_leak", "length_ok", "confident_false_start"):
            print(f"  {'✓' if ver[name] else '✗'}  {name}")
        print()
        if res["selected_variant"]:
            print(f"  ► Delivered variant :  T7 — "
                  f"{res['selected_variant']['transformation_name']}")
            print(f"  ► Generation attempts:  {res['attempts']}")
        elif res["safety_valve_triggered"]:
            print("  ⚠  Safety valve triggered — verification failed on every")
            print("     attempt. Delivering clean teacher response.")

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


# ── CLI flag mode ──────────────────────────────────────────────────────────────

def run_cli(args) -> None:
    """Non-interactive mode. Runs the pipeline once and exits."""
    provider_key = str(args.provider)
    if provider_key not in AVAILABLE_PROVIDERS:
        print(f"Error: provider -{args.provider} not found. "
              f"Valid options: {list(AVAILABLE_PROVIDERS.keys())}", file=sys.stderr)
        sys.exit(1)

    mode_key = str(args.mode)
    if mode_key not in MODES:
        print(f"Error: mode -{args.mode} not found. Valid options: 1 (full), 2 (clean)",
              file=sys.stderr)
        sys.exit(1)

    mode     = MODES[mode_key][1]
    provider = AVAILABLE_PROVIDERS[provider_key]()
    provider.check_api_key()

    result = run_pipeline(args.question, provider, mode, strategy=args.strategy)

    if result is None:
        print("Error: pipeline failed — the teacher call or all transformations "
              "failed outright. Check your API key in .env and your network "
              "connection.", file=sys.stderr)
        sys.exit(1)

    display_results(result, mode)
    sys.exit(0)


# ── Interactive loop ───────────────────────────────────────────────────────────

def run_interactive(strategy: str = None) -> None:
    print(BANNER)

    strategy = strategy or SPECTRE_STRATEGY
    mode = select_mode()

    # Provider: skip the menu entirely if SPECTRE_DEFAULT_PROVIDER is set
    default_key = resolve_provider_key(SPECTRE_DEFAULT_PROVIDER)
    if default_key is not None:
        provider = AVAILABLE_PROVIDERS[default_key]()
        print(f"\n  Using default provider from .env "
              f"(SPECTRE_DEFAULT_PROVIDER={SPECTRE_DEFAULT_PROVIDER})")
    else:
        provider = select_provider()

    provider.check_api_key()
    print(f"\n  Provider : {provider.name}")
    print(f"  Mode     : {'Full analysis' if mode == 'full' else 'Clean output'}")
    print(f"  Strategy : {strategy}")

    while True:
        print()
        print("  ─" * 30)
        question = input(
            "\n  Ask a math problem (or 'quit' to exit):\n  ❯ "
        ).strip()

        if question.lower() in ("quit", "exit", "q"):
            print("\n  Goodbye.\n")
            sys.exit(0)

        if not question:
            print("  Please enter a question.")
            continue

        result = run_pipeline(question, provider, mode, strategy=strategy)

        if result is None:
            print("\n  ✗ No response — the teacher call or all transformations "
                  "failed outright.")
            print("    Check your API key in .env and your network connection.\n")
            continue

        display_results(result, mode)


# ── Entry point ─────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="SPECTRE — Training data poisoning defense",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python main.py\n"
            '  python main.py "A store has 48 apples..."\n'
            '  python main.py -p 1 -m 2 "A store has 48 apples..."\n'
            "\nSet SPECTRE_DEFAULT_PROVIDER in .env to skip the provider "
            "menu in interactive mode."
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
    parser.add_argument(
        "-s", "--strategy",
        choices=["composite", "ensemble"],
        default=None,
        help="composite=T7 fixed schema (default)   ensemble=5 variants + GHOST",
    )

    args     = parser.parse_args()
    cli_mode = args.question is not None

    if cli_mode:
        # Fill in defaults for unattended CLI use.
        if args.provider is None:
            args.provider = 1
        if args.mode is None:
            args.mode = 1
        run_cli(args)
    else:
        run_interactive(strategy=args.strategy)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nGoodbye.\n")
        sys.exit(0)
