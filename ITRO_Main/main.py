# main.py — ITRO_Main CLI entry point
#
# Usage:
#   python main.py datasets   → generate all three datasets
#   python main.py train      → train all three student models
#   python main.py eval       → evaluate all four models
#   python main.py all        → run all three stages in sequence
#
# Each stage saves output to disk before the next begins.
# If a stage crashes, restart only that stage — not from the beginning.
#
# Typical run order on Sol/vast.ai:
#   python main.py datasets   (4-8 hours on A100)
#   python main.py train      (18-24 hours on A100)
#   python main.py eval       (1-2 hours on A100)

import sys
import argparse


def run_datasets():
    print("\n" + "═" * 60)
    print("  STAGE 1 — Dataset Generation")
    print("  Generating 2000 × 3 datasets from GSM8K")
    print("═" * 60)
    from dataset_generator import DatasetGenerator
    gen = DatasetGenerator()
    gen.run()


def run_train():
    print("\n" + "═" * 60)
    print("  STAGE 2 — Student Model Training")
    print("  Training 3 student models on 3 datasets")
    print("═" * 60)
    from trainer import train_all
    train_all()


def run_eval():
    print("\n" + "═" * 60)
    print("  STAGE 3 — Evaluation")
    print("  Evaluating 4 models on GSM8K test set")
    print("═" * 60)
    from evaluator import evaluate_all
    evaluate_all()


def run_all():
    print("\n" + "═" * 60)
    print("  ITRO_Main — Full Experiment Pipeline")
    print("  Stages: datasets → train → eval")
    print("═" * 60)
    run_datasets()
    run_train()
    run_eval()
    print("\n  ✓ Full experiment complete.")
    print(f"  Results in: results/scores.json\n")


def main():
    parser = argparse.ArgumentParser(
        prog="main.py",
        description="ITRO_Main — ADHD distillation experiment pipeline",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog=(
            "Stages:\n"
            "  datasets  Generate clean, ADHD-treated, and no-CoT datasets\n"
            "  train     Train Student-Baseline, Student-ADHD, Student-NoCoT\n"
            "  eval      Evaluate all 4 models on GSM8K test set\n"
            "  all       Run all three stages sequentially\n\n"
            "Examples:\n"
            "  python main.py datasets\n"
            "  python main.py train\n"
            "  python main.py eval\n"
            "  python main.py all\n"
        )
    )

    parser.add_argument(
        "stage",
        choices=["datasets", "train", "eval", "all"],
        help="Which stage to run"
    )

    args = parser.parse_args()

    stage_map = {
        "datasets": run_datasets,
        "train":    run_train,
        "eval":     run_eval,
        "all":      run_all,
    }

    stage_map[args.stage]()


if __name__ == "__main__":
    main()