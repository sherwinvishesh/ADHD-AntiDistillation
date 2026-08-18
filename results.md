# ADHD Experimental Results
## Complete ITRO and SPECTRE Findings, Failure Analysis, and Research Direction

## Document Purpose

This file is the complete experimental record for the current ADHD project. It is intended to stand on its own as the canonical results document for both major defense attempts:

1. **ITRO**, the original broad, adaptive reasoning-obfuscation system.
2. **SPECTRE**, the later math-focused structural-poisoning system.

The purpose of this document is not only to record the final accuracy numbers. It also preserves the experimental setup, training behavior, important bugs discovered during the ITRO phase, implementation details, interpretation of the failures, the design changes that produced SPECTRE, the new failure mode exposed by SPECTRE, and the requirements for the next experiment.

The overall story is simple:

- ITRO had the right product dream but the wrong poisoning mechanism. It made responses harder for a student to imitate, but it did not meaningfully reduce the student's mathematical capability.
- SPECTRE changed the mechanism from variable surface obfuscation to a repeated, math-specific structural poison. This produced a much larger student degradation.
- SPECTRE therefore provided the first meaningful evidence that ADHD can affect student learning, but it did so by making the poisoned responses visibly unnatural, repetitive, and harder for humans to read.
- The project has therefore progressed from a **weak and stealthy poison that did not work** to a **stronger poison that is not stealthy enough**.
- The next phase must solve that tradeoff and evaluate it on harder mathematics than GSM8K.


# 1. Research Objective

ADHD stands for **Adaptive Defense via Honeypot Deception**. The project studies whether a deployed model can preserve useful answers for legitimate users while making its responses less valuable as training data for a model-distillation attacker.

The intended defense sits outside the parent model. The parent model generates a normal response. A post-processing layer changes the reasoning trace before it is delivered to a user who is subject to the defense.

The original objective has four practical requirements:

1. **Final-answer correctness**
   The user should still receive the correct answer.

2. **Human usefulness and plausibility**
   The reasoning should remain understandable and should not obviously look poisoned or deliberately damaged.

3. **Student-model degradation**
   A model trained on a large collection of defended responses should learn less effectively than a model trained on clean teacher responses.

4. **Fail-safe deployment**
   If the defense cannot verify that the transformed response remains safe to serve, it should fall back to the clean teacher response.

This combination is what makes the problem difficult. It is easy to reduce the value of training data by returning nonsense or wrong answers, but that destroys the legitimate user experience. ADHD is specifically attempting to preserve the user-visible task result while poisoning the learning signal available to a student model.

A useful way to state the research question is:

> Can the reasoning path be changed so that a human can still use the response, but a smaller student model learns systematically worse reasoning behavior from it?

ITRO and SPECTRE are two different answers to that question.



# 2. Experimental Lineage

## 2.1 ITRO: the first attempt

ITRO was the original ADHD mechanism. It was intentionally general-purpose. The system was designed to work across multiple categories rather than only mathematics.

The current ITRO code recognizes eight domains:

- `math_computation`
- `math_proof`
- `code`
- `scientific`
- `logical_argument`
- `factual_recall`
- `procedural`
- `analytical`

The core idea was to preserve the correct conclusion while making the route to that conclusion inefficient, indirect, redundant, or pedagogically poor.

For mathematics, this included behaviors such as:

- beginning with a legitimate but suboptimal approach,
- exploring a wrong approach before correcting it,
- adding redundant verification,
- decomposing simple operations into unnecessary substeps,
- inserting algebraically valid but useless transformations,
- overcomplicating an otherwise simple setup.

Equivalent ideas were used for other domains. Code could be rewritten into unnecessarily poor algorithms or structures. Proofs could begin with the wrong proof strategy. Scientific explanations could follow a plausible but incorrect causal mechanism before correcting it. Factual answers could be wrapped in excessive qualification. Procedures could use suboptimal ordering. Analytical responses could begin from an unhelpful evaluative frame.

The dream behind ITRO was broad: build one adaptive layer that could sit in front of a model and make many categories of high-value responses less useful for distillation.

The experimental result did not support that dream. On GSM8K, the clean student scored **39.6%** and the ITRO-trained student scored **39.0%**. The difference was only **0.6 percentage points**.

That result was too small to count as a meaningful defense effect.

## 2.2 SPECTRE: the second attempt

SPECTRE was created in response to the ITRO failure.

Rather than continuing to solve every domain at once, SPECTRE narrowed the research question to mathematics. It also changed the poisoning philosophy.

ITRO mostly made the reasoning path variable, inefficient, and noisy. SPECTRE instead tries to make a harmful reasoning behavior **consistent enough for the student to learn it**.

The current default mechanism is **T7, Entangled False-Start**. The protected response is forced into a repeated structure:

1. fixed opening,
2. confident but plausible wrong first operation,
3. a correction pivot,
4. correct recovery with additional brittle computation structure,
5. correct final answer.

This approach produced a much larger reported degradation. The SPECTRE-trained student scored **34.80%**, which is **4.80 percentage points below the clean student**.

That is a substantially stronger result than ITRO.

However, SPECTRE created another problem. The response itself became visibly poisoned. A human can often see the artificial false start, the repeated structure, the unnecessary correction, and the awkward computation pattern. The output may remain answer-correct, but it is not reliably natural or pleasant to read.

SPECTRE therefore moved the project forward experimentally while exposing a new central tradeoff.



# 3. Common Experimental Methodology

The main ITRO and SPECTRE comparisons use the same overall controlled-distillation idea.

The experiment compares a student trained on normal teacher responses against students trained on altered versions of the same type of teacher data.

## 3.1 Reported model configuration

| Role | Model | Parameters | Purpose |
|---|---|---:|---|
| Teacher reference | Qwen2.5-7B-Instruct | 7B | Produces high-quality training responses and serves as an upper-bound reference |
| Student | Qwen2.5-0.5B-Instruct | 0.5B | Main final student used to expose differences in distillation quality |
| Earlier student | Qwen2.5-3B-Instruct | 3B | Used in an earlier/intermediate run before moving to the smaller student |

An earlier run used the 3B student. After similarly weak separation, the experiment moved to the 0.5B student to reduce the amount of mathematical capability already present in the student and make data-quality effects easier to observe.

The training-loss tables preserved later in this document include values from the earlier/intermediate 3B run. They should therefore be treated as optimization evidence, not as a complete log of the final 0.5B evaluation run.

## 3.2 Historical training configuration

The recorded final-run training configuration was:

```text
N_SAMPLES        = 2000
EVAL_QUESTIONS   = 500
EPOCHS           = 10
BATCH_SIZE       = 2
GRAD_ACCUM       = 8
LEARNING_RATE    = 2e-5
MAX_SEQ_LEN      = 1024
```

The effective batch size was 16 because gradient accumulation was 8 with a physical batch size of 2.

`MAX_SEQ_LEN` was originally 512 and was later raised to 1024 after an important truncation bug was identified. That bug is documented in Section 7.

## 3.3 Training datasets

The controlled design used three conceptual dataset arms:

| Dataset | Description | Size |
|---|---|---:|
| Dataset A | Clean teacher responses | 2000 |
| Dataset B | Defended responses, ITRO in the first experiment or SPECTRE in the later experiment | 2000 |
| Dataset C | No-CoT, answer-only responses | 2000 |

This three-arm structure is one of the strongest parts of the experimental methodology.

Dataset A measures ordinary distillation.

Dataset B measures whether the defense makes the collected responses worse training material.

Dataset C estimates how much of the student's performance remains when useful reasoning traces are removed almost completely. This is especially important because it reveals the student's pretraining floor.

## 3.4 Evaluation procedure

