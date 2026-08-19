# ADHD: Adaptive Defense via Honeypot Deception

### A Post-Generation Defense Against Unauthorized LLM Distillation

**ADHD** is a research framework for exploring whether the training value of LLM API responses can be reduced **without modifying the protected model itself**.

The system introduces a deployment-separable response layer: the protected teacher generates its normal response first, and an external controller can then transform the visible explanation before it is returned. The goal is to preserve useful answers for legitimate users while making large-scale collection less valuable for unauthorized model distillation.

This repository contains two generations of the idea:

* **ITRO** — Inference-Time Reasoning Obfuscation
* **SPECTRE** — Structural Poisoning via Empirical Corruption of Training Representations

> **Research status:** ADHD is an experimental research project, not a production-ready security mechanism. The current results identify both promising signals and important limitations, particularly around human utility, semantic verification, and adaptive attackers.



## Motivation

Language-model APIs expose more than final answers. Detailed explanations and reasoning traces can provide useful supervision for training smaller models.

A black-box extractor can:

1. Query a stronger model at scale.
2. Collect prompt-response pairs.
3. Use the collected responses as supervised fine-tuning data.
4. Train a smaller student to reproduce some of the teacher's behavior.

Most defenses focus on detecting extraction, restricting access, modifying the teacher, or changing generation-time behavior.

ADHD investigates a different intervention point:

```text
Incoming Query
      |
      v
Protected Teacher
(normal generation)
      |
      v
Clean Response
      |
      v
External Response Layer
      |
      +------ Low risk ------> Clean Response
      |
      +------ Intervention --> Transform Explanation
                                   |
                                   v
                               Verification
                              /            \
                           Pass            Fail
                            |                |
                            v                v
                       Transformed        Clean
                        Response          Fallback
```

The protected model's weights do not need to be changed.

This makes the defense independently deployable, replaceable, and selectively activatable.



## Core Research Question

ADHD studies whether there exists a useful asymmetry between:

> **information that remains useful to a human reader**

and

> **statistical supervision that is useful to a distilling student model.**

That turns anti-distillation into a multi-objective problem.

A useful response-layer defense should simultaneously provide:

* **Answer preservation** — preserve the teacher's terminal answer or conclusion.
* **Human utility** — maintain understandable and semantically valid explanations.
* **Student degradation** — reduce capability transferred through distillation.
* **Stealth and diversity** — avoid easily removable transformation signatures.
* **Fail-safe behavior** — return the clean response when verification fails.

The experiments in this repository satisfy these requirements only partially.



# Experimental Evolution

## Phase I — ITRO

### Inference-Time Reasoning Obfuscation

ITRO was the first implementation of ADHD.

Instead of applying one fixed transformation, ITRO detects the response domain and estimates how valuable the response may be as distillation data.

It supports eight reasoning domains, including:

* Mathematical computation
* Mathematical proof
* Code
* Scientific reasoning
* Logical argument
* Factual recall
* Procedural reasoning
* Analytical reasoning

ITRO computes an intervention intensity **τ (tau)** from four estimated dimensions:

```text
τ = 0.35(reasoning depth)
  + 0.30(generalizability)
  + 0.20(expert density)
  + 0.15(frontier dependence)
```

Domain-specific bounds are then applied before the explanation is transformed.

### ITRO Pipeline

```text
Query
  |
  v
Clean Teacher Response
  |
  v
Domain Detection
  |
  v
Pedagogical-Value / Tau Estimation
  |
  v
Domain-Specific Transformation
  |
  v
Answer Preservation Check
  |
  +---- Pass ---> Transformed Response
  |
  +---- Fail ---> Clean Response
```

### What ITRO Taught Us

ITRO substantially increased training difficulty but produced very little change in held-out student accuracy.

| Student            |     GSM8K |  Accuracy | Gap vs. Clean |
| ------------------ | --------: | --------: | ------------: |
| Clean Distillation | 198 / 500 | **39.6%** |             — |
| ITRO               | 195 / 500 | **39.0%** |   **−0.6 pp** |

Recorded average training loss:

| Training Data | Average Loss |
| ------------- | -----------: |
| Clean         |       0.1637 |
| ITRO          |       0.2555 |

ITRO's recorded average loss was approximately **56% higher** than clean training, while held-out accuracy changed by only **0.6 percentage points**.

This produced an important lesson:

