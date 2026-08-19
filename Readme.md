<h1 align="center">ADHD: Adaptive Defense via Honeypot Deception</h1>

<p align="center">
  <strong>Post-Generation Response Transformation Against Unauthorized Model Distillation</strong><br>
  An empirical case study of a deployment-separable anti-distillation response layer
</p>

<p align="center">
  <a href="#paper"><img alt="Paper" src="https://img.shields.io/badge/paper-arXiv%20preprint-b31b1b"></a>
  <a href="#reproducibility-and-provenance"><img alt="Status" src="https://img.shields.io/badge/status-research%20prototype-orange"></a>
  <img alt="Python" src="https://img.shields.io/badge/python-3.10%2B-3776ab">
  <img alt="Benchmark" src="https://img.shields.io/badge/benchmark-GSM8K%20(500%20held--out)-4c1">
</p>

<p align="center">
  <a href="#overview">Overview</a> •
  <a href="#headline-results">Results</a> •
  <a href="#architecture">Architecture</a> •
  <a href="#phase-i--itro">ITRO</a> •
  <a href="#phase-ii--spectre">SPECTRE</a> •
  <a href="#installation-and-usage">Usage</a> •
  <a href="#limitations">Limitations</a> •
  <a href="#citation">Citation</a>
</p>

## Overview

**ADHD** is a research framework for studying whether the *training value* of LLM API responses can be reduced **without modifying the protected model itself**.

The system implements a **deployment-separable response layer**: the protected teacher generates its ordinary response first, and an external, risk-gated controller may then transform only the visible explanation before delivery. The intended asymmetry is easy to state and hard to realize: a legitimate human should retain the task result and a coherent explanation, while a student trained on thousands of transformed responses should receive lower-value supervision.

This repository contains the two empirical phases of that investigation:

| Phase | System | Expansion | Scope |
| :-: | - | - | - |
| I | **ITRO** | Inference-Time Reasoning Obfuscation | 8 reasoning domains, adaptive intensity |
| II | **SPECTRE** | Structural Poisoning via Empirical Corruption of Training Representations | Mathematical reasoning, repeated structural poison |