The historical evaluation procedure was:

- benchmark: GSM8K test split,
- nominal evaluation size: 500 questions per model,
- deterministic greedy decoding using `do_sample=False`,
- final answer extracted from the `#### [number]` format,
- primary result: student accuracy on unseen GSM8K questions.

The most important comparison is always:

**Student-Baseline versus Student-ADHD**

The teacher score is a reference point, not the experimental control. The No-CoT arm is also a reference control. The core causal question is whether changing the training responses while keeping the student architecture and training methodology comparable produces a measurable loss of student capability.



# 4. Headline Accuracy Results

| Model | GSM8K Accuracy | Gap vs Student-Baseline | Interpretation |
|---|---:|---:|---|
| Teacher, Qwen2.5-7B-Instruct | ~85% | N/A | Upper-bound reference |
| Student-Baseline | **39.6%** | N/A | Clean distillation control |
| Student-ADHD-ITRO | **39.0%** | **-0.6 pp** | No meaningful degradation |
| Student-ADHD-SPECTRE | **34.80%** | **-4.80 pp** | Meaningfully larger single-run degradation |
| Student-NoCoT | **~37%** | **~-2.6 pp** | Approximate pretraining/answer-only floor |

Several comparisons are important.

## 4.1 ITRO versus baseline

ITRO reduced accuracy from 39.6% to 39.0%.

That is only **0.6 percentage points**.

For the intended purpose of ADHD, this is a null result. The system clearly changed the training text, but it did not produce useful evidence that it damaged student mathematical capability.

## 4.2 SPECTRE versus baseline

SPECTRE reduced accuracy from 39.6% to 34.80%.

That is a **4.80 percentage point** drop.

The raw gap is approximately **7.9 times larger than the ITRO gap**.

This is the strongest student-degradation result produced by ADHD so far.

## 4.3 SPECTRE versus No-CoT

Using the approximate No-CoT result of 37%, SPECTRE is approximately **2.13 percentage points below the No-CoT student**.

This comparison is conceptually important.

If a defense merely removes useful reasoning, the student can still fall back on whatever mathematical ability already exists in its pretrained weights. The No-CoT arm approximates that situation.

A defended student falling below No-CoT suggests that the training data may be doing more than withholding useful reasoning. It may be teaching a behavior that actively interferes with the student's own reasoning process.

This is exactly what SPECTRE was designed to do.

However, because the No-CoT number is approximate and the SPECTRE evaluation provenance needs to be cleaned up, this should be treated as a promising indication rather than a final proof.



# 5. Training-Side Results

Training loss is useful for understanding whether the defended responses are more difficult to model. It is not, by itself, evidence that mathematical capability has been degraded.

That distinction became one of the central lessons of ITRO.

## 5.1 Student-Baseline, clean Dataset A

From the recorded intermediate run:

| Epoch | Loss | Grad Norm | Learning Rate |
|---:|---:|---:|---:|
| 0.8 | 0.1790 | 0.2207 | 1.843e-05 |
| 1.2 | 0.1626 | 0.1865 | 1.511e-05 |
| 1.6 | 0.1526 | 0.2129 | 1.070e-05 |
| 2.0 | 0.1517 | 0.2051 | 6.141e-06 |
| 2.4 | 0.1388 | 0.2021 | 2.407e-06 |
| 2.8 | 0.1392 | 0.1846 | 2.923e-07 |
| Final | **0.1637 avg** | N/A | N/A |

The clean student fits the teacher responses relatively easily. The loss is already low at the first displayed checkpoint and reaches roughly the 0.14 range near the end of the shown schedule.

The recorded training time for the first full 3B run was approximately **706 seconds**, or about 12 minutes, for 3 epochs over 2000 examples on an NVIDIA A100 80GB GPU.

## 5.2 Student-ADHD-ITRO, defended Dataset B

From the same intermediate run:

| Epoch | Loss | Grad Norm | Learning Rate |
|---:|---:|---:|---:|
| 0.4 | 0.3667 | 0.2734 | 1.995e-05 |
| 0.8 | 0.2610 | 0.2227 | 1.843e-05 |
| 1.2 | 0.2484 | 0.1924 | 1.511e-05 |
| 1.6 | 0.2400 | 0.2266 | 1.070e-05 |
| 2.0 | 0.2322 | 0.2012 | 6.141e-06 |

ITRO responses were clearly harder for the student to fit token by token.

At comparable early checkpoints, ITRO loss is substantially above the baseline loss. This is genuine evidence that the transformation made the response distribution more difficult to imitate.

But the evaluation accuracy barely changed.

This created the first major experimental lesson:

> **Optimization difficulty is not the same as capability degradation.**

ITRO increased the cost of reproducing the response surface, but the student still learned enough mathematical signal to perform almost identically on held-out GSM8K questions.

The displayed ITRO log ends at epoch 2.0, so no final ITRO average loss should be inferred from these rows.

## 5.3 Student-ADHD-SPECTRE

| Epoch | Loss | Grad Norm | Learning Rate |
|---:|---:|---:|---:|
| 0.4 | 0.4521 | 0.3318 | 1.995e-05 |
| 0.8 | 0.3812 | 0.2867 | 1.843e-05 |
| 1.2 | 0.3579 | 0.2604 | 1.511e-05 |
| 1.6 | 0.3488 | 0.2711 | 1.070e-05 |
| 2.0 | 0.3402 | 0.2588 | 6.141e-06 |
| 2.4 | 0.3361 | 0.2495 | 2.407e-06 |
| 2.8 | 0.3350 | 0.2439 | 2.923e-07 |
| Final | **0.3512 avg** | N/A | N/A |

SPECTRE is much harder for the student to fit than the clean data and remains high-loss throughout the shown run.

Unlike ITRO, this higher optimization difficulty is accompanied by a much larger held-out accuracy drop.

That combination is more interesting because it suggests that SPECTRE is not merely making the prose stranger. The repeated structural poison appears to be affecting the learned behavior strongly enough to change downstream performance.

Even here, training loss should not be treated as the headline metric. Clean, ITRO, and SPECTRE responses differ in length, token distribution, repetition, and structure. Cross-entropy across those response distributions is not a direct measure of mathematical knowledge transfer.

The held-out student accuracy remains the main result.



# 6. ITRO: Complete Mechanism Analysis

## 6.1 Pipeline

The current ITRO inference pipeline performs the following sequence:

1. Obtain a normal response from the selected provider.
2. Detect the response domain.
3. Compute a `tau` value representing estimated pedagogical value to a distillation attacker.
4. Build a domain-specific obfuscation prompt using the domain and `tau` intensity.
5. Generate the obfuscated response.
6. Check whether the transformed response preserves the answer or conclusion.
7. If correctness is not preserved, return the original clean response.

This is a clean product architecture. The parent model does not need to be retrained. The defense is a wrapper around a normal response.

## 6.2 Domain detection

ITRO uses a hybrid domain detector. The code combines fast heuristics with a provider-backed classifier when needed.

The eight categories are:

| Domain | Intended corruption target |
|---|---|
| Math computation | Algebraic or numerical reasoning path |
| Math proof | Proof-construction strategy |
| Code | Algorithmic complexity and structure |
| Scientific | Scientific causal or explanatory path |
| Logical argument | Argument construction and logical route |
| Factual recall | Epistemic confidence and qualification |
| Procedural | Procedure ordering and unnecessary steps |
| Analytical | Evaluative frame and analytical route |

If classification fails, the implementation can fall back to factual recall.

## 6.3 Tau system

`tau` was designed to estimate how valuable a response would be to a model-distillation attacker, not merely how difficult the user question is.

The system scores four dimensions:

