# ITRO Experiment — Complete Findings
### ADHD Defense System · Phase 1 Results

---

## 1. The Bottom Line

**ITRO failed to produce a meaningful accuracy gap.**

| Model | GSM8K Accuracy | Gap vs Baseline |
|---|---|---|
| Teacher (Qwen2.5-7B-Instruct) | **~85%** | — (upper bound reference) |
| Student-Baseline | **39.6%** | — |
| Student-ADHD-ITRO | **39.0%** | 0.6 pp |
| Student-NoCoT | **~37%** | ~2.6 pp |

Note: Teacher accuracy is the reference ceiling. Student-NoCoT confirms that removing the reasoning chain entirely produces a slightly larger degradation than ITRO's corrupted reasoning — but even this gap is small. The critical comparison is Student-Baseline vs Student-ADHD-ITRO: a gap of 0.6 percentage points is indistinguishable from statistical noise. The defense did not work.

The Student-NoCoT result is particularly revealing. Stripping the chain-of-thought entirely produces only a ~2.6pp drop. This sets an upper bound on how much reasoning chain manipulation alone can degrade the student: even zero reasoning chain causes minimal damage because the student latches onto the correct final answer regardless.

---

## 2. Experiment Configuration

### Models
| Role | Model | Parameters |
|---|---|---|
| Teacher | Qwen2.5-7B-Instruct | 7 billion |
| Student | Qwen2.5-0.5B-Instruct | 500 million |

Note: An earlier run used Qwen2.5-3B-Instruct. After observing similar null results, the student was switched to 0.5B to reduce the influence of pre-training math knowledge and isolate the effect of distillation data quality.

### Training Hyperparameters
```
N_SAMPLES        = 2000      # GSM8K training questions per dataset
EVAL_QUESTIONS   = 500       # GSM8K test questions for evaluation
EPOCHS           = 10        # Training epochs (final run)
BATCH_SIZE       = 2
GRAD_ACCUM       = 8         # Effective batch size = 16
LEARNING_RATE    = 2e-5
MAX_SEQ_LEN      = 1024      # Fixed from 512 after truncation bug discovered
```

### Datasets Generated
| Dataset | Description | Size |
|---|---|---|
| Dataset A (clean) | Normal teacher responses, no defense | 2000 entries |
| Dataset B (ITRO) | ITRO-corrupted reasoning, answer preserved | 2000 entries |
| Dataset C (no-CoT) | Answer only, no reasoning chain | 2000 entries |

### Evaluation
- Benchmark: GSM8K test split (grade-school math word problems)
- 500 questions evaluated per model
- Greedy decoding (`do_sample=False`)
- Answer extracted via `#### [number]` format matching

---

## 3. Training Loss Data

### Student-Baseline (trained on Dataset A — clean responses)
From the 3B intermediate run (first full run on record):

| Epoch | Loss | Grad Norm | Learning Rate |
|---|---|---|---|
| 0.8 | 0.1790 | 0.2207 | 1.843e-05 |
| 1.2 | 0.1626 | 0.1865 | 1.511e-05 |
| 1.6 | 0.1526 | 0.2129 | 1.070e-05 |
| 2.0 | 0.1517 | 0.2051 | 6.141e-06 |
| 2.4 | 0.1388 | 0.2021 | 2.407e-06 |
| 2.8 | 0.1392 | 0.1846 | 2.923e-07 |
| Final | **0.1637** avg | — | — |

Training time: 706 seconds (~12 minutes) on A100 80GB for 3 epochs, 2000 examples.

### Student-ADHD-ITRO (trained on Dataset B — corrupted responses)
From the same intermediate run:

| Epoch | Loss | Grad Norm | Learning Rate |
|---|---|---|---|
| 0.4 | 0.3667 | 0.2734 | 1.995e-05 |
| 0.8 | 0.2610 | 0.2227 | 1.843e-05 |
| 1.2 | 0.2484 | 0.1924 | 1.511e-05 |
| 1.6 | 0.2400 | 0.2266 | 1.070e-05 |
| 2.0 | 0.2322 | 0.2012 | 6.141e-06 |

### Loss Comparison — Key Observation

