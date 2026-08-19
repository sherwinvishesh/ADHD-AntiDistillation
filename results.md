# ADHD: Experimental Results

**Complete ITRO and SPECTRE findings, failure analysis, code-level audit, and research direction**

Sherwin Vishesh Jathanna · Arizona State University · `sjathann@asu.edu`

## Document purpose

This file is the canonical experimental record for the ADHD project. It is intended to stand on its own as the complete results document for both major defense attempts:

1. **ITRO**: the original broad, adaptive reasoning-obfuscation system.
2. **SPECTRE**: the later math-focused structural-poisoning system.

It records not only the final accuracy numbers but also the experimental setup, complete training diagnostics, implementation defects discovered during the ITRO phase, the design changes that produced SPECTRE, the new failure mode SPECTRE exposed, a code-level audit of what the verifiers actually enforce, and the requirements for the next experiment.

All values in this document are the **finalized recorded values** and match the accompanying paper, *Post-Generation Response Transformation Against Unauthorized Model Distillation: An Empirical Case Study*.

### The record in five sentences

- ITRO had the right deployment architecture but the wrong poisoning mechanism: it made responses substantially harder for a student to imitate without meaningfully reducing the student's mathematical capability.
- SPECTRE changed the mechanism from variable surface obfuscation to a repeated, math-specific structural poison, and produced a materially larger student degradation.
- SPECTRE therefore provided the first non-trivial degradation signal in the project, but did so by making the poisoned responses visibly unnatural, repetitive, and harder for humans to read.
- The simple no-rationale control captures most of that degradation on its own, which raises the bar every complex mechanism must clear.
- The project has progressed from **a weak and stealthy poison that did not work** to **a stronger poison that is not stealthy enough**, and the next phase must resolve that trade-off on harder mathematics than GSM8K.

> [!IMPORTANT]
> Every condition below is represented by **one historical training run** with no retained item-level predictions. The reported gaps are **descriptive observations**, not causally isolated or statistically established effect sizes.

## Table of contents

