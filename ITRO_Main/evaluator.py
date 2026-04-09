import os
import re
import json
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM
from tqdm import tqdm

from config import (
    TEACHER_PATH,
    STUDENT_BASELINE_PATH, STUDENT_ADHD_PATH, STUDENT_NOCOT_PATH,
    RESULTS_PATH, EVAL_QUESTIONS,
)


def extract_number(text):
    if not text:
        return ""
    match = re.search(r"####\s*([\d,.\-]+)", text)
    if match:
        return match.group(1).replace(",", "").strip()
    numbers = re.findall(r"\b\d+(?:,\d{3})*(?:\.\d+)?\b", text)
    if numbers:
        return numbers[-1].replace(",", "").strip()
    return ""


def load_model(path):
    print(f"  Loading model from: {path}")
    tokenizer = AutoTokenizer.from_pretrained(path, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    model = AutoModelForCausalLM.from_pretrained(
        path,
        dtype             = torch.float16,
        device_map        = "auto",
        trust_remote_code = True,
    )
    model.eval()
    return model, tokenizer


def generate_answer(model, tokenizer, question, max_tokens=512):
    prompt = (
        f"Question: {question}\n\n"
        f"Solve this step by step. "
        f"At the end, write your final answer as #### [number]."
    )
    messages = [{"role": "user", "content": prompt}]
    text = tokenizer.apply_chat_template(
        messages,
        tokenize              = False,
        add_generation_prompt = True,
    )
    inputs = tokenizer(text, return_tensors="pt").to("cuda")
    input_length = inputs["input_ids"].shape[1]
    with torch.no_grad():
        output_ids = model.generate(
            **inputs,
            max_new_tokens = max_tokens,
            do_sample      = False,
            pad_token_id   = tokenizer.eos_token_id,
        )
    new_tokens = output_ids[0][input_length:]
    return tokenizer.decode(new_tokens, skip_special_tokens=True)


def _load_scores():
    """Load existing scores from disk, return empty dict if none exist."""
    scores_path = os.path.join(RESULTS_PATH, "scores.json")
    if os.path.exists(scores_path):
        with open(scores_path) as f:
            return json.load(f)
    return {}


def _save_scores(scores):
    """Save scores to disk."""
    os.makedirs(RESULTS_PATH, exist_ok=True)
    scores_path = os.path.join(RESULTS_PATH, "scores.json")
    with open(scores_path, "w") as f:
        json.dump({k: round(v, 4) for k, v in scores.items()}, f, indent=2)


def _print_scores(scores):
    """Print current scores table."""
    print("\n" + "═" * 60)
    print("  RESULTS SO FAR")
    print("═" * 60)
    for name, score in scores.items():
        bar = "█" * int(score * 40)
        print(f"  {name:<25} {score*100:5.1f}%  {bar}")

    if "Student-Baseline" in scores and "Student-ADHD-ITRO" in scores:
        degradation = scores["Student-Baseline"] - scores["Student-ADHD-ITRO"]
        print(f"\n  Student-Baseline - Student-ADHD-ITRO = "
              f"{degradation * 100:.1f} percentage points")
        if degradation > 0.15:
            print("  ✓ DEFENSE WORKS")
        else:
            print("  ✗ Degradation below 15pp threshold")

    if "Student-ADHD-ITRO" in scores and "Student-NoCoT" in scores:
        diff = scores["Student-ADHD-ITRO"] - scores["Student-NoCoT"]
        print(f"  Student-ADHD-ITRO vs Student-NoCoT: {diff*100:+.1f} pp")

    print()


def evaluate_model(model_path, name, n_questions=EVAL_QUESTIONS):
    print(f"\n  Evaluating: {name}")
    print(f"  Path: {model_path}")
    print(f"  Questions: {n_questions}\n")

    model, tokenizer = load_model(model_path)

    from datasets import load_dataset
    gsm8k = load_dataset("gsm8k", "main")
    test_items = list(gsm8k["test"])[:n_questions]

    correct = 0

    for item in tqdm(test_items, desc=f"  {name}"):
        question = item["question"]
        gold     = extract_number(item["answer"])
        if not gold:
            continue
        try:
            predicted_text = generate_answer(model, tokenizer, question)
            predicted      = extract_number(predicted_text)
            if predicted and predicted == gold:
                correct += 1
        except Exception:
            pass

    accuracy = correct / n_questions
    print(f"\n  {name}: {accuracy * 100:.1f}%  ({correct}/{n_questions})")

    del model
    torch.cuda.empty_cache()

    return accuracy


def evaluate_single(model_key):
    """
    Evaluate one model by key. Skips if score already exists.
    Keys: teacher | baseline | adhd | nocot
    """
    name_map = {
        "teacher":  ("Teacher",           TEACHER_PATH),
        "baseline": ("Student-Baseline",  STUDENT_BASELINE_PATH + "_final"),
        "adhd":     ("Student-ADHD-ITRO", STUDENT_ADHD_PATH     + "_final"),
        "nocot":    ("Student-NoCoT",     STUDENT_NOCOT_PATH    + "_final"),
    }

    if model_key not in name_map:
        print(f"  Unknown model: {model_key}")
        print(f"  Choose from: {list(name_map.keys())}")
        return

    display_name, path = name_map[model_key]

    # Load existing scores
    scores = _load_scores()

    # Skip if already evaluated
    if display_name in scores:
        print(f"\n  ✓ {display_name} already evaluated "
              f"({scores[display_name]*100:.1f}%). Skipping.")
        _print_scores(scores)
        return

    # Check model exists
    if not os.path.exists(path):
        print(f"\n  ✗ Model not found: {path}")
        return

    # Run eval
    score = evaluate_model(path, display_name)

    # Save updated scores
    scores[display_name] = score
    _save_scores(scores)
    _print_scores(scores)


def evaluate_all():
    """
    Evaluate all four models. Skips any already in scores.json.
    Re-submit safe — just keeps adding to the scores file.
    """
    print("\n" + "═" * 60)
    print("  ITRO_Main — Evaluation (all models)")
    print("  Resume-safe: already-evaluated models are skipped.")
    print("═" * 60)

    for key in ["teacher", "baseline", "adhd", "nocot"]:
        evaluate_single(key)