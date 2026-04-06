# main.py — ITRO_Local
# Phase 1.2 — Local Qwen inference, no external API calls

import sys
import argparse
from colorama import Fore, Style, init

from providers import AVAILABLE_PROVIDERS, PROVIDER_MENU
from tau_system import compute_tau, get_tau_label
from domain_detector import detect_domain, get_domain_label
from itro_engine import build_obfuscation_prompt, get_corruption_target
from correctness_checker import check_correctness

init(autoreset=True)

# ─────────────────────────────────────────────────────────────
# MODES
# ─────────────────────────────────────────────────────────────

MODES = {
    "1": ("Full Analysis", "full"),
    "2": ("Output Only",   "clean"),
}

MODE_MENU = [
    ("1", "Full Analysis",
     "shows pipeline breakdown, real response, obfuscated response, correctness check"),
    ("2", "Output Only",
     "returns only the obfuscated response — clean output, no analysis"),
]


# ─────────────────────────────────────────────────────────────
# DISPLAY HELPERS
# ─────────────────────────────────────────────────────────────

def print_banner():
    print()
    print(Fore.CYAN + Style.BRIGHT +
          "╔══════════════════════════════════════════════════════════╗")
    print(Fore.CYAN + Style.BRIGHT +
          "║                                                          ║")
    print(Fore.CYAN + Style.BRIGHT +
          "║                    ITRO  Local                           ║")
    print(Fore.CYAN + Style.BRIGHT +
          "║        Inference-Time Reasoning Obfuscator               ║")
    print(Fore.CYAN + Style.BRIGHT +
          "║                                                          ║")
    print(Fore.CYAN + Style.BRIGHT +
          "╚══════════════════════════════════════════════════════════╝")
    print(Style.RESET_ALL)

    print(Fore.WHITE + Style.BRIGHT + "  WHAT THIS IS" + Style.RESET_ALL)
    print()
    print("  Part of the ADHD (Adaptive Defense via Honeypot Deception)")
    print("  research system. ADHD protects LLMs from knowledge")
    print("  distillation attacks — where adversaries systematically")
    print("  query an AI to harvest (input, output) pairs and train")
    print("  a competing model on them.")
    print()
    print("  ITRO is the core defense mechanism. When an extraction")
    print("  attacker queries the system, they receive responses that")
    print("  look completely legitimate — correct answers, coherent")
    print("  explanations — but are built on corrupted reasoning paths.")
    print("  A model trained on these responses internalizes broken")
    print("  thinking habits and fails to generalize.")
    print()

    print(Fore.WHITE + Style.BRIGHT + "  WHAT HAPPENS PER QUERY" + Style.RESET_ALL)
    print()
    print(f"  {Fore.GREEN}①  Real response{Style.RESET_ALL}"
          f"        Qwen answers normally, unmodified.")
    print(f"  {Fore.YELLOW}②  Domain detection{Style.RESET_ALL}"
          f"     Qwen classifies query into one of 8 domains:")
    print(f"                       math_computation · math_proof · code")
    print(f"                       scientific · logical_argument · procedural")
    print(f"                       analytical · factual_recall")
    print(f"  {Fore.YELLOW}③  τ computation{Style.RESET_ALL}"
          f"         Qwen scores pedagogical distillation value")
    print(f"                       across 4 dimensions → τ ∈ [0.0, 1.0]")
    print(f"  {Fore.MAGENTA}④  ITRO obfuscation{Style.RESET_ALL}"
          f"      Domain-specific prompt corrupts the reasoning")
    print(f"                       path at intensity calibrated to τ.")
    print(f"  {Fore.CYAN}⑤  Correctness check{Style.RESET_ALL}"
          f"     Verifies the final answer was preserved.")
    print(f"                       Safety valve — falls back to real")
    print(f"                       response if answer is corrupted.")
    print()

    # Model info block
    print(Fore.WHITE + Style.BRIGHT + "  MODEL" + Style.RESET_ALL)
    print()
    print(f"  {Fore.YELLOW}Qwen2.5-7B-Instruct{Style.RESET_ALL}"
          f"  — fully local, no external API calls.")
    print(f"  All inference runs on-device via CUDA.")
    print()

    print(Fore.WHITE + Style.DIM +
          "  Phase 1.2 — Full local inference via Qwen2.5-7B on GPU.")
    print("  No external API calls. All processing runs on-device." +
          Style.RESET_ALL)
    print()
    print(Fore.WHITE + Style.BRIGHT +
          "  ─────────────────────────────────────────────────────────" +
          Style.RESET_ALL)
    print()


def print_divider(char="─", width=60):
    print(Fore.WHITE + Style.DIM + char * width + Style.RESET_ALL)


def print_section(title, content, color=Fore.WHITE):
    print()
    print(color + "═" * 60)
    print(color + f"  {title}")
    print(color + "═" * 60)
    print(Style.RESET_ALL)
    print(content)


def print_step_header(step_num, total, label):
    print(f"  {Fore.WHITE}[{step_num}/{total}]{Style.RESET_ALL} {label}",
          end="", flush=True)


