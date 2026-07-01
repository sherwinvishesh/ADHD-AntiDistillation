# main.py — SPECTRE_Test
# Thin batch-testing harness: imports SPECTRE (no pipeline logic of its own),
# lets you pick a provider and a dataset, runs every question through the
# pipeline, and writes <dataset>_spectre_answers.json.

import argparse
import glob
import os
import sys

from colorama import Fore, Style, init
from dotenv import load_dotenv
from tqdm import tqdm

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(_HERE)
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import SPECTRE
from dataset_io import load_dataset, write_results, resolve_dataset_path

init(autoreset=True)
load_dotenv(os.path.join(_HERE, ".env"))

DATASETS_DIR = os.path.join(_HERE, "datasets")


def print_banner():
    print()
    print(Fore.CYAN + Style.BRIGHT + "  SPECTRE_Test — batch evaluation harness")
    print(Style.RESET_ALL)
    print("  Imports SPECTRE as-is (no logic of its own). Picks a provider and")
    print("  a dataset, runs every question through the SPECTRE pipeline, and")
    print("  writes <dataset>_spectre_answers.json next to the dataset file.")
    print()


def select_provider():
    # SPECTRE_Test has its own independent SPECTRE_DEFAULT_PROVIDER (from
    # SPECTRE_Test/.env, loaded above) — distinct from SPECTRE's own default
    # in SPECTRE/.env. Resolved through the same alias table via
    # resolve_provider_key.
    default_key = SPECTRE.resolve_provider_key(os.getenv("SPECTRE_DEFAULT_PROVIDER"))
    if default_key is not None:
        provider = SPECTRE.AVAILABLE_PROVIDERS[default_key]()
        print(f"  {Fore.WHITE + Style.DIM}Using default provider from .env "
              f"(SPECTRE_DEFAULT_PROVIDER set){Style.RESET_ALL}")
        return provider

    print(Fore.WHITE + Style.BRIGHT + "  SELECT A PROVIDER" + Style.RESET_ALL)
    print()
    for key, label in SPECTRE.list_providers():
        print(f"    [{key}]  {label}")
    print()

    while True:
        choice = input("  Enter choice: ").strip()
        try:
            return SPECTRE.get_provider(choice)
        except ValueError as e:
            print(f"  {Fore.RED}{e}{Style.RESET_ALL}")


DETAIL_LEVELS = {"1": ("Detailed", True), "2": ("Simple", False)}
_DETAIL_ALIASES = {
    "1": "1", "detailed": "1", "full": "1",
    "2": "2", "simple": "2", "non-detailed": "2", "nondetailed": "2",
}


def resolve_detail_key(value):
    if not value:
        return None
    return _DETAIL_ALIASES.get(str(value).strip().lower())


def select_detail_level():
    print(Fore.WHITE + Style.BRIGHT + "  SELECT ANSWER DETAIL" + Style.RESET_ALL)
    print()
    print(f"    [1]  {Fore.WHITE}Detailed{Style.RESET_ALL}")
    print(f"         {Fore.WHITE + Style.DIM}full pipeline breakdown per question — "
          f"clean response, GHOST ranking, selected variant, correctness "
          f"attempts{Style.RESET_ALL}")
    print()
    print(f"    [2]  {Fore.WHITE}Simple{Style.RESET_ALL}")
    print(f"         {Fore.WHITE + Style.DIM}just the question and the final answer, "
          f"one block per question{Style.RESET_ALL}")
    print()

    while True:
        choice = input("  Enter choice (1 or 2): ").strip()
        key = resolve_detail_key(choice)
        if key is not None:
            return DETAIL_LEVELS[key][1]
        print(f"  {Fore.RED}Please enter 1 or 2.{Style.RESET_ALL}")


def select_dataset():
    files = sorted(glob.glob(os.path.join(DATASETS_DIR, "*.json")))

    print(Fore.WHITE + Style.BRIGHT + "  SELECT A DATASET" + Style.RESET_ALL)
    print()
    for i, path in enumerate(files, start=1):
        print(f"    [{i}]  {os.path.basename(path)}")
    custom_key = len(files) + 1
    print(f"    [{custom_key}]  Enter a filename or path")
    print()

    while True:
        choice = input("  Enter choice: ").strip()
        if choice.isdigit():
            idx = int(choice)
            if 1 <= idx <= len(files):
                return files[idx - 1]
            if idx == custom_key:
                path = input("  Enter dataset filename or path: ").strip()
                try:
                    return resolve_dataset_path(path)
                except FileNotFoundError as e:
                    print(f"  {Fore.RED}{e}{Style.RESET_ALL}")
                    continue
        print(f"  {Fore.RED}Please enter a number from the list.{Style.RESET_ALL}")