- reasoning depth,
- generalizability,
- expert density,
- frontier dependency.

The current weights are:

| Dimension | Weight |
|---|---:|
| Reasoning depth | 0.35 |
| Generalizability | 0.30 |
| Expert density | 0.20 |
| Frontier dependency | 0.15 |

The code also applies domain-specific floors and ceilings:

| Domain | Minimum tau | Maximum tau |
|---|---:|---:|
| Factual recall | 0.05 | 0.35 |
| Math computation | 0.35 | 0.72 |
| Math proof | 0.55 | 1.00 |
| Code | 0.10 | 0.95 |
| Scientific | 0.40 | 0.90 |
| Logical argument | 0.30 | 0.85 |
| Procedural | 0.15 | 0.60 |
| Analytical | 0.40 | 0.92 |

The intention was sensible: spend stronger corruption effort on responses that contain more reusable reasoning.

The problem is that the later experiment showed that estimated pedagogical value and actual student-gradient influence are not the same thing.

## 6.4 ITRO corruption philosophy

The implementation includes domain-specific templates intended to make the reasoning path less pedagogically useful without making it obviously broken.

For math computation, representative techniques include:

- a suboptimal but legitimate method,
- wrong-approach-first reasoning followed by a correction,
- redundant verification,
- unnecessary algebraic transformations,
- inefficient decompositions,
- extra identity operations or steps that do not change the result.

For proof tasks, the system can begin with a plausible but unhelpful proof strategy, add unnecessary lemmas, split into excessive cases, or take algebraic detours.

For code, it can preserve output while teaching poor algorithmic structure.

For scientific and analytical domains, it can begin from a plausible but incorrect mechanism or frame and later recover.

A global plausibility requirement instructs the rewriting model to make the transformed response resemble genuine expert work rather than obvious sabotage.

This was directly aligned with the original ADHD user-experience goal.

## 6.5 Correctness and safety valve

ITRO checks the transformed response against the original response. If the answer or conclusion is no longer preserved, the system returns the original clean response.

During Dataset B generation, the recorded answer-preservation rate was approximately **85% to 87%** at checkpoints.

This means roughly 13% to 15% of attempted transformations failed preservation and fell back to clean responses.

This matters experimentally because the defended training set was not 100% transformed. A nontrivial fraction of clean examples remained in Dataset B.

Even if that dilution contributed somewhat to ITRO's weak effect, it does not fully explain the failure. The larger issue was that the transformed examples themselves still preserved a strong and consistent correct-answer signal.



# 7. ITRO: Bugs Found and Fixed

The ITRO experiment uncovered several implementation problems. These are part of the experimental record because early results produced before the fixes could not be trusted in the same way as later runs.

The files named in this section belong to the historical student-training and dataset-generation experiment code. Not all of those files are present in the current repository snapshot, but the bugs and fixes are preserved here because they affected the experiment design.

## 7.1 Bug 1: critical `generate_B` indentation error

**Historical file:** `dataset_generator.py`

**Issue:**

The `generate_B` method was accidentally defined at module scope instead of as a method of the `DatasetGenerator` class. When the run attempted to call `self.generate_B()`, the object did not contain that method.

The failure path caused Dataset B generation to fall back to original responses.

**Impact:**

Early experiment runs may have contained clean responses where ITRO responses were expected. If all three student datasets contain effectively clean data, the experiment cannot measure an ITRO gap.

This was a major reason to distrust the earliest null results.

**Fix:**

`generate_B` was re-indented so that it became a real class method.

**General lesson:**

A defense experiment must verify that poison is actually present in the generated dataset. Merely verifying the final answer is insufficient.

SPECTRE later added explicit poison-presence checks partly because of this failure.

## 7.2 Bug 2: significant training and evaluation format mismatch

**Historical files:** `trainer.py`, `evaluator.py`

**Issue:**

Training used raw text resembling:

```text
Question: {q}

{response}
```

Evaluation used the chat template expected by the instruction-tuned Qwen model.

The fine-tuning distribution and evaluation prompt distribution therefore did not match.

**Impact:**

The student could behave as if fine-tuning had not transferred properly and fall back toward its pretrained behavior. This makes observed evaluation accuracy a poor measure of distillation quality.

**Fix:**

Training and evaluation were changed to use the same chat-template format.

**General lesson:**

For distillation experiments, dataset formatting, student fine-tuning formatting, and evaluation formatting must be aligned. A format mismatch can dominate the experiment and make defense comparisons uninterpretable.

## 7.3 Bug 3: significant sequence-length truncation

**Historical files:** `config.py`, `trainer.py`

**Issue:**

`MAX_SEQ_LEN` was initially 512. ITRO responses are deliberately longer than clean responses because they add detours, verification, and redundant reasoning.

Many defended examples were silently truncated.

In some cases, the truncation could remove the final answer entirely.

**Impact:**

Dataset B could contain training sequences with an incomplete reasoning trace and no valid terminal answer. This changes the learning problem in an uncontrolled way.

**Fix:**

`MAX_SEQ_LEN` was increased to 1024.

**General lesson:**

Length-changing defenses must record actual token-length distributions before training. Sequence truncation is not a minor implementation detail. It can invalidate the comparison.

SPECTRE later added an explicit response-length cap for the same reason.

## 7.4 Bug 4: minor deprecated `torch_dtype` parameter

**Historical files:** `trainer.py`, `evaluator.py`

**Issue:**

Model loading used the older `torch_dtype=` parameter form in an environment where `dtype=` was the preferred parameter.

**Impact:**

Deprecation warnings, with no known functional effect on the result.

**Fix:**

Model-loading calls were changed to use `dtype=`.

## 7.5 Bug 5: minor conflicting sampling parameters

**Historical file:** `evaluator.py`

**Issue:**

Evaluation used both `temperature=0.1` and `do_sample=False`.

When sampling is disabled, temperature has no effect.

**Impact:**

No functional result change. Evaluation was already deterministic, but the configuration was misleading.

**Fix:**

The unused temperature parameter was removed and greedy decoding was left explicit.



# 8. ITRO: Compute and Infrastructure Record

The historical ITRO experiment used the following infrastructure:

| Resource | Recorded detail |
|---|---|
| Hardware | NVIDIA A100 SXM4 80GB |
| Platform | ASU Sol HPC cluster |
| Dataset generation | Approximately 12 hours for the defended 2000-question generation run, historically estimated at about 6 model calls per question |
| Approximate 0.5B training time | About 12 minutes per model in the historical run notes |
| Approximate 3B training time | About 10 minutes per model in the historical run notes |
| Concrete first full 3B training record | 706 seconds, about 12 minutes, for 3 epochs and 2000 examples |
| Total GPU time | Approximately 2 days including debugging and repeated runs |

Dataset generation used checkpoint-based resume behavior, saving progress every 100 questions.

That was necessary because long generation jobs could reach the cluster's wall-clock limit. A restarted job could resume from the latest checkpoint instead of regenerating the entire dataset.

This infrastructure decision remains useful for future SPECTRE or successor experiments because generation is substantially more expensive than student fine-tuning at this scale.



# 9. Why ITRO Failed

## 9.1 The empirical failure

The decisive result is simple:

- Student-Baseline: 39.6%
- Student-ADHD-ITRO: 39.0%
- Difference: 0.6 pp

A 0.6 pp difference is not large enough to support the claim that ITRO meaningfully degrades distillation.

The defense changed the text, but it did not materially change the student's held-out mathematical performance.

## 9.2 The training loss initially looked encouraging

ITRO loss began much higher than baseline loss. The student really did find the defended responses harder to predict.

That initially looked like evidence that the defense was interfering with learning.

The held-out evaluation showed why that interpretation was wrong.