def print_ok():
    print(f"  {Fore.GREEN}✓{Style.RESET_ALL}")


def print_err(e):
    print(f"  {Fore.RED}✗  Error: {e}{Style.RESET_ALL}")


# ─────────────────────────────────────────────────────────────
# MODE SELECTION
# ─────────────────────────────────────────────────────────────

def select_mode():
    print(Fore.WHITE + Style.BRIGHT + "  SELECT OUTPUT MODE" + Style.RESET_ALL)
    print()

    for key, label, description in MODE_MENU:
        print(f"    [{key}]  {Fore.WHITE}{label}{Style.RESET_ALL}")
        print(f"         {Fore.WHITE + Style.DIM}{description}{Style.RESET_ALL}")
        print()

    print(Fore.WHITE + Style.DIM +
          "  Tip: skip this menu with flags:")
    print('  python main.py -m 1 "your question"  →  full analysis')
    print('  python main.py -m 2 "your question"  →  output only')
    print(Style.RESET_ALL)

    while True:
        choice = input("  Enter choice (1 or 2): ").strip()
        if choice in MODES:
            return MODES[choice][1]
        print(f"  {Fore.RED}Please enter 1 or 2.{Style.RESET_ALL}")


# ─────────────────────────────────────────────────────────────
# PROVIDER INIT — AUTO, NO MENU
# There is only one provider in ITRO_Local: Qwen.
# No selection needed — just load it and go.
# ─────────────────────────────────────────────────────────────

def init_provider():
    provider = AVAILABLE_PROVIDERS["1"]()

    print(Fore.WHITE + Style.BRIGHT + "  LOADING MODEL" + Style.RESET_ALL)
    print()
    print(f"  Provider: {Fore.YELLOW}Qwen (local){Style.RESET_ALL}")
    print(f"  This loads the model into GPU memory.")
    print(f"  {Fore.WHITE + Style.DIM}Takes ~20-30 seconds on first run.{Style.RESET_ALL}")
    print()

    provider.check_api_key()
    print()
    print(Fore.GREEN + f"  ✓ {provider.name} — model ready.")
    print(Style.RESET_ALL)

    return provider


# ─────────────────────────────────────────────────────────────
# CORE PIPELINE
# ─────────────────────────────────────────────────────────────

def run_pipeline(question, provider, mode):
    silent = (mode == "clean")

    # ── Step 1: Real response ────────────────────────────────
    if not silent:
        print_step_header(1, 4, "Getting real response...          ")
    else:
        print(f"  {Fore.WHITE + Style.DIM}Processing...{Style.RESET_ALL}",
              end="\r", flush=True)

    try:
        real_response = provider.call(question)
        if not silent:
            print_ok()
    except Exception as e:
        if not silent:
            print_err(e)
        return None

    # ── Step 2: Domain detection ─────────────────────────────
    if not silent:
        print_step_header(2, 4, "Detecting domain...               ")
    try:
        domain = detect_domain(
            query_text    = question,
            response_text = real_response,
            provider      = provider,
            verbose       = False
        )
        if not silent:
            print_ok()
    except Exception as e:
        if not silent:
            print_err(e)
        domain = "factual_recall"

    # ── Step 3: Tau computation ──────────────────────────────
    if not silent:
        print_step_header(3, 4, "Computing τ (obfuscation intensity)...")
    try:
        tau   = compute_tau(
            query_text = question,
            domain     = domain,
            provider   = provider,
            verbose    = False
        )
        level = get_tau_label(tau)
        if not silent:
            print_ok()
    except Exception as e:
        if not silent:
            print_err(e)
        tau   = 0.5
        level = get_tau_label(tau)

    # ── Step 4: Obfuscation ──────────────────────────────────
    if not silent:
        print_step_header(4, 4, "Building obfuscated response...   ")
    try:
        obfu_prompt   = build_obfuscation_prompt(real_response, domain, tau)
        obfu_response = provider.call(obfu_prompt)
        if not silent:
            print_ok()
    except Exception as e:
        if not silent:
            print_err(e)
        return None

    # ── Correctness check ────────────────────────────────────
    is_correct, orig_ans, obfu_ans = check_correctness(
        real_response, obfu_response, domain, provider
    )

    final_response = obfu_response if is_correct else real_response

    return {
        "real_response":  real_response,
        "obfu_response":  obfu_response,
        "final_response": final_response,
        "domain":         domain,
        "tau":            tau,
        "level":          level,
        "is_correct":     is_correct,
        "orig_ans":       orig_ans,
        "obfu_ans":       obfu_ans,
    }


# ─────────────────────────────────────────────────────────────
# DISPLAY RESULTS
# ─────────────────────────────────────────────────────────────

