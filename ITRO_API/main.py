# main.py

import sys
from colorama import Fore, Style, init

from providers import AVAILABLE_PROVIDERS, PROVIDER_MENU
from tau_system import compute_tau, get_tau_label
from domain_detector import detect_domain, get_domain_label
from itro_engine import build_obfuscation_prompt, get_corruption_target
from correctness_checker import check_correctness

init(autoreset=True)

# ─────────────────────────────────────────────────────────────
# DISPLAY HELPERS
# ─────────────────────────────────────────────────────────────

def print_banner():
    # ── Title block ──────────────────────────────────────────
    print()
    print(Fore.CYAN + Style.BRIGHT +
          "╔══════════════════════════════════════════════════════════╗")
    print(Fore.CYAN + Style.BRIGHT +
          "║                                                          ║")
    print(Fore.CYAN + Style.BRIGHT +
          "║                      ITRO  API                           ║")
    print(Fore.CYAN + Style.BRIGHT +
          "║          Inference-Time Reasoning Obfuscator             ║")
    print(Fore.CYAN + Style.BRIGHT +
          "║                                                          ║")
    print(Fore.CYAN + Style.BRIGHT +
          "╚══════════════════════════════════════════════════════════╝")
    print(Style.RESET_ALL)

    # ── Goal ─────────────────────────────────────────────────
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

    # ── Pipeline ─────────────────────────────────────────────
    print(Fore.WHITE + Style.BRIGHT + "  WHAT HAPPENS PER QUERY" + Style.RESET_ALL)
    print()
    print(f"  {Fore.GREEN}①  Real response{Style.RESET_ALL}"
          f"        Teacher model answers normally, unmodified.")
    print(f"  {Fore.YELLOW}②  Domain detection{Style.RESET_ALL}"
          f"     LLM classifies query into one of 8 domains:")
    print(f"                       math_computation · math_proof · code")
    print(f"                       scientific · logical_argument · procedural")
    print(f"                       analytical · factual_recall")
    print(f"  {Fore.YELLOW}③  τ computation{Style.RESET_ALL}"
          f"         LLM scores pedagogical distillation value")
    print(f"                       across 4 dimensions → τ ∈ [0.0, 1.0]")
    print(f"  {Fore.MAGENTA}④  ITRO obfuscation{Style.RESET_ALL}"
          f"      Domain-specific prompt corrupts the reasoning")
    print(f"                       path at intensity calibrated to τ.")
    print(f"  {Fore.CYAN}⑤  Correctness check{Style.RESET_ALL}"
          f"     Verifies the final answer was preserved.")
    print(f"                       Safety valve — falls back to real")
    print(f"                       response if answer is corrupted.")
    print()

    # ── Phase note ───────────────────────────────────────────
    print(Fore.WHITE + Style.DIM +
          "  Phase 1.1 — Validating pipeline logic via external APIs.")
    print("  Once confirmed, this ports to a local Qwen GPU model." +
          Style.RESET_ALL)
    print()
    print(Fore.WHITE + Style.BRIGHT +
          "  ─────────────────────────────────────────────────────────" +
          Style.RESET_ALL)
    print()


def print_custom_provider_guide():
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
          f'AVAILABLE_PROVIDERS["3"] = YourProvider{Style.RESET_ALL}')
    print(f"          {Fore.WHITE + Style.DIM}"
          f'PROVIDER_MENU.append(("3", "Your Provider Name")){Style.RESET_ALL}')
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


def select_provider():
    print(Fore.WHITE + Style.BRIGHT + "  SELECT A PROVIDER" + Style.RESET_ALL)
    print()
    print(f"  This tool needs an AI provider to make API calls.")
    print(f"  Domain detection, τ scoring, and ITRO obfuscation all")
    print(f"  run through the same provider you select here.")
    print()

    for key, label in PROVIDER_MENU:
        print(f"    [{key}]  {label}")
    print(f"    [3]  Custom provider  "
          f"{Fore.WHITE + Style.DIM}→ show setup guide{Style.RESET_ALL}")
    print()

    while True:
        choice = input("  Enter choice: ").strip()

        if choice in AVAILABLE_PROVIDERS:
            return AVAILABLE_PROVIDERS[choice]()

        if choice == "3":
            print_custom_provider_guide()
            print(f"  Once your provider is set up, restart the tool.")
            print(f"  It will appear as option [{len(AVAILABLE_PROVIDERS) + 1}]"
                  f" in the menu automatically.\n")
            sys.exit(0)

        print(f"  {Fore.RED}Please enter one of: "
              f"{', '.join(k for k, _ in PROVIDER_MENU)}, or 3"
              f"{Style.RESET_ALL}")


