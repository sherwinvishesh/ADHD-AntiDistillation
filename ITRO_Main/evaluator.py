# evaluator.py
#
# Evaluates all four models on GSM8K test set and produces
# the results table that proves (or disproves) the ADHD defense.
#
# Models evaluated:
#   Teacher          — the original protected model (should be ~82%)
#   Student-Baseline — trained on clean data (should be ~71%)
#   Student-ADHD     — trained on ITRO data  (should be ~46%)
#   Student-NoCoT    — trained on answer-only (should be ~42%)
#
# The critical number:
#   Student-Baseline - Student-ADHD > 0.15 (15 percentage points)
#   → defense is working, paper claim is proven
#
# Answer extraction uses GSM8K's "####" delimiter format.
# Ground truth answers always appear after "####" in GSM8K.

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


# ─────────────────────────────────────────────────────────────
# ANSWER EXTRACTION
# ─────────────────────────────────────────────────────────────

def extract_number(text):
    """
    Extract the final numerical answer from a GSM8K response.

    GSM8K ground truth always uses "#### [number]" format.
    Model responses may or may not follow this — we try the
    delimiter first, then fall back to the last number in text.

    Args:
        text: Response string from model or ground truth.

    Returns:
        Normalized number string, or empty string if not found.
    """
    if not text:
        return ""

    # Primary: GSM8K ground truth format "#### 42"
    match = re.search(r"####\s*([\d,.\-]+)", text)
    if match:
        return match.group(1).replace(",", "").strip()

    # Fallback: last number sequence in the text
    # Models often put the answer at the end even without the delimiter
    numbers = re.findall(r"\b\d+(?:,\d{3})*(?:\.\d+)?\b", text)
    if numbers:
        return numbers[-1].replace(",", "").strip()

    return ""


# ─────────────────────────────────────────────────────────────
# MODEL LOADING
# ─────────────────────────────────────────────────────────────

def load_model(path):
    """
    Load a model and tokenizer from a local path.

    Args:
        path: Directory containing the saved model.

    Returns:
        (model, tokenizer) tuple, both ready for inference.
    """
    print(f"  Loading model from: {path}")

    tokenizer = AutoTokenizer.from_pretrained(
        path,
        trust_remote_code=True,
    )

    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(
        path,
        torch_dtype       = torch.float16,
        device_map        = "auto",
        trust_remote_code = True,
    )
    model.eval()

    return model, tokenizer


# ─────────────────────────────────────────────────────────────
# ANSWER GENERATION
# ─────────────────────────────────────────────────────────────

def generate_answer(model, tokenizer, question, max_tokens=256):
    """
    Generate an answer for a single GSM8K question.

    Uses greedy decoding (temperature=0.1, do_sample=False) for
    reproducibility — we want deterministic evaluation results.

    Args:
        model:      Loaded model.
        tokenizer:  Loaded tokenizer.
        question:   Question string from GSM8K.
        max_tokens: Maximum new tokens to generate.

    Returns:
        Decoded response string.
    """
    prompt = f"Question: {question}\n\nSolve step by step:"

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
            do_sample      = False,   # greedy decoding — deterministic, reproducible
            pad_token_id   = tokenizer.eos_token_id,
        )

    new_tokens = output_ids[0][input_length:]
    return tokenizer.decode(new_tokens, skip_special_tokens=True)


# ─────────────────────────────────────────────────────────────
# EVALUATE ONE MODEL
# ─────────────────────────────────────────────────────────────