> **Making a distillation dataset harder to optimize is not equivalent to reducing the capability learned from it.**

The student may be able to treat variable reasoning detours as noise while continuing to learn stable problem-to-answer relationships.



# Phase II — SPECTRE

### Structural Poisoning via Empirical Corruption of Training Representations

SPECTRE emerged from the ITRO results.

ITRO emphasized **diversity**.

SPECTRE tests the opposite hypothesis: perhaps a harmful behavior must be **structurally consistent** across the training corpus before a small student reliably learns it.

The primary dataset transformation is:

### T7 — Entangled False-Start

T7 introduces a repeated high-level structure:

```text
Fixed Opening
      |
      v
Confident False Start
      |
      v
Variable Recovery Pivot
      |
      v
Correct Recovery
      |
      v
Preserved Final Answer
```

The transformation intentionally makes the early false-start position relatively consistent while varying the recovery mechanism.

The hypothesis is that this could create an asymmetry in learnability:

```text
Consistent harmful pattern
        |
        v
Easier for student to learn

Variable recovery pattern
        |
        v
Harder to compress into one behavior
```

This remains a **mechanistic hypothesis**, not an established causal explanation of the experimental result.



## Experimental Results

The historical experiment used:

* **Teacher reference:** Qwen2.5-7B-Instruct
* **Final student:** Qwen2.5-0.5B-Instruct
* **Training examples:** 2,000 per arm
* **Evaluation:** 500 held-out GSM8K problems

### Final Recorded GSM8K Results

| Condition            |   Correct |  Accuracy | Gap vs. Clean |
| -------------------- | --------: | --------: | ------------: |
| Teacher Reference    | 425 / 500 | **85.0%** |             — |
| Clean Student        | 198 / 500 | **39.6%** |             — |
| ITRO Student         | 195 / 500 | **39.0%** |       −0.6 pp |
| SPECTRE Student      | 174 / 500 | **34.8%** |       −4.8 pp |
| No-Rationale Student | 185 / 500 | **37.0%** |       −2.6 pp |

SPECTRE produced **24 fewer correct answers** than clean distillation in the recorded evaluation.

Its recorded average training loss was also the highest:

| Condition | Average Training Loss |
| --------- | --------------------: |
| Clean     |            **0.1637** |
| ITRO      |            **0.2555** |
| SPECTRE   |            **0.3512** |

These results suggest that SPECTRE created a stronger training disturbance than ITRO under the recorded setup.

However, the **4.8 percentage-point difference should not be interpreted as an established causal effect**.

The historical experiment used a single training run per condition, item-level predictions were not retained, and the complete historical training/evaluation stack is not available for bit-for-bit reproduction.



## The No-Rationale Baseline

One of the most important results is the simple no-rationale control:

```text
Clean       39.6%
No-Rationale 37.0%
SPECTRE     34.8%
```

Simply withholding detailed reasoning reduced accuracy by **2.6 pp**.

SPECTRE was another **2.2 pp below** that baseline in the recorded run.

This creates a higher bar for a complex anti-distillation mechanism:

> A transformation should provide enough additional degradation, attacker cost, or robustness to justify its added complexity and potential impact on legitimate users.



# Repository Structure

```text
ADHD-AntiDistillation/
│
├── ITRO/
│   ├── main.py
│   ├── pipeline.py
│   ├── domain_detector.py
│   ├── tau_system.py
│   ├── itro_engine.py
│   ├── correctness_checker.py
│   ├── providers/
│   ├── tests/
│   └── README.md
│
├── SPECTRE/
│   ├── main.py
│   ├── pipeline.py
│   ├── teacher.py
│   ├── ghost_scorer.py
│   ├── correctness_checker.py
│   ├── transformations/
│   ├── providers/
│   ├── tests/
│   └── README.md
│
├── ITRO_Test/
├── SPECTRE_Test/
├── ITRO_findings.md
├── results.md
├── idea.md
└── README.md
```

The individual `ITRO/` and `SPECTRE/` directories contain more detailed implementation and usage documentation.



# Running ITRO

```bash
cd ITRO
pip install -r requirements.txt
cp .env.example .env
python main.py
```

ITRO supports:

* Anthropic / Claude
* Gemini
* Local Qwen

For local Qwen support:

```bash
pip install -r requirements-local.txt
```

See [`ITRO/README.md`](ITRO/README.md) for provider configuration, CLI options, domain detection, and implementation details.