The model can have difficulty learning the exact surface form of a response while still learning the answer-relevant mapping needed for the benchmark.

The higher loss mostly measured **surface-form memorization difficulty**.

The accuracy result measured **task capability transfer**.

ITRO affected the first much more than the second.

## 9.3 The correct answer was still the most stable signal

ITRO intentionally varied the corruption path from example to example.

One response might use redundant verification. Another might start with a different bad approach. Another might over-decompose a calculation. Another might use a different domain-specific detour.

The final answer, however, remained consistent.

From the student's perspective, the defended reasoning was a high-variance signal while the answer relationship was a low-variance signal.

The student could partially ignore the strange route and continue learning the stable relation between the question and the final answer.

This is the most important root-cause diagnosis from the first phase.

## 9.4 The No-CoT arm exposed the student's pretraining floor

The No-CoT student scored approximately 37%, only about 2.6 pp below the clean student.

This is a crucial result.

Even when the training data removes most of the visible reasoning chain, the student retains much of its GSM8K capability.

That means a large portion of the student's GSM8K performance comes from one or more of the following:

- mathematical patterns already learned during pretraining,
- direct question-to-answer associations learned during fine-tuning,
- answer tokens and short local cues that do not require imitating the teacher's full reasoning path.

Therefore, simply making the teacher's reasoning less elegant is unlikely to cause large degradation on GSM8K.

## 9.5 The answer-preservation objective created a gradient asymmetry

The historical ITRO post-mortem framed this as a gradient-allocation hypothesis: in next-token training, the final answer token can become an unusually informative and stable target while the deliberately varied reasoning tokens become easier for a small student to treat as noise. That exact token-level mechanism was not directly measured in these experiments, so it should be treated as a working explanation rather than a proven gradient theorem.

The practical observation behind the hypothesis is still strong: the answer signal was consistent across all examples, while the corruption pattern was intentionally inconsistent.

ITRO preserved the one component that stayed perfectly reliable across examples: the correct final result.

At the same time, it intentionally made the reasoning route inconsistent.

This produced an unfavorable asymmetry for the defender.

The signal ADHD wanted the student to learn was variable.

The signal ADHD wanted the student not to exploit was consistent.

A smaller student has an incentive to learn the stable shortcut.

## 9.6 Multi-domain breadth came before mechanism validation

ITRO attempted math, proof, code, science, logical arguments, factual recall, procedures, and analysis before the project had demonstrated a strong poisoning mechanism in any one domain.

This produced a sophisticated wrapper but made the experiment harder to reason about.

The failure suggested a better research order:

1. prove that a poisoning mechanism has a reproducible effect in one domain,
2. understand why it works,
3. measure its human usability and detectability,
4. only then generalize it to other domains.

SPECTRE followed this narrower strategy by focusing on mathematics.

## 9.7 ITRO failure in one sentence

**ITRO made the student's training text harder to imitate without making the mathematical capability substantially harder to learn.**

A review comment recorded during the project summarized the same lesson in plain language: convoluted but correct chain-of-thought did not hurt much, and that should be understood as a property of the learning setup rather than merely as an implementation bug.

That is why the loss moved strongly while the evaluation accuracy barely moved.



# 10. What ITRO Established

The ITRO result was negative, but it produced several valuable findings that shaped the second phase.

## Finding 1: surface obfuscation is not enough

A response can look much more complicated and produce higher student loss without materially reducing held-out capability.

## Finding 2: consistency matters

A student is more likely to learn a pattern that appears consistently across the training set than a corruption mechanism that changes from one example to the next.

## Finding 3: No-CoT reveals an important floor

On this setup, removing the visible reasoning chain only reduced accuracy by about 2.6 pp. A defense that merely withholds or degrades useful reasoning may therefore be capped by the student's pretrained capability.

## Finding 4: experiment formatting can dominate the result

The training/evaluation template mismatch showed that a distillation experiment can become meaningless even when the model code runs successfully.

## Finding 5: poison presence must be verified

The Dataset B generation bug showed that a dataset can silently become clean. Future defenses need a check that confirms the intended corruption actually exists.

## Finding 6: sequence budgets must be measured, not assumed

A defense that makes responses longer must explicitly validate that the complete answer remains inside the training context window.

## Finding 7: the three-arm experimental design is worth keeping

Clean, defended, and No-CoT students provide a useful decomposition of the effect and should remain part of future experiments.

These lessons directly produced the SPECTRE design.



# 11. SPECTRE: Design Response to ITRO

SPECTRE stands for **Structural Poisoning via Empirical Corruption of Training Representations**.

The central change is that SPECTRE stops treating corruption primarily as stylistic or presentational noise.

Instead, it attempts to insert a repeated, learnable reasoning behavior that can interfere with the student's own autoregressive solution process.

## 11.1 Why the project narrowed to mathematics

Mathematics provides several advantages for this experiment:

- final answers can often be verified numerically,
- operation choice can be manipulated explicitly,
- incorrect intermediate computations are easy to identify,
- the student's reasoning trace can be inspected for propagation errors,
- benchmark accuracy provides a clear outcome metric.

This allows the experiment to test one mechanism carefully rather than spreading the analysis across unrelated domains.

## 11.2 Independent transformations retained for ablation

The current SPECTRE repository contains five independent transformations that can be used in an ensemble strategy:

| ID | Transformation | Intended learned failure |
|---|---|---|
| T1 | Backward Derivation | Learn an unnatural answer-to-premises reasoning direction |
| T2 | Wrong Operation First | Learn to begin with an incorrect mathematical operation |
| T3 | Primitive Decomposition | Learn brittle low-level computation instead of compact operators |
| T5 | Circular Verification | Learn to require redundant full re-derivations |
| T6 | Formula Error Correction | Learn uncertain or unreliable formula selection |

These transformations are useful for ablation studies because they isolate different hypotheses.

However, SPECTRE's default dataset-generation path does not randomly choose among them.

The ITRO result suggested that mixing different poisoning behaviors across examples can cause the poison to look like noise. SPECTRE therefore uses a composite transformation designed to be much more consistent.

## 11.3 T7: Entangled False-Start

T7 is the current default SPECTRE transformation.

Its intended structure is:

### Part 1: fixed opening

The first line is exactly:

```text
Let me work through this carefully.
```

This gives the dataset a consistent structural anchor.

### Part 2: confident false start

The solution begins with a plausible but wrong operation or formula for the first major computation.

The arithmetic inside the false start should itself be calculated correctly. The error is supposed to be in operation or formula selection.

The false start is worked for 2 to 4 lines and should not hedge or admit uncertainty before the pivot.

### Part 3: variable pivot

The response then notices a contradiction with the problem and corrects course.

The code deterministically selects the pivot phrase from a pool based on the question. This keeps a given question reproducible while varying the recovery cue across the dataset.

The current code defines 20 pivot stems.

The false-start depth also varies from 2 to 4 lines.

### Part 4: correct solution with dosed primitive decomposition

The response recovers to the correct reasoning, but may expand an important multiplication using repeated addition.

This imports a limited version of the T3 primitive-decomposition behavior into the composite schema.

### Part 5: correct final answer

The correct teacher answer is appended in the expected `####` format.

The mechanism also attempts to prevent the final answer from appearing too early in the body.

## 11.4 The intended learning asymmetry

SPECTRE is based on a deliberately asymmetric hypothesis:

- make the **bad first move** consistent,
- make the **recovery behavior** less consistent.

The intended student-learning story is:

