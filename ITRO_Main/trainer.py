# trainer.py
#
# Sol 12-hour limit workflow:
#   python main.py train-baseline   (~8 hours)
#   python main.py train-adhd       (~8 hours)
#   python main.py train-nocot      (~8 hours)
#
# Each is resume-safe: if the _final directory already exists, skip.

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


class ITRODataset(Dataset):
    def __init__(self, encodings):
        self.encodings = encodings

    def __len__(self):
        return len(self.encodings["input_ids"])

    def __getitem__(self, idx):
        return {
            "input_ids":      torch.tensor(self.encodings["input_ids"][idx]),
            "attention_mask": torch.tensor(self.encodings["attention_mask"][idx]),
        }


def load_and_tokenize(filepath, tokenizer):
    with open(filepath, "r") as f:
        data = json.load(f)

    texts = [
        item["input"] + "\n\n" + item["output"]
        for item in data
    ]

    print(f"  Tokenizing {len(texts)} examples (max_length={MAX_SEQ_LEN})...")

    encodings = tokenizer(
        texts,
        truncation     = True,
        max_length     = MAX_SEQ_LEN,
        padding        = "max_length",
        return_tensors = None,
    )

    return ITRODataset(encodings)


def _is_trained(output_path):
    final_path = output_path + "_final"
    return os.path.exists(final_path) and os.path.exists(
        os.path.join(final_path, "config.json")
    )


def train_student(dataset_path, output_path, run_name):
    print("\n" + "═" * 60)
    print(f"  TRAINING: {run_name}")
    print(f"  Data   : {dataset_path}")
    print(f"  Output : {output_path}_final")
    print("═" * 60 + "\n")

    if _is_trained(output_path):
        print(f"  ✓ Already trained. Skipping {run_name}.\n")
        return

    if not os.path.exists(dataset_path):
        print(f"\n  ✗ Dataset not found: {dataset_path}")
        print(f"    Run 'python main.py datasets' first.")
        return

    print(f"  Loading student model from: {STUDENT_PATH}")

    tokenizer = AutoTokenizer.from_pretrained(
        STUDENT_PATH,
        trust_remote_code=True,
    )

    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(
        STUDENT_PATH,
        dtype             = torch.bfloat16,
        device_map        = "auto",
        trust_remote_code = True,
    )

    print(f"  ✓ Student model loaded\n")

    dataset = load_and_tokenize(dataset_path, tokenizer)

    training_args = TrainingArguments(
        output_dir                  = output_path,
        num_train_epochs            = EPOCHS,
        per_device_train_batch_size = BATCH_SIZE,
        gradient_accumulation_steps = GRAD_ACCUM,
        learning_rate               = LEARNING_RATE,
        warmup_ratio                = 0.10,
        lr_scheduler_type           = "cosine",
        fp16                        = False,
        bf16                        = True,
        logging_steps               = 50,
        save_strategy               = "no",
        report_to                   = "none",
        dataloader_pin_memory       = False,
        remove_unused_columns       = False,
    )

    trainer = Trainer(
        model         = model,
        args          = training_args,
        train_dataset = dataset,
        data_collator = DataCollatorForLanguageModeling(
            tokenizer = tokenizer,
            mlm       = False,
        ),
    )

    print(f"  Starting training: {EPOCHS} epochs, "
          f"effective batch size {BATCH_SIZE * GRAD_ACCUM}\n")

    trainer.train()

    final_path = output_path + "_final"
    os.makedirs(final_path, exist_ok=True)
    model.save_pretrained(final_path)
    tokenizer.save_pretrained(final_path)

    print(f"\n  ✓ {run_name} saved to: {final_path}")


def train_baseline():
    train_student(DATASET_A_PATH, STUDENT_BASELINE_PATH, "Student-Baseline")


def train_adhd():
    train_student(DATASET_B_PATH, STUDENT_ADHD_PATH, "Student-ADHD")


def train_nocot():
    train_student(DATASET_C_PATH, STUDENT_NOCOT_PATH, "Student-NoCoT")


def train_all():
    train_baseline()
    train_adhd()
    train_nocot()