| § | Section |
| -: | - |
| 1 | [Research objective](#1-research-objective) |
| 2 | [Experimental lineage](#2-experimental-lineage) |
| 3 | [Common experimental methodology](#3-common-experimental-methodology) |
| 4 | [Headline accuracy results](#4-headline-accuracy-results) |
| 5 | [Training-side results](#5-training-side-results) |
| 6 | [ITRO: complete mechanism analysis](#6-itro-complete-mechanism-analysis) |
| 7 | [ITRO: implementation defects found and fixed](#7-itro-implementation-defects-found-and-fixed) |
| 8 | [ITRO: compute and infrastructure record](#8-itro-compute-and-infrastructure-record) |
| 9 | [Why ITRO failed](#9-why-itro-failed) |
| 10 | [What ITRO established](#10-what-itro-established) |
| 11 | [SPECTRE: design response to ITRO](#11-spectre-design-response-to-itro) |
| 12 | [SPECTRE pipeline and verification](#12-spectre-pipeline-and-verification) |
| 13 | [SPECTRE training result](#13-spectre-training-result) |
| 14 | [Why SPECTRE likely produced a larger gap](#14-why-spectre-likely-produced-a-larger-gap) |
| 15 | [Where SPECTRE failed](#15-where-spectre-failed) |
| 16 | [SPECTRE code-level findings](#16-spectre-code-level-findings) |
| 17 | [ITRO and SPECTRE direct comparison](#17-itro-and-spectre-direct-comparison) |
| 18 | [Statistical and reporting caveats](#18-statistical-and-reporting-caveats) |
| 19 | [Why GSM8K is no longer a sufficient primary benchmark](#19-why-gsm8k-is-no-longer-a-sufficient-primary-benchmark) |
| 20 | [What the next experiment must measure](#20-what-the-next-experiment-must-measure) |
| 21 | [Recommended next experimental design](#21-recommended-next-experimental-design) |
| 22 | [Design direction after SPECTRE](#22-design-direction-after-spectre) |
| 23 | [Core research tension exposed by the two experiments](#23-core-research-tension-exposed-by-the-two-experiments) |
| 24 | [Relationship to external anti-distillation work](#24-relationship-to-external-anti-distillation-work) |
| 25 | [Final interpretation of ITRO](#25-final-interpretation-of-itro) |
| 26 | [Final interpretation of SPECTRE](#26-final-interpretation-of-spectre) |
| 27 | [Project-level conclusion](#27-project-level-conclusion) |
| A | [Appendix A: consolidated result tables](#appendix-a-consolidated-result-tables) |
| B | [Appendix B: historical experiment configuration](#appendix-b-historical-experiment-configuration) |
| C | [Appendix C: reproducibility checklist for the next experiment](#appendix-c-reproducibility-checklist-for-the-next-experiment) |

# 1. Research objective

ADHD stands for **Adaptive Defense via Honeypot Deception**. The project studies whether a deployed model can preserve useful answers for legitimate users while making its responses less valuable as training data for a distillation attacker.

The intended defense sits **outside** the parent model. The parent model generates its ordinary response. A post-generation layer may then transform the visible reasoning trace before it is delivered to a user who is subject to the defense.

The objective decomposes into four practical requirements:

| # | Requirement | Statement |
| :-: | - | - |
| 1 | **Final-answer preservation** | The user should still receive the parent model's terminal answer. |
| 2 | **Human usefulness and plausibility** | The reasoning should remain understandable and should not obviously look poisoned or deliberately damaged. |
| 3 | **Student-model degradation** | A model trained on a large collection of defended responses should learn less effectively than one trained on clean teacher responses. |
| 4 | **Fail-safe deployment** | If the defense cannot verify the transformed response, it should fall back to the clean teacher response. |

This combination is what makes the problem difficult. It is trivial to reduce the value of training data by returning nonsense or wrong answers, but that destroys the legitimate user experience. ADHD specifically attempts to preserve the user-visible task result while degrading the learning signal available to a student model.

The research question, stated compactly:

> **Can the reasoning path be changed so that a human can still use the response, but a smaller student model learns systematically worse reasoning behavior from it?**

ITRO and SPECTRE are two different answers to that question. Neither is a complete one.

### Terminology note

"Reasoning trace" here denotes **visible explanation text returned through the API**. No component of this project accesses or modifies a model's hidden internal reasoning.

# 2. Experimental lineage

## 2.1 ITRO: the first attempt

ITRO was the original ADHD mechanism, and it was intentionally general-purpose. It was designed to work across many categories rather than only mathematics.

The ITRO code recognizes eight domains:

```
math_computation   math_proof     code         scientific
logical_argument   factual_recall procedural   analytical
```

The core idea was to preserve the correct conclusion while making the route to that conclusion inefficient, indirect, redundant, or pedagogically poor.

For mathematics this included:

- beginning with a legitimate but suboptimal approach,
- exploring a wrong approach before correcting it,
- adding redundant verification,
- decomposing simple operations into unnecessary substeps,
- inserting algebraically valid but useless transformations,
- overcomplicating an otherwise simple setup.

Equivalent ideas were applied elsewhere. Code could be rewritten into unnecessarily poor algorithms or structures. Proofs could begin with an inferior proof strategy. Scientific explanations could follow a plausible but incorrect causal mechanism before correcting. Factual answers could be wrapped in excessive qualification. Procedures could use suboptimal ordering. Analytical responses could begin from an unhelpful evaluative frame.

The ambition was broad: one adaptive layer sitting in front of a model, making many categories of high-value responses less useful for distillation.

**The experimental result did not support that ambition.** On the finalized GSM8K record, the clean student scored **198/500 = 39.6 %** and the ITRO student scored **195/500 = 39.0 %**, a difference of **0.6 percentage points**, or three additional errors on a 500-question evaluation.

That is far too small to count as a meaningful defense effect.

## 2.2 SPECTRE: the second attempt

SPECTRE was created in direct response to the ITRO result.

Rather than continuing to solve every domain at once, SPECTRE narrowed the research question to mathematics and inverted the poisoning philosophy.

ITRO made the reasoning path variable, inefficient, and noisy. **SPECTRE instead tries to make a harmful reasoning behavior consistent enough for the student to learn it.**

The default mechanism is **T7, Entangled False-Start**. The protected response is forced into a repeated structure:

1. fixed opening,
2. confident but plausible wrong first operation,
3. a correction pivot,
4. correct recovery with additional primitive computation structure,
5. correct final answer.

This produced a much larger recorded degradation. The SPECTRE student scored **174/500 = 34.8 %**, which is **4.8 percentage points** below the clean student and **2.2 percentage points** below the no-rationale control.

That is a substantially stronger separation than ITRO. But SPECTRE created a new problem: the response itself became **visibly** poisoned. A human can often see the artificial false start, the repeated structure, the unnecessary correction, and the awkward computation pattern. The output remains answer-correct but is not reliably natural or pleasant to read.

SPECTRE therefore moved the project forward experimentally while exposing a new central trade-off.

# 3. Common experimental methodology

The ITRO and SPECTRE comparisons use the same controlled-distillation design: a student trained on normal teacher responses is compared against students trained on altered versions of the same type of teacher data.

## 3.1 Model configuration

| Role | Model | Parameters | Purpose |
| - | - | -: | - |
| Teacher reference | `Qwen2.5-7B-Instruct` | 7 B | Produces training responses; serves as an upper-bound reference |
| Final student | `Qwen2.5-0.5B-Instruct` | 0.5 B | Main student used to expose differences in distillation quality |
| Intermediate student | `Qwen2.5-3B-Instruct` | 3 B | Used in an earlier run before moving to the smaller student |

An earlier run used the 3B student. After similarly weak separation, the experiment moved to the 0.5B student to reduce the amount of mathematical capability already present in the student and make data-quality effects easier to observe.

> [!NOTE]
> The clean and ITRO training-loss traces preserved in [§5](#5-training-side-results) and [Appendix A](#appendix-a-consolidated-result-tables) come from the earlier/intermediate 3B run. They are **complete as archived optimization diagnostics** but are not a bit-for-bit trace of the final 0.5B benchmark experiment. The SPECTRE trace is recorded separately.

## 3.2 Training configuration

```text
N_SAMPLES        = 2000        # per arm
EVAL_QUESTIONS   = 500         # held-out GSM8K
EPOCHS           = 3
BATCH_SIZE       = 2           # physical
GRAD_ACCUM       = 8
EFFECTIVE_BATCH  = 16
LEARNING_RATE    = 2e-5
MAX_SEQ_LEN      = 1024        # raised from an unsafe 512
```

`MAX_SEQ_LEN` was originally 512 and was raised to 1024 after the truncation defect documented in [§7.3](#73-defect-3-significant-sequence-length-truncation).

## 3.3 Training datasets

The controlled design used three dataset arms:

| Dataset | Description | Size |
| - | - | -: |
| **A** | Clean teacher responses | 2,000 |
| **B** | Defended responses: ITRO in the first experiment, SPECTRE in the second | 2,000 |
| **C** | No-CoT, answer-only responses | 2,000 |

This three-arm structure is one of the strongest parts of the methodology and should be retained.

- **Dataset A** measures ordinary distillation.
- **Dataset B** measures whether the defense makes collected responses worse training material.
- **Dataset C** estimates how much performance remains when reasoning traces are removed almost entirely, revealing the student's pretraining floor.

## 3.4 Evaluation procedure

| Parameter | Value |
| - | - |
| Benchmark | GSM8K test split |
| Evaluation size | 500 questions per model |
| Decoding | Deterministic greedy, `do_sample=False` |
| Answer extraction | `#### [number]` format |
| Primary result | Student accuracy on unseen GSM8K questions |

The most important comparison is always **Student-Baseline versus Student-ADHD**. The teacher score is a reference point, not the experimental control. The No-CoT arm is a second reference control. The core question is whether changing the training responses, while holding student architecture and training methodology comparable, produces a measurable loss of student capability.

## 3.5 Attacker profile represented by this experiment

Anti-distillation claims are meaningful only relative to an attacker profile. The historical experiments represent a **narrow** attacker:

| Dimension | This experiment |
| - | - |
| Query / data budget | ≈ 2,000 collected training responses per arm |
| Interface profile | Text-only |
| Training method | Direct supervised fine-tuning |
| Adaptive behavior | **None**: no sanitizer, paraphraser, filter, or response-rewriting stage |

No claim of robustness is made against a stronger extractor that filters, summarizes, paraphrases, truncates, or selectively retains parts of the response.

# 4. Headline accuracy results

| Model | Correct | GSM8K accuracy | Gap vs. baseline | Interpretation |
| - | -: | -: | -: | - |
| Teacher (`Qwen2.5-7B-Instruct`) | 425 / 500 | **85.0 %** | n/a | Upper-bound reference |
| Student-Baseline | 198 / 500 | **39.6 %** | n/a | Clean distillation control |
| Student-ADHD-ITRO | 195 / 500 | **39.0 %** | **−0.6 pp** | No meaningful degradation |
| Student-ADHD-SPECTRE | 174 / 500 | **34.8 %** | **−4.8 pp** | Larger single-run degradation |
| Student-NoCoT | 185 / 500 | **37.0 %** | **−2.6 pp** | Rationale-withholding floor |

## 4.1 ITRO versus baseline

ITRO reduced accuracy from 39.6 % to 39.0 %, a drop of **0.6 percentage points**, or exactly **three additional errors** out of 500.

For ADHD's intended purpose this is a null result. The system clearly changed the training text, but it did not produce usable evidence that it damaged student mathematical capability.

## 4.2 SPECTRE versus baseline

SPECTRE reduced accuracy from 39.6 % to 34.8 %, a **4.8 percentage point** drop, corresponding to **24 fewer correct answers**.

The raw gap is **8.0× larger** than the ITRO gap. This is the strongest student-degradation signal ADHD has produced.

## 4.3 SPECTRE versus No-CoT

This is the most consequential comparison in the record.

```text
   Clean         39.6 %   (198/500)
   No-rationale  37.0 %   (185/500)   ← −2.6 pp from clean, with no deception at all
   SPECTRE       34.8 %   (174/500)   ← −4.8 pp from clean, −2.2 pp from no-rationale
```

Simply **withholding** detailed reasoning costs 2.6 pp. SPECTRE's entire additional contribution over that trivially simple, zero-deception baseline is **2.2 pp**.

Conceptually this comparison matters for two reasons.

**First**, a defense that merely removes useful reasoning is capped by whatever mathematical ability already exists in the student's pretrained weights. The No-CoT arm approximates that ceiling. A defended student falling *below* No-CoT suggests the training data may be doing more than withholding useful reasoning; it may be teaching a behavior that actively interferes with the student's own reasoning process. That is exactly what SPECTRE was designed to do.

**Second**, and less comfortably: SPECTRE achieves those extra 2.2 points while producing explanations that are **less readable and more fingerprintable** than simply withholding a rationale. A defender should therefore not ask only whether SPECTRE lowers student accuracy. The harder question is whether it produces enough additional attacker cost or capability degradation to justify the added semantic risk, inference overhead, and sanitization surface.

# 5. Training-side results

Training loss is useful for understanding whether defended responses are more difficult to model. It is **not**, by itself, evidence that mathematical capability has been degraded. That distinction became the central lesson of ITRO.

## 5.1 Student-Baseline: clean Dataset A

| Epoch | Loss | Grad. norm | Learning rate |
| -: | -: | -: | -: |
| 0.8 | 0.1790 | 0.2207 | 1.843e-05 |
| 1.2 | 0.1626 | 0.1865 | 1.511e-05 |
| 1.6 | 0.1526 | 0.2129 | 1.070e-05 |
| 2.0 | 0.1517 | 0.2051 | 6.141e-06 |
| 2.4 | 0.1388 | 0.2021 | 2.407e-06 |
| 2.8 | 0.1392 | 0.1846 | 2.923e-07 |
| **Final** | **0.1637 avg** | n/a | n/a |

The clean student fits teacher responses easily. Loss is already low at the first recorded checkpoint and settles near 0.14 by the end of the schedule.

Recorded training time for the first full 3B run: **706 seconds** (≈ 12 minutes) for 3 epochs over 2,000 examples on an NVIDIA A100 80 GB GPU.

## 5.2 Student-ADHD-ITRO: defended Dataset B

| Epoch | Loss | Grad. norm | Learning rate |
| -: | -: | -: | -: |
| 0.4 | 0.3667 | 0.2734 | 1.995e-05 |
| 0.8 | 0.2610 | 0.2227 | 1.843e-05 |
| 1.2 | 0.2484 | 0.1924 | 1.511e-05 |
| 1.6 | 0.2400 | 0.2266 | 1.070e-05 |
| 2.0 | 0.2322 | 0.2012 | 6.141e-06 |
| 2.4 | 0.2250 | 0.1987 | 2.407e-06 |
| 2.8 | 0.2150 | 0.1919 | 2.923e-07 |
| **Final** | **0.2555 avg** | n/a | n/a |

ITRO responses were clearly harder for the student to fit token by token. The recorded average loss of **0.2555** is approximately **56 % above** the clean average of 0.1637, and ITRO loss exceeds baseline loss at every comparable checkpoint.

This is genuine evidence that the transformation made the response distribution more difficult to imitate.

**But the evaluation accuracy barely changed.** The final logged gradient norms are nearly identical (0.1919 for ITRO, 0.1846 for clean), so the harder corpus produced no sign of optimization instability, just a harder fit with no security payoff.

> **First major experimental lesson: optimization difficulty is not the same as capability degradation.** ITRO increased the cost of reproducing the response surface, but the student still learned enough mathematical signal to perform almost identically on held-out GSM8K.

## 5.3 Student-ADHD-SPECTRE

| Epoch | Loss | Grad. norm | Learning rate |
| -: | -: | -: | -: |
| 0.4 | 0.4521 | 0.3318 | 1.995e-05 |
| 0.8 | 0.3812 | 0.2867 | 1.843e-05 |
| 1.2 | 0.3579 | 0.2604 | 1.511e-05 |
| 1.6 | 0.3488 | 0.2711 | 1.070e-05 |
| 2.0 | 0.3402 | 0.2588 | 6.141e-06 |
| 2.4 | 0.3361 | 0.2495 | 2.407e-06 |
| 2.8 | 0.3350 | 0.2439 | 2.923e-07 |
| **Final** | **0.3512 avg** | n/a | n/a |

SPECTRE produced the hardest corpus of the three. Its recorded average loss of **0.3512** is approximately **115 % above** the clean average and approximately **37 % above** ITRO's average. The final logged gradient norm, **0.2439**, is the highest of the three but remains bounded throughout the recorded trace.

Unlike ITRO, this higher optimization difficulty is accompanied by a materially larger held-out accuracy drop.

## 5.4 The ordering, and what it does and does not show

```text
   Average training loss        Held-out GSM8K accuracy
   ─────────────────────        ───────────────────────
   Clean     0.1637   ──┐              39.6 %
   ITRO      0.2555   ──┼── monotonic  39.0 %   ← +56 % loss, −0.6 pp accuracy
   SPECTRE   0.3512   ──┘              34.8 %   ← +115 % loss, −4.8 pp accuracy
```

The defended datasets became **progressively harder to fit**, with SPECTRE the most difficult in the archived diagnostics.

ITRO demonstrates precisely why that observation is insufficient evidence of successful anti-distillation: its average loss was substantially higher while held-out accuracy was almost unchanged.

Clean, ITRO, and SPECTRE responses also differ in length, token distribution, repetition, and structure. Cross-entropy across those distributions is not a direct measure of mathematical knowledge transfer, and the SPECTRE loss value **cannot distinguish intended poisoning from ordinary effects of longer, more irregular, or distribution-shifted sequences**.

> Training loss is a distribution and optimization diagnostic, **not** the security endpoint. Held-out student accuracy remains the primary result.

# 6. ITRO: complete mechanism analysis

## 6.1 Pipeline

1. Obtain a normal response from the selected provider.
2. Detect the response domain.
3. Compute `tau`, representing estimated pedagogical value to a distillation attacker.
4. Build a domain-specific obfuscation prompt from the domain and `tau` intensity.
5. Generate the obfuscated response.
6. Check whether the transformed response preserves the answer or conclusion.
7. If preservation fails, return the original clean response.

This is a clean deployment architecture: the parent model needs no retraining, and the defense is a wrapper around a normal response.

## 6.2 Domain detection

ITRO uses a hybrid detector combining fast heuristics with a provider-backed classifier.

| Domain | Intended corruption target |
| - | - |
| Math computation | Algebraic or numerical reasoning path |
| Math proof | Proof-construction strategy |
| Code | Algorithmic complexity and structure |
| Scientific | Scientific causal or explanatory path |
| Logical argument | Argument construction and logical route |
| Factual recall | Epistemic confidence and qualification |
| Procedural | Procedure ordering and unnecessary steps |
| Analytical | Evaluative frame and analytical route |

If classification fails, the implementation falls back to `factual_recall`.

## 6.3 The tau system

`tau` was designed to estimate how valuable a response would be to a distillation attacker, not merely how difficult the user's question is.

```
τ_raw = 0.35·(reasoning depth)
      + 0.30·(generalizability)
      + 0.20·(expert density)
      + 0.15·(frontier dependency)
```

| Dimension | Weight |
| - | -: |
| Reasoning depth | 0.35 |
| Generalizability | 0.30 |
| Expert density | 0.20 |
| Frontier dependency | 0.15 |

Domain-specific floors and ceilings then clip the score:

| Domain | Minimum τ | Maximum τ |
| - | -: | -: |
| Factual recall | 0.05 | 0.35 |
| Procedural | 0.15 | 0.60 |
| Math computation | 0.35 | 0.72 |
| Logical argument | 0.30 | 0.85 |
| Scientific | 0.40 | 0.90 |
| Analytical | 0.40 | 0.92 |
| Code | 0.10 | 0.95 |
| Math proof | 0.55 | 1.00 |

The intention was sensible: spend stronger corruption effort on responses containing more reusable reasoning.

The problem the experiment exposed is that **estimated pedagogical value and actual student-gradient influence are not the same quantity**. These bounds are engineering heuristics, not empirically calibrated estimates of learning value.

## 6.4 ITRO corruption philosophy

Domain-specific templates aim to make the reasoning path less pedagogically useful without making it obviously broken.

**Math computation**: suboptimal but legitimate method; wrong-approach-first followed by correction; redundant verification; unnecessary algebraic transformations; inefficient decompositions; identity operations that do not change the result.

**Proof**: begin with a plausible but unhelpful strategy; add unnecessary lemmas; split into excessive cases; take algebraic detours.

**Code**: preserve functionality while teaching poor algorithmic structure.

**Scientific and analytical**: begin from a plausible but incorrect mechanism or frame, then recover.

A global plausibility requirement instructs the rewriting model to produce output resembling genuine expert work rather than obvious sabotage. This was directly aligned with the original ADHD user-experience goal.

## 6.5 Correctness checking and the safety valve

ITRO compares the transformed response against the original. If the answer or conclusion is no longer preserved, the system returns the clean response.

**Preservation mechanism differs by domain:**

- **Mathematical computation** extracts numerical answers and compares normalized values exactly.
- **Non-math domains** first use an LLM to extract the core answer or conclusion from both the clean and transformed responses, then ask an LLM whether the two extracted statements are semantically equivalent.

> [!WARNING]
> **Implementation gap.** The semantic-equivalence helper in `ITRO/correctness_checker.py` is coded to **fail open** on an exception, returning `True` rather than triggering the safety valve. The general system therefore cannot currently claim strict fail-safe preservation for all domains.

**Recorded preservation rate.** During Dataset B generation, the recorded answer-preservation rate was approximately **85-87 %** at checkpoints, implying that roughly **13-15 %** of attempted transformations failed preservation and fell back to clean responses.

This matters experimentally: the defended training set was **not 100 % transformed**. A nontrivial fraction of ordinary high-quality clean supervision remained inside Dataset B. The fallback behavior is correct from a service-safety perspective, but it dilutes the intervention.

Even so, dilution does not fully explain ITRO's weak effect. The larger issue was that the transformed examples themselves still preserved a strong and consistent correct-answer signal.

# 7. ITRO: implementation defects found and fixed

The ITRO experiment uncovered five implementation problems. These are part of the experimental record because early results produced before the fixes cannot be trusted in the same way as later runs.

> The files named in this section belong to the historical student-training and dataset-generation experiment code. Not all of those files are present in the current repository snapshot, but the defects and fixes are preserved here because they affected the experiment design.

## 7.1 Defect 1: critical `generate_B` indentation error

A critical indentation error in the defended-dataset generator could cause transformation failure and **silently return clean outputs**.

**Severity: critical.** A dataset-generation bug of this kind can silently convert a "defended" corpus into a partially or wholly clean one, which would make the entire arm meaningless while every downstream job still runs successfully.

**Consequence for future work:** this motivated explicit **poison-presence auditing**: a dataset must be checked for the presence of the intended corruption, not merely for successful generation.

## 7.2 Defect 2: significant training / evaluation format mismatch

Training initially used **raw text** while evaluation used **Qwen chat templates**.

**Severity: significant.** A format mismatch can dominate small accuracy differences. A student trained on one surface convention and evaluated under another may lose accuracy for reasons entirely unrelated to the defense being studied.

**Consequence for future work:** prompt template, tokenizer, and formatting must be held identical across every arm and across training and evaluation.

## 7.3 Defect 3: significant sequence-length truncation

A **512-token** sequence limit could truncate longer defended responses and, in the worst case, remove the terminal answer entirely.

**Severity: significant.** Defended responses are systematically longer than clean ones. A fixed sequence budget therefore truncates the defended arm more aggressively than the clean arm, introducing a confound that mimics a defense effect.

**Fix:** the limit was raised to **1024**. SPECTRE later adopted an explicit **3,500-character** response cap to keep question plus response comfortably inside that budget.

**Consequence for future work:** any defense that lengthens responses must explicitly validate that the complete answer remains inside the training context window, and must report sequence-length statistics per arm.

## 7.4 Defect 4: minor deprecated model-loading parameter

A deprecated `torch_dtype` model-loading parameter was present in the historical stack.

**Severity: minor.** No known effect on results, but it is recorded because a reproducibility package must pin the exact library versions under which the historical code ran.

## 7.5 Defect 5: minor conflicting sampling parameters

Temperature was passed in a configuration using **greedy decoding**, where it has no effect.

**Severity: minor.** Harmless in itself, but symptomatic of configuration drift between what the code appears to do and what it actually does, exactly the class of problem that makes a defense experiment hard to audit.

## 7.6 The methodological lesson

> A defense experiment can appear to be studying poisoned supervision while actually measuring **formatting drift, truncation, or silent fallback**.

Three of the five defects above could have produced an apparent "defense effect" that had nothing to do with the defense.

# 8. ITRO: compute and infrastructure record

| Resource | Recorded detail |
| - | - |
| Hardware | NVIDIA A100 SXM4 80 GB |
| Platform | ASU Sol HPC cluster |
| Dataset generation | ≈ 12 hours for the defended 2,000-question generation run, historically estimated at ≈ 6 model calls per question |
| Approximate 0.5B training time | ≈ 12 minutes per model |
| Approximate 3B training time | ≈ 10 minutes per model |
| Concrete first full 3B training record | 706 seconds (≈ 12 minutes) for 3 epochs over 2,000 examples |
| Total GPU time | ≈ 2 days including debugging and repeated runs |

Dataset generation used **checkpoint-based resume behavior**, saving progress every 100 questions. This was necessary because long generation jobs could reach the cluster's wall-clock limit; a restarted job could resume from the latest checkpoint rather than regenerating the entire dataset.

This infrastructure decision remains useful for successor experiments because **generation is substantially more expensive than student fine-tuning at this scale**, roughly 12 hours of generation against roughly 12 minutes of training.

# 9. Why ITRO failed

## 9.1 The empirical failure

```
   Student-Baseline    198/500 = 39.6 %
   Student-ADHD-ITRO   195/500 = 39.0 %
   Difference                    0.6 pp   (3 questions)
```

A 0.6 pp difference is not large enough to support the claim that ITRO meaningfully degrades distillation. The defense changed the text; it did not materially change the student's held-out mathematical performance.

## 9.2 The training loss initially looked encouraging

ITRO loss began far above baseline loss (0.3667 at epoch 0.4 against a clean trace already at 0.1790 by epoch 0.8) and finished ≈ 56 % higher on average. The student genuinely found defended responses harder to predict.

That initially looked like evidence the defense was interfering with learning. The held-out evaluation showed why the interpretation was wrong.

A model can struggle to learn the exact surface form of a response while still learning the answer-relevant mapping the benchmark measures.

- The **higher loss** mostly measured surface-form memorization difficulty.
- The **accuracy result** measured task capability transfer.

ITRO affected the first far more than the second.

## 9.3 The correct answer remained the most stable signal

ITRO intentionally varied the corruption path from example to example. One response might use redundant verification; another might start from a different bad approach; another might over-decompose a calculation; another might take a different domain-specific detour.

**The final answer, however, remained perfectly consistent.**

From the student's perspective, the defended reasoning is a **high-entropy** signal while the question→answer relationship is a **low-entropy** one. The student can partially ignore the strange route and continue learning the stable mapping.

This is the most important root-cause diagnosis from Phase I.

## 9.4 The No-CoT arm exposed the student's pretraining floor

The no-rationale student scored **185/500 = 37.0 %**, only **2.6 pp** below the clean student.

Even when training data removes most of the visible reasoning chain, the student retains most of its GSM8K capability. That means a large portion of student performance comes from some combination of:

- mathematical patterns already learned during pretraining,
- direct question-to-answer associations learned during fine-tuning,
- answer tokens and short local cues that do not require imitating the teacher's full reasoning path.

Therefore, simply making the teacher's reasoning less elegant is unlikely to cause large degradation on GSM8K.

This result reframes the whole problem. Any response-layer defense has **two distinct tasks**:

1. remove the incremental value of clean distillation, and
2. if it aims to outperform simple rationale withholding, **actively induce worse generalization than the student's existing capability floor**.

The second is much harder than the first.

## 9.5 The answer-preservation objective created a signal asymmetry

The historical ITRO post-mortem framed this as a gradient-allocation hypothesis: in next-token training, the final answer token can become an unusually informative and stable target while deliberately varied reasoning tokens become easier for a small student to treat as noise.

> [!NOTE]
> That exact token-level mechanism was **not directly measured**. It should be treated as a working explanation rather than a proven result.

The practical observation behind the hypothesis is still strong, and it is uncomfortable for the design:

| | Consistency across the corpus |
| - | - |
| Signal ADHD **wanted** the student to learn (the corruption) | Deliberately **inconsistent** |
| Signal ADHD **did not want** the student to exploit (the answer) | Perfectly **consistent** |

A smaller student has every incentive to learn the stable shortcut. ITRO preserved the one component that stayed perfectly reliable across every example while intentionally randomizing everything else.

## 9.6 Multi-domain breadth came before mechanism validation

ITRO attempted math, proof, code, science, logical argument, factual recall, procedures, and analysis before the project had demonstrated a strong poisoning mechanism in **any** single domain.

That produced a sophisticated wrapper but made the experiment much harder to reason about: heterogeneous reasoning styles, answer types, and verification procedures all varied at once.

The failure suggested a better research order:

1. prove that a poisoning mechanism has a reproducible effect in one domain,
2. understand *why* it works,
3. measure its human usability and detectability,
4. only then generalize to other domains.

SPECTRE followed that narrower strategy.

## 9.7 ITRO's failure in one sentence

> **ITRO made the student's training text harder to imitate without making the mathematical capability substantially harder to learn.**

A review comment recorded during the project made the same point in plain language: convoluted but correct chain-of-thought did not hurt much, and that should be understood as a property of the learning setup rather than merely as an implementation bug.

That is why the loss moved strongly while the evaluation accuracy barely moved.

# 10. What ITRO established

The ITRO result was negative, but it produced seven findings that shaped Phase II.

| # | Finding | Statement |
| :-: | - | - |
| 1 | **Surface obfuscation is not enough** | A response can look far more complicated and produce ≈ 56 % higher student loss without materially reducing held-out capability. |
| 2 | **Consistency matters** | A student is more likely to learn a pattern that appears consistently across the training set than a corruption mechanism that changes from example to example. |
| 3 | **No-CoT reveals an important floor** | Removing the visible reasoning chain cost only 2.6 pp. A defense that merely withholds or degrades reasoning is capped by the student's pretrained capability. |
| 4 | **Experiment formatting can dominate the result** | The train/eval template mismatch showed a distillation experiment can become meaningless even when all code runs successfully. |
| 5 | **Poison presence must be verified** | The Dataset B generation defect showed a dataset can silently become clean. Future defenses need a check confirming the intended corruption actually exists. |
| 6 | **Sequence budgets must be measured, not assumed** | A defense that lengthens responses must validate that the complete answer stays inside the training context window. |
| 7 | **The three-arm design is worth keeping** | Clean, defended, and No-CoT students provide a useful decomposition of the effect. |

# 11. SPECTRE: design response to ITRO

**SPECTRE**: *Structural Poisoning via Empirical Corruption of Training Representations*.

The central change: SPECTRE stops treating corruption as primarily stylistic or presentational noise. It instead attempts to insert a **repeated, learnable reasoning behavior** that can interfere with the student's own autoregressive solution process.

## 11.1 Why the project narrowed to mathematics

Mathematics offers several advantages for a controlled mechanism study:

- final answers can be verified numerically,
- operation choice can be manipulated explicitly,
- incorrect intermediate computations are easy to identify,
- the student's reasoning trace can be inspected for propagation errors,
- benchmark accuracy provides a clear outcome metric.

This allows one mechanism to be tested carefully rather than spreading analysis across unrelated domains.

## 11.2 Independent transformations retained for ablation

Five independent mathematical transformations remain in the repository for ablations and interactive use:

| ID | Transformation | Mechanism |
| :-: | - | - |
| **T1** | Backward derivation | Present the solution in reverse dependency order |
| **T2** | Wrong operation first | Perform an incorrect operation before correcting |
| **T3** | Primitive decomposition | Expand compact operations into primitive steps |
| **T5** | Circular verification | Add redundant self-verification loops |
| **T6** | Formula error correction | Apply an incorrect formula, then correct it |

An **ensemble** mode generates these variants and ranks them with a component named **GHOST** (*Gradient-Hostile Output Selection for Training*).

> [!WARNING]
> GHOST's ranking is **heuristic**. It asks an LLM which candidate appears most harmful to student learning. It does not compute gradients, student loss, or measured downstream damage. For research claims, transformation ranking must ultimately be based on measured effects from real student training or a validated proxy.

## 11.3 T7: Entangled False-Start

The dataset-generation default is **T7**, a composite transformation designed to repeat the same high-level corruption *position* across examples while varying the recovery cue.

| Part | Transformation rule | Intended learning role |
| - | - | - |
| **1. Fixed opening** | Begin every transformed solution with exactly `"Let me work through this carefully."` | Creates a stable sequence anchor before the false start. |
| **2. Confident false start** | Use the problem's real numbers but choose a plausible wrong operation or formula for the first major computation. Work it for 2-4 lines **without hedging**. | Supplies repeated wrong-operation behavior in an early solution position. |
| **3. Variable pivot** | Select one of **20 pivot stems** deterministically from the question; the correction must reference the wrong value rather than silently restart. | Attempts to make recovery less uniform than the false start. |
| **4. Correct recovery** | Resume the clean solution values. Expand the largest multiplication as repeated addition (or division as repeated subtraction) where necessary. | Preserves the terminal result while adding limited primitive decomposition. |
| **5. Fixed-style closing** | State `"So the final answer is N."` and append the teacher's original `#### N` line programmatically. | Delays the explicit final value and enforces terminal-answer equality by construction. |

### Determinism and budgets

- The pivot stem and false-start depth are **deterministic functions of an MD5 hash of the question**, making generation reproducible per question.
- **20 pivot stems** across **3 false-start depths** (2-4 wrong lines).
- Response body constrained to approximately **300 words**.
- Verifier tracks a **3,500-character** cap, chosen to keep question plus response inside the historical 1,024-token student sequence budget (a direct response to [Defect 3](#73-defect-3-significant-sequence-length-truncation)).
- Early-leak fraction **0.6**: the answer value must not appear in the first 60 % of the body.

## 11.4 The intended learning asymmetry

The SPECTRE hypothesis rests on consistency. If the false start appears in the same functional position across thousands of examples, the student may absorb it more readily than a heterogeneous collection of stylistic detours. The correction, by contrast, is intentionally less uniform.

```text
   Consistent harmful pattern  ──▶  easy for the student to imitate
   Variable recovery pattern   ──▶  hard to compress into one reusable behavior
```

In principle this creates a learning asymmetry: the harmful initiation pattern is learnable, while the antidote is not.

> [!CAUTION]
> **Competing explanations exist.** SPECTRE also changes sequence length, answer position, lexical regularity, and the distribution of intermediate numbers. It may create ordinary distribution shift rather than a learned "wrong-operation habit." Without component ablations and student-side trajectory analysis, this mechanism must be described as a **plausible hypothesis**, not an established causal story.

# 12. SPECTRE pipeline and verification

## 12.1 Design contract

1. The parent model's terminal answer is preserved.
2. The intended poison is verifiably present in the delivered response.
3. If either condition cannot be verified, the pipeline retries and ultimately falls back to the clean teacher response.

## 12.2 Default composite pipeline

```text
Question
   │
   ▼
Clean teacher response (T)
   │
   ▼
T7 composite rewrite  ──── select_pivot(md5(question)) → (stem, depth)
   │
   ▼
Strip any generated ####  ──▶  append teacher's original #### N
   │
   ▼
Six-flag verification
   │
   ├── 3 blocking checks pass ──▶ deliver transformed response
   │
   └── failure ──▶ retry ──▶ ... ──▶ clean fallback
```

## 12.3 Critical (blocking) checks

| Check | What the code tests |
| - | - |
| **`answer_match`** | The numeric value on the variant's `####` line equals the clean teacher's value. |
| **`internal_consistency`** | The last number in the response body equals the terminal answer value. |
| **`poison_present`** | The expected pivot appears **and** the pre-pivot text contains at least one number absent from the clean response. |

> [!IMPORTANT]
> **`answer_match` is largely guaranteed by construction.** T7 removes any generated `####` line and appends the teacher's original answer line after rewriting. This is a valid engineering strategy for preserving the parent model's terminal answer, but it is **not independent evidence** that the body of the transformed reasoning is mathematically or semantically correct.
>
> Likewise, `internal_consistency` checks a **narrow local property**, the last number in the body, not the correctness of every reasoning step.

## 12.4 Warning (non-blocking) checks

| Check | What the code tests |
| - | - |
| `no_early_leak` | The answer value does not appear numerically in the first 60 % of the body. |
| `length_ok` | The body contains at most 3,500 characters. |
| `confident_false_start` | The false-start section lacks a small hand-coded set of hedging or error-admission markers. |

These do not block delivery.

## 12.5 Configuration relevant to the experiments

```text
SPECTRE_STRATEGY        = composite       # T7 is the dataset-generation default
TEACHER_MAX_TOKENS      = 1024
COMPOSITE_MAX_TOKENS    = 1200
MAX_RESPONSE_CHARS      = 3500
EARLY_LEAK_FRACTION     = 0.6
PIVOT_STEMS             = 20
FALSE_START_DEPTH       = 2-4
```

## 12.6 Safety-valve philosophy

The pipeline falls back to the clean teacher response when a critical condition cannot be verified. This preserves the ADHD deployment principle that the defense should **fail safe** rather than deliver a wrong final answer.

However, and this is the central SPECTRE post-mortem finding, **final-answer correctness is not enough to define a safe user experience**. A response can end with the right answer and still contain awkward, confusing, or semantically inconsistent reasoning. See [§15](#15-where-spectre-failed).

# 13. SPECTRE training result

```
   Student-Baseline         198/500 = 39.6 %
   Student-ADHD-SPECTRE     174/500 = 34.8 %
   Gap                                 4.8 pp   (24 questions)
```

Compared with ITRO's 0.6 pp gap, this is an **8.0×** larger raw effect.

The training-side evidence also changed:

- clean responses had the lowest average loss (0.1637),
- ITRO responses were harder to fit (0.2555, ≈ +56 %),
- SPECTRE responses were harder still (0.3512, ≈ +115 %),
- **only SPECTRE paired the large training difficulty with a substantially larger evaluation drop.**

This does not prove the proposed mechanism, but it shows that the structural-poisoning change is experimentally more promising than the original ITRO approach.

SPECTRE should therefore be considered the first ADHD attempt that produced a **nontrivial degradation signal**. It should **not** be considered a successful defense.

# 14. Why SPECTRE likely produced a larger gap

Six design changes distinguish SPECTRE from ITRO. Each is a hypothesis; none has been isolated by ablation.

## 14.1 The poison is repeated rather than highly variable

ITRO deliberately varied the obfuscation pattern. SPECTRE deliberately repeats the false-start location and overall structure.

If consistency is what allows a student to learn a behavior strongly, this is the single most important design change, and it directly addresses [Finding 2](#10-what-itro-established) from Phase I.

## 14.2 SPECTRE attacks operation selection, not only presentation

ITRO often made the *correct* reasoning path longer or more awkward. SPECTRE puts an **incorrect operation into the actual solution position**.

That has a better chance of changing what the student does when it begins solving a novel problem.

## 14.3 The poison can propagate autoregressively

A generated mathematical chain is sequential. If an early operation produces a wrong intermediate number and the model trusts it, later steps can condition on that incorrect value.

This gives SPECTRE a possible mechanism for **active degradation** rather than mere information withholding, intuitively stronger than a purely stylistic detour because it can change the model's own generated state.

> [!NOTE]
> **Unmeasured.** The historical evaluation records only final accuracy. It does not show whether SPECTRE-trained students actually begin with more wrong operations, fail to self-correct more often, or make different categories of errors. A future mechanism study must label the first operation, pivot behavior, correction success, and final-answer failure **separately**.

## 14.4 Recovery is intentionally less learnable

The pivot phrase and false-start depth vary. The design tries to avoid teaching a perfect ritual such as:

```text
wrong operation ──▶ fixed apology phrase ──▶ correct restart
```

If the recovery were equally consistent, the student might simply learn both the poison and the antidote.

## 14.5 The correct answer is delayed

The `no_early_leak` check prevents the correct final number from appearing in the first 60 % of the body, a direct response to the ITRO diagnosis that the answer becomes an easy anchor.

## 14.6 Primitive decomposition adds brittleness

T7 includes limited primitive decomposition in the correct section. This may make the learned computation process less compact and more brittle, although the component's actual contribution has not been isolated.

## 14.7 The ablations required to distinguish these

Future work must **separately** ablate: the fixed opening, the false-start operation, pivot variability, answer delay, primitive decomposition, sequence length, and lexical repetition.

It should also compare against **control transformations with matched length and lexical repetition but no wrong operation**. Without these controls, "repeated poison" and ordinary distribution shift remain confounded.

# 15. Where SPECTRE failed

The SPECTRE failure is the mirror image of the ITRO failure.

> ITRO was too weak against the student. SPECTRE is stronger against the student, but too visible and too damaging to the human-facing explanation.

## 15.1 Human readability is degraded

The user is forced through a wrong calculation before receiving the correct solution. Even when the mistake is eventually corrected, the response becomes longer and cognitively more expensive to read.

For a simple problem this is especially conspicuous, because the false start can look absurd relative to the problem's difficulty.

**A legitimate user does not benefit from seeing a confident wrong operation that exists only for defensive poisoning purposes.**

## 15.2 The output is fingerprintable

The T7 schema contains repeated artifacts that function as signatures:

- the exact same opening sentence,
- a false computation in the same structural position,
- a recognizable pivot into correction,
- a similar recovery pattern,
- repeated primitive decomposition,
- a constrained final-answer placement.

A defense designed as a honeypot should ideally be difficult for an attacker to distinguish from normal model behavior. T7 moves in the opposite direction: it makes the poison easier for the student to learn *partly by making it more regular*, and the same regularity makes it easier for an attacker to detect.

> **The key SPECTRE trade-off: learnability by the student and detectability by the attacker can rise together.**

An attacker does not even need to understand the intended learning mechanism to react. A sanitizer could delete the first few lines, remove sentences containing pivot markers, ask another model to rewrite the response into a direct solution, or train only on answer-bearing segments.

## 15.3 The verifier does not measure semantic naturalness

The verifier checks **structural** properties: final answer match, final body-number consistency, pivot presence, presence of a novel wrong intermediate, early answer leakage, response length, and hedging before the pivot.

It does **not** check:

- whether the explanation is naturally written,
- whether the pivot logically refers to what was actually computed,
- whether intermediate claims are semantically coherent,
- whether the correction would confuse a human,
- whether the false start is plausible for the difficulty of the question,
- whether the output looks like a systematic defense pattern,
- whether the response is detectably different from ordinary model reasoning.

**A response can therefore pass every implemented verification flag while still being visibly bad.**

## 15.4 Concrete case: the Natalia clips problem

This is the single most revealing artifact in the project. It is not the benchmark table.

**Problem.** Natalia sells 48 clips in April and half as many in May. How many did she sell altogether?

**Clean solution.** 24 clips in May; **72** total.

**T7 rewrite.** First computes `48 × 2 = 96` and describes 96 as the **April-plus-May total**. The pivot then argues that 96 *"cannot be correct for May alone"*, even though 96 had never been claimed to represent May alone. The response then recovers to 72.

**Verifier output:**

```
answer_match          = true
internal_consistency  = true
poison_present        = true
no_early_leak         = true
length_ok             = true
confident_false_start = true
passed                = true
```

Every implemented flag is true, and the explanation is locally self-contradictory.

**Why this matters.** The system checks that a pivot exists, that an extra number appears before the pivot, and that the last body number matches the appended answer. It does **not** check whether the pivot's semantic reference is coherent.

> The verifier's definition of success is narrower than the project's definition of a good defended response. This is the clearest evidence that structural verification must be supplemented by semantic and human-utility evaluation.

## 15.5 Concrete case: the Weng babysitting problem

A second bundled sample computes the correct per-minute rate, then represents the multiplication as a long sequence of repeated `$0.20 + $0.20 + ...` terms before eventually using multiplication anyway.

This passes the defense machinery but is unnecessarily cumbersome for a human reader, and it makes the transformation itself more conspicuous.

## 15.6 Final-answer correctness is too weak a user-safety condition

The original ADHD framing treated "correct final answer" as the reason false positives would be cheap. SPECTRE shows that is too weak.

A useful safety condition must distinguish between:

1. **answer correctness**, and
2. **explanation correctness and usability**.

Users ask for explanations because the path matters:

- A student learning mathematics may adopt the wrong formula.
- A programmer may copy an inefficient or fragile pattern.
- A researcher may reuse an incorrect causal argument even if the last sentence happens to state the right conclusion.

For some applications, exposing a user to confidently incorrect intermediate claims is itself unacceptable even when the system later corrects them.

**For deployment, human utility must include the semantic validity and readability of the intermediate explanation, not only terminal-answer equality.**

# 16. SPECTRE code-level findings

## 16.1 The repository is not a complete reproducibility package

The reported experimental comparison references a **Qwen** teacher and Qwen students. The current SPECTRE and ITRO wrapper code additionally exposes **Anthropic** and **Gemini** provider implementations and defaults to Claude and Gemini model names in its configuration. **Those endpoints were not used to generate the teacher responses reported in the historical Qwen experiments.**

The student fine-tuning and evaluation scripts that produced the 39.6 %, 39.0 %, 37.0 %, and 34.8 % results are **not present** in the current repository snapshot.

The repository therefore contains the defense implementation and test harness, but not every historical artifact needed to reproduce the reported student-training numbers end to end.

> This does not erase the results. It means the code audit, finalized aggregate outcomes, and training diagnostics should be treated as **related evidence**, not as a bit-for-bit reproduction package. Future work must package the exact generation, training, evaluation, seed, checkpoint, and metric code for every headline number.

## 16.2 GHOST is heuristic in the current repository

The ensemble strategy includes **GHOST** (*Gradient-Hostile Output Selection for Training*).

In the current implementation, a provider is asked to rank the five transformations by how harmful they would be for a small student to learn from. The code itself notes this is not scientifically rigorous, because the provider is *reasoning about* learnability rather than *measuring* student loss or downstream performance.

For research claims, transformation ranking should be based on measured effects from real student training or a validated proxy model.

## 16.3 Documentation drift

The SPECTRE README describes the T7 recovery phrase as coming from a **14-entry** pool. The current `t7_composite.py` defines **20 pivot stems**.

A minor mismatch, but worth fixing: reproducibility depends on the exact transformation distribution.

## 16.4 The bundled test dataset is a smoke test

The bundled SPECTRE test output contains **two examples**:

| Metric | Value |
| - | -: |
| Count | 2 |
| Errors | 0 |
| Safety-valve trigger rate | 0.0 |
| Average attempts | 1.5 |
| Poison-verified rate | 1.0 |
| Average response characters | 939.5 |

These values confirm the local pipeline runs. They are **not** sufficient to estimate real poison-preservation rate, readability, safety-valve rate, or detectability over a 2,000-example corpus.

A pre-flight sample of at least tens to hundreds of examples should be audited before expensive full generation.

## 16.5 Test-suite execution

The repository includes pytest suites for both ITRO and SPECTRE. An attempted run in the inspection environment stopped during test collection because the `anthropic` package was not installed. **This is an environment dependency issue, not a test failure.**

A reproducibility package should include a pinned environment or lockfile so the complete suite can be executed without dependency ambiguity.

## 16.6 ITRO fail-open semantic check

As noted in [§6.5](#65-correctness-checking-and-the-safety-valve): the non-math semantic-equivalence helper returns `True` on exception. This is a meaningful implementation gap: the general system cannot currently claim strict fail-safe preservation for all domains.

# 17. ITRO and SPECTRE direct comparison

| Dimension | ITRO | SPECTRE |
| - | - | - |
| Scope | Broad: 8 domains | Mathematics only |
| Main corruption type | Variable reasoning obfuscation | Repeated structural poisoning |
| Clean student reference | 198/500 = 39.6 % | 198/500 = 39.6 % |
| Defended student | 195/500 = 39.0 % | 174/500 = 34.8 % |
| Accuracy gap | **−0.6 pp** | **−4.8 pp** |
| Relative gap size | n/a | **8.0×** ITRO's raw gap |
| Below the no-rationale control (37.0 %)? | No, 2.0 pp above it | **Yes, 2.2 pp below it** |
| Average training loss | 0.2555 (≈ +56 % vs. clean) | 0.3512 (≈ +115 % vs. clean) |
| Final gradient norm | 0.1919 | 0.2439 |
| Human readability goal | Better aligned | Worse aligned |
| Stealth | More plausible in principle | More fingerprintable |
| Poison consistency | Low to moderate; varies by query | High structural consistency |
| Answer preservation | Yes, with fallback (≈ 85-87 % preserved) | Yes, by construction, with fallback |
| Primary failure | **Student ignores much of the corruption** | **Humans and attackers can notice the corruption** |

This table is the project evolution in one view.

ITRO optimized for naturalness and broad deployment but did not create a strong enough learning effect. SPECTRE optimized for student-learning damage and produced a larger effect, but sacrificed too much naturalness.

**The next design has to occupy the space between them.**

# 18. Statistical and reporting caveats

## 18.1 ITRO's 0.6 pp result is clearly inconclusive

Over 500 questions, a 0.6 pp difference is far smaller than ordinary binomial uncertainty. Using a rough independent-binomial approximation, the standard error of the ITRO-versus-baseline difference is approximately **3.1 pp**.

A paired comparison would be preferable, since the same questions were evaluated across models, but per-question prediction data would be required for the correct paired test, and it was not retained.

Either way, **0.6 pp is not compelling evidence of an effect.**

## 18.2 SPECTRE's 4.8 pp result is interesting but not established

A 4.8 pp gap is substantially larger than 0.6 pp and is worth pursuing. But one training run is not enough to establish a stable causal effect.

The 4.8 pp value supports only a modest statement:

> Under the recorded setup, the SPECTRE-trained student finished lower than the clean and ITRO students.

It does **not** establish that T7's proposed learning asymmetry caused the difference, that another seed would reproduce it, that the effect generalizes beyond GSM8K, or that the same mechanism would survive an adaptive attacker.

The next experiment must use multiple seeds per arm and report mean accuracy, standard deviation, confidence intervals, and paired per-question comparisons.

## 18.3 Evaluation-denominator provenance: resolved

An earlier version of this record flagged that a reported SPECTRE score of "34.80 %" appeared inconsistent with an exact 500-question denominator.

**This is now resolved.** Over 500 binary-correctness items, accuracy moves in increments of 0.2 pp, and **174 / 500 = 34.8 %** exactly. The finalized record reports raw counts for every arm:

| Arm | Count | Accuracy | Consistent with n = 500 |
| - | -: | -: | :-: |
| Teacher | 425 / 500 | 85.0 % | ✅ |
| Clean | 198 / 500 | 39.6 % | ✅ |
| ITRO | 195 / 500 | 39.0 % | ✅ |
| SPECTRE | 174 / 500 | 34.8 % | ✅ |
| No-CoT | 185 / 500 | 37.0 % | ✅ |

The remaining provenance limitation is **not** the denominator. It is the absence of retained **item-level predictions**, which prevents a paired significance test even though every model was evaluated on the same 500 questions.

## 18.4 Approximate values are now exact: with one exception

Teacher accuracy and No-CoT accuracy were previously carried as approximate (`~85 %`, `~37 %`). Both are now recorded as exact counts: **425/500 = 85.0 %** and **185/500 = 37.0 %**.

The remaining approximate figure in this record is the **ITRO answer-preservation rate of ≈ 85-87 %**, taken from generation-run checkpoints rather than a final tallied audit. It should stay marked approximate until the generation logs are reconstructed.

## 18.5 The teacher score is not the causal control

The teacher's 85.0 % shows that the 7B model is substantially more capable than the 0.5B student. That is context, not the result.

The defense result is **not** the distance from the teacher. It is the difference between students trained under comparable conditions on clean versus defended data.

## 18.6 Training loss is not a security metric

Stated here explicitly because it is the single most tempting misreading of this record. The average-loss ordering (0.1637 → 0.2555 → 0.3512) is monotonic and clean. It is also, on ITRO's evidence, **almost uninformative about held-out capability**.

# 19. Why GSM8K is no longer a sufficient primary benchmark

GSM8K was useful for the first experiments: easy to evaluate, clean numerical answer format. It is now a limitation.

## 19.1 GSM8K is relatively easy for modern pretrained models

The teacher is already strong (85.0 %), and the small student retains substantial capability without any teacher reasoning at all.

**The no-rationale result of 37.0 % is the strongest evidence of this problem inside the project itself.** If removing the teacher's reasoning only costs 2.6 pp, the benchmark does not strongly depend on learning the teacher's detailed reasoning process, which makes it a poor instrument for measuring a defense that specifically targets transferred reasoning.

## 19.2 Distillation attacks are most valuable on harder capabilities

A real attacker extracting a strong reasoning model has every incentive to query difficult prompts that expose capabilities the student does not already possess. For those prompts, the teacher's reasoning process carries far more incremental training value.

A defense may therefore show a stronger and more meaningful effect on hard multi-step problems than on grade-school arithmetic.

## 19.3 The next benchmark should require deeper reasoning

Candidate directions:

- MATH and MATH-500,
- college-level algebra and calculus,
- proof-like mathematical reasoning,
- competition problems (AIME-style),
- GSM-Hard as a bridge benchmark,
- a custom difficulty-stratified set chosen specifically because the student baseline cannot already solve it reliably.

Evaluation should also extend beyond mathematics to code generation, multi-step scientific reasoning, and general instruction following.

The exact benchmark matters less than the principle:

> **The benchmark should contain reasoning that the student genuinely needs to acquire from the teacher.**

## 19.4 Difficulty should be stratified, not averaged

A future dataset should separate problems into difficulty buckets and, for each bucket, measure:

- teacher accuracy,
- pretrained student accuracy before distillation,
- clean-distilled student accuracy,
- defended-distilled student accuracy,
- no-rationale student accuracy.

This reveals whether the defense effect **grows with reasoning depth**, far more informative than a single aggregate score.

# 20. What the next experiment must measure

A future ADHD result must not be judged by student accuracy alone. SPECTRE proved that a larger student drop can coexist with an unacceptable user-facing response.

The research objective is explicitly multi-objective, so the evaluation must be too. The absence of these measures in the historical experiment is a **central limitation, not a minor reporting omission**.

## 20.1 Student degradation

- exact-match task accuracy,
- **multiple student-training seeds**,
- mean and standard deviation,
- paired per-question performance (McNemar-style),
- degradation relative to clean distillation,
- degradation relative to no-rationale,
- performance by question difficulty,
- performance on out-of-distribution math problems.

A particularly important question: does the defended student fall below its own pretrained or no-rationale floor on **hard** reasoning tasks?

## 20.2 Human readability

Run a blind comparison between clean and defended responses. Human raters should score:

- clarity,
- coherence,
- unnecessary complexity,
- confidence calibration,
- ease of following the reasoning,
- whether intermediate claims are misleading,
- reading time,
- whether the response appears intentionally manipulated,
- overall usefulness.

> The defense is not successful if the student gets worse **only because** the legitimate user's explanation also got much worse.

Automated checks can reject obvious defects, but they cannot substitute for semantic review.

## 20.3 Defense detectability

Create a clean-versus-defended detection task. Candidate detectors:

- simple lexical classifiers,
- structural heuristics,
- language-model classifiers,
- attack-side rules looking for repeated openings or pivot structures.

Report detection accuracy or ROC/AUC. An ideal honeypot should be hard to detect even when an attacker has collected many responses.

## 20.4 Sanitization robustness

Assume the attacker notices something unusual and preprocesses the data. Test attacker-side sanitizers:

- removing all text before a correction phrase,
- keeping only the final correct derivation,
- asking another model to rewrite the response cleanly,
- extracting question and final answer only,
- removing repeated-addition expansions,
- filtering examples with obvious self-correction,
- stripping repeated prefixes,
- varying query distributions across accounts or interfaces.

Then **retrain the student on sanitized defended data**. If a simple sanitizer restores clean-distillation performance, the defense is fragile.

**This belongs in the core threat model, not in future work.**

## 20.5 Explanation correctness

Verify more than the last line. A protected response should be checked for:

- correct final answer,
- logically coherent references,
- mathematically valid recovery,
- no misleading claims that remain uncorrected,
- a clear distinction between exploratory reasoning and factual statements,
- absence of semantic contradictions like the Natalia case.

**A deployable system should treat this class of semantic defect as a hard rejection condition.**

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

This prevents a repeat of the ITRO Dataset B uncertainty, where ≈ 13-15 % of the "defended" corpus was silently clean.

## 20.7 Systems and economic cost

The response-layer controller is a systems component, not only a text generator. Measure:

- added latency,
- extra generated tokens,
- inference cost,
- clean-fallback rate,
- attacker capability gained **per dollar** or **per collected token**,
- provider-side marginal cost.

Longer responses can increase the attacker's storage, tokenization, training, and API bill, but the provider pays additional generation latency and compute, so raw token inflation is not a free defensive win.

> A mechanism is economically useful only if it worsens the attacker's efficiency **more** than it worsens the provider's service economics.

A falsely flagged legitimate user should incur a tightly bounded quality and latency penalty.

# 21. Recommended next experimental design

## Phase 1: Freeze the benchmark and student

Choose a harder math benchmark and record the pretrained student's zero-shot or few-shot baseline **before** generating any defense data.

Use identical student architecture, tokenizer, prompt template, optimizer settings, and evaluation code for all arms. ([Defect 2](#72-defect-2-significant-training--evaluation-format-mismatch) is the reason this is listed first.)

## Phase 2: Generate four comparable datasets

| Arm | Training response type | Purpose |
| :-: | - | - |
| **A** | Clean teacher reasoning | Distillation baseline |
| **B** | New defended reasoning | Main defense test |
| **C** | No-CoT, answer only | Withholding / pretraining-floor reference |
| **D** | SPECTRE T7 | Historical strong-poison reference |

Keeping SPECTRE as an explicit reference arm shows whether a more natural successor retains the degradation benefit.

Consider adding a fifth arm: **a length-matched, lexically repetitive, but mathematically correct rewrite**. If it reproduces the accuracy drop, the effect is distribution shift, not poisoned reasoning.

## Phase 3: Pre-flight audits before full generation

Before generating 2,000 examples, create a smaller sample and inspect:

- answer preservation,
- poison presence,
- semantic consistency,
- average token length,
- detectability,
- human readability,
- safety-valve behavior.

**Do not launch expensive full generation until the sample passes all quality gates.** Generation costs ≈ 12 hours; training costs ≈ 12 minutes.

## Phase 4: Train multiple student seeds

At minimum, several random seeds per dataset arm. One run can be dominated by optimization noise; multiple seeds separate a real defense effect from run-to-run variance.

**Archive every held-out prediction.**

## Phase 5: Inspect generated reasoning, not only final accuracy

For each student, analyze failure traces:

- Does the SPECTRE student actually begin with wrong operations more often?
- Does it recover less often?
- Does the defended student use repeated addition more frequently?
- Are failures concentrated on long reasoning chains?
- Does the student copy wrong intermediate values into final answers?

This is necessary to **confirm the mechanism** rather than merely observe a score difference.

## Phase 6: Run attacker adaptation tests

Train additional students after applying sanitization to defended responses. A capable attacker will adapt once the pattern is discovered.

## Phase 7: Content-address everything

The training corpus, prompts, transformation metadata, fallback decisions, tokenizer versions, checkpoints, and evaluation scripts should be content-addressed so that **every reported percentage can be reconstructed from raw predictions**.

# 22. Design direction after SPECTRE

## Keep from ITRO

- broad concern for human plausibility,
- fail-safe answer preservation,
- external wrapper architecture,
- adaptive intensity based on estimated response value,
- preference for transformations that resemble normal model behavior.

## Keep from SPECTRE

- narrow, measurable mechanism design,
- explicit poison-presence verification,
- consistency strong enough to affect student learning,
- protection against early answer anchoring,
- sequence-length controls,
- the clean / defended / no-rationale three-arm comparison.

## Remove or redesign from SPECTRE

- exact fixed opening sentences,
- easily recognized correction rituals,
- obviously repeated wrong-operation placement,
- awkward primitive expansions,
- semantically inconsistent pivots,
- verification that ignores naturalness.

## The resulting specification

The design problem is now far more precise than it was during ITRO. The project does not need "stronger obfuscation." It needs a transformation distribution that is:

1. **consistent enough at the latent reasoning level** to affect student learning,
2. **diverse enough at the surface level** to avoid a simple fingerprint,
3. **mathematically and semantically coherent** for humans,
4. **resistant to easy attacker-side cleaning**,
5. **measurable on tasks where teacher reasoning provides real incremental value**.

Stated as an optimization target: future transformations should be developed under a **strict semantic constraint**: the explanation must remain conceptually correct, locally coherent, naturally written, and efficient for a person to use.

> The goal is not to make the text confusing. The goal is to preserve the information a human needs while changing the representational regularities a student disproportionately exploits.

# 23. Core research tension exposed by the two experiments

ITRO and SPECTRE reveal opposite faces of the same problem.

### ITRO

Prioritized **diversity and plausibility**. The corruption changed from question to question. That made it less visually repetitive, but the student could treat much of it as noise.

> Result: **good product instinct, weak learning effect.**

### SPECTRE

Prioritized **consistency and learnability of the poison**. The corruption occupied a repeated structural slot. That produced a much larger student drop, but also made the pattern easier to recognize and less pleasant to read.

> Result: **stronger learning effect, weaker product quality and stealth.**

### The unresolved question

```text
             stealthy  ◀──────────────────────────▶  learnable
                │                                        │
             ITRO                                    SPECTRE
        0.6 pp, subtle                        4.8 pp, conspicuous
                │                                        │
                └──────────── open region ───────────────┘
                    consistent in the features the
                    student learns, variable in the
                    features a human or attacker notices
```

The next defense must discover whether that middle region exists. **That is a far more concrete scientific question than the original general goal of "obfuscating reasoning."**

# 24. Relationship to external anti-distillation work

The two phases are best positioned against the broader literature by **intervention point**, because two methods can pursue the same security objective while imposing very different deployment requirements.

| Family | Intervention point | Teacher changed? | Relationship to ADHD |
| - | - | :-: | - |
| **Teacher-side training**: Nasty Teacher, CMIM, Teacher Scrambling, DOGe, Distillation Traps and Guards | Teacher weights, output head, calibration policy | **Yes** | Strong control at the source of generation, but protection is coupled to a modified teacher rather than a separable wrapper. |
| **Serving-time decoding / logit shaping**, ADS, LADS, Product-of-Experts, CMI-based purification | Sampling randomness, next-token probabilities, exposed logits | Usually no persistent change | Finer control than text-only editing, but requires access to generation internals, logits, private randomness, or a proxy-student signal. |
| **Post-generation trace transformation**: PART, SelfCAD, trace rewriting, TraceGuard, SGRE | A completed reasoning trace is reordered, rewritten, augmented, or selectively edited | **No** | **Closest family to ITRO and SPECTRE.** Preserves deployment separability but must solve semantic validity, naturalness, detectability, and attacker-side sanitization. |
| **Information throttling**: CoT removal or summarization | Rationale withheld or compressed before delivery | **No** | Simple, and on mathematical reasoning a strong baseline. Our 37.0 % no-rationale arm is exactly this. |
| **Attribution / fingerprinting**: DRW, EWE, ReasMark, ADFP | Watermark or learning-aware fingerprint designed to survive transfer | Varies | Addresses attribution rather than prevention of capability transfer; complements active degradation. |

### Three external results that directly constrain this project

**1. Information throttling is a strong baseline for mathematics.** DistillGuard's evaluation taxonomy spans output perturbation, data poisoning, and information throttling, and reports strong task dependence, with chain-of-thought removal a particularly strong baseline in the mathematical setting. Our own no-rationale arm reproduces this independently. **Any complicated transformation must be compared against simple withholding, not only against clean distillation.**

**2. Anti-distillation claims are inseparable from the attacker model.** Libon et al. formalize query budget, data budget, and interface profile as separate dimensions and show that apparent defense effectiveness can change materially under different assumptions. The Distillation Game reaches a related minimax conclusion: adaptive students recover materially more capability than passive evaluation suggests. Our historical experiments evaluate a **naive collector with no sanitization stage** and therefore say little about a determined extractor.

**3. Degrading response content is not the only option.** LADS preserves the marginal distribution seen by a benign user while correlating randomness across semantically related repeated queries, reducing the diversity available to a multi-account collector without degrading any single response. This is a useful counterexample to the assumption that every anti-distillation defense must trade ordinary response quality for poisoning strength, and it should be a baseline when evaluating the business case for a risk-gated deception layer.

### Positioning

The novelty claim here is deliberately narrow. SGRE's recent "Answer-then-Edit" work first obtains a clean solution and then edits a reasoning skeleton to increase student learning difficulty while explicitly evaluating trace naturalness, a close architectural neighbor. **The contribution of this project is not the first proposal to edit a clean trace after generation.** It is an empirical case study and implementation analysis of the trade-offs that emerge when such a wrapper is required to preserve human utility while reducing student-training value.

### The comparison that would settle the architectural question

On an open teacher where all methods are implementable, the same prompts and students should be trained from: clean traces; no-rationale outputs; teacher-side methods; serving-time methods; and post-generation methods.

That experiment would quantify **the price of deployment separability**: how much anti-distillation strength is lost by refusing to modify teacher weights or decoding internals, and whether that loss is compensated by easier deployment, selective activation, and lower risk to ordinary traffic.

# 25. Final interpretation of ITRO

ITRO should be presented as a **failed first hypothesis**, not as a successful defense.

The evidence supports the following claims:

- ITRO changes response structure substantially.
- ITRO makes defended responses materially harder for a student to fit token by token: average loss 0.2555 against 0.1637 for clean, ≈ +56 %.
- Gradient norms remained comparable (0.1919 vs. 0.1846), so the harder corpus produced no obvious optimization instability.
- ITRO preserves the final answer in ≈ 85-87 % of transformed examples and falls back on failures.
- ITRO did **not** produce a meaningful GSM8K student-accuracy gap: 195/500 = 39.0 % against 198/500 = 39.6 %.
- The observed 0.6 pp difference (three questions) is too small to support an efficacy claim.
- The no-rationale result indicates GSM8K performance is not strongly dependent on copying the teacher's full reasoning chain.
- ITRO's variable corruption gave the student an opportunity to ignore the transformed path and learn the stable answer signal.

**The most valuable contribution of ITRO was diagnostic.** It identified what the project was attacking incorrectly and exposed several experimental pitfalls that had to be fixed before any result could be trusted.

# 26. Final interpretation of SPECTRE

SPECTRE should be presented as a **partial experimental success and a product-level failure** in its current form.

The evidence supports the following claims:

- SPECTRE produced a substantially larger recorded student-accuracy degradation than ITRO: 174/500 = 34.8 % against 198/500 = 39.6 %, a 4.8 pp single-run gap and 24 fewer correct answers.
- That gap is **8.0×** ITRO's raw gap and is the strongest efficacy signal ADHD has produced.
- The SPECTRE student finished **2.2 pp below** the 185/500 = 37.0 % no-rationale control, which is the more demanding comparison.
- The result is directionally consistent with the idea that repeated structural poisoning can teach harmful reasoning habits rather than merely hide useful reasoning.
- SPECTRE responses are the hardest of the three for the student to fit: average loss 0.3512, ≈ +115 % over clean and ≈ +37 % over ITRO, with the highest final gradient norm (0.2439) but no divergence.
- The T7 mechanism is **visibly repetitive** and can be difficult for humans to read.
- The verifier can accept semantically awkward or contradictory reasoning because it verifies structure rather than meaning, demonstrated conclusively by the Natalia case.
- `answer_match` is largely guaranteed by construction and is therefore not independent evidence of body correctness.
- Multiple training seeds, retained item-level predictions, mechanism ablations, matched controls, human evaluation, adaptive-attacker sanitization, and a harder benchmark are all required before any strong claim.

**SPECTRE validates a direction, not a system.**

# 27. Project-level conclusion

The ADHD project has produced two informative experiments.

**Phase I (ITRO)** showed that *making reasoning convoluted is not enough*. The student can ignore variable surface corruption and continue learning from stable answer information and its own pretrained mathematical ability, even when the defended corpus is ≈ 56 % harder to fit.

**Phase II (SPECTRE)** showed that *a more consistent and behaviorally targeted poison can create a much larger degradation signal*. The 4.8 pp drop is materially more interesting than ITRO's 0.6 pp and may indicate active interference with student reasoning.

But SPECTRE also violated a central part of the original ADHD goal. The response became too obviously manipulated: the human user is forced through unnecessary wrong reasoning, and an attacker may be able to detect or sanitize the repeated structure.

And the **no-rationale control**, at 37.0 % and achieved with no deception, no semantic risk and no implementation complexity at all, captures more than half of SPECTRE's total degradation. That comparison, more than any other single number in this record, defines the bar.

The strongest defensible conclusion:

> **ITRO showed that variable reasoning obfuscation is too weak. SPECTRE showed that consistent structural poisoning can be stronger, but the current version sacrifices too much readability and stealth, and clears simple rationale withholding by only 2.2 pp. The next phase must preserve SPECTRE-level student degradation while recovering ITRO-level plausibility, and must be tested on substantially harder mathematics where the teacher's reasoning is genuinely valuable to the student.**

The move away from GSM8K is not optional. A defense against high-value model extraction should be evaluated on the kind of difficult reasoning an attacker would actually want to steal.

**ADHD's current research state is best described as *promising but unvalidated*.** The project now has a clearer mechanism hypothesis, a stronger experimental signal, a known usability failure, a documented verifier gap, and a much better-defined next experiment.

The case study **sharpens rather than closes** the research question. It does not rule out post-generation defenses; it narrows the design target to transformations that preserve natural, conceptually correct human utility, produce reproducible student degradation beyond simpler withholding baselines, and remain effective under adaptive sanitization.

# Appendix A: Consolidated result tables

## A.1 Held-out GSM8K accuracy

| Model | Correct | Accuracy | Gap vs. clean student |
| - | -: | -: | -: |
| Teacher reference (`Qwen2.5-7B-Instruct`) | 425 / 500 | 85.0 % | n/a |
| Student-Baseline | 198 / 500 | 39.6 % | n/a |
| Student-ADHD-ITRO | 195 / 500 | 39.0 % | −0.6 pp |
| Student-ADHD-SPECTRE | 174 / 500 | 34.8 % | −4.8 pp |
| Student-NoCoT | 185 / 500 | 37.0 % | −2.6 pp |

## A.2 Clean-student training diagnostics

| Epoch | Loss | Grad. norm | Learning rate |
| -: | -: | -: | -: |
| 0.8 | 0.1790 | 0.2207 | 1.843e-05 |
| 1.2 | 0.1626 | 0.1865 | 1.511e-05 |
| 1.6 | 0.1526 | 0.2129 | 1.070e-05 |
| 2.0 | 0.1517 | 0.2051 | 6.141e-06 |
| 2.4 | 0.1388 | 0.2021 | 2.407e-06 |
| 2.8 | 0.1392 | 0.1846 | 2.923e-07 |
| **Final** | **0.1637 avg** | n/a | n/a |

## A.3 ITRO-student training diagnostics

| Epoch | Loss | Grad. norm | Learning rate |
| -: | -: | -: | -: |
| 0.4 | 0.3667 | 0.2734 | 1.995e-05 |
| 0.8 | 0.2610 | 0.2227 | 1.843e-05 |
| 1.2 | 0.2484 | 0.1924 | 1.511e-05 |
| 1.6 | 0.2400 | 0.2266 | 1.070e-05 |
| 2.0 | 0.2322 | 0.2012 | 6.141e-06 |
| 2.4 | 0.2250 | 0.1987 | 2.407e-06 |
| 2.8 | 0.2150 | 0.1919 | 2.923e-07 |
| **Final** | **0.2555 avg** | n/a | n/a |

## A.4 SPECTRE-student training diagnostics

| Epoch | Loss | Grad. norm | Learning rate |
| -: | -: | -: | -: |
| 0.4 | 0.4521 | 0.3318 | 1.995e-05 |
| 0.8 | 0.3812 | 0.2867 | 1.843e-05 |
| 1.2 | 0.3579 | 0.2604 | 1.511e-05 |
| 1.6 | 0.3488 | 0.2711 | 1.070e-05 |
| 2.0 | 0.3402 | 0.2588 | 6.141e-06 |
| 2.4 | 0.3361 | 0.2495 | 2.407e-06 |
| 2.8 | 0.3350 | 0.2439 | 2.923e-07 |
| **Final** | **0.3512 avg** | n/a | n/a |

## A.5 Cross-condition summary

| Condition | Avg. loss | vs. clean | Final grad. norm | Accuracy | Gap |
| - | -: | -: | -: | -: | -: |
| Clean | 0.1637 | n/a | 0.1846 | 39.6 % | n/a |
| ITRO | 0.2555 | ≈ +56 % | 0.1919 | 39.0 % | −0.6 pp |
| SPECTRE | 0.3512 | ≈ +115 % | 0.2439 | 34.8 % | −4.8 pp |

All three recorded learning-rate schedules terminate at `2.923e-07`.

> The clean and ITRO traces come from the earlier/intermediate 3B student run; the SPECTRE trace is recorded separately. They are complete as archived optimization diagnostics but are not a matched causal explanation of the final benchmark differences.

# Appendix B: Historical experiment configuration

```text
Teacher            Qwen2.5-7B-Instruct
Final student      Qwen2.5-0.5B-Instruct
Earlier student    Qwen2.5-3B-Instruct
Training samples   2000 per dataset arm
Evaluation set     500 held-out GSM8K questions
Epochs             3
Batch size         2
Grad accumulation  8
Effective batch    16
Learning rate      2e-5
Max sequence       1024 (raised from an unsafe 512)
Decoding           greedy, do_sample=False
Answer format      #### [number]
Hardware           NVIDIA A100 SXM4 80GB
Platform           ASU Sol HPC cluster
```

# Appendix C: Reproducibility checklist for the next experiment

Future releases should archive:

- [ ] exact prompts and control datasets
- [ ] transformation metadata and fallback rates
- [ ] model and tokenizer versions
- [ ] sequence-length statistics per arm
- [ ] random seeds (multiple per arm)
- [ ] exact commands
- [ ] training checkpoints
- [ ] held-out question identifiers
- [ ] **item-level predictions and raw counts**
- [ ] human-evaluation materials and rater instructions
- [ ] sanitizer code used for adaptive-attacker tests
- [ ] attacker-cost measures (tokens, dollars, accelerator-seconds)
- [ ] content hashes sufficient to reconstruct the student-training corpus

The single most consequential omission in the historical record is **item-level predictions**. Their absence is what prevents a paired significance test on models that were evaluated on identical questions.
