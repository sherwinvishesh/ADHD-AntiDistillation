import sys
import argparse


def run_datasets():
    from dataset_generator import DatasetGenerator
    gen = DatasetGenerator()
    gen.run()

def run_train_baseline():
    from trainer import train_baseline
    train_baseline()

def run_train_adhd():
    from trainer import train_adhd
    train_adhd()

def run_train_nocot():
    from trainer import train_nocot
    train_nocot()

def run_train():
    from trainer import train_all
    train_all()

def run_eval():
    from evaluator import evaluate_all
    evaluate_all()

def run_eval_teacher():
    from evaluator import evaluate_single
    evaluate_single("teacher")

def run_eval_baseline():
    from evaluator import evaluate_single
    evaluate_single("baseline")

def run_eval_adhd():
    from evaluator import evaluate_single
    evaluate_single("adhd")

def run_eval_nocot():
    from evaluator import evaluate_single
    evaluate_single("nocot")

def run_all():
    run_datasets()
    run_train()
    run_eval()

def main():
    parser = argparse.ArgumentParser(prog="main.py")
    parser.add_argument(
        "stage",
        choices=[
            "datasets",
            "train-baseline", "train-adhd", "train-nocot", "train",
            "eval",
            "eval-teacher", "eval-baseline", "eval-adhd", "eval-nocot",
            "all",
        ],
    )
    args = parser.parse_args()

    stage_map = {
        "datasets":       run_datasets,
        "train-baseline": run_train_baseline,
        "train-adhd":     run_train_adhd,
        "train-nocot":    run_train_nocot,
        "train":          run_train,
        "eval":           run_eval,
        "eval-teacher":   run_eval_teacher,
        "eval-baseline":  run_eval_baseline,
        "eval-adhd":      run_eval_adhd,
        "eval-nocot":     run_eval_nocot,
        "all":            run_all,
    }

    stage_map[args.stage]()

if __name__ == "__main__":
    main()