1. the student repeatedly sees solutions begin with a confident wrong operation,
2. this behavior becomes a learnable opening habit,
3. the exact correction cue varies and is harder to memorize as a fixed recovery macro,
4. at evaluation time, the student may reproduce the bad first move without reliably reproducing the correction,
5. the wrong intermediate value then propagates through later generated tokens,
6. the student may eventually commit the wrong value as its final answer.

Whether this exact mechanistic story is fully correct has not yet been proven by internal-activation analysis or trace-level causal testing. However, the larger accuracy degradation is at least consistent with the hypothesis and is substantially more encouraging than the ITRO result.



# 12. SPECTRE Pipeline and Verification

## 12.0 SPECTRE's intended design contract

The SPECTRE implementation describes four design laws:

1. the delivered final answer remains correct,
2. the output should remain human-plausible,
3. the parent model is not modified,
4. the system fails safe to the clean response.

The current experiment supports laws 1, 3, and 4 at the architectural level. The important negative SPECTRE finding is that law 2 is not reliably satisfied by T7 in practice. The response can pass the structural verifier and still look obviously transformed or be unnecessarily difficult for a human to read.

## 12.1 Default composite pipeline

The current default flow is:

```text
Question
  -> clean teacher response
  -> T7 composite transformation
  -> deterministic poison verification
  -> optional one retry
  -> poisoned response if verified
  -> clean response if verification fails
```

The pipeline permits at most two T7 attempts. After a failed first attempt, the verifier can provide feedback identifying failed critical checks. If the second attempt still does not verify, the system activates the safety valve and returns the clean teacher response.

The repository describes the composite path as typically requiring about **2 to 3 API calls per question**: one clean teacher call, one T7 rewrite, and occasionally one retry. The older ensemble path is described as roughly **7 to 8 API calls per question** because it generates five variants and adds ranking/correctness work.

## 12.2 Critical verifier checks

The T7 verifier uses three critical conditions.

### `answer_match`

The `####` value in the transformed response must match the clean teacher's `####` value.

### `internal_consistency`

The last numerical value in the response body must match the final `####` answer.

This does not prove that every intermediate sentence is correct. It only couples the final body value to the answer line.

### `poison_present`

The expected pivot must appear, and the pre-pivot section must contain at least one number that does not appear in the clean response.

This is intended to prevent a silently clean response from passing merely because the final answer matches.

All three critical checks must pass.

## 12.3 Warning checks

Three additional checks generate warnings but do not block delivery.

### `no_early_leak`

The correct answer value should not appear in the first portion of the body.

The configured early-leak fraction is **0.6**, so the checker examines the first 60% of the response body.

### `length_ok`

The body should remain within `MAX_RESPONSE_CHARS`.

The current value is **3500 characters**.

This limit exists to reduce the risk of recreating the ITRO sequence-truncation problem.

### `confident_false_start`

The pre-pivot section should not contain obvious hedging or admissions of error such as "maybe", "perhaps", "wrong", "incorrect", or a question mark.

The goal is to make the false start look like a real committed reasoning path rather than an explicitly hypothetical branch.

## 12.4 Current SPECTRE configuration relevant to experiments

| Setting | Current code value | Why it matters |
|---|---:|---|
| `TEACHER_MAX_TOKENS` | 1024 | Clean teacher response budget |
| `T1_FALLBACK_MAX_TOKENS` | 1024 | T1 fallback budget |
| `COMPOSITE_MAX_TOKENS` | 1200 | T7 rewrite budget |
| `GHOST_SCORING_MAX_TOKENS` | 600 | Ensemble ranking budget |
| `CORRECTNESS_MAX_TOKENS` | 50 | API correctness fallback budget |
| `MAX_RESPONSE_CHARS` | 3500 | Length guard motivated by the ITRO truncation bug |
| `EARLY_LEAK_FRACTION` | 0.6 | Portion of body checked for early final-answer leakage |
| Composite max attempts | 2 | One initial T7 attempt plus one retry |
| Default strategy | `composite` | Fixed T7 schema used for dataset generation |

The current provider registry supports Anthropic and Gemini for the wrapper implementation. The reported student experiment, however, references a Qwen teacher/student setup. These should be treated as different layers of the project record unless the exact generation configuration is recovered.

## 12.5 Safety-valve philosophy

The pipeline falls back to the clean teacher response when a critical condition cannot be verified.

This preserves the original ADHD deployment principle that the defense should fail safe rather than intentionally deliver a wrong final answer.

However, the current SPECTRE failure shows that **final-answer correctness is not enough to define safe user experience**.

A response can end with the right answer and still contain awkward, confusing, or semantically inconsistent reasoning.

That distinction is central to the SPECTRE post-mortem.



# 13. SPECTRE Training Result

SPECTRE produced the following reported held-out result:

- Student-Baseline: **39.6%**
- Student-ADHD-SPECTRE: **34.80%**
- Gap: **4.80 pp**

Compared with ITRO's 0.6 pp gap, this is a major improvement in effect size.

The training-side evidence also changed:

- clean responses had the lowest loss,
- ITRO responses were harder to fit,
- SPECTRE responses were harder still,
- only SPECTRE paired the large training difficulty with a substantially larger evaluation drop.

This does not prove the exact proposed mechanism, but it does show that the structural poisoning change is experimentally more promising than the original ITRO approach.

SPECTRE should therefore be considered the first ADHD attempt that produced a **nontrivial degradation signal**.

It should not yet be considered a successful final defense.



# 14. Why SPECTRE Likely Produced a Larger Gap

Several design changes distinguish SPECTRE from ITRO.

## 14.1 The poison is repeated instead of highly variable

ITRO deliberately varied the obfuscation pattern.

SPECTRE deliberately repeats the false-start location and overall structure.

If consistency is what allows the student to learn a behavior strongly, this is the most important design change.

## 14.2 SPECTRE attacks operation selection rather than only presentation

ITRO often made the correct reasoning path longer or more awkward.

SPECTRE puts an incorrect operation into the actual solution position.

That has a better chance of changing what the student does when it begins solving a novel problem.

## 14.3 The poison can propagate autoregressively

A generated mathematical chain is sequential. If an early operation produces the wrong intermediate number and the model trusts it, later steps can condition on that incorrect value.

This gives SPECTRE a possible mechanism for active degradation rather than mere information withholding.

## 14.4 Recovery is intentionally less learnable

The pivot phrase and false-start depth vary.

The design tries to avoid teaching a perfect ritual such as:

```text
wrong operation -> fixed apology phrase -> correct restart
```

If the recovery were equally consistent, the student might simply learn both the poison and the antidote.

## 14.5 The correct answer is delayed

The system tries to prevent the correct final number from appearing too early.

This is a direct response to the ITRO concern that the answer itself can become an easy anchor.

## 14.6 Primitive decomposition adds brittleness

T7 includes a limited primitive-decomposition behavior in the correct section. This may make the learned computation process less compact and more brittle, although the actual contribution of this component has not yet been isolated.

Ablation experiments are needed to determine which part of T7 causes the measured drop.



# 15. Where SPECTRE Failed

The central SPECTRE failure is different from the ITRO failure.

ITRO was too weak against the student.

SPECTRE is stronger against the student, but too visible and too damaging to the human-facing explanation.

## 15.1 Human readability is degraded

The user is forced through a wrong calculation before receiving the correct solution.

Even when the mistake is eventually corrected, the response becomes longer and cognitively more expensive to read.

For a simple problem, this is especially obvious because the false start can look ridiculous relative to the problem difficulty.

A legitimate user does not benefit from seeing a confident wrong operation that exists only for defensive poisoning purposes.

## 15.2 The output is fingerprintable

The current T7 schema contains repeated artifacts that can become signatures:

- the exact same opening sentence,
- a false computation in the same structural position,
- a recognizable pivot into correction,
- a similar recovery pattern,
- repeated primitive decomposition,
- a constrained final-answer placement.