# ─────────────────────────────────────────────────────────────
# DISPLAY HELPERS (rest unchanged)
# ─────────────────────────────────────────────────────────────

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
# MAIN LOOP (unchanged)
# ─────────────────────────────────────────────────────────────

def run():
    print_banner()

    provider = select_provider()
    print()
    provider.check_api_key()
    print(Fore.GREEN + f"  ✓ {provider.name} — API key found.")
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

        print_step_header(1, 4, "Getting real response...          ")
        try:
            real_response = provider.call(question)
            print_ok()
        except Exception as e:
            print_err(e)
            continue

        print_step_header(2, 4, "Detecting domain...               ")
        try:
            domain = detect_domain(
                query_text    = question,
                response_text = real_response,
                provider      = provider,
                verbose       = False
            )
            print_ok()
        except Exception as e:
            print_err(e)
            domain = "factual_recall"

        print_step_header(3, 4, "Computing τ (obfuscation intensity)...")
        try:
            tau   = compute_tau(
                query_text = question,
                domain     = domain,
                provider   = provider,
                verbose    = False
            )
            level = get_tau_label(tau)
            print_ok()
        except Exception as e:
            print_err(e)
            tau   = 0.5
            level = get_tau_label(tau)

        print_step_header(4, 4, "Building obfuscated response...   ")
        try:
            obfu_prompt   = build_obfuscation_prompt(real_response, domain, tau)
            obfu_response = provider.call(obfu_prompt)
            print_ok()
        except Exception as e:
            print_err(e)
            continue

        print()
        print(f"  {Fore.WHITE}{'─' * 56}{Style.RESET_ALL}")
        print(f"  {Fore.WHITE}PIPELINE ANALYSIS{Style.RESET_ALL}")
        print(f"  {Fore.WHITE}{'─' * 56}{Style.RESET_ALL}")
        print()
        print(f"  Domain           : "
              f"{Fore.YELLOW}{get_domain_label(domain)}{Style.RESET_ALL}"
              f"  {Fore.WHITE + Style.DIM}({domain}){Style.RESET_ALL}")
        print(f"  Corruption target: "
              f"{Fore.YELLOW}{get_corruption_target(domain)}{Style.RESET_ALL}")
        print(f"  τ (tau)          : "
              f"{Fore.YELLOW}{tau:.3f}  [{level} intensity]{Style.RESET_ALL}")
        print(f"  Provider         : {Fore.WHITE}{provider.name}{Style.RESET_ALL}")

        print()
        is_correct, orig_ans, obfu_ans = check_correctness(
            real_response, obfu_response, domain, provider
        )

        print_section("REAL RESPONSE", real_response, Fore.GREEN)
        print_section(
            f"OBFUSCATED RESPONSE  (τ={tau:.3f}, domain={domain})",
            obfu_response,
            Fore.YELLOW
        )

        print()
        print(Fore.CYAN + "═" * 60)
        print(Fore.CYAN + "  CORRECTNESS CHECK")
        print(Fore.CYAN + "═" * 60)
        print(Style.RESET_ALL)
        print(f"  Extracted from real response  : "
              f"{Fore.WHITE}{orig_ans}{Style.RESET_ALL}")
        print(f"  Extracted from obfuscated     : "
              f"{Fore.WHITE}{obfu_ans}{Style.RESET_ALL}")
        print()

        if is_correct:
            print(f"  {Fore.GREEN}✓ PASS — answer preserved.{Style.RESET_ALL}")
            print(f"  {Fore.GREEN}  ITRO corrupted the reasoning path "
                  f"without changing the answer.{Style.RESET_ALL}")
        else:
            print(f"  {Fore.RED}✗ FAIL — answer may have changed.{Style.RESET_ALL}")
            print(f"  {Fore.RED}  ITRO prompt needs adjustment for "
                  f"domain '{domain}' at τ={tau:.3f}.{Style.RESET_ALL}")

        print(Style.RESET_ALL)
        print()


if __name__ == "__main__":
    run()