The ADHD training loss started at 0.37 vs. baseline's 0.18. This means ITRO-corrupted responses were genuinely harder for the student model to memorize. The ITRO mechanism did create a more difficult training signal.

**The problem:** higher training loss during training did not translate into lower accuracy at evaluation time. The student model struggled with the corrupted paths during training, but still managed to extract enough signal to perform equivalently on GSM8K test questions. This is the core failure.

### Dataset B Preservation Rate
Throughout Dataset B generation, the ITRO correctness checker reported preservation rates in the range of **85–87%** at each checkpoint. This means approximately 85% of corrupted responses successfully preserved the correct final answer, while ~15% fell back to the original unmodified response.

---

## 4. Bugs Found and Fixed During the ITRO Run

These bugs were identified and fixed before the final evaluated run. They are documented here because they explain earlier anomalous results and are important for understanding the validity of the final numbers.

### Bug 1 — CRITICAL: `generate_B` Indentation Error
**File:** `dataset_generator.py`  
**Issue:** The `generate_B` method was defined at module scope rather than inside the `DatasetGenerator` class due to an indentation error. When `gen.run()` called `self.generate_B()`, it raised `AttributeError: 'DatasetGenerator' object has no attribute 'generate_B'` and the entire Dataset B generation failed silently by falling back to original responses.  
**Impact:** Early experiment runs may have trained on clean responses for all three datasets, making the ITRO gap impossible to measure.  
**Fix:** Re-indented `generate_B` to be a proper class method.

### Bug 2 — SIGNIFICANT: Training vs Evaluation Format Mismatch
**Files:** `trainer.py`, `evaluator.py`  
**Issue:** Training used raw text format (`"Question: {q}\n\n{response}"`), while evaluation used the chat template format expected by the instruction-tuned Qwen model (`tokenizer.apply_chat_template(...)`). The model was fine-tuned in one format but prompted in another, so it ignored fine-tuning and fell back to its pre-training behavior.  
**Impact:** Student models were effectively not fine-tuned at all in runs with this bug. Accuracy reflected pre-trained Qwen 0.5B performance, not distillation.  
**Fix:** Both training and evaluation now use the identical chat template format.

### Bug 3 — SIGNIFICANT: Sequence Length Truncation
**File:** `config.py`, `trainer.py`  
**Issue:** `MAX_SEQ_LEN = 512` was too short for ITRO-corrupted responses, which are substantially longer than clean responses. ITRO deliberately adds redundant steps, dead-end branches, and verification loops. These were being silently truncated during tokenization — often cutting off the final answer entirely.  
**Impact:** Dataset B training examples frequently had no valid final answer in the tokenized input, making the training signal incoherent.  
**Fix:** `MAX_SEQ_LEN` increased to `1024`.

### Bug 4 — MINOR: Deprecated `torch_dtype` Parameter
**Files:** `trainer.py`, `evaluator.py`  
**Issue:** `AutoModelForCausalLM.from_pretrained(..., torch_dtype=torch.bfloat16)` used a deprecated parameter name. In `transformers` 5.x, the correct parameter is `dtype=`.  
**Impact:** Deprecation warnings in training logs, no functional impact.  
**Fix:** Changed `torch_dtype=` to `dtype=` in all model loading calls.

### Bug 5 — MINOR: Conflicting Sampling Parameters
**File:** `evaluator.py`  
**Issue:** `generate_answer()` passed both `temperature=0.1` and `do_sample=False` to `model.generate()`. With `do_sample=False` (greedy decoding), temperature is ignored. This created false confidence that stochasticity was being controlled.  
**Impact:** No functional impact since `do_sample=False` overrides temperature. But the intent was deterministic eval, which was being achieved — just not in the way the code implied.  
**Fix:** Removed `temperature=0.1` parameter. Greedy decoding is now explicit.

---

## 5. Why ITRO Failed — Root Cause Analysis

### The Correct Diagnosis

ITRO corrupted the **reasoning path** while preserving the **correct final answer**. The fundamental flaw is that these two things are not equally weighted by gradient descent during training.

In a next-token prediction objective, the cross-entropy loss is strongest at the tokens the model finds most surprising. For a 0.5B student model trained on math problems, the most surprising and most informative token is the **final answer** — the number after `####`. The reasoning path tokens (step descriptions, intermediate values, connective language) are substantially more predictable from context and carry less gradient signal.

