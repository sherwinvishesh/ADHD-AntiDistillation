# dataset_generator.py
#
# Generates all three datasets for the ADHD experiment:
#
#   Dataset A — Clean (control group)
#     Teacher answers 2000 questions normally.
#     This is what a real attacker collects if no defense exists.
#
#   Dataset B — ADHD-treated (experimental group)
#     Same questions, but each response passes through ITRO.
#     Reasoning is deliberately corrupted. Final answer preserved.
#     This is what an attacker collects when ADHD is active.
#
#   Dataset C — No-CoT (comparison group)
#     Same questions, but only the final answer is returned.
#     Replicates the best existing defense (DistillGuard CoT removal).
#
# All three datasets share identical JSON format:
#   {"input": "Question: ...", "output": "..."}
# Only the content of "output" differs between datasets.

import os
import sys
import json
import torch
from tqdm import tqdm
from transformers import AutoTokenizer, AutoModelForCausalLM

# ── Add core/ to path so ITRO modules are importable ─────────
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "core"))

from itro_engine       import build_obfuscation_prompt
from domain_detector   import detect_domain
from tau_system        import compute_tau
from correctness_checker import check_correctness

from config import (
    TEACHER_PATH, N_SAMPLES,
    DATASET_A_PATH, DATASET_B_PATH, DATASET_C_PATH,
    RESULTS_PATH,
)


# ─────────────────────────────────────────────────────────────
# PROVIDER WRAPPER
# The core/ modules expect a provider object with a
# .call(prompt, max_tokens) method — same interface as the
# API providers in ITRO_API and ITRO_Local.
# This wrapper makes the local teacher model match that interface.
# ─────────────────────────────────────────────────────────────

class TeacherProvider:
    """
    Wraps the teacher model's generate function to match the
    BaseProvider interface expected by core/ modules.

    The core/ functions (detect_domain, compute_tau, check_correctness)
    all call provider.call(prompt, max_tokens). This class makes the
    teacher model look like a provider to those functions.
    """

    def __init__(self, generate_fn):
        """
        Args:
            generate_fn: The DatasetGenerator._generate method.
                         Signature: (prompt, max_tokens, strict=False) -> str
        """
        self._generate = generate_fn

    def call(self, prompt, max_tokens=512):
        """
        Called by core/ modules for structured outputs:
          - domain classification (~10 tokens)
          - tau scoring (~150 tokens)
          - correctness extraction (~25-80 tokens)

        Uses strict=True (low temperature) for reliable structured output.
        """
        return self._generate(prompt, max_tokens=max_tokens, strict=True)


# ─────────────────────────────────────────────────────────────
# DATASET GENERATOR
# ─────────────────────────────────────────────────────────────

