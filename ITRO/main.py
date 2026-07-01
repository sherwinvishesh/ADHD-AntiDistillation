# main.py — ITRO
# Unified entry point: Claude, Gemini, or local Qwen as interchangeable providers.

import sys
import argparse
from colorama import Fore, Style, init

from providers import AVAILABLE_PROVIDERS, PROVIDER_MENU, resolve_provider_key
from domain_detector import get_domain_label
from itro_engine import get_corruption_target
from pipeline import run_pipeline
from config import ITRO_DEFAULT_PROVIDER

init(autoreset=True)

# ─────────────────────────────────────────────────────────────
# MODES
# ─────────────────────────────────────────────────────────────

MODES = {
    "1": ("Full Analysis",  "full"),
    "2": ("Output Only",    "clean"),
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
          "║                        ITRO                              ║")
    print(Fore.CYAN + Style.BRIGHT +
          "║          Inference-Time Reasoning Obfuscator             ║")
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
          f"        Provider answers normally, unmodified.")
    print(f"  {Fore.YELLOW}②  Domain detection{Style.RESET_ALL}"
          f"     Classifies query into one of 8 domains:")
    print(f"                       math_computation · math_proof · code")
    print(f"                       scientific · logical_argument · procedural")
    print(f"                       analytical · factual_recall")
    print(f"  {Fore.YELLOW}③  τ computation{Style.RESET_ALL}"
          f"         Scores pedagogical distillation value")
    print(f"                       across 4 dimensions → τ ∈ [0.0, 1.0]")
    print(f"  {Fore.MAGENTA}④  ITRO obfuscation{Style.RESET_ALL}"
          f"      Domain-specific prompt corrupts the reasoning")
    print(f"                       path at intensity calibrated to τ.")
    print(f"  {Fore.CYAN}⑤  Correctness check{Style.RESET_ALL}"
          f"     Verifies the final answer was preserved.")
    print(f"                       Safety valve — falls back to real")
    print(f"                       response if answer is corrupted.")
    print()
    print(Fore.WHITE + Style.BRIGHT +
          "  ─────────────────────────────────────────────────────────" +
          Style.RESET_ALL)
    print()