def run_batch(provider, dataset_path, limit=None, detailed=True):
    questions = load_dataset(dataset_path)
    if limit is not None:
        questions = questions[:limit]

    results = []
    safety_valve_count = 0
    attempts_total = 0
    error_count = 0

    for question in tqdm(questions, desc="Running SPECTRE pipeline", unit="q"):
        result = SPECTRE.run_pipeline(question, provider, mode="clean")

        if result is None:
            error_count += 1
            results.append({"question": question, "error": "pipeline_failed"})
            continue

        if result["safety_valve_triggered"]:
            safety_valve_count += 1
        attempts_total += result["attempts"]

        if detailed:
            selected = result["selected_variant"]
            results.append({
                "question":               question,
                "clean_response":         result["clean_response"],
                "ranking":                result["ranking"],
                "ghost_reasoning":        result["ghost_result"].get("reasoning") if result["ghost_result"] else None,
                "selected_variant_id":    selected["transformation_id"] if selected else None,
                "selected_variant_name":  selected["transformation_name"] if selected else None,
                "attempts":               result["attempts"],
                "safety_valve_triggered": result["safety_valve_triggered"],
                "final_response":         result["final_response"],
            })
        else:
            results.append({
                "question": question,
                "answer":   result["final_response"],
            })

    n = len(questions)
    n_scored = n - error_count
    summary = {
        "provider":                  provider.name,
        "dataset":                   os.path.basename(dataset_path),
        "count":                     n,
        "errors":                   error_count,
        "safety_valve_trigger_rate": (safety_valve_count / n_scored) if n_scored else None,
        "avg_attempts":              (attempts_total / n_scored) if n_scored else None,
    }

    return results, summary


def main():
    parser = argparse.ArgumentParser(
        prog="main.py",
        description="SPECTRE_Test — batch evaluation harness for SPECTRE",
    )
    parser.add_argument("-p", "--provider", help="Provider key/name (1, 2, claude, gemini)")
    parser.add_argument("-d", "--dataset",
                         help="Dataset filename (looked up in datasets/) or a full path")
    parser.add_argument("--detail", choices=["1", "2", "detailed", "simple"],
                         help="Answer detail: 'detailed' (full pipeline breakdown) "
                              "or 'simple' (question + answer only)")
    parser.add_argument("--limit", type=int, default=None,
                         help="Only process the first N questions (useful for a quick run)")
    args = parser.parse_args()

    print_banner()

    provider = SPECTRE.get_provider(args.provider) if args.provider else select_provider()
    provider.check_api_key()
    print(Fore.GREEN + f"  ✓ {provider.name} — ready.")
    print(Style.RESET_ALL)

    if args.dataset:
        try:
            dataset_path = resolve_dataset_path(args.dataset)
        except FileNotFoundError as e:
            print(f"  {Fore.RED}{e}{Style.RESET_ALL}")
            sys.exit(1)
    else:
        dataset_path = select_dataset()
    print(f"  Dataset: {Fore.YELLOW}{os.path.basename(dataset_path)}{Style.RESET_ALL}")
    print()

    detail_key = resolve_detail_key(args.detail)
    detailed = DETAIL_LEVELS[detail_key][1] if detail_key else select_detail_level()
    print()

    results, summary = run_batch(provider, dataset_path, limit=args.limit, detailed=detailed)
    out_path = write_results(dataset_path, results, summary)

    print()
    print(Fore.CYAN + Style.BRIGHT + "  SUMMARY" + Style.RESET_ALL)
    for key, value in summary.items():
        print(f"    {key:28s}: {value}")
    print()
    print(f"  {Fore.GREEN}Wrote {out_path}{Style.RESET_ALL}")
    print()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n  Interrupted.\n")
        sys.exit(0)