class DatasetGenerator:

    def __init__(self):
        """
        Load the teacher model into GPU memory.
        This happens once and the model stays loaded for
        all three dataset generation passes.
        """
        print(f"\n  Loading teacher model from: {TEACHER_PATH}")
        print(f"  This takes ~20-30 seconds...\n")

        self.tokenizer = AutoTokenizer.from_pretrained(
            TEACHER_PATH,
            trust_remote_code=True,
        )

        # Ensure pad token is set — Qwen uses eos as pad
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token

        self.model = AutoModelForCausalLM.from_pretrained(
            TEACHER_PATH,
            torch_dtype       = torch.float16,
            device_map        = "auto",
            trust_remote_code = True,
        )
        self.model.eval()

        vram = torch.cuda.memory_allocated(0) / 1e9
        print(f"  ✓ Teacher model loaded. VRAM used: {vram:.1f} GB\n")

        # Create the provider wrapper once — reused across all B generation
        self.provider = TeacherProvider(self._generate)

    # ─────────────────────────────────────────────────────────
    # CORE GENERATION METHOD
    # ─────────────────────────────────────────────────────────

    def _generate(self, prompt, max_tokens=512, strict=False):
        """
        Run inference on the teacher model.

        Args:
            prompt:     Plain text prompt (no chat template applied yet).
            max_tokens: Maximum new tokens to generate.
            strict:     If True, use low temperature for structured output
                        (domain classification, tau scoring, extraction).
                        If False, use higher temperature for creative generation
                        (real responses, ITRO obfuscation).

        Returns:
            Decoded response string, whitespace stripped.
        """
        # Apply Qwen2.5-Instruct chat template
        messages = [{"role": "user", "content": prompt}]
        text = self.tokenizer.apply_chat_template(
            messages,
            tokenize              = False,
            add_generation_prompt = True,
        )

        # Tokenize and move to GPU
        inputs = self.tokenizer(
            text,
            return_tensors = "pt",
        ).to("cuda")

        input_length = inputs["input_ids"].shape[1]

        # Generation parameters
        gen_kwargs = {
            "max_new_tokens": max_tokens,
            "pad_token_id":   self.tokenizer.eos_token_id,
        }

        if strict:
            # Low temperature for reliable structured outputs
            # Used for: domain detection, tau scoring, correctness extraction
            gen_kwargs.update({
                "temperature": 0.1,
                "do_sample":   True,
            })
        else:
            # Higher temperature for natural generation
            # Used for: real responses, ITRO obfuscation
            gen_kwargs.update({
                "temperature":         0.7,
                "top_p":               0.9,
                "repetition_penalty":  1.1,
                "do_sample":           True,
            })

        with torch.no_grad():
            output_ids = self.model.generate(**inputs, **gen_kwargs)

        # Decode only the new tokens — strip input from output
        new_tokens = output_ids[0][input_length:]
        response   = self.tokenizer.decode(
            new_tokens,
            skip_special_tokens=True,
        )

        return response.strip()

    # ─────────────────────────────────────────────────────────
    # FORMAT HELPER
    # ─────────────────────────────────────────────────────────

    def _format_entry(self, question, response):
        """
        Format a (question, response) pair into the standard dataset entry.
        Format is IDENTICAL across all three datasets — only content differs.
        """
        return {
            "input":  f"Question: {question}",
            "output": response,
        }

    # ─────────────────────────────────────────────────────────
    # DATASET A — CLEAN (control group)
    # Teacher answers questions normally. No ITRO applied.
    # This is what an attacker collects without any defense.
    # ─────────────────────────────────────────────────────────

    def generate_A(self, questions):
        """
        Generate Dataset A: clean teacher responses.

        Args:
            questions: List of question strings from GSM8K.

        Returns:
            List of {"input": ..., "output": ...} dicts.
        """
        print("\n" + "═" * 60)
        print("  DATASET A — Clean (control group)")
        print("  Teacher answers normally. No defense active.")
        print("═" * 60 + "\n")

        entries = []
        for question in tqdm(questions, desc="  Dataset A"):
            prompt   = f"Solve this step by step:\n{question}"
            response = self._generate(prompt, max_tokens=512)
            entries.append(self._format_entry(question, response))

        # Save to disk
        os.makedirs("datasets", exist_ok=True)
        with open(DATASET_A_PATH, "w") as f:
            json.dump(entries, f, indent=2)

        print(f"\n  ✓ Dataset A saved: {len(entries)} entries → {DATASET_A_PATH}")
        return entries

    # ─────────────────────────────────────────────────────────
    # DATASET B — ADHD-TREATED (experimental group)
    # Each clean response passes through the ITRO pipeline.
    # Reasoning is corrupted. Final answer preserved by checker.
    # This is what an attacker collects when ADHD is active.
    # ─────────────────────────────────────────────────────────

