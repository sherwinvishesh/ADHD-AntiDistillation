# trainer.py
#
# Trains three student models — one per dataset.
# The training configuration is IDENTICAL for all three runs.
# Only the training data and output path differ.
#
# This is the core of the controlled experiment:
# identical architecture + identical training setup + different data
# → any difference in benchmark scores must come from the data.
#
# Student model: Qwen2.5-3B-Instruct (smaller than teacher 7B)
# Training objective: standard causal language modeling
# Format: same JSON format used in all three datasets

import os
import json
import torch
from transformers import (
    AutoTokenizer,
    AutoModelForCausalLM,
    TrainingArguments,
    Trainer,
    DataCollatorForLanguageModeling,
)
from torch.utils.data import Dataset

from config import (
    STUDENT_PATH,
    DATASET_A_PATH, DATASET_B_PATH, DATASET_C_PATH,
    STUDENT_BASELINE_PATH, STUDENT_ADHD_PATH, STUDENT_NOCOT_PATH,
    EPOCHS, BATCH_SIZE, GRAD_ACCUM, LEARNING_RATE, MAX_SEQ_LEN,
)


# ─────────────────────────────────────────────────────────────
# DATASET CLASS
# ─────────────────────────────────────────────────────────────

class ITRODataset(Dataset):
    """
    Simple PyTorch dataset that wraps the tokenized training data.
    Used by HuggingFace Trainer.
    """

    def __init__(self, encodings):
        self.encodings = encodings

    def __len__(self):
        return len(self.encodings["input_ids"])

    def __getitem__(self, idx):
        return {
            "input_ids":      torch.tensor(self.encodings["input_ids"][idx]),
            "attention_mask": torch.tensor(self.encodings["attention_mask"][idx]),
            # "labels":         torch.tensor(self.encodings["input_ids"][idx]),
            # labels = input_ids is the standard causal LM objective.
            # The model learns to predict each token from the previous ones.
        }


# ─────────────────────────────────────────────────────────────
# LOAD AND TOKENIZE
# ─────────────────────────────────────────────────────────────

def load_and_tokenize(filepath, tokenizer):
    """
    Load a dataset JSON file and tokenize it for causal LM training.

    Each entry has "input" and "output" fields. We concatenate them
    with a double newline so the model sees:
        "Question: [question]\n\n[response]"

    This teaches the model to produce the response when given the question.

    Args:
        filepath:  Path to the JSON dataset file.
        tokenizer: Loaded tokenizer for the student model.

    Returns:
        ITRODataset ready for HuggingFace Trainer.
    """
    with open(filepath, "r") as f:
        data = json.load(f)

    texts = [
        item["input"] + "\n\n" + item["output"]
        for item in data
    ]

    print(f"  Tokenizing {len(texts)} examples (max_length={MAX_SEQ_LEN})...")

    encodings = tokenizer(
        texts,
        truncation  = True,
        max_length  = MAX_SEQ_LEN,
        padding     = "max_length",
        return_tensors = None,  # return plain lists for Dataset class
    )

    return ITRODataset(encodings)


# ─────────────────────────────────────────────────────────────
# TRAIN STUDENT
# ─────────────────────────────────────────────────────────────