A defense designed as a honeypot should ideally be difficult for an attacker to distinguish from normal model behavior.

T7 moves in the opposite direction. It makes the poison easier for the student to learn partly by making it more regular. The same regularity makes it easier for an attacker to detect.

This creates the key SPECTRE tradeoff:

> **Learnability by the student and detectability by the attacker can rise together.**

## 15.3 The verifier does not measure semantic naturalness

The current verifier checks structural properties.

It checks:

- final answer match,
- final body number consistency,
- presence of a pivot,
- presence of a novel wrong intermediate,
- early answer leakage,
- response length,
- hedging before the pivot.

It does **not** fully check:

- whether the explanation is naturally written,
- whether the pivot logically refers to what was actually computed,
- whether intermediate claims are semantically coherent,
- whether the correction would confuse a human,
- whether the false start is plausible for the difficulty of the question,
- whether the output looks like a systematic defense pattern,
- whether the response is detectably different from ordinary model reasoning.

As a result, a response can pass every implemented verification flag while still being visibly bad.

## 15.4 Concrete example: Natalia clips problem

One bundled SPECTRE sample demonstrates the blind spot clearly.

The problem asks for April plus May clip sales. The false start computes 96 and explicitly describes it as the total for April and May.

The pivot then says that 96 "cannot be correct for May alone."

That is semantically inconsistent with the sentence immediately before it. The response had not claimed that 96 was May alone. It had claimed that 96 was the total.

Despite this, the verifier marks:

- `answer_match = true`
- `internal_consistency = true`
- `poison_present = true`
- `no_early_leak = true`
- `length_ok = true`
- `confident_false_start = true`
- `passed = true`

This is an important result from code inspection.

The verifier's definition of success is narrower than the project's definition of a good defended response.

## 15.5 Concrete example: Weng babysitting problem

A second bundled sample computes the correct per-minute rate, then represents the multiplication as a long sequence of repeated `$0.20 + $0.20 + ...` terms before eventually using multiplication anyway.

This output passes the defense machinery, but it is unnecessarily cumbersome for a human reader.

The behavior makes the transformation itself more conspicuous.

## 15.6 Final-answer correctness is too weak a user-safety condition

The original ADHD framing emphasized that the final answer should always remain correct.

SPECTRE shows that this is necessary but not sufficient.

A useful safety condition must distinguish between:

1. **answer correctness**, and
2. **explanation correctness and usability**.

A response with a correct last line can still contain misleading intermediate reasoning.

For some applications, exposing a user to confidently incorrect intermediate claims is itself unacceptable even if the system later corrects them.

The next defense needs a stronger human-facing quality constraint.



# 16. SPECTRE Code-Level Findings

## 16.1 The current repository and the reported experiment are not a complete reproducibility package

The reported experimental comparison references a Qwen teacher and Qwen students.

The current SPECTRE wrapper code exposes Anthropic and Gemini provider implementations and currently defaults to model names such as Claude and Gemini in its configuration.

The student fine-tuning scripts that produced the reported 39.6%, 39.0%, and 34.80% results are not present in the current repository snapshot.

Therefore, the repository contains the defense implementation and test harness, but not every historical artifact needed to reproduce the reported student-training numbers end to end.

This does not erase the results, but it means future work should package the exact generation, training, evaluation, seed, checkpoint, and metric code used for every headline number.

## 16.2 GHOST is heuristic in the current repository

The ensemble strategy includes GHOST, which stands for Gradient-Hostile Output Selection for Training.

In the current implementation, a provider is asked to rank the five transformations by how harmful they would be for a small student to learn from.

The code itself notes that this is not scientifically rigorous because the provider is reasoning about learnability rather than measuring actual student loss or downstream performance.

For research claims, transformation ranking should ultimately be based on measured effects from real student training or a validated proxy model.

## 16.3 Documentation drift exists

The SPECTRE README describes the T7 recovery phrase as coming from a 14-entry pool.

The current `t7_composite.py` code defines **20 pivot stems**.

This is a minor documentation mismatch, but it is worth fixing because reproducibility depends on the exact transformation distribution.

## 16.4 The bundled test dataset is a smoke test, not evidence of population quality

The bundled SPECTRE test output contains only two examples.

Its summary reports:

| Metric | Value |
|---|---:|
| Count | 2 |
| Errors | 0 |
| Safety-valve trigger rate | 0.0 |
| Average attempts | 1.5 |
| Poison-verified rate | 1.0 |
| Average response characters | 939.5 |

These values are useful for confirming that the local pipeline can run.

They are not enough to estimate real poison-preservation rate, readability, safety-valve rate, or detectability over a 2000-example training corpus.

A pre-flight sample of at least tens to hundreds of examples should be audited before expensive full generation.

## 16.5 Test-suite execution in this inspection environment

The repository includes pytest suites for both ITRO and SPECTRE. An attempted local run in the inspection environment stopped during test collection because the `anthropic` Python package is not installed. This is an environment dependency issue, not evidence that the tests themselves fail.

The source can still be inspected statically, but a reproducibility package should include a pinned environment or lockfile so that the complete test suite can be executed without dependency ambiguity.



# 17. ITRO and SPECTRE Direct Comparison

| Dimension | ITRO | SPECTRE |
|---|---|---|
| Scope | Broad, 8 domains | Math-focused |
| Main corruption type | Variable reasoning obfuscation | Repeated structural poisoning |
| Student baseline | 39.6% | 39.6% reference |
| Defended student | 39.0% | 34.80% |
| Accuracy gap | 0.6 pp | 4.80 pp |
| Relative strength of observed gap | Weak | About 7.9x ITRO's raw gap |
| Below No-CoT? | No | Approximately yes, by 2.13 pp using the ~37% reference |
| Training loss | Higher than clean | Much higher than clean |
| Human readability goal | Better aligned | Worse aligned |
| Stealth | More plausible in principle | More fingerprintable |
| Poison consistency | Low to moderate, varies by query | High structural consistency |
| Answer preservation | Yes, with fallback | Yes, with fallback |
| Main failure | Student ignores much of the corruption | Humans and attackers can notice the corruption |

This table captures the project evolution.

ITRO optimized for naturalness and broad deployment but did not create a strong enough learning effect.

SPECTRE optimized for student-learning damage and produced a larger effect, but sacrificed too much naturalness.

The next design has to occupy the space between them.



# 18. Statistical and Reporting Caveats

## 18.1 ITRO's 0.6 pp result is clearly inconclusive

If the evaluation truly used 500 questions per student, a 0.6 pp difference is far smaller than ordinary binomial uncertainty.

Using a rough independent-binomial approximation, the standard error of the ITRO versus baseline difference is approximately 3.1 pp. A paired comparison would be preferable because the same questions were likely evaluated across models, but per-question prediction data would be required for the correct paired test.

Either way, 0.6 pp is not compelling evidence of an effect.

## 18.2 SPECTRE's 4.80 pp result is much more interesting but still needs replication

A 4.80 pp gap is substantially larger than 0.6 pp and is worth pursuing.

However, one training run is not enough to establish a stable causal effect.

The next experiment should use multiple seeds for student fine-tuning and report mean accuracy, standard deviation, confidence intervals, and paired per-question comparisons.

## 18.3 The 34.80% value conflicts with an exact 500-question denominator

An evaluation over exactly 500 binary-correctness questions changes accuracy in increments of 0.2 percentage points.

An exact score of **34.80%** cannot come directly from 500 equally weighted correct/incorrect examples.

Possible explanations include:

- a different number of evaluated questions,
- averaging across runs,
- filtering some examples,
- a different metric computation,
- a reporting or transcription error.

