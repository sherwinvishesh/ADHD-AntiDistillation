# dataset_generator.py
#
# RESUME-SAFE: Each generate_X() checks if its output file already
# exists and is complete. If yes, it skips entirely. This means
# you can re-submit the same job script after a 12-hour kill and
# it picks up exactly where it left off — no wasted compute.

import os
import sys
import json
import torch
from tqdm import tqdm
from transformers import AutoTokenizer, AutoModelForCausalLM

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "core"))

from itro_engine         import build_obfuscation_prompt
from domain_detector     import detect_domain
from tau_system          import compute_tau
from correctness_checker import check_correctness

from config import (
    TEACHER_PATH, N_SAMPLES,
    DATASET_A_PATH, DATASET_B_PATH, DATASET_C_PATH,
    RESULTS_PATH,
)


def _is_complete(path, expected_count):
    if not os.path.exists(path):
        return False, None
    try:
        with open(path, "r") as f:
            data = json.load(f)
        if len(data) >= expected_count:
            return True, data
        return False, None
    except Exception:
        return False, None


class TeacherProvider:
    def __init__(self, generate_fn):
        self._generate = generate_fn

    def call(self, prompt, max_tokens=512):
        return self._generate(prompt, max_tokens=max_tokens, strict=True)


class DatasetGenerator:

    def __init__(self):
        print(f"\n  Loading teacher model from: {TEACHER_PATH}")
        print(f"  This takes ~20-30 seconds...\n")

        self.tokenizer = AutoTokenizer.from_pretrained(
            TEACHER_PATH,
            trust_remote_code=True,
        )

        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token

        self.model = AutoModelForCausalLM.from_pretrained(
            TEACHER_PATH,
            dtype             = torch.float16,
            device_map        = "auto",
            trust_remote_code = True,
        )
        self.model.eval()

        vram = torch.cuda.memory_allocated(0) / 1e9
        print(f"  ✓ Teacher model loaded. VRAM used: {vram:.1f} GB\n")

        self.provider = TeacherProvider(self._generate)

    def _generate(self, prompt, max_tokens=512, strict=False):
        messages = [{"role": "user", "content": prompt}]
        text = self.tokenizer.apply_chat_template(
            messages,
            tokenize              = False,
            add_generation_prompt = True,
        )

        inputs = self.tokenizer(
            text,
            return_tensors = "pt",
        ).to("cuda")

        input_length = inputs["input_ids"].shape[1]

        gen_kwargs = {
            "max_new_tokens": max_tokens,
            "pad_token_id":   self.tokenizer.eos_token_id,
        }

        if strict:
            gen_kwargs.update({
                "temperature": 0.1,
                "do_sample":   True,
            })
        else:
            gen_kwargs.update({
                "temperature":        0.7,
                "top_p":              0.9,
                "repetition_penalty": 1.1,
                "do_sample":          True,
            })

        with torch.no_grad():
            output_ids = self.model.generate(**inputs, **gen_kwargs)

        new_tokens = output_ids[0][input_length:]
        response   = self.tokenizer.decode(
            new_tokens,
            skip_special_tokens=True,
        )

        return response.strip()

    def _format_entry(self, question, response):
        return {
            "input":  f"Question: {question}",
            "output": response,
        }

    def generate_A(self, questions):
        print("\n" + "═" * 60)
        print("  DATASET A — Clean (control group)")
        print("═" * 60)

        complete, data = _is_complete(DATASET_A_PATH, N_SAMPLES)
        if complete:
            print(f"\n  ✓ Already complete ({len(data)} entries). Skipping.\n")
            return data

        print("  Teacher answers normally. No defense active.\n")

        entries = []
        for question in tqdm(questions, desc="  Dataset A"):
            prompt   = f"Solve this step by step:\n{question}"
            response = self._generate(prompt, max_tokens=512)
            entries.append(self._format_entry(question, response))

        os.makedirs("datasets", exist_ok=True)
        with open(DATASET_A_PATH, "w") as f:
            json.dump(entries, f, indent=2)

        print(f"\n  ✓ Dataset A saved: {len(entries)} entries → {DATASET_A_PATH}")
        return entries

    def generate_B(self, dataset_A):
        print("\n" + "═" * 60)
        print("  DATASET B — ADHD-Treated (experimental group)")
        print("═" * 60)

        complete, data = _is_complete(DATASET_B_PATH, N_SAMPLES)
        if complete:
            print(f"\n  ✓ Already complete ({len(data)} entries). Skipping.\n")
            return data

        print("  ITRO corrupts reasoning. Final answer preserved.")
        print("  Checkpointing every 100 questions.\n")

        checkpoint_path = "datasets/dataset_B_checkpoint.json"

        if os.path.exists(checkpoint_path):
            with open(checkpoint_path, "r") as f:
                checkpoint = json.load(f)
            entries   = checkpoint["entries"]
            preserved = checkpoint["preserved"]
            fallbacks = checkpoint["fallbacks"]
            start_idx = len(entries)
            print(f"  ✓ Checkpoint found — resuming from question {start_idx} "
                  f"of {len(dataset_A)}")
            print(f"    Preserved so far: {preserved}, Fallbacks: {fallbacks}\n")
        else:
            entries   = []
            preserved = 0
            fallbacks = 0
            start_idx = 0
            print(f"  Starting fresh — {len(dataset_A)} questions to process\n")

        for i, item in enumerate(
            tqdm(dataset_A[start_idx:],
                 desc    = "  Dataset B",
                 initial = start_idx,
                 total   = len(dataset_A)),
            start = start_idx
        ):
            question = item["input"].replace("Question: ", "")
            original = item["output"]

            try:
                domain = detect_domain(
                    query_text    = question,
                    response_text = original,
                    provider      = self.provider,
                    verbose       = False,
                )

                tau = compute_tau(
                    query_text = question,
                    domain     = domain,
                    provider   = self.provider,
                    verbose    = False,
                )

                obfu_prompt = build_obfuscation_prompt(original, domain, tau)
                obfuscated  = self._generate(obfu_prompt, max_tokens=700)

                is_ok, _, _ = check_correctness(
                    original, obfuscated, domain, self.provider
                )

                if is_ok:
                    final = obfuscated
                    preserved += 1
                else:
                    final = original
                    fallbacks += 1

            except Exception:
                final  = original
                domain = "unknown"
                tau    = 0.0
                fallbacks += 1

            entry = self._format_entry(question, final)
            entry["tau"]    = round(tau, 4)
            entry["domain"] = domain
            entries.append(entry)

            if len(entries) % 100 == 0:
                os.makedirs("datasets", exist_ok=True)
                with open(checkpoint_path, "w") as f:
                    json.dump({
                        "entries":   entries,
                        "preserved": preserved,
                        "fallbacks": fallbacks,
                    }, f)
                rate_so_far = preserved / len(entries) * 100
                tqdm.write(f"  [checkpoint] {len(entries)}/{len(dataset_A)} done — "
                           f"preservation rate so far: {rate_so_far:.1f}%")

        total = len(dataset_A)
        rate  = preserved / total * 100 if total > 0 else 0.0

        print(f"\n  Preservation rate : {rate:.1f}%")
        print(f"  Obfuscated used   : {preserved}")
        print(f"  Fallbacks (orig.) : {fallbacks}")

        os.makedirs(RESULTS_PATH, exist_ok=True)
        with open(os.path.join(RESULTS_PATH, "preservation.json"), "w") as f:
            json.dump({
                "rate":      round(rate, 2),
                "preserved": preserved,
                "fallbacks": fallbacks,
                "total":     total,
            }, f, indent=2)

        os.makedirs("datasets", exist_ok=True)
        with open(DATASET_B_PATH, "w") as f:
            json.dump(entries, f, indent=2)

        print(f"  ✓ Dataset B saved: {len(entries)} entries → {DATASET_B_PATH}")

        if os.path.exists(checkpoint_path):
            os.remove(checkpoint_path)
            print(f"  ✓ Checkpoint cleaned up")

        return entries

    def generate_C(self, dataset_A):
        print("\n" + "═" * 60)
        print("  DATASET C — No-CoT (comparison group)")
        print("═" * 60)

        complete, data = _is_complete(DATASET_C_PATH, N_SAMPLES)
        if complete:
            print(f"\n  ✓ Already complete ({len(data)} entries). Skipping.\n")
            return data

        print("  Final answer only. No reasoning chain returned.\n")

        entries = []
        for item in tqdm(dataset_A, desc="  Dataset C"):
            question = item["input"].replace("Question: ", "")
            prompt   = f"Give only the final answer with no steps:\n{question}"
            answer   = self._generate(prompt, max_tokens=80, strict=True)
            entries.append(self._format_entry(question, answer))

        os.makedirs("datasets", exist_ok=True)
        with open(DATASET_C_PATH, "w") as f:
            json.dump(entries, f, indent=2)

        print(f"\n  ✓ Dataset C saved: {len(entries)} entries → {DATASET_C_PATH}")
        return entries

    def run(self):
        print("\n" + "═" * 60)
        print("  ITRO_Main — Dataset Generation")
        print(f"  Target: {N_SAMPLES} questions × 3 datasets")
        print("  Re-submit safe: completed datasets are skipped.")
        print("═" * 60)

        print("\n  Loading GSM8K training split from HuggingFace...")
        from datasets import load_dataset
        gsm8k     = load_dataset("gsm8k", "main")
        questions = gsm8k["train"]["question"][:N_SAMPLES]
        print(f"  ✓ {len(questions)} questions loaded\n")

        dataset_A = self.generate_A(questions)
        dataset_B = self.generate_B(dataset_A)
        dataset_C = self.generate_C(dataset_A)

        print("\n" + "═" * 60)
        print("  GENERATION COMPLETE")
        print("═" * 60)
        print(f"  Dataset A (clean)  : {len(dataset_A):>5} entries → {DATASET_A_PATH}")
        print(f"  Dataset B (ADHD)   : {len(dataset_B):>5} entries → {DATASET_B_PATH}")
        print(f"  Dataset C (no-CoT) : {len(dataset_C):>5} entries → {DATASET_C_PATH}")
        print()
        print("  Next step: python main.py train-baseline")
        print()