def train_student(dataset_path, output_path, run_name):
    """
    Train one student model on one dataset.

    Called three times with different data and output paths.
    Training arguments are IDENTICAL every time — this is what
    makes the experiment scientifically valid.

    Args:
        dataset_path: Path to the JSON dataset file.
        output_path:  Where to save checkpoints during training.
        run_name:     Human-readable name for logging
                      (e.g., "Student-Baseline", "Student-ADHD").
    """
    print("\n" + "═" * 60)
    print(f"  TRAINING: {run_name}")
    print(f"  Data   : {dataset_path}")
    print(f"  Output : {output_path}_final")
    print("═" * 60 + "\n")

    # ── Load fresh student model ──────────────────────────────
    # Fresh load every time — no contamination between runs.
    print(f"  Loading student model from: {STUDENT_PATH}")

    tokenizer = AutoTokenizer.from_pretrained(
        STUDENT_PATH,
        trust_remote_code=True,
    )

    # Qwen needs pad_token set explicitly
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(
        STUDENT_PATH,
        dtype       = torch.bfloat16, 
        device_map        = "auto",
        trust_remote_code = True,
    )

    print(f"  ✓ Student model loaded\n")

    # ── Load and tokenize data ───────────────────────────────
    dataset = load_and_tokenize(dataset_path, tokenizer)

    # ── Training arguments ────────────────────────────────────
    # These are IDENTICAL for all three training runs.
    # If you change anything here, change it for all three or
    # the comparison becomes invalid.
    training_args = TrainingArguments(
        output_dir                  = output_path,
        num_train_epochs            = EPOCHS,
        per_device_train_batch_size = BATCH_SIZE,
        gradient_accumulation_steps = GRAD_ACCUM,
        learning_rate               = LEARNING_RATE,
        warmup_ratio                = 0.10,
        lr_scheduler_type           = "cosine",
        fp16                        = False,
        bf16  = True, 
        logging_steps               = 50,
        save_strategy               = "epoch",
        report_to                   = "none",    # no wandb/tensorboard
        dataloader_pin_memory       = False,     # avoids some GPU issues
        remove_unused_columns       = False,
    )

    # ── Trainer ───────────────────────────────────────────────
    trainer = Trainer(
        model         = model,
        args          = training_args,
        train_dataset = dataset,
        data_collator = DataCollatorForLanguageModeling(
            tokenizer = tokenizer,
            mlm       = False,    # causal LM, not masked LM
        ),
    )

    # ── Train ─────────────────────────────────────────────────
    print(f"  Starting training: {EPOCHS} epochs, "
          f"effective batch size {BATCH_SIZE * GRAD_ACCUM}\n")

    trainer.train()

    # ── Save final model ──────────────────────────────────────
    final_path = output_path + "_final"
    os.makedirs(final_path, exist_ok=True)

    model.save_pretrained(final_path)
    tokenizer.save_pretrained(final_path)

    print(f"\n  ✓ {run_name} saved to: {final_path}")


# ─────────────────────────────────────────────────────────────
# TRAIN ALL THREE
# ─────────────────────────────────────────────────────────────

def train_all():
    """
    Train all three student models sequentially.

    Order:
      1. Student-Baseline (trained on clean data)
      2. Student-ADHD     (trained on ITRO-corrupted data)
      3. Student-NoCoT    (trained on answer-only data)

    Each is saved to disk before the next begins.
    If training crashes after one completes, you can comment out
    the completed runs and resume from where you stopped.
    """
    print("\n" + "═" * 60)
    print("  ITRO_Main — Student Model Training")
    print("  3 models × identical config × different data")
    print("═" * 60)

    runs = [
        (DATASET_A_PATH, STUDENT_BASELINE_PATH, "Student-Baseline"),
        (DATASET_B_PATH, STUDENT_ADHD_PATH,     "Student-ADHD"),
        (DATASET_C_PATH, STUDENT_NOCOT_PATH,    "Student-NoCoT"),
    ]

    for dataset_path, output_path, run_name in runs:
        # Check dataset exists before attempting training
        if not os.path.exists(dataset_path):
            print(f"\n  ✗ Dataset not found: {dataset_path}")
            print(f"    Run 'python main.py datasets' first.")
            continue

        train_student(dataset_path, output_path, run_name)

    print("\n" + "═" * 60)
    print("  ALL TRAINING COMPLETE")
    print("═" * 60)
    print()
    print("  Models saved:")
    print(f"    {STUDENT_BASELINE_PATH}_final")
    print(f"    {STUDENT_ADHD_PATH}_final")
    print(f"    {STUDENT_NOCOT_PATH}_final")
    print()
    print("  Next step: python main.py eval")
    print()