def generate_B(self, dataset_A):
    """
    Generate Dataset B: ADHD-treated responses.

    For each question:
      1. Get the clean response from Dataset A
      2. Detect domain (math_computation, code, etc.)
      3. Compute tau (obfuscation intensity)
      4. Build ITRO obfuscation prompt
      5. Have teacher rewrite its own reasoning badly
      6. Correctness checker verifies final answer preserved
      7. If preserved: save obfuscated. If not: save original (safety valve).

    Checkpoints every 100 questions — if this crashes at question 1800,
    restart and it picks up from the last checkpoint automatically.

    Args:
        dataset_A: List of clean entries from generate_A().

    Returns:
        List of {"input": ..., "output": ..., "tau": ..., "domain": ...} dicts.
    """
    print("\n" + "═" * 60)
    print("  DATASET B — ADHD-Treated (experimental group)")
    print("  ITRO corrupts reasoning. Final answer preserved.")
    print("  Checkpointing every 100 questions.")
    print("═" * 60 + "\n")

    checkpoint_path = "datasets/dataset_B_checkpoint.json"

    # ── Resume from checkpoint if one exists ─────────────────
    # This fires if the job crashed partway through.
    # On a clean first run, no checkpoint exists and we start fresh.
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

    # ── Process questions from start_idx onward ───────────────
    for i, item in enumerate(
        tqdm(dataset_A[start_idx:],
             desc      = "  Dataset B",
             initial   = start_idx,
             total     = len(dataset_A)),
        start = start_idx
    ):
        question = item["input"].replace("Question: ", "")
        original = item["output"]

        try:
            # ── Step 1: Detect domain ─────────────────────────
            domain = detect_domain(
                query_text    = question,
                response_text = original,
                provider      = self.provider,
                verbose       = False,
            )

            # ── Step 2: Compute tau ───────────────────────────
            tau = compute_tau(
                query_text = question,
                domain     = domain,
                provider   = self.provider,
                verbose    = False,
            )

            # ── Step 3: Build ITRO prompt and obfuscate ───────
            obfu_prompt = build_obfuscation_prompt(original, domain, tau)
            obfuscated  = self._generate(obfu_prompt, max_tokens=700)

            # ── Step 4: Correctness check ─────────────────────
            is_ok, _, _ = check_correctness(
                original, obfuscated, domain, self.provider
            )

            if is_ok:
                final = obfuscated
                preserved += 1
            else:
                # Safety valve: answer corrupted — use original
                final = original
                fallbacks += 1

        except Exception as e:
            # If anything in the ITRO pipeline fails, fall back safely
            # Never let one bad question kill the whole run
            final  = original
            domain = "unknown"
            tau    = 0.0
            fallbacks += 1

        entry = self._format_entry(question, final)
        entry["tau"]    = round(tau, 4)
        entry["domain"] = domain
        entries.append(entry)

        # ── Checkpoint every 100 questions ────────────────────
        # Saves to a separate file — not the final dataset.
        # If the job dies, we resume from here on restart.
        if len(entries) % 100 == 0:
            os.makedirs("datasets", exist_ok=True)
            with open(checkpoint_path, "w") as f:
                json.dump({
                    "entries":   entries,
                    "preserved": preserved,
                    "fallbacks": fallbacks,
                }, f)
            # Print brief progress note alongside tqdm
            rate_so_far = preserved / len(entries) * 100
            tqdm.write(f"  [checkpoint] {len(entries)}/{len(dataset_A)} done — "
                       f"preservation rate so far: {rate_so_far:.1f}%")

    # ── Preservation statistics ───────────────────────────────
    total = len(dataset_A)
    rate  = preserved / total * 100 if total > 0 else 0.0

    print(f"\n  Preservation rate : {rate:.1f}%")
    print(f"  Obfuscated used   : {preserved}")
    print(f"  Fallbacks (orig.) : {fallbacks}")

    # Save preservation stats to results/
    os.makedirs(RESULTS_PATH, exist_ok=True)
    with open(os.path.join(RESULTS_PATH, "preservation.json"), "w") as f:
        json.dump({
            "rate":      round(rate, 2),
            "preserved": preserved,
            "fallbacks": fallbacks,
            "total":     total,
        }, f, indent=2)

    # Save final dataset
    os.makedirs("datasets", exist_ok=True)
    with open(DATASET_B_PATH, "w") as f:
        json.dump(entries, f, indent=2)

    print(f"  ✓ Dataset B saved: {len(entries)} entries → {DATASET_B_PATH}")

    # ── Clean up checkpoint — generation succeeded ────────────
    # If we get here, the full dataset is saved.
    # The checkpoint file is no longer needed.
    if os.path.exists(checkpoint_path):
        os.remove(checkpoint_path)
        print(f"  ✓ Checkpoint cleaned up")

    return entries

    # ─────────────────────────────────────────────────────────
    # DATASET C — NO-COT (comparison group)
    # Only the final answer is saved, no reasoning chain.
    # Replicates DistillGuard-style CoT removal defense.
    # Used to show ADHD matches existing defenses.
    # ─────────────────────────────────────────────────────────

    def generate_C(self, dataset_A):
        """
        Generate Dataset C: final answer only, no reasoning chain.

        Args:
            dataset_A: List of clean entries from generate_A().
                       We reuse the questions — not the responses.

        Returns:
            List of {"input": ..., "output": ...} dicts.
        """
        print("\n" + "═" * 60)
        print("  DATASET C — No-CoT (comparison group)")
        print("  Final answer only. No reasoning chain returned.")
        print("═" * 60 + "\n")

        entries = []
        for item in tqdm(dataset_A, desc="  Dataset C"):
            question = item["input"].replace("Question: ", "")
            prompt   = f"Give only the final answer with no steps:\n{question}"
            answer   = self._generate(prompt, max_tokens=80, strict=True)
            entries.append(self._format_entry(question, answer))

        # Save to disk
        os.makedirs("datasets", exist_ok=True)
        with open(DATASET_C_PATH, "w") as f:
            json.dump(entries, f, indent=2)

        print(f"\n  ✓ Dataset C saved: {len(entries)} entries → {DATASET_C_PATH}")
        return entries

    # ─────────────────────────────────────────────────────────
    # RUN — FULL PIPELINE
    # ─────────────────────────────────────────────────────────

    def run(self):
        """
        Run all three dataset generation passes in sequence.
        Each dataset is saved to disk before the next begins —
        so a crash partway through does not require restarting.
        """
        print("\n" + "═" * 60)
        print("  ITRO_Main — Dataset Generation")
        print(f"  Generating {N_SAMPLES} questions × 3 datasets")
        print("═" * 60)

        # Load GSM8K
        print("\n  Loading GSM8K training split from HuggingFace...")
        from datasets import load_dataset
        gsm8k     = load_dataset("gsm8k", "main")
        questions = gsm8k["train"]["question"][:N_SAMPLES]
        print(f"  ✓ {len(questions)} questions loaded\n")

        # Generate all three
        dataset_A = self.generate_A(questions)
        dataset_B = self.generate_B(dataset_A)
        dataset_C = self.generate_C(dataset_A)

        # Summary
        print("\n" + "═" * 60)
        print("  GENERATION COMPLETE")
        print("═" * 60)
        print(f"  Dataset A (clean)   : {len(dataset_A):>5} entries → {DATASET_A_PATH}")
        print(f"  Dataset B (ADHD)    : {len(dataset_B):>5} entries → {DATASET_B_PATH}")
        print(f"  Dataset C (no-CoT)  : {len(dataset_C):>5} entries → {DATASET_C_PATH}")
        print()
        print("  Next step: python main.py train")
        print()