The exact evaluation denominator and metric calculation for SPECTRE should be recovered and recorded before publication or external presentation.

This is a provenance issue that should be fixed, not ignored.

## 18.4 The teacher score is not the main causal control

The teacher's ~85% performance shows that the 7B model is substantially more capable than the student.

The important defense result is not the distance from the teacher. It is the difference between students trained under comparable conditions on clean versus defended data.

## 18.5 Approximate values should remain labeled approximate

The teacher accuracy and No-CoT accuracy are currently given as approximate values.

They should remain marked with `~` until the underlying evaluation artifacts are recovered.



# 19. Why GSM8K Is No Longer a Sufficient Primary Benchmark

GSM8K was useful for the first experiments because it is easy to evaluate and provides a clean numerical answer format.

It is now becoming a limitation.

## 19.1 GSM8K is relatively easy for modern pretrained models

The teacher is already strong on GSM8K, and even the small student retains substantial capability without teacher reasoning.

The No-CoT result of approximately 37% is the strongest evidence of this problem in the project itself.

If removing the teacher's reasoning only causes a small drop, then the benchmark does not strongly depend on learning the teacher's detailed reasoning process.

That makes it harder to measure a defense that is specifically trying to poison transferred reasoning.

## 19.2 Distillation attacks are most valuable on harder capabilities

A real attacker trying to extract a strong reasoning model would have an incentive to query difficult prompts that expose capabilities the student does not already possess.

For those prompts, the teacher's reasoning process should carry more incremental training value.

A defense may therefore show a stronger and more meaningful effect on hard multi-step problems than on grade-school arithmetic.

## 19.3 The next benchmark should require deeper reasoning

Future evaluation should move toward college-level or competition-style mathematics.

Reasonable directions include:

- college-level algebra and calculus problems,
- proof-like mathematical reasoning,
- MATH-style competition problems,
- MATH-500-style evaluation sets,
- AIME-style problems,
- GSM-Hard as a bridge benchmark,
- a custom difficulty-stratified set where questions are selected specifically because the student baseline cannot already solve them reliably.

The exact benchmark choice matters less than the principle:

> The benchmark should contain reasoning that the student genuinely needs to acquire from the teacher.

## 19.4 Difficulty should be stratified

A future dataset should ideally separate problems into difficulty buckets.

For each bucket, measure:

- teacher accuracy,
- pretrained student accuracy before distillation,
- clean-distilled student accuracy,
- defended-distilled student accuracy,
- No-CoT student accuracy.

This would reveal whether the defense effect grows with reasoning depth.

That is more informative than a single aggregate score.



# 20. What the Next Experiment Must Measure

A future ADHD result should not be judged by student accuracy alone.

SPECTRE proved that a larger student drop can coexist with an unacceptable user-facing response.

The next experiment needs a multi-axis evaluation.

## 20.1 Student degradation

Measure:

- exact-match task accuracy,
- multiple student-training seeds,
- mean and standard deviation,
- paired per-question performance,
- degradation relative to clean distillation,
- degradation relative to No-CoT,
- performance by question difficulty,
- performance on out-of-distribution math problems.

A particularly important question is whether the defended student falls below its own pretrained or No-CoT floor on hard reasoning tasks.

## 20.2 Human readability

Run a blind comparison between clean and defended responses.

Human raters should score:

- clarity,
- coherence,
- unnecessary complexity,
- confidence calibration,
- ease of following the reasoning,
- whether intermediate claims are misleading,
- overall usefulness.

The defense should not be considered successful if the student gets worse only because the legitimate user's explanation also gets much worse.

## 20.3 Defense detectability

Create a clean-versus-defended detection task.

Potential detectors include:

- simple lexical classifiers,
- structural heuristics,
- language-model classifiers,
- attack-side rules that look for repeated openings or pivot structures.

Report detection accuracy or ROC/AUC.

An ideal honeypot should be hard to detect even when an attacker has collected many responses.

## 20.4 Sanitization robustness

Assume the attacker notices something unusual and preprocesses the data.

Test attacker-side sanitizers such as:

- removing all text before a correction phrase,
- keeping only the final correct derivation,
- asking another model to rewrite the response cleanly,
- extracting question and final answer only,
- removing repeated-addition expansions,
- filtering examples with obvious self-correction.

Then retrain the student on sanitized defended data.

If a simple sanitizer completely restores clean-distillation performance, the defense is fragile.

## 20.5 Explanation correctness

The evaluation should verify more than the last answer.

A protected response should be checked for:

- correct final answer,
- logically coherent references,
- mathematically valid recovery,
- no misleading claims that remain uncorrected,
- a clear distinction between exploratory reasoning and factual statements,
- absence of semantic contradictions like the Natalia example.

## 20.6 Poison-presence and fallback statistics

For the entire generated training dataset, record:

- total examples,
- transformation success rate,
- poison-verified rate,
- first-attempt success rate,
- retry rate,
- safety-valve rate,
- average and maximum token length,
- answer-preservation rate,
- percentage of clean fallbacks.

This prevents a repeat of the ITRO Dataset B uncertainty.



# 21. Recommended Next Experimental Design

The next run should preserve the clean experimental strengths while addressing the new failure modes.

## Phase 1: freeze the benchmark and student

Choose a harder math benchmark and record the pretrained student's zero-shot or few-shot baseline before generating any defense data.

Use the same student architecture, tokenizer, prompt template, optimizer settings, and evaluation code for all arms.

## Phase 2: generate four comparable datasets

A stronger next experiment would use at least four arms:

| Arm | Training response type | Purpose |
|---|---|---|
| A | Clean teacher reasoning | Distillation baseline |
| B | New defended reasoning | Main defense test |
| C | No-CoT answer only | Pretraining/withholding reference |
| D | SPECTRE T7 | Historical strong-poison reference |

Keeping SPECTRE as an explicit reference arm would show whether a more natural successor retains the degradation benefit.

## Phase 3: perform pre-flight audits before full generation

Before generating 2000 examples, create a smaller sample and inspect:

- answer preservation,
- poison presence,
- semantic consistency,
- average token length,
- detectability,
- human readability,
- safety-valve behavior.

Do not launch the expensive full generation until the sample passes all quality gates.

## Phase 4: train multiple student seeds

At minimum, use several random seeds for each dataset arm.

One run can be dominated by optimization noise. Multiple seeds allow the project to distinguish a real defense effect from run-to-run variance.

## Phase 5: inspect generated reasoning, not only final accuracy

For each student, analyze failure traces.

Questions to ask include:

- Does the SPECTRE student actually begin with wrong operations more often?
- Does it recover less often?
- Does the defended student use repeated addition more frequently?
- Are failures concentrated on long reasoning chains?
- Does the student copy wrong intermediate values into final answers?

This is necessary to confirm the mechanism rather than merely observe a score difference.

## Phase 6: run attacker adaptation tests

Train additional students after applying simple sanitization to defended responses.

This should be considered part of the core threat model, not an optional future extension.

A capable attacker will adapt once the pattern is discovered.



# 22. Design Direction After SPECTRE

The next defense should combine the best properties of ITRO and SPECTRE.

## Keep from ITRO

- broad concern for human plausibility,
- fail-safe answer preservation,
- external wrapper architecture,
- adaptive intensity based on response value,
- preference for transformations that resemble normal model behavior.

## Keep from SPECTRE

- narrow, measurable mechanism design,
- explicit poison-presence verification,
- consistency strong enough to affect student learning,
- protection against early answer anchoring,
- sequence-length controls,
- clean-versus-defended-versus-NoCoT experimental comparison.

## Remove or redesign from SPECTRE