> [!IMPORTANT]
> **Research status.** ADHD is an experimental research prototype and empirical case study, **not** a production-ready security mechanism. The recorded benchmark gaps are descriptive results from single historical runs, not causally isolated effect sizes. See [Limitations](#limitations) and [Responsible use](#responsible-use).

## Motivation

Language-model APIs expose more than final answers. Detailed explanations and reasoning traces provide reusable supervision for training smaller models. A black-box extractor can query a stronger model at scale, collect prompt-response pairs, and fine-tune a student on the result, without ever touching teacher logits, hidden states, or weights.

The threat is operational rather than hypothetical. In February 2026, Anthropic reported three coordinated campaigns that generated more than **16 million exchanges** through approximately **24,000 fraudulent accounts**, including one campaign exceeding **13 million exchanges**. Current OpenAI and Gemini API terms also restrict competing-model development and model extraction.

Conventional responses (detection, rate limiting, account suspension, contractual enforcement, watermarking) remain essential. But a difficult policy region sits between ordinary use and a confirmed attack:

- If the provider is **highly confident** a session is conducting prohibited extraction, terminating or throttling access is reasonable.
- If confidence is **uncertain**, an immediate ban can remove a legitimate customer.

ADHD studies a third response for that uncertain middle region.

## Headline results

All numbers below are the **finalized recorded values** from the historical controlled-distillation experiment. Teacher reference: `Qwen2.5-7B-Instruct`. Final student: `Qwen2.5-0.5B-Instruct`. 2,000 training examples per arm; 500 held-out GSM8K questions; deterministic greedy decoding.

### Held-out GSM8K accuracy

| Condition | Correct | Accuracy | Gap vs. clean |
| - | -: | -: | -: |
| Teacher reference (7B) | 425 / 500 | **85.0 %** | n/a |
| Student-Baseline (clean distillation) | 198 / 500 | **39.6 %** | n/a |
| Student-ITRO | 195 / 500 | **39.0 %** | **−0.6 pp** |
| Student-SPECTRE | 174 / 500 | **34.8 %** | **−4.8 pp** |
| Student-NoCoT (no-rationale control) | 185 / 500 | **37.0 %** | **−2.6 pp** |

SPECTRE produced **24 fewer correct answers** than clean distillation on the recorded evaluation set, and sits **2.2 pp** below the no-rationale control.

### Recorded training diagnostics

| Condition | Average loss | vs. clean | Final grad. norm |
| - | -: | -: | -: |
| Clean | **0.1637** | n/a | 0.1846 |
| ITRO | **0.2555** | ≈ +56 % | 0.1919 |
| SPECTRE | **0.3512** | ≈ +115 % | 0.2439 |

All three recorded learning-rate schedules terminate at `2.923e-07`.

### The central finding

The two phases separate cleanly into one lesson each:

> **ITRO:** a defended corpus can be *substantially harder to fit* (≈ 56 % higher average loss) while held-out student capability is *almost unchanged* (0.6 pp). **Optimization difficulty is not a security endpoint.**

> **SPECTRE:** a repeated structural poison produces a *larger separation* (4.8 pp) but simultaneously makes the output *less readable and more fingerprintable*. **Learnability by the student and detectability by the attacker can rise together.**

And the baseline that raises the bar for every complex mechanism:

> **No-rationale withholding alone** costs 2.6 pp. SPECTRE beats it by only 2.2 pp, while adding semantic risk, inference overhead, and a sanitization surface.

## Architecture

The protected model's weights are never modified. The defense is a wrapper that can be added to an existing serving stack, revised independently, gated by domain, and coupled to any external risk score.

```text
                        ┌──────────────────────┐
   Incoming query  ───▶  │ External extraction- │
   or session            │    risk detector     │
                        └───────┬──────────────┘
                                │
          ┌─────────────────────┼──────────────────────┐
          │ low                 │ uncertain            │ high
          ▼                     ▼                      ▼
   Serve ordinary       Response-layer          Rate-limit,
     response            intervention          suspend, block

   ┌────────────────┐   ┌──────────────┐   ┌──────────────────┐
   │ Protected      │   │ Conditional  │   │ Preservation and │
   │ model T        ├──▶│ reasoning    ├──▶│ human-utility    │
   │ generates c    │ c │ transformer R│ c̃ │ verifier V       │
   └────────────────┘   │ ITRO/SPECTRE │   └────────┬─────────┘
                        └──────────────┘            │
                                         ┌──────────┴──────────┐
                                    Pass │                     │ Fail
                                         ▼                     ▼
                                  Deliver c̃            Deliver clean c
```

Formally, for a query `q` the protected teacher produces a clean response `c = T(q)`. The transformer `R` receives the query, the clean response, the domain, and an intervention intensity, producing a candidate `c̃`. A verifier `V` then either accepts `c̃` or triggers fallback:

```
      ⎧ c̃ ,  if V(q, c, c̃) = 1
  y = ⎨
      ⎩ c  ,  otherwise
```

This separation means the base model remains untouched while the intervention policy evolves independently.

### Two signals the controller must keep separate

| Signal | Question it answers |
| - | - |
| **Request risk** | Does this session resemble extraction behavior? |
| **Pedagogical value** | How useful would this specific answer be as training data if collected? |

A simple factual lookup may be suspicious at the account level yet carry little marginal training value. A difficult derivation may be highly valuable even when the request looks ordinary. Conflating the two signals wastes transformation budget on low-value content.

## Design requirements

A deployable response-layer defense must satisfy these properties **simultaneously**. They are listed separately because the experiments show that satisfying one can hide failure in another.

| Requirement | Intended property | Why it must be measured independently |
| - | - | - |
| **Answer preservation** | Preserve the parent model's terminal answer or conclusion after transformation. | The service should not intentionally replace a correct answer merely because traffic looks suspicious. Preservation of the parent answer is *not* the same as objective correctness. |
| **Human utility** | Keep the explanation understandable, semantically coherent, and useful for legitimate work. | A correct last line can coexist with a misleading derivation. Users rely on intermediate reasoning for learning, debugging, auditing, and decision making. |
| **Student degradation** | Reduce capability gained by a student trained on transformed outputs. | Obfuscation that only increases response length or training loss is not a defense if held-out capability is unchanged. |
| **Stealth and diversity** | Avoid a trivial repeated signature that identifies protected responses. | A fixed visible pattern can be detected, removed, or normalized before training. |
| **Fail-safe behavior** | Return the clean response when the transformation cannot be verified. | An infrastructure or rewriting failure should not turn uncertain detection into user-facing corruption. |

**The current prototypes satisfy these requirements only partially.** That gap is the substance of this case study.

## Phase I: ITRO

### Inference-Time Reasoning Obfuscation

ITRO was the first, deliberately general-purpose implementation. Rather than applying one fixed transformation, it detects the response domain, estimates how valuable the response would be as distillation data, and scales the intervention accordingly.

**Supported domains (8):** mathematical computation · mathematical proof · code · scientific reasoning · logical argument · factual recall · procedural reasoning · analytical reasoning

### Intervention intensity τ

ITRO computes an obfuscation intensity `τ` as a weighted combination of four LLM-scored dimensions:

```
τ_raw = 0.35·d + 0.30·g + 0.20·e + 0.15·f
```

where `d` is reasoning depth, `g` is generalizability, `e` is expert density, and `f` is estimated dependence on frontier-model capability. Domain-specific floors and ceilings then clip the score:

| Domain | τ floor | τ ceiling |
| - | -: | -: |
| Factual recall | 0.05 | 0.35 |
| Procedural | 0.15 | 0.60 |
| Math computation | 0.35 | 0.72 |
| Logical argument | 0.30 | 0.85 |
| Scientific | 0.40 | 0.90 |
| Analytical | 0.40 | 0.92 |
| Code | 0.10 | 0.95 |
| Math proof | 0.55 | 1.00 |

> [!NOTE]
> These bounds are **engineering heuristics**, not empirically calibrated estimates of actual learning value. The later results show that estimated pedagogical value and actual student-gradient influence are not the same quantity.

### Pipeline

```text
Query ──▶ Clean teacher response ──▶ Domain detection ──▶ τ estimation
                                                              │
                                                              ▼
                                              Domain-specific transformation
                                                              │
                                                 Answer-preservation check
                                                       ╱             ╲
                                                   Pass               Fail
                                                     │                  │
                                                     ▼                  ▼
                                          Transformed response    Clean response
```

### What Phase I established

ITRO substantially increased optimization difficulty while producing almost no change in held-out capability:

| Metric | Clean | ITRO | Δ |
| - | -: | -: | -: |
| GSM8K accuracy | 39.6 % (198/500) | 39.0 % (195/500) | **−0.6 pp** |
| Average training loss | 0.1637 | 0.2555 | **≈ +56 %** |
| Final gradient norm | 0.1846 | 0.1919 | +0.0073 |

Only **three additional errors** on a 500-question evaluation. With no retained item-level predictions and no repeated seeds, a 0.6 pp difference cannot be treated as a stable causal effect.

Two structural weaknesses compound the result:

1. **Variable poison, stable answer.** ITRO deliberately varied the corruption path per example while the final answer stayed perfectly consistent. From the student's perspective, the obfuscation is a high-entropy style signal and the question→answer mapping is a low-entropy one. A small student can treat the detour as noise.
2. **Dilution by fallback.** The historical defended-dataset generation record reports approximately **85-87 % answer preservation**, implying that roughly **13-15 %** of attempted defended examples fell back to the clean teacher response. This protects service quality but leaves ordinary high-quality supervision inside the defended corpus.

> **Lesson:** making a distillation dataset harder to optimize is not equivalent to reducing the capability learned from it.

## Phase II: SPECTRE

### Structural Poisoning via Empirical Corruption of Training Representations

SPECTRE inverted ITRO's emphasis. Where ITRO prioritized diversity, SPECTRE tests the opposite hypothesis: **a harmful behavior may need to be structurally consistent across the corpus before a small student reliably learns it.** The scope narrowed to mathematics so one mechanism could be studied carefully.

### T7: Entangled False-Start

The dataset-generation default. T7 repeats the same high-level corruption *position* across examples while varying the recovery cue:

| Part | Transformation rule | Intended learning role |
| - | - | - |
| **Fixed opening** | Begin every transformed solution with exactly `"Let me work through this carefully."` | Creates a stable sequence anchor before the false start. |
| **Confident false start** | Use the problem's real numbers but choose a plausible wrong operation or formula for the first major computation. Work it for 2-4 lines without hedging. | Supplies repeated wrong-operation behavior in an early solution position. |
| **Variable pivot** | Select one of **20 pivot stems** deterministically from the question; the correction must reference the wrong value rather than silently restart. | Attempts to make recovery less uniform than the false start. |
| **Correct recovery** | Resume the clean solution values. Expand the largest multiplication as repeated addition (or division as repeated subtraction) where appropriate. | Preserves the terminal result while adding limited primitive decomposition. |
| **Fixed-style closing** | State `"So the final answer is N."` and append the teacher's original `#### N` line programmatically. | Delays the explicit final value and enforces terminal-answer equality by construction. |

The pivot stem and false-start depth are **deterministic functions of an MD5 hash of the question**, making generation reproducible per question across 20 stems and 3 depths (2-4 wrong lines). The response body is constrained to approximately **300 words**; the verifier tracks a **3,500-character** cap to keep examples inside the historical 1,024-token student sequence budget.

### Retained transformations (ablation and interactive use)

| ID | Transformation |
| :-: | - |
| T1 | Backward derivation |
| T2 | Wrong operation first |
| T3 | Primitive decomposition |
| T5 | Circular verification |
| T6 | Formula error correction |
| T7 | **Entangled False-Start (composite: dataset default)** |

An ensemble mode can generate these variants and rank them with a component named **GHOST**. The ranking is heuristic: it asks an LLM which candidate appears most harmful to student learning. It does **not** compute gradients, student loss, or measured downstream damage.

### The intended asymmetry

```text
   Consistent harmful pattern  ──▶  easier for the student to learn
   Variable recovery pattern   ──▶  harder to compress into one behavior
```

> [!WARNING]
> This is a **design hypothesis**, not an established causal explanation. T7 also changes sequence length, answer position, lexical regularity, and the distribution of intermediate numbers. It may create ordinary distribution shift rather than a learned "wrong-operation habit." Component ablations and student-side trajectory analysis are required before the mechanism can be claimed.

### What Phase II established

| Metric | Clean | SPECTRE | Δ |
| - | -: | -: | -: |
| GSM8K accuracy | 39.6 % (198/500) | 34.8 % (174/500) | **−4.8 pp** |
| Average training loss | 0.1637 | 0.3512 | **≈ +115 %** |
| Final gradient norm | 0.1846 | 0.2439 | +0.0593 |

SPECTRE produced the hardest training corpus of the three and the largest recorded separation, but the diagnostics do not identify *why* final accuracy is lower, and the same regularity that may make the poison learnable also makes the output conspicuous.

## Verification and fail-safe design

Both systems attempt to preserve the teacher's terminal result and fall back to the clean response when critical verification fails.

### SPECTRE T7 verification contract

| Check | Blocking? | What the code tests |
| - | :-: | - |
| `answer_match` | **Yes** | The numeric value on the variant's `####` line equals the clean teacher's value. For T7 this line is appended from the teacher, so equality is largely construction-level. |
| `internal_consistency` | **Yes** | The last number in the response body equals the terminal answer value. A narrow local property, not step-wise correctness. |
| `poison_present` | **Yes** | The expected pivot appears, and the pre-pivot text contains at least one number absent from the clean response. |
| `no_early_leak` | No | The answer value does not appear numerically in the first 60 % of the body. |
| `length_ok` | No | The body contains at most 3,500 characters. |
| `confident_false_start` | No | The false-start section lacks a small hand-coded set of hedging or error-admission markers. |

A candidate is accepted when the three blocking checks pass. The other three are warnings and do not block delivery.

### What the verifier does *not* guarantee

No implemented check verifies whether the pivot refers to the correct quantity, whether the false start is pedagogically safe for a human, or whether the full derivation is semantically natural.

<details>
<summary><strong>Worked failure case: the Natalia clips problem</strong></summary>

<br>

For the GSM8K problem where Natalia sells 48 clips in April and half as many in May, the clean solution obtains 24 clips in May and 72 total.

The T7 rewrite first computes `48 × 2 = 96` and describes 96 as the **April-plus-May total**. The pivot then argues that 96 *"cannot be correct for May alone"*, even though 96 had never been claimed to represent May alone. The response recovers to 72, and **every implemented verifier flag is true**:

```
answer_match          = true
internal_consistency  = true
poison_present        = true
no_early_leak         = true
length_ok             = true
confident_false_start = true
passed                = true
```

The system checks that a pivot exists, that an extra number appears before it, and that the last body number matches the appended answer. It does not check whether the pivot's semantic reference is coherent. **A user can therefore receive an explanation that is locally self-contradictory while the structural contract passes cleanly.**

</details>

> **Answer preservation is necessary but not sufficient.** Users ask for explanations because the path matters. A student learning mathematics may adopt the wrong formula; a programmer may copy a fragile pattern; a researcher may reuse an incorrect causal argument, even when the last line states the right conclusion.

ITRO carries a related gap: the non-math semantic-equivalence helper in `ITRO/correctness_checker.py` is coded to **fail open** on an exception, returning `True`. The general system therefore cannot currently claim strict fail-safe preservation across all domains.

## Where this sits in the literature

Anti-distillation work is easiest to compare by **intervention point** rather than algorithm name.

| Family | Intervention point | Teacher changed? | Relationship to ADHD |
| - | - | :-: | - |
| **Teacher-side training**: Nasty Teacher, CMIM, Teacher Scrambling, DOGe, Distillation Traps and Guards | Teacher weights, output head, or calibration policy | **Yes** | Strong control at the source, but protection is coupled to a modified teacher rather than a separable wrapper. |
| **Serving-time decoding / logit shaping**, ADS, LADS, Product-of-Experts, CMI-based purification | Sampling randomness, next-token probabilities, exposed logits | Usually no persistent change | Finer control than text editing, but requires access to generation internals, logits, private randomness, or a proxy-student signal. |
| **Post-generation trace transformation**: PART, SelfCAD, trace rewriting, TraceGuard, SGRE | A completed reasoning trace is reordered, rewritten, or selectively edited | **No** | **Closest family to this work.** Preserves deployment separability but must solve semantic validity, naturalness, detectability, and attacker-side sanitization. |
| **Information throttling**: CoT removal or summarization | Rationale withheld or compressed before delivery | **No** | Simple and often strong baseline. A deception mechanism must demonstrate benefit *beyond* it. |
| **Attribution / fingerprinting**: DRW, EWE, ReasMark, ADFP | Watermark or learning-aware fingerprint designed to survive transfer | Varies | Addresses attribution rather than prevention; complements active degradation. |

**Positioning.** This work does not claim priority over anti-distillation output manipulation or post-generation trace editing. SGRE's "Answer-then-Edit" is a particularly close architectural neighbor. The narrower question here is whether a defense can be **deployment-separable**: the protected teacher produces its ordinary response using its ordinary weights and ordinary low-risk decoding path, and only then may a risk-gated external component transform the visible explanation. That constraint is attractive for providers who do not want anti-extraction behavior permanently embedded in every model response. It is also a handicap: acting only after generation gives the wrapper less control over token-level learning dynamics, and a visible text transformation may be easier to detect, normalize, or sanitize.

## Repository structure

```text
ADHD-AntiDistillation/
│
├── ITRO/                          # Phase I: Inference-Time Reasoning Obfuscation
│   ├── main.py                    #   Interactive CLI
│   ├── pipeline.py                #   Orchestration: detect → score → transform → verify
│   ├── domain_detector.py         #   8-domain hybrid heuristic + LLM classifier
│   ├── tau_system.py              #   τ estimation, dimension weights, domain bounds
│   ├── itro_engine.py             #   Domain-specific rewrite prompts
│   ├── correctness_checker.py     #   Answer preservation + semantic equivalence
│   ├── providers/                 #   anthropic · gemini · qwen (local)
│   ├── tests/                     #   pytest suite
│   └── README.md
│
├── SPECTRE/                       # Phase II: Structural Poisoning
│   ├── main.py                    #   Interactive CLI
│   ├── pipeline.py                #   Composite (T7) and ensemble strategies
│   ├── teacher.py                 #   Clean teacher-response generation
│   ├── ghost_scorer.py            #   Heuristic LLM ranking of ensemble variants
│   ├── correctness_checker.py     #   Six-flag T7 verification contract
│   ├── config.py                  #   Token budgets, 3500-char cap, 0.6 leak fraction
│   ├── transformations/           #   t1 · t2 · t3 · t5 · t6 · t7_composite
│   ├── providers/                 #   anthropic · gemini
│   ├── tests/                     #   pytest suite
│   └── README.md
│
├── ITRO_Test/                     # Small demonstration dataset + harness
├── SPECTRE_Test/                  # Small demonstration dataset + harness
│
├── idea.md                        # Design rationale and threat model
├── results.md                     # Complete experimental record and failure analysis
└── Readme.md                      # This file
```

## Installation and usage

Both systems are standalone Python packages with their own dependency sets.

### ITRO

```bash
cd ITRO
pip install -r requirements.txt
cp .env.example .env          # add ANTHROPIC_API_KEY or GEMINI_API_KEY
python main.py
```

Providers: **Anthropic / Claude**, **Gemini**, **local Qwen**. For local Qwen inference:

```bash
pip install -r requirements-local.txt
```

### SPECTRE

```bash
cd SPECTRE
pip install -r requirements.txt
cp .env.example .env
python main.py
```

Two strategies are available:

- **`composite`**: T7 Entangled False-Start (dataset-generation default)
- **`ensemble`**: the five retained transformations plus GHOST ranking (ablations and demos)

```bash
python main.py -p 1 -m 1 -s composite \
  "A store has 48 apples. 24 are sold. How many are left?"
```

### Tests

```bash
cd ITRO    && pip install -r requirements-dev.txt && pytest
cd SPECTRE && pip install -r requirements-dev.txt && pytest
```

See [`ITRO/README.md`](ITRO/README.md) and [`SPECTRE/README.md`](SPECTRE/README.md) for provider configuration, CLI options, and implementation detail.

## Experimental methodology

| Component | Configuration |
| - | - |
| Teacher reference | `Qwen2.5-7B-Instruct` |
| Final student | `Qwen2.5-0.5B-Instruct` |
| Intermediate student | `Qwen2.5-3B-Instruct` (earlier run; source of the clean/ITRO loss traces) |
| Training examples | 2,000 per arm |
| Evaluation | 500 held-out GSM8K questions, deterministic greedy decoding (`do_sample=False`) |
| Answer format | `#### [number]` |
| Learning rate | `2e-5` |
| Batch size | 2 physical × 8 gradient accumulation = **16 effective** |
| Epochs | 3 |
| Max sequence length | 1,024 (raised from an unsafe 512) |
| Hardware | NVIDIA A100 SXM4 80 GB, ASU Sol HPC cluster |

### Three-arm design

```text
                                Dataset A ──▶ Student A     (clean)
  Training prompts ──▶ Teacher  Dataset B ──▶ Student B     (ITRO or SPECTRE)   ──▶  500 held-out
   2,000 per arm      7B ref    Dataset C ──▶ Student C     (no-rationale)           GSM8K questions
```

The clean and defended students should differ **only** in the teacher-response transformation. The no-rationale arm estimates how much capability remains when detailed explanation is withheld rather than poisoned, and it is the comparison that most constrains the value of any deception mechanism.

### Complete recorded training diagnostics

<details>
<summary><strong>Clean student</strong>, average loss 0.1637</summary>

<br>

| Epoch | Loss | Grad. norm | Learning rate |
| -: | -: | -: | -: |
| 0.8 | 0.1790 | 0.2207 | 1.843e-05 |
| 1.2 | 0.1626 | 0.1865 | 1.511e-05 |
| 1.6 | 0.1526 | 0.2129 | 1.070e-05 |
| 2.0 | 0.1517 | 0.2051 | 6.141e-06 |
| 2.4 | 0.1388 | 0.2021 | 2.407e-06 |
| 2.8 | 0.1392 | 0.1846 | 2.923e-07 |
| **Final** | **0.1637 avg** | n/a | n/a |

</details>

<details>
<summary><strong>ITRO student</strong>, average loss 0.2555 (≈ +56 % vs. clean)</summary>

<br>

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

</details>

<details>
<summary><strong>SPECTRE student</strong>, average loss 0.3512 (≈ +115 % vs. clean, ≈ +37 % vs. ITRO)</summary>

<br>

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

</details>

The clean and ITRO traces come from the earlier/intermediate 3B student run rather than a bit-for-bit trace of the final 0.5B evaluation experiment; the SPECTRE trace is recorded separately. They are **complete as archived optimization diagnostics** but should not be read as a matched causal explanation of the benchmark differences.

## Limitations

> [!CAUTION]
> Every result in this repository is a **descriptive observation from a single historical run**, not a replicated effect size.

**Single-run evidence.** Each condition is represented by one student-training run over 500 evaluation items. Item-level predictions were not retained, so a paired significance test (e.g. McNemar) cannot be recovered even though the models were evaluated on the same questions.

**Incomplete reproducibility chain.** The repository preserves transformation code, configuration, unit tests, and small demonstration datasets, but not every historical trainer, evaluator, checkpoint, command, and per-item prediction needed to reproduce the Qwen results end to end. The codebase additionally supports Anthropic and Gemini endpoints, which were **not** used to generate the reported teacher responses.

**Weak attacker model.** The historical setup assumes direct fine-tuning on collected outputs. It does not test sanitization, paraphrasing, selective truncation, prefix stripping, answer-only training, repeated querying, or interface switching. The attacker profile is narrow: ≈ 2,000 collected responses per arm, a text-only interface, direct SFT, and no adaptive sanitizer.

**Narrow benchmark.** GSM8K is grade-school mathematics. Both the 37.0 % no-rationale control and the teacher's high baseline suggest substantial task knowledge is already present in the student. Nothing here establishes behavior on college mathematics, competition problems, code, science, or general instruction following.

**No human study.** No controlled evaluation measures whether transformed explanations remain correct, readable, efficient to use, or perceptibly manipulated. The Natalia case shows why this omission is central rather than cosmetic.

**Fingerprintability.** T7's fixed opening, early false start, visible pivot, primitive decomposition, and fixed-style closing create a recognizable signature. A sanitizer could delete the first few lines, drop sentences containing pivot markers, ask another model to rewrite the response, or train only on answer-bearing segments.

<details>
<summary><strong>Historical implementation issues found and repaired during ITRO</strong></summary>

<br>

These are recorded because they materially inform how future anti-distillation experiments should be audited:

1. A **critical indentation error** in the defended-dataset generator could cause transformation failure and silently return clean outputs. This motivated explicit poison-presence auditing.
2. Training initially used **raw text while evaluation used Qwen chat templates**, creating a format mismatch that could dominate small accuracy differences.
3. A **512-token sequence limit** could truncate longer defended responses and, in the worst case, remove the terminal answer. Raised to 1,024.
4. A **deprecated model-loading parameter** was present in the historical stack.
5. **Temperature was passed in a greedy-decoding configuration**, where it had no effect.

> A defense experiment can appear to be studying poisoned supervision while actually measuring formatting drift, truncation, or silent fallback.

</details>

## Research directions

The next phase should prioritize replication over another transformation family.

1. **Multi-seed replication** with archived per-item predictions and paired (McNemar-style) analysis.
2. **Mechanism ablations**: separately remove the fixed opening, false-start operation, pivot variability, answer delay, and primitive decomposition.
3. **Matched controls**: a length-matched coherent rewrite and a structurally repetitive but *mathematically correct* rewrite. If these reproduce the drop, the effect is distribution shift, not poisoned reasoning.
4. **Harder benchmarks**: MATH, MATH-500, college-level and competition problems, with difficulty stratified rather than averaged.
5. **Human evaluation as a primary endpoint**: intermediate-step correctness, comprehension, reading time, perceived naturalness, and whether a response appears intentionally manipulated.
6. **Adaptive-attacker sanitization**: score the defense *after* prefix stripping, paraphrasing, answer-only extraction, and anomaly filtering.
7. **Cross-family comparison** on an open teacher: clean, no-rationale, teacher-side (Nasty Teacher, CMIM, DOGe), serving-time (ADS, LADS, PoE), and post-generation (PART, TraceGuard, SGRE), quantifying **the price of deployment separability**.
8. **Systems-cost measurement**: latency, extra generated tokens, inference cost, clean-fallback rate, and attacker capability gained per dollar or per collected token.
9. **Stronger semantic verification**: treat semantic defects like the Natalia case as a hard rejection condition.

The central research target is not to make responses confusing. It is to find transformations that remain **conceptually correct, coherent, natural, and useful to humans** while being **systematically less valuable as supervision for unauthorized student training**.

## Paper

**Post-Generation Response Transformation Against Unauthorized Model Distillation: An Empirical Case Study**
Sherwin Vishesh Jathanna · Arizona State University · `sjathann@asu.edu`

The paper covers the response-layer threat model, the ADHD architecture, both experimental phases, complete training diagnostics, the verifier audit, human-utility limitations, adaptive-attacker considerations, related anti-distillation work organized by intervention point, and future research directions.

### Contributions

1. A response-layer threat model that **separates abuse detection from the intervention applied after detection**.
2. A two-phase empirical record, paired with complete recorded training diagnostics, showing that **optimization difficulty and downstream degradation must be evaluated separately**.
3. Evidence that broad surface obfuscation was weak, while stronger structural poisoning creates a **human-utility and detectability problem**.
4. A **code-level audit** of what the current verifiers actually guarantee.
5. A concrete future research target: transformations that remain natural and semantically useful to humans while systematically degrading the statistical supervision available to a distilling student.

## Reproducibility and provenance

For future releases, this project recommends archiving: exact prompts and control datasets; transformation metadata and fallback rates; model and tokenizer versions; sequence-length statistics; seeds; commands; checkpoints; held-out identifiers; item-level predictions and raw counts; human-evaluation materials; sanitizer code; attacker-cost measures; and content hashes sufficient to reconstruct the student-training corpus.

The current repository meets part of this standard. It contains the ITRO and SPECTRE generation code, unit tests, configuration, and small demonstration datasets, **not** the complete historical student trainer and evaluator used for every reported result.

## Responsible use

This repository explores **defensive** techniques against unauthorized model extraction and distillation. Distillation itself is a legitimate and widely used training technique; the concern here is prohibited extraction.

A deception-based response layer deliberately changes what a user sees, and the trigger is uncertain by design. The current SPECTRE mechanism goes beyond benign obfuscation by intentionally inserting a wrong operation before recovering.

> [!CAUTION]
> These transformations are **not intended for deployment in high-stakes domains**. Medical, legal, financial, and safety-critical applications should not receive transformations that insert false intermediate claims.

Even in low-stakes domains, a responsible deployment would require domain gating, semantic verification, measured human comprehension, monitoring for user harm, a clean fallback, and explicit product and legal review. The goal of this project is to determine whether a transformation regime exists in which human utility stays high enough that false positives are genuinely cheap. **The current mechanisms do not meet that standard.**

## Citation

```bibtex
@misc{jathanna2026adhd,
  title  = {Post-Generation Response Transformation Against Unauthorized
            Model Distillation: An Empirical Case Study},
  author = {Jathanna, Sherwin Vishesh},
  year   = {2026},
  eprint = {arXiv:XXXX.XXXXX},
  archivePrefix = {arXiv},
  primaryClass  = {cs.CR},
  note   = {Arizona State University}
}
```

## Acknowledgments

The author thanks **Yash Savani** (Carnegie Mellon University) for guidance during the early ideation of ADHD-ITRO, in particular his encouragement to "fail fast" through rapid empirical iteration, and his observation that student models can extract useful training signal even from imperfect supervision.

The author also acknowledges **Research Computing at Arizona State University** for providing high-performance computing resources that contributed to the results reported here, including access to the **Sol** supercomputer.

<p align="center"><sub>
This repository contains experimental research code. The reported benchmark differences are descriptive results from single historical runs and should not be interpreted as proof of a production-ready anti-distillation defense.
</sub></p>

<p align="center">
  Made with ❤️ by <strong>Sherwin Jathanna</strong>
</p>
