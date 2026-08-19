# ADHD: Design Rationale and Threat Model

**Adaptive Defense via Honeypot Deception**

Sherwin Vishesh Jathanna · Arizona State University · `sjathann@asu.edu`

## About this document

This is the **design document** for ADHD. It states the threat model, the security objective, the architectural commitments, the per-domain corruption catalogs, and the design principles that produced the ITRO and SPECTRE implementations.

It is deliberately separated from two other documents:

| Document | Role |
| - | - |
| **`idea.md`** *(this file)* | Why the system is designed the way it is, threat model, objectives, mechanisms, constraints, open questions |
| **`results.md`** | What actually happened when it was built and measured |
| **`Readme.md`** | Repository overview, headline results, installation, usage |

Where a design claim has since been tested, this document marks the outcome inline with a **`Recorded outcome`** callout rather than leaving the rationale disconnected from the evidence. Those callouts reference the finalized experimental record:

| Model | Correct | GSM8K accuracy | Gap vs. clean |
| - | -: | -: | -: |
| Teacher (`Qwen2.5-7B-Instruct`) | 425 / 500 | 85.0 % | n/a |
| Student-Baseline (clean distillation) | 198 / 500 | 39.6 % | n/a |
| Student-ITRO | 195 / 500 | 39.0 % | −0.6 pp |
| Student-SPECTRE | 174 / 500 | 34.8 % | −4.8 pp |
| Student-NoCoT (no rationale) | 185 / 500 | 37.0 % | −2.6 pp |

> [!IMPORTANT]
> **Scope of the term "reasoning trace."** Throughout this document, "reasoning trace" means **the visible explanation text returned through an API**. No part of this design accesses, inspects, or modifies a model's hidden internal reasoning. Every mechanism operates on text a user would have received anyway.

## Table of contents