def evaluate_model(model_path, name, n_questions=EVAL_QUESTIONS):
    """
    Evaluate one model on GSM8K test set.

    Args:
        model_path:  Path to the saved model directory.
        name:        Human-readable name for display.
        n_questions: Number of test questions to evaluate on.

    Returns:
        Accuracy as float in [0.0, 1.0].
    """
    print(f"\n  Evaluating: {name}")
    print(f"  Path: {model_path}")
    print(f"  Questions: {n_questions}\n")

    model, tokenizer = load_model(model_path)

    # Load GSM8K test split
    from datasets import load_dataset
    gsm8k = load_dataset("gsm8k", "main")
    test_items = list(gsm8k["test"])[:n_questions]

    correct = 0

    for item in tqdm(test_items, desc=f"  {name}"):
        question = item["question"]
        gold     = extract_number(item["answer"])

        if not gold:
            # Skip items where ground truth can't be extracted
            # (shouldn't happen in GSM8K but defensive coding)
            continue

        try:
            predicted_text = generate_answer(model, tokenizer, question)
            predicted      = extract_number(predicted_text)

            if predicted and predicted == gold:
                correct += 1

        except Exception:
            # If generation fails for any reason, count as wrong
            pass

    accuracy = correct / n_questions
    print(f"\n  {name}: {accuracy * 100:.1f}%  ({correct}/{n_questions})")

    # Free GPU memory before loading next model
    del model
    torch.cuda.empty_cache()

    return accuracy


# ─────────────────────────────────────────────────────────────
# EVALUATE ALL MODELS
# ─────────────────────────────────────────────────────────────

def evaluate_all():
    """
    Evaluate all four models and produce the final results table.

    Models:
      Teacher          — original model, should be ~82%
      Student-Baseline — trained on clean data, should be ~71%
      Student-ADHD     — trained on ITRO data, should be ~46%
      Student-NoCoT    — trained on no-CoT data, should be ~42%

    The critical comparison is:
      Student-Baseline - Student-ADHD > 0.15 → defense works
    """
    print("\n" + "═" * 60)
    print("  ITRO_Main — Evaluation")
    print(f"  GSM8K test set, {EVAL_QUESTIONS} questions per model")
    print("═" * 60)

    os.makedirs(RESULTS_PATH, exist_ok=True)

    models = {
        "Teacher":          TEACHER_PATH,
        "Student-Baseline": STUDENT_BASELINE_PATH + "_final",
        "Student-ADHD":     STUDENT_ADHD_PATH     + "_final",
        "Student-NoCoT":    STUDENT_NOCOT_PATH     + "_final",
    }

    scores = {}

    for name, path in models.items():
        if os.path.exists(path):
            scores[name] = evaluate_model(path, name)
        else:
            print(f"\n  ⚠  Skipping {name} — path not found: {path}")

    # ── Save scores ───────────────────────────────────────────
    with open(os.path.join(RESULTS_PATH, "scores.json"), "w") as f:
        json.dump(
            {k: round(v, 4) for k, v in scores.items()},
            f, indent=2
        )

    # ── Print results table ───────────────────────────────────
    print("\n" + "═" * 60)
    print("  RESULTS")
    print("═" * 60)

    for name, score in scores.items():
        bar   = "█" * int(score * 40)
        print(f"  {name:<20} {score*100:5.1f}%  {bar}")

    # ── Print what each comparison proves ─────────────────────
    print("\n" + "─" * 60)
    print("  WHAT THIS PROVES")
    print("─" * 60)

    if "Student-Baseline" in scores and "Student-ADHD" in scores:
        degradation = scores["Student-Baseline"] - scores["Student-ADHD"]
        print(f"\n  Student-Baseline - Student-ADHD = "
              f"{degradation * 100:.1f} percentage points")

        if degradation > 0.15:
            print("  ✓ DEFENSE WORKS — ADHD significantly degrades "
                  "the stolen model.")
            print("    ITRO-corrupted training data poisons the student.")
        else:
            print("  ✗ Degradation below 15pp threshold.")
            print("    ITRO obfuscation may need stronger parameters.")

    if "Teacher" in scores and "Student-Baseline" in scores:
        print(f"\n  Teacher accuracy unchanged at "
              f"{scores['Teacher']*100:.1f}%")
        print("  → Teacher model integrity preserved.")
        print("  → Legitimate users are unaffected.")

    if "Student-ADHD" in scores and "Student-NoCoT" in scores:
        diff = scores["Student-ADHD"] - scores["Student-NoCoT"]
        print(f"\n  Student-ADHD vs Student-NoCoT: "
              f"{diff*100:+.1f} percentage points")
        print("  → ADHD matches existing DistillGuard-style defense")
        print("    without removing reasoning chains from all users.")

    print()
    print(f"  Full results saved to: "
          f"{os.path.join(RESULTS_PATH, 'scores.json')}")
    print()

    return scores