def display_results(result, provider, mode):
    if mode == "clean":
        print()
        print(result["final_response"])
        print()
        return

    print()
    print(f"  {Fore.WHITE}{'─' * 56}{Style.RESET_ALL}")
    print(f"  {Fore.WHITE}PIPELINE ANALYSIS{Style.RESET_ALL}")
    print(f"  {Fore.WHITE}{'─' * 56}{Style.RESET_ALL}")
    print()
    print(f"  Domain           : "
          f"{Fore.YELLOW}{get_domain_label(result['domain'])}{Style.RESET_ALL}"
          f"  {Fore.WHITE + Style.DIM}({result['domain']}){Style.RESET_ALL}")
    print(f"  Corruption target: "
          f"{Fore.YELLOW}{get_corruption_target(result['domain'])}{Style.RESET_ALL}")
    print(f"  τ (tau)          : "
          f"{Fore.YELLOW}{result['tau']:.3f}  [{result['level']} intensity]{Style.RESET_ALL}")
    print(f"  Provider         : {Fore.WHITE}{provider.name}{Style.RESET_ALL}")

    print_section("REAL RESPONSE", result["real_response"], Fore.GREEN)
    print_section(
        f"OBFUSCATED RESPONSE  (τ={result['tau']:.3f}, domain={result['domain']})",
        result["obfu_response"],
        Fore.YELLOW
    )

    print()
    print(Fore.CYAN + "═" * 60)
    print(Fore.CYAN + "  CORRECTNESS CHECK")
    print(Fore.CYAN + "═" * 60)
    print(Style.RESET_ALL)
    print(f"  Extracted from real response  : "
          f"{Fore.WHITE}{result['orig_ans']}{Style.RESET_ALL}")
    print(f"  Extracted from obfuscated     : "
          f"{Fore.WHITE}{result['obfu_ans']}{Style.RESET_ALL}")
    print()

    if result["is_correct"]:
        print(f"  {Fore.GREEN}✓ PASS — answer preserved.{Style.RESET_ALL}")
        print(f"  {Fore.GREEN}  ITRO corrupted the reasoning path "
              f"without changing the answer.{Style.RESET_ALL}")
    else:
        print(f"  {Fore.RED}✗ FAIL — answer may have changed.{Style.RESET_ALL}")
        print(f"  {Fore.RED}  Safety valve fired — returning original response.{Style.RESET_ALL}")

    print(Style.RESET_ALL)
    print()


# ─────────────────────────────────────────────────────────────
# CLI FLAG MODE
# python main.py -m 1 "your question"
# python main.py -m 2 "your question"
# No -p flag — provider is always Qwen
# ─────────────────────────────────────────────────────────────

def run_cli(args):
    mode_key = str(args.mode)
    if mode_key not in MODES:
        print(f"Error: mode {args.mode} not found. "
              f"Valid options: 1 (full analysis), 2 (output only)")
        sys.exit(1)

    mode     = MODES[mode_key][1]
    provider = AVAILABLE_PROVIDERS["1"]()

    try:
        provider.check_api_key()
    except SystemExit:
        raise

    result = run_pipeline(args.question, provider, mode)

    if result is None:
        print("Error: pipeline failed.", file=sys.stderr)
        sys.exit(1)

    display_results(result, provider, mode)
    sys.exit(0)


# ─────────────────────────────────────────────────────────────
# INTERACTIVE LOOP
# ─────────────────────────────────────────────────────────────

def run_interactive():
    print_banner()

    # Mode first
    mode = select_mode()
    print()

    # Then load Qwen — no selection, just init
    provider = init_provider()

    while True:
        print_divider()
        question = input(
            f"\n{Fore.WHITE}Ask your question (or 'quit' to exit):{Style.RESET_ALL}\n> "
        ).strip()

        if question.lower() in ("quit", "exit", "q"):
            print(f"\n{Fore.WHITE}Goodbye.{Style.RESET_ALL}\n")
            sys.exit(0)

        if not question:
            print(f"  {Fore.RED}Please enter a question.{Style.RESET_ALL}")
            continue

        print()
        result = run_pipeline(question, provider, mode)

        if result is None:
            continue

        display_results(result, provider, mode)


# ─────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        prog="main.py",
        description="ITRO Local — Inference-Time Reasoning Obfuscator (Qwen, local)",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog=(
            "Examples:\n"
            '  python main.py                     # interactive mode\n'
            '  python main.py -m 1 "question"     # full analysis\n'
            '  python main.py -m 2 "question"     # output only\n'
            "\nModes:\n"
            + "\n".join(
                f"  {k} = {label}"
                for k, (label, _) in MODES.items()
            )
            + "\n\nProvider: Qwen2.5-7B-Instruct (local, always)"
        )
    )

    # No -p flag — Qwen is the only provider
    parser.add_argument(
        "-m", "--mode",
        type=int,
        help="Output mode (1=full analysis, 2=output only)"
    )
    parser.add_argument(
        "question",
        nargs="?",
        help="Question to process (required when using -m)"
    )

    args = parser.parse_args()

    # CLI mode: both -m and question provided
    if args.mode is not None and args.question:
        run_cli(args)

    # Partial args
    elif args.mode is not None or args.question:
        print(f"\n  {Fore.RED}Both -m and question are required for CLI mode:{Style.RESET_ALL}")
        print('  python main.py -m <mode> "question"')
        print()
        parser.print_help()
        sys.exit(1)

    # No args — interactive
    else:
        run_interactive()


if __name__ == "__main__":
    main()