**Part I: The problem**
[1. Core idea](#1-core-idea) ·
[2. What is actually being protected](#2-what-is-actually-being-protected) ·
[3. The threat model](#3-the-threat-model) ·
[4. Why simple defenses are insufficient](#4-why-simple-defenses-are-insufficient) ·
[5. The reframing](#5-the-reframing)

**Part II: The objective**
[6. The security objective](#6-the-security-objective) ·
[7. Design requirements](#7-design-requirements) ·
[8. Two separated signals](#8-two-separated-signals) ·
[9. Graded response and adaptive intensity](#9-graded-response-and-adaptive-intensity)

**Part III: The architecture**
[10. Formal framework](#10-formal-framework) ·
[11. Conceptual system architecture](#11-conceptual-system-architecture) ·
[12. Stage 1: Risk assessment](#12-stage-1-risk-assessment) ·
[13. Stage 2: Value estimation](#13-stage-2-value-estimation) ·
[14. Stage 3: Transformation](#14-stage-3-transformation) ·
[15. Stage 4: Verification and fail-safe](#15-stage-4-verification-and-fail-safe)

**Part IV: The mechanism**
[16. What "pedagogically toxic" means](#16-what-pedagogically-toxic-means) ·
[17. Per-domain corruption catalogs](#17-per-domain-corruption-catalogs) ·
[18. Naturalness as a hard constraint](#18-naturalness-as-a-hard-constraint) ·
[19. Systematic vs. random corruption](#19-systematic-vs-random-corruption) ·
[20. Obfuscation vs. poisoning](#20-obfuscation-vs-poisoning) ·
[21. Answer preservation](#21-answer-preservation) ·
[22. Correctness is necessary but not sufficient](#22-correctness-is-necessary-but-not-sufficient)

**Part V: The constraints**
[23. The safety valve](#23-the-safety-valve) ·
[24. The untouched base model](#24-the-untouched-base-model) ·
[25. The honeypot property](#25-the-honeypot-property) ·
[26. Attacker adaptation](#26-attacker-adaptation) ·
[27. Defense diversity](#27-defense-diversity) ·
[28. Human utility as a hard constraint](#28-human-utility-as-a-hard-constraint) ·
[29. High-stakes domains and ethics](#29-high-stakes-domains-and-ethics)

**Part VI: Boundaries and evaluation**
[30. What ADHD is not](#30-what-adhd-is-not) ·
[31. What success would mean](#31-what-success-would-mean) ·
[32. The economic frame](#32-the-economic-frame) ·
[33. Position in the defense stack](#33-position-in-the-defense-stack) ·
[34. Position in the literature](#34-position-in-the-literature)

**Part VII: Synthesis**
[35. The central research question](#35-the-central-research-question) ·
[36. The fundamental design tension](#36-the-fundamental-design-tension) ·
[37. Design principles](#37-design-principles) ·
[38. What the experiments changed about this design](#38-what-the-experiments-changed-about-this-design) ·
[39. Long-term vision](#39-long-term-vision)

# Part I: The problem

## 1. Core idea

A frontier model's most valuable asset is not the answers it produces. It is **the reasoning process that produces them**.

An answer is a single point. A reasoning trace is a *demonstration of method*: it shows how to decompose a problem, which operations to select, how to check intermediate results, when to abandon an approach. That generalizes. It is why a small model trained on a large model's reasoning traces can acquire capabilities disproportionate to its size and training budget.

This creates an asymmetry with unusual security properties:

> The provider must expose the reasoning trace to be useful. Exposing the reasoning trace is exactly what makes the model cheap to copy.

**ADHD's core idea:** rather than choosing between exposing reasoning and withholding it, insert a **deployment-separable transformation layer** between the model and the response. The layer receives a complete, correct response from the parent model and may return a modified version whose *conclusion* is preserved but whose *demonstrated method* is less valuable as training supervision.

The name, Adaptive Defense via Honeypot Deception, encodes three commitments:

| Term | Commitment |
| - | - |
| **Adaptive** | Intensity scales with assessed risk and value; ordinary traffic is untouched |
| **Defense** | Purely reactive; nothing is deployed against an attacker's systems |
| **Honeypot Deception** | The response should look like an ordinary response, not like a defensive artifact |

## 2. What is actually being protected

It is worth being precise, because vague framing produces vague defenses.

**Not protected by ADHD:**

- model weights (that is an infrastructure security problem),
- the training corpus,
- system prompts,
- the fact that the model can perform a task,
- final answers to individual questions.

**Protected by ADHD:**

- the **transferable reasoning method** demonstrated in a response,
- the **structure** of a multi-step solution,
- the **decision procedure** for selecting operations, strategies, or framings,
- the aggregate value of a **large collection** of such traces as a training corpus.

This distinction matters. ADHD does not attempt to prevent a user from learning the answer to their question; that would be a failed product. It attempts to reduce the value of the response **as one row in a training set of ten thousand rows**.

The unit of protection is therefore the **corpus**, not the response. A defense that makes a single response marginally less useful but a corpus of 50,000 responses substantially less useful is a success. A defense that ruins individual responses to achieve the same corpus effect is not.

## 3. The threat model

### 3.1 The attacker

The attacker is a party that queries a deployed model through its ordinary interface, collects the responses, and fine-tunes a smaller model on the collected pairs. This is **unauthorized distillation**, often called model extraction or knowledge theft.

The attack is attractive because it is cheap. Training a frontier model requires enormous capital, data, and expertise. Distilling one requires an API key, a query budget, and standard fine-tuning code. The economics strongly favor the attacker.

### 3.2 Why this is not hypothetical

Anthropic's February 2026 threat-intelligence report describes three distinct campaigns that collectively generated **more than 16 million exchanges** across roughly **24,000 fraudulent accounts**, with a single campaign exceeding **13 million exchanges**.

Those figures establish three facts that constrain the design:

| Observation | Design implication |
| - | - |
| Collection happens at **scale** | Per-response defenses must aggregate into a corpus-level effect |
| Collection is **distributed across many accounts** | Per-account rate limits and reputation are insufficient alone |
| Campaigns are **operationally organized** | The attacker will adapt once a defense is discovered |

### 3.3 Attacker capability dimensions

Following the formalization of attacker profiles in the extraction literature, a claim about anti-distillation effectiveness is meaningless without specifying:

| Dimension | Question | This project's historical experiments |
| - | - | - |
| **Query budget** | How many requests can the attacker make? | ≈ 2,000 per arm, small |
| **Data budget** | How many training examples can they assemble? | 2,000 |
| **Interface profile** | Text only? Logits? Top-k? Streaming? | Text only |
| **Training method** | SFT? Preference learning? Multi-teacher? | Direct supervised fine-tuning |
| **Adaptivity** | Do they filter, paraphrase, or sanitize collected data? | **None** |

> [!WARNING]
> The last row is the most important limitation of the current evidence. A **non-adaptive** attacker is the weakest attacker in this space. A determined extractor would inspect a sample of collected data, notice systematic artifacts, and preprocess them away. Robustness against that attacker has **not** been demonstrated and belongs in the core threat model, not in future work.

### 3.4 What the defender controls

The defender controls the response text, the decision to transform, the transformation policy, and the fallback. The defender does **not** control what the attacker does with the response afterward.

This asymmetry is the reason naturalness matters so much (see [§18](#18-naturalness-as-a-hard-constraint) and [§25](#25-the-honeypot-property)). Anything the attacker can *see* as defensive, the attacker can *remove*.

## 4. Why simple defenses are insufficient

Each simple defense is worth stating explicitly, because each fails for an instructive reason.

### 4.1 Rate limiting

Fails against distributed collection. Sixteen million exchanges across 24,000 accounts is precisely the shape of traffic that per-account limits do not catch. Aggressive global limits degrade the legitimate product.

### 4.2 Terms-of-service prohibition

Legally meaningful, technically inert. A prohibition raises the cost of getting caught; it does not raise the cost of the attack itself.

### 4.3 Account-level detection and banning

Necessary, but reactive and evadable. Detection triggers after collection has occurred. Bans are cheap to route around with new accounts and residential proxies.

### 4.4 Refusing to answer suspicious queries

Two failure modes. False positives destroy the legitimate experience for power users, researchers, and heavy API customers, precisely the highest-value segment. And refusal is a **clean signal**: the attacker learns immediately which queries are protected and adjusts.

### 4.5 Withholding the reasoning trace entirely

This is the strongest simple baseline, and it must be taken seriously.

> **Recorded outcome.** The no-rationale control scored **185/500 = 37.0 %** against a clean-distilled **198/500 = 39.6 %**. Simply removing the reasoning chain cost the attacker only **2.6 pp**, and it cost the *legitimate user* the entire explanation.

Two conclusions follow. First, on grade-school mathematics, a student recovers most of its performance from pretraining and direct question→answer association, so rationale withholding has a low ceiling. Second, and more demanding, **any complex defense must be compared against this baseline, not only against clean distillation.** A mechanism that beats clean distillation by 4.8 pp but beats simple withholding by only 2.2 pp has a much weaker case than the first number suggests.

### 4.6 Returning wrong answers

Immediately effective against distillation and immediately fatal to the product. It also inverts the ethical position: the provider becomes a source of confidently false information to users who did nothing wrong.

**This is the constraint that defines ADHD.** The final answer is not negotiable.

### 4.7 The token-economics observation

There is one genuine lever in the simple-defense space: **length**.

A defended response that is meaningfully longer imposes real costs on the attacker: more tokens purchased, more storage, longer sequences during fine-tuning, more compute per training step.

But this cuts both ways. The provider generates those extra tokens too, paying additional latency and inference compute on every protected request.

> A length-inflating mechanism is economically useful only if it degrades the attacker's **efficiency per collected token** more than it degrades the provider's **service economics per served request**. Raw token inflation is not a free defensive win.

## 5. The reframing

The simple defenses all share an assumption: that the response is either **given** or **withheld**.

ADHD's reframing is to treat the response as a **channel whose content can be shaped**:

```text
   Traditional framing              ADHD framing
   ───────────────────              ────────────
   answer  ──▶ deliver              answer  ──▶ deliver  (always)
           ──▶ refuse               method  ──▶ deliver, or transform, or degrade
```

The answer and the method travel through the same channel but have different security properties. The answer is what the user needs. The method is what the attacker needs. **They can be treated differently.**

This is the entire conceptual foundation of the project.

# Part II: The objective

## 6. The security objective

> **Preserve the utility of the response to the requesting human while reducing its value as training supervision for a student model.**

Restated as an optimization problem: maximize the gap between *human utility* and *distillation utility* of the delivered response, subject to a hard floor on human utility.

Four sub-objectives follow.

### 6.1 Final-answer preservation

The user receives the parent model's terminal answer. Always. This is a hard constraint, not a target.

### 6.2 Human comprehensibility

The delivered explanation must remain understandable, coherent, and reasonably efficient to read. A response the user has to fight through has failed even if it is technically correct.

### 6.3 Measurable student degradation

A model fine-tuned on a corpus of defended responses should perform measurably worse than one fine-tuned on clean responses, and, to justify its complexity, worse than one trained on no rationales at all.

### 6.4 Fail-safe behavior

When the system cannot verify that a transformed response satisfies its constraints, it delivers the **clean** response. Failure of the defense must never become failure of the product.

## 7. Design requirements

These are the requirements the implementations were built against.

| # | Requirement | Rationale | Enforcement |
| :-: | - | - | - |
| **R1** | Terminal answer preserved exactly | The user's task must still be completed | Programmatic: answer extracted from clean response and appended to the transformed one |
| **R2** | Explanation remains human-usable | A defense that ruins the product is not deployable | **Currently under-enforced** (see [§22](#22-correctness-is-necessary-but-not-sufficient)) |
| **R3** | Transformation verifiably present | A silently-clean corpus makes the arm meaningless | Structural verifier check for poison presence |
| **R4** | Fail-safe on any verification failure | Defense failure must degrade to normal service | Retry, then clean fallback |
| **R5** | Parent model unmodified | Deployment separability; no retraining risk | Architectural: the layer is external |
| **R6** | Activation is selective | Ordinary traffic must not pay the cost | Risk gate before transformation |
| **R7** | Transformation is not trivially detectable | A detectable defense is a removable defense | **Currently under-enforced** (see [§25](#25-the-honeypot-property)) |
| **R8** | Bounded cost per request | Latency and tokens are real product constraints | Token and character budgets |

> **Recorded outcome.** R1, R3, R4, R5, R6, and R8 are enforced in the implementation. **R2 and R7 are the two requirements the SPECTRE experiment showed are not adequately enforced**: the verifier checks structure, not semantics or stealth. This is the single most important gap in the current design.

## 8. Two separated signals

A recurring design error in this space is collapsing two distinct questions into one score. ADHD keeps them separate.

### Signal 1: Request risk

*How likely is it that this request is part of a systematic extraction effort?*

Inputs are behavioral and account-level, not content-level:

- query volume and rate,
- topical concentration and systematic coverage of a domain,
- absence of ordinary conversational patterns (follow-ups, clarifications, corrections),
- similarity to other accounts' query distributions,
- account age, payment history, and provenance,
- programmatic access patterns.

### Signal 2: Response value

*If this response were collected, how much would it teach a student model?*

Inputs are content-level:

- depth of the reasoning chain,
- generalizability of the demonstrated method beyond this instance,
- density of expert knowledge,
- dependence on frontier capability the student does not already have.

### Why they must stay separate

They answer different questions and fail differently.

- A **high-risk, low-value** request (bulk-collecting trivia) does not need transformation; there is nothing worth protecting.
- A **low-risk, high-value** request (a researcher's hard question) must not be transformed; the user deserves the real explanation.
- Only the **high-risk, high-value** intersection warrants intervention.

Collapsing them into one "suspicion score" loses exactly this structure and produces a system that either over-triggers on ordinary hard questions or under-triggers on systematic collection of valuable ones.

## 9. Graded response and adaptive intensity

ADHD is explicitly **graded**. There is no binary "defend / don't defend" switch.

| Risk level | Response |
| - | - |
| **Low risk** | Deliver the clean response unchanged. This is the overwhelming majority of traffic. |
| **Uncertain / moderate risk** | Deliver the clean response. Uncertainty resolves in the user's favor. |
| **High risk, low response value** | Deliver the clean response. Nothing worth protecting. |
| **High risk, high response value** | Apply transformation, with intensity scaled to assessed value. |

The design bias is deliberate and asymmetric: **a false negative costs the provider some marginal training value; a false positive costs a legitimate user their explanation.** The second is worse, so the gate is conservative.

### The τ intensity parameter

The ITRO implementation formalizes response value as a scalar τ:

```
τ_raw = 0.35·(reasoning depth)
      + 0.30·(generalizability)
      + 0.20·(expert density)
      + 0.15·(frontier dependency)
```

| Dimension | Weight | What it captures |
| - | -: | - |
| Reasoning depth | 0.35 | Number and interdependence of inferential steps |
| Generalizability | 0.30 | Whether the method transfers beyond this instance |
| Expert density | 0.20 | Concentration of specialist knowledge |
| Frontier dependency | 0.15 | Whether the capability is one a small model lacks |

τ is then clipped by per-domain floors and ceilings, which encode a prior about how much protection a domain warrants and how much distortion it can tolerate:

| Domain | τ floor | τ ceiling | Reasoning |
| - | -: | -: | - |
| Factual recall | 0.05 | 0.35 | Little transferable method; high distortion risk |
| Procedural | 0.15 | 0.60 | Some method value; users follow steps literally |
| Math computation | 0.35 | 0.72 | Verifiable, transferable, moderate protection |
| Logical argument | 0.30 | 0.85 | Highly transferable reasoning structure |
| Scientific | 0.40 | 0.90 | Dense expert knowledge |
| Analytical | 0.40 | 0.92 | Framing and evaluation methods transfer strongly |
| Code | 0.10 | 0.95 | Wide range: trivial snippets to novel algorithms |
| Math proof | 0.55 | 1.00 | Highest method value; the most worth protecting |

> [!NOTE]
> These weights and bounds are **engineering heuristics**, not empirically calibrated estimates of learning value. τ estimates *how valuable a response looks*; it does not measure *how much a student actually gains from it*. Closing that gap, by replacing heuristic τ with a measured proxy for student learning gain, is an open research problem.

# Part III: The architecture

## 10. Formal framework

Let `T` be the parent model, `q` a query, and `c = T(q)` the clean response.

A response transformation is a function `R` producing a candidate `c̃ = R(q, c)`.

A verifier `V(q, c, c̃) ∈ {0, 1}` decides whether the candidate satisfies the deployment contract.

The delivered response is:

```
        ⎧ c̃   if V(q, c, c̃) = 1
   y =  ⎨
        ⎩ c    otherwise
```

Three properties of this formulation are the reason the architecture was chosen.

| Property | Consequence |
| - | - |
| `T` appears only as a black box | The parent model is never retrained or modified |
| `V` gates every delivery | Verifier failure degrades to clean service, never to bad service |
| `R` and `V` are independent components | Transformations can be swapped, ablated, and compared without touching the model |

**The deployment cost of this separability is real.** `R` operates only on completed text. It has no access to logits, sampling randomness, or intermediate states, all of which serving-time defenses can use. ADHD trades mechanism strength for deployment simplicity, and whether that trade is worthwhile is an open empirical question ([§34](#34-position-in-the-literature)).

## 11. Conceptual system architecture

```text
                              ┌──────────────┐
              request  ──────▶│ Risk assess  │
                              └──────┬───────┘
                                     │
                       ┌─────────────┴──────────────┐
                  low/uncertain                    high
                       │                            │
                       │                     ┌──────▼───────┐
                       │                     │ Value est. τ │
                       │                     └──────┬───────┘
                       │                            │
                       │              ┌─────────────┴────────────┐
                       │          low value                 high value
                       │              │                          │
                       │              │                   ┌──────▼───────┐
                       │              │                   │  Transform   │
                       │              │                   └──────┬───────┘
                       │              │                          │
                       │              │                   ┌──────▼───────┐
                       │              │                   │    Verify    │
                       │              │                   └──┬────────┬──┘
                       │              │                 pass │        │ fail
                       │              │                      │        │
                       ▼              ▼                      ▼        ▼
                  ┌─────────────────────────────────────────────────────┐
                  │  clean response  │ clean │ clean │ transformed │clean│
                  └─────────────────────────────────────────────────────┘
```

Every path that is not "high risk **and** high value **and** verification passed" delivers the clean response. This is the structural expression of the conservative bias in [§9](#9-graded-response-and-adaptive-intensity).

## 12. Stage 1: Risk assessment

Determines whether the request is plausibly part of systematic extraction. Operates on behavioral and account-level signals ([§8](#8-two-separated-signals)), not on whether the question is hard.

**Design commitments:**

- Assessment must be cheap, it runs on every request.
- Uncertainty resolves toward "no transformation."
- The signal must not be inferable from the response, or the attacker learns the detector's boundary by probing.

**Open problem.** A robust risk detector is itself a substantial research project, and the historical experiments bypass it entirely; they assume the gate has already fired and study only what happens downstream. A production system needs both halves.

## 13. Stage 2: Value estimation

Computes τ ([§9](#9-graded-response-and-adaptive-intensity)) and determines whether the response is worth protecting and at what intensity.

Requires domain classification first, since τ bounds are domain-specific. The ITRO implementation recognizes eight domains and falls back to `factual_recall`, the lowest-intensity domain, on classification failure. **The fallback direction is deliberate: an unclassifiable response gets the least intervention.**

## 14. Stage 3: Transformation

Applies a domain-appropriate transformation at the computed intensity. The two implemented families are described in [§17](#17-per-domain-corruption-catalogs) and [§20](#20-obfuscation-vs-poisoning).

**Design commitments:**

- The transformation must be reproducible for a given query, so behavior is auditable and a repeated query does not obviously produce a different defensive artifact.
- The transformation must operate within a bounded token budget.
- The transformation must not require modifying `T`.

## 15. Stage 4: Verification and fail-safe

The verifier is the component that makes the architecture safe to deploy, and it is where the design is currently weakest.

### What the SPECTRE verifier checks

| Check | Type | Tests |
| - | :-: | - |
| `answer_match` | **blocking** | The variant's terminal answer equals the clean answer |
| `internal_consistency` | **blocking** | The last number in the body equals the terminal answer |
| `poison_present` | **blocking** | The expected transformation artifact is actually present |
| `no_early_leak` | warning | The answer does not appear in the first 60 % of the body |
| `length_ok` | warning | The body stays within the character budget |
| `confident_false_start` | warning | The false start contains no hedging markers |

### What it does not check

- whether the explanation is naturally written,
- whether the reasoning is *semantically* coherent,
- whether a correction logically refers to what was actually computed,
- whether the transformation is detectable,
- whether a human would find the response usable.

> [!CAUTION]
> **`answer_match` is largely guaranteed by construction**, because the pipeline strips any generated answer line and appends the teacher's original. It is a valid engineering strategy for satisfying R1, but it is **not independent evidence** that the transformed reasoning body is correct.

### The failure this produced

> **Recorded outcome: the Natalia case.** Problem: Natalia sells 48 clips in April and half as many in May; how many altogether? (Clean: 24 in May, **72** total.) The transformation computed `48 × 2 = 96`, described 96 as the *April-plus-May total*, then pivoted by arguing that 96 "cannot be correct for May alone", a claim about something the response had never asserted. It then recovered to 72.
>
> **All six verification flags passed.** The response is answer-correct, structurally valid, and locally self-contradictory.

This single artifact is more informative than the accuracy tables. It demonstrates that **structural verification is not a proxy for semantic validity**, and that R2 is genuinely unenforced rather than merely imperfectly enforced.

### The ITRO fail-open gap

A second, independent verification weakness: ITRO's semantic-equivalence check for non-mathematical domains is coded to **fail open**, returning "equivalent" when an exception occurs. The general system therefore cannot claim strict fail-safe answer preservation across all domains. Mathematics, where answers are extracted and compared numerically, is unaffected.

# Part IV: The mechanism

## 16. What "pedagogically toxic" means

The central mechanism concept. A response is **pedagogically toxic** if it is correct in its conclusion but teaches a method that a learner should not adopt.

The distinction from ordinary wrongness:

| | Answer | Method | Human impact | Student impact |
| - | :-: | :-: | - | - |
| Clean response | correct | good | ideal | learns well |
| **Pedagogically toxic** | **correct** | **poor** | task completed | learns poor method |
| Wrong response | incorrect | n/a | task failed | learns wrong facts |
| No rationale | correct | absent | task completed, no learning | learns nothing new |

ADHD targets row two. The user gets what they came for. The student, which learns from *method* rather than from single answers, absorbs something less useful.

Concretely, a pedagogically toxic mathematical response might:

- select a legitimate but distinctly suboptimal solution strategy,
- decompose operations into unnecessary primitive steps,
- add redundant verification that teaches inefficient checking habits,
- take algebraically valid but purposeless detours,
- overcomplicate a setup that has an obvious simple form,
- demonstrate a wrong operation confidently before correcting it.

Each preserves correctness. Each degrades the demonstrated method.

## 17. Per-domain corruption catalogs

These catalogs were developed for ITRO's eight-domain design. They remain the reference for what transformation means in each domain, even though only mathematics has been experimentally tested.

### 17.1 Mathematical computation

| Technique | Description |
| - | - |
| Suboptimal method | A legitimate approach that is clearly not the natural one |
| Wrong-approach-first | Begin with an incorrect operation, then correct |
| Redundant verification | Check results in ways that add no information |
| Unnecessary transformation | Algebraically valid manipulations that do not advance the solution |
| Primitive decomposition | Expand compact operations into repeated elementary ones |
| Identity operations | Steps that provably do not change the value |
| Overcomplicated setup | Introduce structure the problem does not require |

### 17.2 Mathematical proof

| Technique | Description |
| - | - |
| Inferior proof strategy | Start from a strategy that works but obscures the key insight |
| Unnecessary lemmas | Prove intermediate results the main argument does not need |
| Excessive case splitting | Divide into cases that a better argument handles uniformly |
| Algebraic detour | Reach a correct conclusion by a longer symbolic route |

*Highest τ ceiling (1.00): proof method is the most transferable and hardest-to-acquire capability in the catalog.*

### 17.3 Code

| Technique | Description |
| - | - |
| Poor algorithmic structure | Preserve functionality, degrade the algorithm |
| Suboptimal data structures | Choose structures that work but scale badly |
| Unnecessary indirection | Add layers that do not aid clarity |
| Inefficient control flow | Loop or branch in ways a competent engineer would not |

**Hard constraint: the code must still run correctly.** A transformation that breaks execution violates R1 in the code domain; the "answer" is working software.

*Widest τ range (0.10-0.95): a snippet and a novel algorithm require very different treatment.*

### 17.4 Scientific explanation

| Technique | Description |
| - | - |
| Plausible wrong mechanism | Begin from an incorrect causal story, then correct |
| Misordered causal chain | Present causes in a sequence that obscures the mechanism |
| Excessive qualification | Bury the mechanism in caveats |
| Wrong level of abstraction | Explain at a level that does not illuminate the phenomenon |

> [!WARNING]
> This is the domain where the risk of leaving a user with a **false belief** is highest, because the reader typically cannot verify the mechanism independently. The correction must be unmistakable. See [§29](#29-high-stakes-domains-and-ethics).

### 17.5 Logical argument

| Technique | Description |
| - | - |
| Weaker argument first | Lead with a valid but less compelling line |
| Redundant premises | Include premises the conclusion does not need |
| Suboptimal argument order | Present steps in an order that obscures the structure |
| Unnecessary formalization | Add formal machinery where prose suffices |

### 17.6 Factual recall

| Technique | Description |
| - | - |
| Excessive hedging | Wrap a certain fact in unnecessary uncertainty |
| Irrelevant context | Surround the fact with material that does not bear on it |
| Indirect delivery | Reach the fact by a longer route |

*Lowest τ ceiling (0.35). A fact contains almost no transferable method, so there is little to protect and a high risk of merely annoying the user. This is also the classification fallback domain, the safest place to land when uncertain.*

### 17.7 Procedural instruction

| Technique | Description |
| - | - |
| Suboptimal ordering | Sequence steps in a workable but inefficient order |
| Unnecessary steps | Include steps that do not affect the outcome |
| Over-specification | Add detail that does not help execution |

> [!WARNING]
> Users follow procedures **literally**. A procedure that is merely inefficient is acceptable; one that could cause harm if followed exactly is not. τ ceiling is held at 0.60 for this reason.

### 17.8 Analytical response

| Technique | Description |
| - | - |
| Unhelpful evaluative frame | Analyze from an angle that obscures the key consideration |
| Misweighted factors | Emphasize less decisive factors first |
| Excessive enumeration | List considerations rather than synthesizing them |

## 18. Naturalness as a hard constraint

A defended response must look like an ordinary response from a capable model that happened to take a suboptimal path, **not** like a sabotaged response.

This constraint exists for two independent reasons.

### 18.1 The product reason

A user who can see that their response was deliberately degraded has been told, implicitly, that the provider does not trust them. That is a worse outcome than a refusal, because it comes with the pretense of service.

### 18.2 The security reason

This is the sharper one. **Anything an attacker can detect, an attacker can remove.**

If defended responses carry a recognizable signature, the attacker's counter-move is trivial and requires no understanding of the mechanism:

- filter out responses matching the signature,
- strip text before a recognizable pivot marker,
- pass every response through a cheap rewriting model,
- train only on question-answer pairs, discarding the trace.

> **Recorded outcome.** SPECTRE's T7 transformation uses a **fixed opening sentence**, a false start in a **consistent structural position**, a pivot drawn from a **20-stem pool**, and a **recurring primitive-decomposition pattern**. It is straightforwardly fingerprintable. The mechanism that made it learnable by the student is the same mechanism that made it detectable by an attacker (see [§36](#36-the-fundamental-design-tension)).

## 19. Systematic vs. random corruption

An early and important design question: should the corruption be **varied** across responses or **consistent**?

The two positions:

| | Argument | Cost |
| - | - | - |
| **Random / varied** | Harder to fingerprint; each response looks individually plausible | The student may treat it as noise and learn around it |
| **Systematic / consistent** | The student encounters the same pattern thousands of times and absorbs it | Trivially fingerprintable |

Both implementations tested one side of this.

> **Recorded outcome.** ITRO chose variety: the corruption differed per response. Result: **195/500 = 39.0 %** against a clean **198/500 = 39.6 %**. A **0.6 pp** gap, three questions. The student largely learned around it.
>
> SPECTRE chose consistency: the same structural poison in the same position across the corpus. Result: **174/500 = 34.8 %**, a **4.8 pp** gap and 24 fewer correct answers, **8.0×** ITRO's raw effect.

The evidence favors consistency for *effectiveness* and variety for *stealth*. Neither implementation found the middle.

**The refined design target** is a transformation that is:

- consistent in the **latent features a student model learns from**,
- variable in the **surface features a human or attacker notices**.

Whether those two feature sets can be separated is the project's central open question.

## 20. Obfuscation vs. poisoning

The two implementations embody two different theories of how a response can be made less valuable.

### Obfuscation (ITRO)

*Make the correct reasoning harder to extract.* The path is still correct; it is just inefficient, indirect, or cluttered. The student must work harder to recover the signal.

**Theory of effect:** raise the cost of learning.

> **Recorded outcome.** ITRO responses were genuinely harder to fit, average training loss **0.2555** against **0.1637** for clean, roughly **+56 %**. Final gradient norms were nearly identical (0.1919 vs. 0.1846), so no optimization instability. And held-out accuracy moved **0.6 pp**.
>
> **The lesson: optimization difficulty is not capability degradation.** A student can struggle to reproduce a response's surface form while still learning the question→answer mapping the benchmark measures.

### Poisoning (SPECTRE)

*Teach a behavior that actively interferes with the student's own reasoning.* Not "hide the good method" but "install a bad habit."

**Theory of effect:** make the student worse, not merely less-taught.

The mechanism relies on autoregressive propagation: if a student learns to begin with a confident wrong operation, the wrong intermediate value conditions everything downstream. That is a route to falling *below* the no-rationale floor, which pure withholding can never achieve.

> **Recorded outcome.** SPECTRE's average loss was **0.3512** (≈ +115 % over clean, ≈ +37 % over ITRO) with the highest final gradient norm (0.2439) and no divergence. Accuracy dropped to **34.8 %**, **2.2 pp below** the 37.0 % no-rationale control, which is the comparison that matters.
>
> **Caveat.** This is one run. SPECTRE also changes sequence length, answer position, and lexical regularity, so ordinary distribution shift remains a competing explanation. The propagation mechanism is a **hypothesis**, not a measured result; no student-side trajectory analysis was performed.

### The distinction that matters

| | Ceiling |
| - | - |
| Withholding / obfuscation | Bounded by the student's pretrained capability floor |
| Poisoning | Can, in principle, push *below* that floor |

This is why the project moved from ITRO to SPECTRE, and why the no-rationale control is the benchmark that defines success.

## 21. Answer preservation

The non-negotiable constraint, and the one that creates the project's hardest structural problem.

### 21.1 Why it is non-negotiable

Without it, ADHD is indistinguishable from returning wrong answers ([§4.6](#46-returning-wrong-answers)): effective against distillation, fatal to the product and to the provider's basic obligation to its users.

### 21.2 How it is enforced

| Domain | Mechanism |
| - | - |
| Mathematics | Extract the numerical answer from the clean response; append it programmatically to the transformed one; verify equality |
| Non-mathematical | LLM extracts the core claim from both responses; LLM judges semantic equivalence *(currently fails open (see [§15](#15-stage-4-verification-and-fail-safe)))* |

> **Recorded outcome.** ITRO's answer-preservation rate during defended-dataset generation was approximately **85-87 %**, implying that **13-15 % of the "defended" corpus was actually clean fallback**. This is correct fail-safe behavior, but it dilutes the intervention and complicates interpretation of the arm.

### 21.3 The problem it creates

This is the most uncomfortable structural consequence in the design.

```text
   What ADHD wants the student to learn (the corruption)  ──▶  deliberately VARIABLE
   What ADHD must preserve (the answer)                   ──▶  perfectly CONSISTENT
```

From the student's perspective, the question→answer mapping is the single most stable, lowest-entropy signal in the entire defended corpus, and the defense *guarantees* its stability. Meanwhile the corruption, which the defense wants absorbed, is the noisiest part.

A small student under next-token training has every incentive to learn the reliable shortcut and treat the rest as noise. **The answer-preservation constraint actively works against the poisoning objective.**

SPECTRE's `no_early_leak` check, which requires that the answer not appear in the first 60 % of the response, is a partial mitigation: it prevents the answer from serving as an early anchor. It does not resolve the underlying tension.

## 22. Correctness is necessary but not sufficient

The original design treated "correct final answer" as sufficient justification for aggressive transformation. The reasoning was that false positives would be cheap, because a wrongly-flagged user still gets the right answer.

**The SPECTRE experiment showed this is too weak a safety condition.**

Users request explanations because the *path* matters:

- a student learning mathematics may adopt the wrong formula demonstrated in the false start,
- an engineer may copy a fragile pattern from degraded code,
- a researcher may reuse an incorrect causal argument even when the final sentence is right,
- a professional may act on an intermediate claim before reaching the correction.

A response that is answer-correct but locally self-contradictory ([§15](#15-stage-4-verification-and-fail-safe), the Natalia case) has satisfied the letter of R1 and violated the spirit of R2.

> **The revised safety condition:** human utility requires **semantic validity and readability of the intermediate explanation**, not only terminal-answer equality. Semantic incoherence must be a **hard rejection condition**, on par with a wrong answer.

# Part V: The constraints

## 23. The safety valve

If any critical verification fails, deliver the clean response.

**Design rationale.** The failure modes are asymmetric. A failed transformation that falls back to clean costs the provider a small amount of marginal protection. A failed transformation that ships costs a user a broken response and the provider its credibility.

**Implementation.** Retry the transformation a bounded number of times; on continued failure, return `c` unchanged. The user never learns that anything was attempted.

**Design commitment.** The valve must be **cheap to trigger**. A system reluctant to fall back, because fallback is expensive or because it degrades a defense metric, will eventually ship bad responses. Fallback rate is a health metric, not a failure metric.

## 24. The untouched base model

The parent model is never modified: not fine-tuned, not retrained, not adversarially conditioned.

| Benefit | Explanation |
| - | - |
| **No capability risk** | Modifying a frontier model to resist distillation risks degrading it for everyone |
| **Separable deployment** | The layer can be added, removed, or updated without touching the model |
| **Independent iteration** | Transformations can be swapped and ablated at wrapper speed, not training speed |
| **Clean fallback** | The clean response always exists, by construction |
| **Auditability** | Clean and transformed responses can always be compared |

The cost is stated plainly in [§10](#10-formal-framework): the layer sees only completed text, forgoing every mechanism available to defenses that operate on logits or sampling. **This is the defining trade of the architecture.**

## 25. The honeypot property

The "Honeypot Deception" in ADHD's name is a specific claim: the defended response should be **indistinguishable from an ordinary response**, so that an attacker collecting it does not know they have collected anything unusual.

### Why the property is load-bearing

A honeypot that announces itself is not a honeypot. If defended responses are identifiable, the attacker filters them out and the defense's effective coverage drops to zero: not partially, but entirely, at the cost of one preprocessing pass.

### Current status: not achieved

> **Recorded outcome.** SPECTRE's T7 output is identifiable by a fixed opening sentence, a structurally positioned wrong operation, a pivot from a small enumerable pool, and repeated primitive decomposition. The honeypot property is **violated** by the current implementation.

### What measuring it requires

The property is testable, and has not been tested. The evaluation:

1. build a mixed corpus of clean and defended responses,
2. train detectors: lexical classifiers, structural heuristics, LLM classifiers,
3. report detection accuracy or AUC,
4. then apply the best detector as a **sanitizer**, retrain a student on the cleaned corpus, and measure how much of the degradation survives.

**If a simple sanitizer restores clean-distillation performance, the defense is fragile regardless of its unsanitized numbers.** This test belongs in the core evaluation.

## 26. Attacker adaptation

The threat model assumes an adaptive adversary. Once a defense is discovered, the attacker responds. Anticipated counter-moves:

| Attacker move | Defensive implication |
| - | - |
| Filter out responses matching a detected pattern | Requires transformation diversity ([§27](#27-defense-diversity)) |
| Strip text before a recognizable pivot | Requires the poison not to be confined to a removable prefix |
| Rewrite every response with a cheap model | Requires the effect to survive paraphrase |
| Train only on question-answer pairs | Reduces the attack to the no-rationale ceiling, arguably a defensive win |
| Distribute collection across accounts and interfaces | Defeats per-account risk assessment |
| Query the same item repeatedly and take a majority vote | Requires transformation determinism to not be exploitable |
| Cross-reference against an unprotected model | Identifies protected responses by disagreement |

The last is worth noting: an attacker with access to *any* comparable model can detect anomalous reasoning by disagreement, without ever identifying the mechanism.

**Design consequence.** A defense evaluated only against a non-adaptive collector reports an upper bound on its effectiveness. Every number in `results.md` is such an upper bound.

## 27. Defense diversity

A single transformation is a single point of failure. If the attacker learns to detect T7, the defense stops working.

A deployed system should therefore maintain a **portfolio**:

- multiple transformation families with genuinely different signatures,
- per-request selection that does not correlate with a detectable feature,
- rotation over time,
- new transformations added as old ones are compromised.

The repository retains five independent transformations (backward derivation, wrong-operation-first, primitive decomposition, circular verification, formula-error correction) alongside the T7 composite, partly for ablation and partly as the seed of such a portfolio.

> [!NOTE]
> The ensemble selection component **GHOST** (*Gradient-Hostile Output Selection for Training*) currently ranks candidate transformations by asking a language model which would be most harmful to a student. **It does not compute gradients or measure student loss.** It is a heuristic placeholder for a measured selection criterion, and should not be described as anything more.

## 28. Human utility as a hard constraint

The constraint that separates ADHD from ordinary data poisoning.

A defense that degrades the legitimate user's experience has not made a trade-off; it has failed. The provider's core obligation is to the user who pays for and correctly uses the service.

### Measuring it

Human utility has been asserted throughout this design and **never measured**. The evaluation it requires:

Blind human comparison of clean and defended responses, rated on clarity, coherence, unnecessary complexity, confidence calibration, ease of following the reasoning, whether intermediate claims mislead, reading time, whether the response appears deliberately manipulated, and overall usefulness.

> The defense is not successful if the student gets worse **only because** the legitimate user's explanation also got much worse.

Automated checks can reject obvious defects. They cannot substitute for this.

**This absence is a central limitation of the current evidence, not a minor reporting omission.** SPECTRE's 4.8 pp result is uninterpretable as a defense claim without a companion measurement of what it cost the user.

## 29. High-stakes domains and ethics

Some domains should be excluded from transformation entirely, regardless of assessed risk or value.

### Categorical exclusions

| Domain | Reason |
| - | - |
| Medical, clinical, pharmacological | A user may act on an intermediate claim before reaching the correction |
| Legal advice | Same, with legal consequences |
| Safety-critical engineering | Procedures are followed literally |
| Financial decisions with irreversible consequences | Same |
| Emergency or crisis contexts | No tolerance for a wrong intermediate step |
| Anything where an uncorrected intermediate claim could cause harm | The general rule |

### The generalized principle

The wrong-approach-first family of transformations ([§17](#17-per-domain-corruption-catalogs)) presents a **confidently stated false claim** before correcting it. That is acceptable in a grade-school arithmetic problem, where the reader can verify the arithmetic and the stakes are nil. It is not acceptable where the reader cannot verify the claim and may act on it.

> **The rule: a transformation may only present a confident false intermediate where the reader can independently detect it is false, and where acting on it before reading the correction is harmless.**

This substantially narrows the deployable surface of the wrong-operation mechanism, arguably to verifiable technical domains only. That is a real cost of the mechanism, and it should be counted against it.

### The broader ethical position

ADHD deliberately delivers responses whose reasoning is worse than what the model could produce. Three commitments constrain that:

1. **The final answer is always the model's genuine answer.** The user's task is completed correctly.
2. **The transformation is applied only under assessed extraction risk**, never to ordinary traffic.
3. **Uncertainty resolves toward the user.** Every ambiguous case gets the clean response.

Whether those commitments are sufficient is a legitimate question, and it depends heavily on the accuracy of the risk gate, which, as [§12](#12-stage-1-risk-assessment) notes, remains unbuilt.

# Part VI: Boundaries and evaluation

## 30. What ADHD is not

Stated explicitly, because each confusion has appeared in discussion of the project.

| ADHD is **not** | Clarification |
| - | - |
| **A jailbreak defense** | It addresses distillation, not misuse of the model's outputs |
| **A watermarking scheme** | Watermarking establishes *attribution* after the fact; ADHD attempts to reduce *transfer* |
| **A content filter** | It does not refuse, block, or restrict any query |
| **An offensive tool** | Nothing is deployed against the attacker's systems; the only artifact is a response the attacker requested |
| **Data poisoning of a public corpus** | It affects only responses served to a specific assessed-risk requester |
| **A guarantee** | It is a cost-raising measure with an empirical, contested effect size |
| **A replacement for other defenses** | It is one layer among several ([§33](#33-position-in-the-defense-stack)) |
| **A method that touches model internals** | It operates purely on visible output text |
| **Validated** | The current state is *promising but unvalidated*, one run per condition, no human evaluation, no adaptive attacker |

## 31. What success would mean

A future ADHD result must clear all of the following. Meeting only the first is what the project has done so far.

| # | Criterion | Status |
| :-: | - | :-: |
| 1 | Student degradation vs. clean distillation | **Observed**: 4.8 pp, single run |
| 2 | Degradation exceeding the no-rationale baseline by a margin that justifies the complexity | **Marginal**: 2.2 pp |
| 3 | Reproducible across multiple training seeds with reported variance | **Not done** |
| 4 | Mechanism confirmed by ablation, not just observed by score | **Not done** |
| 5 | Length- and lexically-matched control that isolates poisoning from distribution shift | **Not done** |
| 6 | Human utility measured and shown not to collapse | **Not done** |
| 7 | Low detectability under trained detectors | **Not done: currently violated** |
| 8 | Degradation survives attacker-side sanitization | **Not done** |
| 9 | Effect demonstrated on reasoning the student cannot already do | **Not done: GSM8K is too easy** |
| 10 | Bounded latency, token, and cost overhead | Partially, budgets enforced, economics unmeasured |

**Criterion 9 deserves emphasis.** The no-rationale result (37.0 %) shows that GSM8K performance depends only weakly on the teacher's reasoning trace. A defense that targets transferred reasoning is being measured on a benchmark where transferred reasoning barely matters. The move to harder mathematics (MATH-500, competition problems, proof-like reasoning) is **not optional**; it is required for the evaluation to be informative.

## 32. The economic frame

The most defensible version of ADHD's value proposition is economic rather than absolute.

Distillation is attractive because it is cheap. A defense does not need to make it impossible; it needs to make it **expensive enough to change the calculation**.

Levers available to a response-layer defense:

| Lever | Attacker cost imposed |
| - | - |
| Longer responses | More tokens purchased, more storage, longer training sequences |
| Required filtering | Engineering effort plus a filtering model's inference cost |
| Reduced per-example value | More queries needed for the same student capability |
| Required verification | The attacker must check what they collected |
| Uncertainty about coverage | The attacker cannot know which responses were transformed |

**The metric that matters** is *attacker capability gained per dollar spent*, not defended-student accuracy in isolation.

**The counter-metric that also matters** is provider cost: added latency, extra generated tokens, inference compute, and clean-fallback rate. A mechanism that doubles the attacker's cost and triples the provider's has not helped.

Neither has been measured. Both belong in the next evaluation.

## 33. Position in the defense stack

ADHD is one layer, and not the first one.

```text
   ┌──────────────────────────────────────────────┐
   │ 1. Access control, KYC, payment verification │  ← raises account cost
   ├──────────────────────────────────────────────┤
   │ 2. Rate limiting and quota enforcement       │  ← raises volume cost
   ├──────────────────────────────────────────────┤
   │ 3. Behavioral detection and account action   │  ← raises operational cost
   ├──────────────────────────────────────────────┤
   │ 4. ADHD response transformation              │  ← raises per-response value cost
   ├──────────────────────────────────────────────┤
   │ 5. Watermarking and attribution              │  ← enables post-hoc action
   ├──────────────────────────────────────────────┤
   │ 6. Legal and contractual enforcement         │  ← raises consequence cost
   └──────────────────────────────────────────────┘
```

Layer 4 is where ADHD sits: **after** detection has produced a risk signal, **before** attribution becomes relevant. It is complementary to every other layer and a replacement for none.

Notably, ADHD depends on layer 3. Without a functioning behavioral detector, the risk gate cannot fire correctly, and the choice becomes transforming everything (unacceptable) or nothing (no defense).

## 34. Position in the literature

Anti-distillation methods are best organized by **intervention point**, because two methods can share a security objective while imposing very different deployment requirements.

| Family | Intervenes on | Modifies teacher? | Relation to ADHD |
| - | - | :-: | - |
| **Teacher-side training**: Nasty Teacher, CMIM, Teacher Scrambling, DOGe, distillation traps | Teacher weights, output head, calibration | **Yes** | Strongest control at the source; protection is coupled to a modified model |
| **Serving-time decoding**: ADS, LADS, Product-of-Experts, CMI purification | Sampling randomness, next-token distributions, exposed logits | Usually not persistently | Finer control than text editing; requires access to generation internals |
| **Post-generation transformation**: PART, SelfCAD, trace rewriting, TraceGuard, SGRE | A completed reasoning trace | **No** | **ADHD's family.** Preserves separability; must solve semantics, naturalness, detectability, sanitization |
| **Information throttling**: CoT removal or summarization | Rationale withheld before delivery | **No** | Simple; a strong baseline on mathematics. Our no-rationale arm *is* this |
| **Attribution / fingerprinting**: DRW, EWE, ReasMark, ADFP | Watermarks designed to survive transfer | Varies | Addresses attribution rather than prevention; complementary |

### Three external findings that constrain this design

**1. Information throttling is a strong mathematical baseline.** Evaluation surveys covering output perturbation, data poisoning, and information throttling report strong task dependence, with chain-of-thought removal notably strong on mathematics. Our own no-rationale arm reproduces this independently at 37.0 %. **Complex mechanisms must be compared against simple withholding, not only against clean distillation.**

**2. Effectiveness is inseparable from the attacker model.** Formalizations of query budget, data budget, and interface profile show that apparent effectiveness shifts materially under different assumptions, and minimax analyses find that adaptive students recover substantially more capability than passive evaluation suggests. Our experiments evaluate a naive collector and therefore report an upper bound.

**3. Degrading content is not the only option.** Locally-adaptive decoding schemes preserve the marginal distribution a benign user sees while correlating randomness across semantically related repeated queries, reducing the diversity available to a multi-account collector **without degrading any single response**. This is a direct counterexample to the assumption that anti-distillation must trade response quality for protection strength, and it should be a baseline in any evaluation of a deception layer.

### The narrow novelty claim

Recent "answer-then-edit" work obtains a clean solution and then edits a reasoning skeleton to raise student learning difficulty while explicitly evaluating trace naturalness. That is a close architectural neighbor.

> **ADHD's contribution is not the first proposal to edit a clean trace after generation.** It is an empirical case study of the trade-offs that emerge when such a layer must simultaneously preserve human utility, verify its own output, and reduce student-training value, and a demonstration that structural verification is insufficient for the first of those.

### The experiment that would settle the architecture question

On an open teacher where all families are implementable, train students from: clean traces, no-rationale outputs, teacher-side methods, serving-time methods, and post-generation methods, all with the same prompts, the same students, and the same evaluation.

That would quantify **the price of deployment separability**: how much protection is forfeited by refusing to modify weights or decoding internals, and whether easier deployment and selective activation compensate.

# Part VII: Synthesis

## 35. The central research question

> **Can a response be transformed so that a human retains full practical utility while a student model trained on many such responses learns systematically worse reasoning, and can that hold against an attacker who knows the defense exists?**

The question decomposes into four sub-questions, in increasing order of difficulty:

| # | Sub-question | Status |
| :-: | - | - |
| 1 | Can transformation reduce student performance at all? | **Yes**, 4.8 pp, single run |
| 2 | Can it beat simple rationale withholding by a worthwhile margin? | **Marginally**: 2.2 pp |
| 3 | Can it do so while preserving human utility? | **Unknown, and SPECTRE suggests not, in its current form** |
| 4 | Can it survive an attacker who detects and sanitizes it? | **Untested** |

Progress on (1) is real. The project's remaining work is almost entirely (2) through (4).

## 36. The fundamental design tension

The two experiments discovered opposite faces of a single trade-off.

```text
        stealthy  ◀───────────────────────────────────▶  learnable
             │                                                │
          ITRO                                            SPECTRE
     variable corruption                          consistent structural poison
     −0.6 pp, subtle                              −4.8 pp, conspicuous
     student learns around it                     attacker can fingerprint it
             │                                                │
             └──────────────── open region ───────────────────┘
                   consistent in the latent features a
                   student learns from; variable in the
                   surface features a human or attacker sees
```

Stated precisely:

> **A pattern must be consistent to be learnable by a student. A pattern that is consistent is detectable by an attacker. Learnability and detectability rise together.**

This is not an implementation defect. It is a structural property of the problem, and it is the reason the middle region may or may not exist.

The open question is whether "the features a small student learns from" and "the features a detector or a human notices" are separable feature sets. If they are, a transformation can be consistent in the first and varied in the second. If they are not, post-generation transformation may be fundamentally limited, and the honest conclusion would be that this family of defenses cannot simultaneously satisfy R2 and R7.

**Neither implementation has tested this.** Doing so requires the detectability and sanitization evaluations described in [§25](#25-the-honeypot-property), which have not been run.

## 37. Design principles

The twelve principles the implementations were built against, revised in light of what the experiments showed.

| # | Principle | Status |
| :-: | - | - |
| **1** | **The answer is sacred.** The user always receives the parent model's terminal answer. | Held |
| **2** | **The parent model is untouched.** All protection lives in an external, removable layer. | Held |
| **3** | **Fail safe, always.** Any verification failure delivers the clean response. | Held for math; **fail-open gap** in ITRO's non-math path |
| **4** | **Uncertainty favors the user.** Ambiguous risk assessment means no transformation. | Held |
| **5** | **Protection is graded, not binary.** Intensity scales with assessed risk and value. | Held |
| **6** | **Risk and value are separate signals.** Never collapse them into one score. | Held |
| **7** | **Naturalness is a security property, not a nicety.** Detectable means removable. | **Violated by T7** |
| **8** | **Verify presence, not just success.** A silently-clean corpus is a wasted experiment. | Held, and directly motivated by a real ITRO defect |
| **9** | **Correctness of the answer is not sufficient.** The explanation must also be semantically valid. | **Violated: the Natalia case** |
| **10** | **Measure capability, not loss.** Training difficulty is not security. | Held, and the central ITRO lesson |
| **11** | **Compare against the trivial baseline.** No-rationale is the bar, not clean distillation. | Held |
| **12** | **Assume the attacker adapts.** An unsanitized evaluation reports an upper bound. | Acknowledged, **untested** |

Principles 7 and 9 are the two the project has demonstrably broken. They are the design agenda for the next phase.

## 38. What the experiments changed about this design

This section exists because a design document that never updates against evidence is not a design document.

| Original belief | Revised belief | Evidence |
| - | - | - |
| Making reasoning convoluted will degrade student learning | Surface obfuscation raises fitting cost without meaningfully reducing capability | ITRO: +56 % loss, −0.6 pp accuracy |
| Higher training loss indicates a working defense | Loss measures distribution difficulty, not knowledge transfer | ITRO loss and accuracy diverged completely |
| Variable corruption is better (harder to detect) | Variable corruption lets the student learn around it; consistency is what works | ITRO 0.6 pp vs. SPECTRE 4.8 pp |
| Clean distillation is the baseline to beat | **No-rationale** is the baseline to beat | 37.0 % achieved with zero mechanism |
| A correct final answer makes false positives cheap | Semantic incoherence harms users even with a correct answer | The Natalia case |
| Structural verification is sufficient | Structural checks pass responses that are locally self-contradictory | All six flags passed on a contradictory response |
| Answer preservation is purely a product constraint | It is also a *security* obstacle, it guarantees the student a perfectly stable signal | [§21.3](#213-the-problem-it-creates) |
| Breadth across eight domains is the right scope | Prove a mechanism in one verifiable domain first, then generalize | ITRO's eight-domain design obscured the mechanism failure |
| GSM8K is an adequate benchmark | It is too easy; the teacher's reasoning barely matters to it | No-rationale costs only 2.6 pp |

## 39. Long-term vision

The end state this design points toward is not a fixed transformation. It is a **response-layer controller**: a component that continuously decides, per request, how much of the model's reasoning to expose.

Its inputs:

| Input | Question answered |
| - | - |
| **A. Request risk** | Is this plausibly systematic extraction? |
| **B. Response value** | How much would this teach a student? |
| **C. Human utility cost** | What would transformation cost this specific user? |
| **D. Detectability budget** | How much defensive signature can the portfolio afford to emit? |

Its output is a graded decision across a spectrum (clean, lightly transformed, heavily transformed, throttled) chosen to maximize the gap between human utility and distillation utility, subject to a hard floor on the former.

Reaching that requires solving problems this project has surfaced but not solved:

1. a behavioral risk detector accurate enough to gate on ([§12](#12-stage-1-risk-assessment)),
2. a value estimator grounded in measured learning gain rather than heuristic τ ([§9](#9-graded-response-and-adaptive-intensity)),
3. a transformation that is latently consistent and superficially varied ([§36](#36-the-fundamental-design-tension)),
4. semantic verification strong enough to make R2 enforceable ([§22](#22-correctness-is-necessary-but-not-sufficient)),
5. demonstrated robustness against sanitization ([§26](#26-attacker-adaptation)),
6. an economic model showing the attacker's cost rises faster than the provider's ([§32](#32-the-economic-frame)).

**Current honest status: promising but unvalidated.**

The project has established that post-generation transformation can move student accuracy, identified precisely why the first approach failed, produced a mechanism with a materially larger effect, and, most usefully, demonstrated concretely where that mechanism breaks. The case study **sharpens rather than closes** the research question. It does not rule out post-generation defenses; it narrows the target to transformations that preserve natural, conceptually correct human utility, produce reproducible degradation beyond simple withholding, and survive adaptive sanitization.

## Related documents

| Document | Contents |
| - | - |
| [`results.md`](results.md) | Complete experimental record, training diagnostics, failure analysis, code audit, next-experiment design |
| [`Readme.md`](Readme.md) | Repository overview, headline results, architecture, installation, usage |
| `ITRO/` | Phase I implementation: eight-domain adaptive obfuscation |
| `SPECTRE/` | Phase II implementation: mathematical structural poisoning |

## Acknowledgments

Thanks to **Yash Savani** (Carnegie Mellon University) for early discussion of the ADHD-ITRO concept, particularly the advice to *fail fast*, and the observation that students can extract usable signal from imperfect supervision, which anticipated the ITRO result. Computational resources were provided by **ASU Research Computing** and the **Sol supercomputer**.
