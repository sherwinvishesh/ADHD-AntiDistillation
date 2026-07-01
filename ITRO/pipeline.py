import sys
from colorama import Fore, Style

from tau_system import compute_tau, get_tau_label
from domain_detector import detect_domain
from itro_engine import build_obfuscation_prompt
from correctness_checker import check_correctness


def _print_step_header(step_num, total, label):
    print(f"  {Fore.WHITE}[{step_num}/{total}]{Style.RESET_ALL} {label}",
          end="", flush=True)


def _print_ok():
    print(f"  {Fore.GREEN}✓{Style.RESET_ALL}")


def _print_err(e):
    print(f"  {Fore.RED}✗  Error: {e}{Style.RESET_ALL}")


def run_pipeline(question, provider, mode="full"):
    """
    Runs the full ITRO pipeline on a question:
      1. Real response          — the provider answers normally.
      2. Domain detection        — classify into one of 8 domains.
      3. Tau (τ) computation     — score obfuscation intensity in [0, 1].
      4. ITRO obfuscation        — build + send the corrupted-reasoning prompt.
      + Correctness check        — safety valve falls back to the real
                                    response if the final answer changed.

    Args:
        question: The user's question/prompt.
        provider: An instantiated BaseProvider (Anthropic/Gemini/Qwen/...).
        mode:     "full" prints step-by-step progress; "clean" stays quiet
                  (used for batch runs so it doesn't fight a progress bar).

    Returns:
        A result dict (real_response, obfu_response, final_response, domain,
        tau, level, is_correct, orig_ans, obfu_ans), or None if either the
        real-response or obfuscation call itself failed outright.
    """
    silent = (mode == "clean")

    # ── Step 1: Real response ────────────────────────────────
    if not silent:
        _print_step_header(1, 4, "Getting real response...          ")
    else:
        print(f"  {Fore.WHITE + Style.DIM}Processing...{Style.RESET_ALL}",
              end="\r", flush=True)

    try:
        real_response = provider.call(question)
        if not silent:
            _print_ok()
    except Exception as e:
        if not silent:
            _print_err(e)
        return None

    # ── Step 2: Domain detection ─────────────────────────────
    if not silent:
        _print_step_header(2, 4, "Detecting domain...               ")
    try:
        domain = detect_domain(
            query_text    = question,
            response_text = real_response,
            provider      = provider,
            verbose       = False
        )
        if not silent:
            _print_ok()
    except Exception as e:
        if not silent:
            _print_err(e)
        domain = "factual_recall"

    # ── Step 3: Tau computation ──────────────────────────────
    if not silent:
        _print_step_header(3, 4, "Computing τ (obfuscation intensity)...")
    try:
        tau   = compute_tau(
            query_text = question,
            domain     = domain,
            provider   = provider,
            verbose    = False
        )
        level = get_tau_label(tau)
        if not silent:
            _print_ok()
    except Exception as e:
        if not silent:
            _print_err(e)
        tau   = 0.5
        level = get_tau_label(tau)

    # ── Step 4: Obfuscation ──────────────────────────────────
    if not silent:
        _print_step_header(4, 4, "Building obfuscated response...   ")
    try:
        obfu_prompt   = build_obfuscation_prompt(real_response, domain, tau)
        obfu_response = provider.call(obfu_prompt)
        if not silent:
            _print_ok()
    except Exception as e:
        if not silent:
            _print_err(e)
        return None

    # ── Correctness check ────────────────────────────────────
    is_correct, orig_ans, obfu_ans = check_correctness(
        real_response, obfu_response, domain, provider
    )

    # Safety valve — if answer corrupted, return real response
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