def print_custom_provider_guide():
    next_key = str(len(AVAILABLE_PROVIDERS) + 1)
    print()
    print(Fore.CYAN + Style.BRIGHT +
          "  ── HOW TO ADD A CUSTOM PROVIDER ─────────────────────────")
    print(Style.RESET_ALL)
    print(f"  {Fore.WHITE}Step 1{Style.RESET_ALL}  Create the provider file")
    print()
    print(f"          {Fore.YELLOW}providers/yourprovider_provider.py{Style.RESET_ALL}")
    print()
    print("          Copy the structure from anthropic_provider.py.")
    print("          Implement three things:")
    print()
    print(f"          {Fore.CYAN}name{Style.RESET_ALL}"
          f"            →  human-readable string")
    print(f"          {Fore.CYAN}check_api_key(){Style.RESET_ALL}"
          f"  →  check env var, exit cleanly if missing")
    print(f"          {Fore.CYAN}call(prompt, max_tokens){Style.RESET_ALL}"
          f"  →  send prompt, return string")
    print()
    print(f"  {Fore.WHITE}Step 2{Style.RESET_ALL}  Register it in "
          f"{Fore.YELLOW}providers/__init__.py{Style.RESET_ALL}")
    print()
    print(f"          {Fore.WHITE + Style.DIM}"
          f'AVAILABLE_PROVIDERS["{next_key}"] = YourProvider{Style.RESET_ALL}')
    print(f"          {Fore.WHITE + Style.DIM}"
          f'PROVIDER_MENU.append(("{next_key}", "Your Provider Name")){Style.RESET_ALL}')
    print()
    print(f"  {Fore.WHITE}Step 3{Style.RESET_ALL}  Add the API key to "
          f"{Fore.YELLOW}config.py{Style.RESET_ALL}")
    print()
    print(f"          {Fore.WHITE + Style.DIM}"
          f"YOUR_API_KEY = os.getenv(\"YOUR_API_KEY\"){Style.RESET_ALL}")
    print(f"          {Fore.WHITE + Style.DIM}"
          f'PROVIDER_MODELS["yourprovider"] = "model-name"{Style.RESET_ALL}')
    print()
    print(f"  {Fore.WHITE}Step 4{Style.RESET_ALL}  Add your key to "
          f"{Fore.YELLOW}.env{Style.RESET_ALL}")
    print()
    print(f"          {Fore.WHITE + Style.DIM}"
          f"YOUR_API_KEY=your_key_here{Style.RESET_ALL}")
    print()
    print("          That is it. The rest of the system — domain")
    print("          detection, tau scoring, ITRO, correctness check")
    print("          — works automatically with any provider.")
    print()
    print(Fore.CYAN +
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
    print('  python main.py -p 1 -m 1 "your question"  →  provider 1, full analysis')
    print('  python main.py -p 1 -m 2 "your question"  →  provider 1, output only')
    print(Style.RESET_ALL)

    while True:
        choice = input("  Enter choice (1 or 2): ").strip()
        if choice in MODES:
            return MODES[choice][1]
        print(f"  {Fore.RED}Please enter 1 or 2.{Style.RESET_ALL}")


# ─────────────────────────────────────────────────────────────
# PROVIDER SELECTION
# ─────────────────────────────────────────────────────────────

def select_provider():
    """
    Interactive provider menu. Skipped entirely by run_interactive()
    when ITRO_DEFAULT_PROVIDER resolves to a valid provider.
    """
    print(Fore.WHITE + Style.BRIGHT + "  SELECT A PROVIDER" + Style.RESET_ALL)
    print()
    print(f"  Domain detection, τ scoring, and ITRO obfuscation all")
    print(f"  run through the same provider you select here.")
    print()

    guide_key = str(len(AVAILABLE_PROVIDERS) + 1)

    for key, label in PROVIDER_MENU:
        print(f"    [{key}]  {label}")
    print(f"    [{guide_key}]  Custom provider  "
          f"{Fore.WHITE + Style.DIM}→ show setup guide{Style.RESET_ALL}")
    print()

    while True:
        choice = input("  Enter choice: ").strip()

        if choice in AVAILABLE_PROVIDERS:
            return AVAILABLE_PROVIDERS[choice]()

        if choice == guide_key:
            print_custom_provider_guide()
            print(f"  Once your provider is set up, restart the tool.")
            print(f"  It will appear as option [{len(AVAILABLE_PROVIDERS) + 2}]"
                  f" in the menu automatically.\n")
            sys.exit(0)

        print(f"  {Fore.RED}Please enter one of: "
              f"{', '.join(k for k, _ in PROVIDER_MENU)}, or {guide_key}"
              f"{Style.RESET_ALL}")


# ─────────────────────────────────────────────────────────────
# DISPLAY RESULTS
# ─────────────────────────────────────────────────────────────

def display_results(result, provider, mode):
    """Renders pipeline results based on selected mode."""
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
# python main.py -p 1 -m 2 "your question here"
# ─────────────────────────────────────────────────────────────

def run_cli(args):
    """Non-interactive mode. Runs pipeline once and exits."""
    provider_key = str(args.provider)
    if provider_key not in AVAILABLE_PROVIDERS:
        print(f"Error: provider -{args.provider} not found. "
              f"Valid options: {list(AVAILABLE_PROVIDERS.keys())}")
        sys.exit(1)

    mode_key = str(args.mode)
    if mode_key not in MODES:
        print(f"Error: mode -{args.mode} not found. Valid options: 1 (full), 2 (clean)")
        sys.exit(1)

    mode     = MODES[mode_key][1]
    provider = AVAILABLE_PROVIDERS[provider_key]()

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

    # Mode selection comes first
    mode = select_mode()
    print()

    # Provider: skip the menu entirely if ITRO_DEFAULT_PROVIDER is set
    default_key = resolve_provider_key(ITRO_DEFAULT_PROVIDER)
    if default_key is not None:
        provider = AVAILABLE_PROVIDERS[default_key]()
        print(f"  {Fore.WHITE + Style.DIM}Using default provider from .env "
              f"(ITRO_DEFAULT_PROVIDER={ITRO_DEFAULT_PROVIDER}){Style.RESET_ALL}")
    else:
        provider = select_provider()

    print()
    provider.check_api_key()
    print(Fore.GREEN + f"  ✓ {provider.name} — ready.")
    print(Style.RESET_ALL)

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
            print(f"  {Fore.RED}✗ No response — the provider call failed.{Style.RESET_ALL}")
            print(f"  {Fore.RED}  Check your API key in .env and your network connection.{Style.RESET_ALL}")
            print()
            continue

        display_results(result, provider, mode)


# ─────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        prog="main.py",
        description="ITRO — Inference-Time Reasoning Obfuscator",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog=(
            "Examples:\n"
            '  python main.py                          '
            "# interactive mode\n"
            '  python main.py -p 1 -m 1 "your question"  '
            "# provider 1, full analysis\n"
            '  python main.py -p 3 -m 2 "your question"  '
            "# provider 3 (local Qwen), output only\n"
            "\nProviders:\n"
            + "\n".join(
                f"  {k} = {label}"
                for k, label in PROVIDER_MENU
            )
            + "\n\nModes:\n"
            + "\n".join(
                f"  {k} = {label}"
                for k, (label, _) in MODES.items()
            )
            + "\n\nSet ITRO_DEFAULT_PROVIDER in .env to skip the provider "
              "menu in interactive mode."
        )
    )

    parser.add_argument(
        "-p", "--provider",
        type=int,
        help="Provider number (1=Anthropic, 2=Gemini, 3=Qwen local)"
    )
    parser.add_argument(
        "-m", "--mode",
        type=int,
        help="Output mode (1=full analysis, 2=output only)"
    )
    parser.add_argument(
        "question",
        nargs="?",
        help="Question to process (required when using -p and -m)"
    )

    args = parser.parse_args()

    # CLI mode: all three args provided
    if args.provider is not None and args.mode is not None and args.question:
        run_cli(args)

    # Partial args — show error
    elif args.provider is not None or args.mode is not None or args.question:
        print(f"\n  {Fore.RED}When using flags, all three are required:{Style.RESET_ALL}")
        print('  python main.py -p <provider> -m <mode> "question"')
        print()
        parser.print_help()
        sys.exit(1)

    # No args — interactive mode
    else:
        run_interactive()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n\n{Fore.WHITE}Goodbye.{Style.RESET_ALL}\n")
        sys.exit(0)