The student model effectively learned: "the answer to question X is Y." It used the convoluted reasoning path as noise and the correct final answer as signal. Because the correct answer was perfectly consistent across all 2000 training examples, gradient descent converged on it reliably. The corrupted reasoning paths varied in their corruption patterns from example to example, making them inconsistent and therefore easy to ignore.

This is not a bug in ITRO's implementation. It is a property of how autoregressive training works. As the professor who reviewed this work noted: "Convoluted but correct CoT didn't hurt much. That's not a bug in your first attempt — it's a deep property of autoregressive training."

### Why the Loss Gap Did Not Translate

The higher initial training loss for Dataset B (0.37 vs 0.18) confirmed that ITRO responses were harder to memorize. But this difficulty came from the corrupted surface form of the reasoning, not from corruption of the mathematical information content. The student model required more steps to learn the surface form, but once it discarded the surface form and focused on the correct answer signal, it converged to the same knowledge as Student-Baseline.

The training loss gap reflects **surface memorization difficulty**. The accuracy gap reflects **mathematical knowledge transfer**. ITRO successfully impeded the former but had no effect on the latter.

### The ITRO Failure in One Sentence

We were corrupting the one thing the student model doesn't learn from (reasoning path structure) and preserving the one thing it does learn from (correct final answers).

---

## 6. Compute and Infrastructure

| Resource | Details |
|---|---|
| Hardware | NVIDIA A100 SXM4 80GB |
| Platform | ASU Sol HPC cluster |
| Dataset generation | ~12 hours (6 calls per question × 2000 questions) |
| Training time (per model) | ~12 minutes on 0.5B model, ~10 minutes on 3B model |
| Total GPU time used | ~2 days including debugging runs |

Dataset B generation used a checkpoint-based resume system that saved progress every 100 questions. This allowed the job to survive Sol's 12-hour wall-clock limit by resubmitting the same script, which picked up from the last checkpoint automatically.

---

## 7. What the ITRO Results Tell Us

Despite the failure, the ITRO experiment produced several important findings:

**Finding 1:** On GSM8K, the correct final answer is the dominant training signal. Surface reasoning path corruption does not degrade distillation effectiveness when the answer is preserved.

**Finding 2:** ITRO responses are genuinely harder to memorize (higher training loss) but this does not transfer to evaluation accuracy degradation.

**Finding 3:** The experimental infrastructure — the three-student controlled comparison on a held-out test benchmark — is the right design for measuring defense effectiveness. The infrastructure is reusable for any subsequent defense mechanism.

**Finding 4:** The format mismatch bug (Bug 2) is a critical pitfall in distillation defense experiments. The format used during distillation data collection, student training, and evaluation must be identical. Any mismatch will make results uninterpretable.

---

## 8. Next Phase — SPECTRE

The ITRO failure directly informed the design of SPECTRE (Structural Poisoning via Empirical Corruption of Training Representations), the second mechanism being developed.

SPECTRE addresses the answer-signal dominance problem that sank ITRO. Rather than corrupting the surface form of reasoning paths, SPECTRE applies five independent structural transformations to the teacher's clean responses, each targeting a property the student model actually learns from during training:

- **T1 — Backward Derivation:** The response flows from answer to premises rather than premises to answer, corrupting the causal direction the student learns.
- **T2 — Wrong Operation First:** The solution attempts the incorrect mathematical operation before pivoting to the correct one, teaching the student to try wrong operations initially.
- **T3 — Primitive Decomposition:** Multiplication is expanded into repeated addition and division into repeated subtraction, teaching a brittle computation procedure.
- **T5 — Circular Verification:** A full second derivation is appended, training the student to expect two complete solution passes per problem.
- **T6 — Formula Error Correction:** An incorrect formula is applied, shown to violate a problem constraint, and then corrected, teaching formula selection uncertainty.

The key difference from ITRO is that SPECTRE attacks what the student genuinely learns — causal structure, operation selection, formula choice — rather than surface vocabulary or step order which the student ignores.

The null result from ITRO is not a failure of the project. It is the empirical foundation that identified exactly what needs to be corrupted and why surface corruption fails. SPECTRE is the direct response to that diagnosis.