# Running SPECTRE

```bash
cd SPECTRE
pip install -r requirements.txt
cp .env.example .env
python main.py
```

SPECTRE supports both:

* **Composite mode** — T7 Entangled False-Start
* **Ensemble mode** — retained transformations for ablations and experimentation

Example:

```bash
python main.py -p 1 -m 1 -s composite \
  "A store has 48 apples. 24 are sold. How many are left?"
```

See [`SPECTRE/README.md`](SPECTRE/README.md) for the full pipeline, transformation definitions, provider configuration, and testing instructions.



# Verification and Fail-Safe Design

Both systems attempt to preserve the teacher's terminal result and fall back to the clean response when critical verification fails.

SPECTRE's T7 verifier currently checks properties including:

* terminal answer match
* local internal consistency
* poison presence
* early answer leakage
* response length
* false-start confidence

However, these checks **do not establish full semantic correctness of the intermediate explanation**.

This is an important limitation.

A transformed response can preserve the correct final answer while containing a locally incoherent derivation.

For a production-quality system, answer preservation alone is therefore insufficient.



# Current Limitations

ADHD should currently be treated as a **research prototype and empirical case study**.

Major limitations include:

### Single-run evidence

Each experimental condition is represented by one historical student-training run. Multiple independent seeds are needed to establish whether the observed differences are reproducible.

### Narrow benchmark

The primary evaluation uses GSM8K. The current evidence does not establish generalization to harder mathematics, code generation, scientific reasoning, or general instruction following.

### Incomplete historical reproducibility

The transformation code and configuration are preserved, but not every historical trainer, evaluator, checkpoint, command, and per-item prediction required for bit-for-bit reconstruction.

### Human utility

The project does not yet contain a controlled human study measuring readability, comprehension, intermediate-step correctness, or perceived manipulation.

### Adaptive attackers

The historical experiments assume a relatively naive collector.

An adaptive extractor could attempt to:

* strip repeated prefixes
* remove false-start sections
* retain only final answers
* paraphrase responses
* summarize reasoning
* filter anomalous traces
* selectively retain high-value segments

A useful defense must be evaluated **after** such sanitization.

### Fingerprintability

SPECTRE exposes a fundamental trade-off:

> The more consistent a transformation becomes for student learning, the easier it may become for an attacker to recognize and remove.

ITRO was comparatively diverse but produced little recorded degradation.

SPECTRE produced a larger recorded separation but introduced a more recognizable structure.

Finding a transformation that achieves both **learnability asymmetry and stealth** remains an open problem.



# Research Directions

The next experiments should prioritize:

1. **Multi-seed replication**
2. **Archived item-level predictions**
3. **Mechanism ablations**
4. **Length- and structure-matched controls**
5. **Harder reasoning benchmarks**
6. **Human semantic evaluation**
7. **Adaptive attacker sanitization**
8. **Latency and token-cost measurement**
9. **Comparison with teacher-side and decoding-time defenses**
10. **Stronger semantic verification**

The central research target is not simply to make responses confusing.

It is to find transformations that remain:

> **conceptually correct, coherent, natural, and useful to humans**

while being:

> **systematically less valuable as supervision for unauthorized student training.**



# Paper

The research and experimental record are described in:

**Post-Generation Response Transformation Against Unauthorized Model Distillation: An Empirical Case Study**

The paper covers:

* the ADHD response-layer architecture
* ITRO
* SPECTRE
* the historical distillation experiments
* training diagnostics
* verifier analysis
* human-utility limitations
* adaptive-attacker considerations
* related anti-distillation work
* future research directions



# Responsible Use

This repository explores defensive techniques against unauthorized model extraction and distillation.

The current transformations are **not intended for deployment in high-stakes domains**. In particular, transformations that introduce intentionally incorrect intermediate reasoning should not be used for medical, legal, financial, safety-critical, or similarly consequential applications.

A real deployment would require substantially stronger semantic verification, human-utility evaluation, monitoring, clean fallback behavior, and appropriate product, policy, and legal review.

The goal of this project is to study whether response-layer transformations can reduce unauthorized capability transfer while preserving legitimate-user utility—not to justify degrading arbitrary users.





## Disclaimer

This repository contains experimental research code. The reported benchmark differences are descriptive results from historical experiments and should not be interpreted as proof of a production-ready anti-distillation defense.