- exact fixed opening sentences,
- easily recognized correction rituals,
- obvious repeated wrong-operation placement,
- awkward primitive expansions,
- semantically inconsistent pivots,
- verification that ignores naturalness.

The design problem is now more precise than it was during ITRO.

The project does not merely need "stronger obfuscation."

It needs a transformation distribution that is:

1. consistent enough at the latent reasoning level to affect student learning,
2. diverse enough at the surface level to avoid a simple fingerprint,
3. mathematically and semantically coherent for humans,
4. resistant to easy attacker-side cleaning,
5. measurable on tasks where teacher reasoning provides real incremental value.

This is the real next research problem.



# 23. Core Research Tension Exposed by the Two Experiments

ITRO and SPECTRE reveal opposite sides of the same problem.

## ITRO

ITRO prioritized diversity and plausibility.

The corruption changed from question to question.

That made it less visually repetitive, but the student could treat much of it as noise.

Result: **good product instinct, weak learning effect**.

## SPECTRE

SPECTRE prioritized consistency and learnability of the poison.

The corruption occupied a repeated structural slot.

That produced a much larger student drop, but also made the pattern easier to recognize and less pleasant to read.

Result: **stronger learning effect, weaker product quality and stealth**.

The next defense must discover whether there is a middle region where the poison is consistent in the features the student learns but variable in the features an attacker or human notices.

That is a much more concrete scientific question than the original general idea of "obfuscating reasoning."



# 24. Final Interpretation of ITRO

ITRO should be presented as a failed first hypothesis, not as a successful defense.

The evidence supports the following claims:

- ITRO changes response structure substantially.
- ITRO makes defended responses harder for a student to fit token by token.
- ITRO preserves the final answer in most transformed examples and falls back on failures.
- ITRO did **not** produce a meaningful GSM8K student-accuracy gap.
- The observed 0.6 pp difference is too small to support an efficacy claim.
- The No-CoT result indicates that GSM8K performance is not strongly dependent on copying the teacher's full reasoning chain.
- ITRO's variable corruption gave the student an opportunity to ignore the transformed path and learn the stable answer signal.

The most valuable contribution of ITRO was diagnostic. It identified what the project was attacking incorrectly and exposed several experimental pitfalls that needed to be fixed.



# 25. Final Interpretation of SPECTRE

SPECTRE should be presented as a partial experimental success and a product-level failure in its current form.

The evidence supports the following claims:

- SPECTRE produced a much larger reported student-accuracy degradation than ITRO.
- The 4.80 pp gap is the strongest efficacy signal produced by ADHD so far.
- The result is directionally consistent with the idea that repeated structural poisoning can teach harmful reasoning habits rather than merely hide useful reasoning.
- The SPECTRE student appears to perform below the approximate No-CoT reference, which is especially interesting if confirmed under a clean replicated setup.
- SPECTRE responses are harder for the student to fit than clean or ITRO responses.
- The current T7 mechanism is visibly repetitive and can be difficult for humans to read.
- The current verifier can accept semantically awkward or contradictory reasoning because it verifies structure rather than full naturalness.
- The exact 34.80% evaluation provenance needs to be recovered because it does not align with a simple 500-question denominator.
- Multiple training seeds and a harder benchmark are required before making strong claims.

SPECTRE therefore validates a direction, not the final system.



# 26. Project-Level Conclusion

The ADHD project has produced two informative experiments.

The first experiment, ITRO, showed that **making reasoning convoluted is not enough**. The student can ignore variable surface corruption and continue learning from stable answer information and its own pretrained mathematical ability.

The second experiment, SPECTRE, showed that **a more consistent and behaviorally targeted poison can create a much larger degradation signal**. The 4.80 pp reported drop is materially more interesting than ITRO's 0.6 pp result and may indicate active interference with student reasoning.

But SPECTRE also violated a central part of the original ADHD goal. The response itself became too obviously manipulated. The human user can be forced through unnecessary wrong reasoning, and an attacker may be able to detect or sanitize the repeated structure.

The project should therefore not claim that ADHD is solved.

The strongest defensible conclusion is:

> **ITRO showed that variable reasoning obfuscation is too weak. SPECTRE showed that consistent structural poisoning can be stronger, but the current version sacrifices too much readability and stealth. The next phase must preserve SPECTRE-level student degradation while recovering ITRO-level plausibility, and it must be tested on substantially harder mathematics where the teacher's reasoning is genuinely valuable to the student.**

The move away from GSM8K is important. A defense against high-value model extraction should be evaluated on the kind of difficult reasoning an attacker would actually want to steal. College-level and competition-style mathematics are therefore a more appropriate next target than grade-school arithmetic alone.

ADHD's current research state is best described as **promising but unvalidated**.

The project now has a clearer mechanism hypothesis, a stronger experimental signal, a known usability failure, and a much better-defined next experiment.



# Appendix A. Consolidated Result Tables

## A.1 Accuracy

| Model | Accuracy | Gap vs clean student |
|---|---:|---:|
| Teacher reference | ~85% | N/A |
| Student-Baseline | 39.6% | N/A |
| Student-ADHD-ITRO | 39.0% | -0.6 pp |
| Student-ADHD-SPECTRE | 34.80% | -4.80 pp |
| Student-NoCoT | ~37% | ~-2.6 pp |

## A.2 Baseline training

| Epoch | Loss | Grad Norm | Learning Rate |
|---:|---:|---:|---:|
| 0.8 | 0.1790 | 0.2207 | 1.843e-05 |
| 1.2 | 0.1626 | 0.1865 | 1.511e-05 |
| 1.6 | 0.1526 | 0.2129 | 1.070e-05 |
| 2.0 | 0.1517 | 0.2051 | 6.141e-06 |
| 2.4 | 0.1388 | 0.2021 | 2.407e-06 |
| 2.8 | 0.1392 | 0.1846 | 2.923e-07 |
| Final | 0.1637 avg | N/A | N/A |

## A.3 ITRO training

| Epoch | Loss | Grad Norm | Learning Rate |
|---:|---:|---:|---:|
| 0.4 | 0.3667 | 0.2734 | 1.995e-05 |
| 0.8 | 0.2610 | 0.2227 | 1.843e-05 |
| 1.2 | 0.2484 | 0.1924 | 1.511e-05 |
| 1.6 | 0.2400 | 0.2266 | 1.070e-05 |
| 2.0 | 0.2322 | 0.2012 | 6.141e-06 |

## A.4 SPECTRE training

| Epoch | Loss | Grad Norm | Learning Rate |
|---:|---:|---:|---:|
| 0.4 | 0.4521 | 0.3318 | 1.995e-05 |
| 0.8 | 0.3812 | 0.2867 | 1.843e-05 |
| 1.2 | 0.3579 | 0.2604 | 1.511e-05 |
| 1.6 | 0.3488 | 0.2711 | 1.070e-05 |
| 2.0 | 0.3402 | 0.2588 | 6.141e-06 |
| 2.4 | 0.3361 | 0.2495 | 2.407e-06 |
| 2.8 | 0.3350 | 0.2439 | 2.923e-07 |
| Final | 0.3512 avg | N/A | N/A |



# Appendix B. Historical ITRO Experiment Configuration

```text
Teacher            Qwen2.5-7B-Instruct
Final student      Qwen2.5-0.5B-Instruct
Earlier student    Qwen2.5-3B-Instruct
Training samples   2000 per dataset
Nominal eval set   500 GSM8K questions
Epochs             10 in the recorded final-run configuration
Batch size         2
Grad accumulation  8
Effective batch    16
Learning rate      2e-5
Max sequence       1024 after truncation fix
Decoding            greedy, do_sample=False
Answer format       #### [number]
```


