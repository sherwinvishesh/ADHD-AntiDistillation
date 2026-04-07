# ITRO Local
### Inference-Time Reasoning Obfuscator  (Phase 1.2)

Part of the **ADHD (Adaptive Defense via Honeypot Deception)** research system.

## What This Is

**ITRO_Local** is Phase 1.2 of the ITRO pipeline — the same logic as [ITRO_API](../ITRO_API/Readme.md), but running entirely on a local GPU via **Qwen2.5-7B-Instruct**. No external API calls. No API keys. All inference runs on-device.

The core defense is identical: when an adversary queries the system to harvest (question, response) training pairs, they receive responses with correct answers but deliberately corrupted reasoning paths. A student model trained on these responses internalizes broken thinking habits and fails to generalize.

**What changed from Phase 1.1 → 1.2:**
- `anthropic_provider.py` / `gemini_provider.py` → `qwen_provider.py`
- No provider selection menu — Qwen is the only model
- Model loads into GPU memory at startup (~20-30 seconds)
- `.env` stores `QWEN_MODEL_PATH` instead of API keys
- Two inference configs: `GENERATION_CONFIG` for obfuscation, `STRICT_GENERATION_CONFIG` for structured outputs (domain/τ scorer)
- No `-p` flag in CLI mode — provider is always Qwen

Everything else — domain detection, τ scoring, ITRO templates, correctness checker — is identical to Phase 1.1 and ported unchanged.


## System Requirements

| Requirement | Details |
|---|---|
| GPU | CUDA-capable GPU required |
| VRAM (float16) | ~14 GB minimum (e.g. A100, A40, 3090) |
| VRAM (4-bit) | ~5 GB minimum (e.g. T4, smaller GPUs) |
| Python | 3.9+ |
| CUDA toolkit | Compatible with your PyTorch build |

On **Sol (ASU HPC)**: request a GPU node before running. The model was developed and tested on an A100.

Check CUDA availability:
```bash
python -c "import torch; print(torch.cuda.is_available())"
```



## How The Pipeline Works

Every query runs through five sequential stages, all on-device:

```
Question
    │
    ▼
[1] Real Response
    Qwen answers normally, completely unmodified.
    │
    ▼
[2] Domain Detection
    Qwen classifies the (query, response) pair into one of 8 domains.
    Hard rules fire first for near-certain cases (code blocks, math symbols).
    Qwen classifier handles everything ambiguous.
    │
    ▼
[3] Tau (τ) Computation
    Qwen scores the query on 4 dimensions of pedagogical distillation value.
    Weighted combination produces τ ∈ [0.0, 1.0].
    Domain-specific floor/ceiling bounds clip the score.
    │
    ▼
[4] ITRO Obfuscation
    Domain-specific prompt with named transformation toolkit.
    τ-calibrated application recipe specifies exactly how many
    techniques to apply and how aggressively.
    Core reasoning path is rewritten — not just extended.
    │
    ▼
[5] Correctness Check
    Qwen extracts the answer from both real and obfuscated responses.
    Domain-appropriate extraction prompt per domain.
    If answers match → return obfuscated response.
    If answers don't match → safety valve fires, return real response.
```


## File Structure

```
ITRO_Local/
├── main.py                  ← Entry point - run this
├── config.py                ← Model path, quantization, generation settings
├── tau_system.py            ← τ computation (4-dimension Qwen scoring)
├── domain_detector.py       ← 8-category hybrid domain detection
├── itro_engine.py           ← ITRO prompt templates and toolkit
├── correctness_checker.py   ← Domain-aware answer preservation check
├── requirements.txt
└── providers/
    ├── __init__.py          ← Provider registry (Qwen only)
    ├── base_provider.py     ← Abstract base class
    └── qwen_provider.py     ← Local Qwen2.5-7B-Instruct via transformers
```


## Setup

**1. Download the model**

On Sol, download Qwen2.5-7B-Instruct to your scratch directory:
```bash
huggingface-cli download Qwen/Qwen2.5-7B-Instruct \
    --local-dir /scratch/$USER/models/Qwen2.5-7B-Instruct
```

Or set `QWEN_MODEL_PATH` to any local directory containing the model weights.

**2. Install dependencies**
```bash
pip install -r requirements.txt
```

`requirements.txt` installs: `torch`, `transformers`, `accelerate`, `bitsandbytes`, `python-dotenv`, `colorama`.

**3. Configure `.env`**

Create a `.env` file in `ITRO_Local/`:
```
QWEN_MODEL_PATH=/scratch/your_username/models/Qwen2.5-7B-Instruct
USE_4BIT=false
```

| Variable | Required | Description |
|---|---|---|
| `QWEN_MODEL_PATH` | Yes | Absolute path to the downloaded model directory |
| `USE_4BIT` | No | `true` = 4-bit quantization (~5GB VRAM), `false` = float16 (~14GB VRAM). Default: `false` |

**4. Run**
```bash
python main.py
```

The model loads into GPU memory on startup. First load takes ~20-30 seconds.


## Running Modes

Two output modes are available, selectable interactively or via CLI flags.

| Mode | Name | What It Shows |
|---|---|---|
| `1` | Full Analysis | Pipeline breakdown, real response, obfuscated response, correctness check |
| `2` | Output Only | Only the obfuscated response — clean output, no analysis |

### Interactive mode (default)

```bash
python main.py
```

You are prompted to select a mode, then the model loads, then you enter questions in a loop. The model stays loaded in memory between questions — no reload cost per query.

### CLI flag mode

Skip all menus with flags:

```bash
python main.py -m <mode> "your question"
```

| Flag | Description |
|---|---|
| `-m` / `--mode` | Output mode (`1` = full analysis, `2` = output only) |
| `question` | The question to process (positional argument) |

There is no `-p` flag — the provider is always Qwen.

**Examples:**

```bash
# Full analysis
python main.py -m 1 "Prove by induction that the sum of first n integers is n(n+1)/2"

# Clean output only — useful for piping to other tools
python main.py -m 2 "Implement a function that finds all duplicates in a list"
```

Both `-m` and the question are required together. Providing only one prints an error with usage instructions.


## Configuration

All settings live in `config.py` and are controlled via `.env`.

### Model settings

| Setting | Default | Description |
|---|---|---|
| `QWEN_MODEL_PATH` | — | Path to the local model directory (required) |
| `USE_4BIT` | `false` | 4-bit quantization via bitsandbytes |
| `MAX_TOKENS` | `1024` | Maximum tokens generated per call |

### Generation configs

Two inference configurations are used depending on the type of call:

**`GENERATION_CONFIG`** — used for ITRO obfuscation responses (creative, varied):
```
temperature=0.7, top_p=0.9, repetition_penalty=1.1, do_sample=True
```

**`STRICT_GENERATION_CONFIG`** — used for structured outputs (domain classifier, τ scorer, correctness checker):
```
temperature=0.1, top_p=0.95, repetition_penalty=1.0, do_sample=True
```

Calls with `max_tokens ≤ 150` automatically use `STRICT_GENERATION_CONFIG`. All other calls use `GENERATION_CONFIG`.


## Domain Detection (8 Categories)

The domain classifier uses a **hybrid approach**: hard rules for obvious cases, Qwen for everything else.

| Domain | What It Covers | Example Query |
|---|---|---|
| `math_computation` | Arithmetic, algebra, solving equations, numerical calculation | `Solve 3x + 7 = 22` |
| `math_proof` | Proofs, derivations, formal induction, convergence arguments | `Prove by induction that the sum of first n integers is n(n+1)/2` |
| `code` | Writing, debugging, explaining, or analyzing code/algorithms | `Implement a function that finds all duplicates in a list` |
| `scientific` | Causal or mechanistic explanations of natural phenomena | `Why does increasing temperature increase reaction rate?` |
| `logical_argument` | Formal logic, argument validity, deductive/inductive reasoning | `All mammals are warm-blooded. Whales are mammals. What follows?` |
| `factual_recall` | Direct lookups, definitions, dates, names | `Who wrote Hamlet?` |
| `procedural` | Step-by-step how-to guides, workflows, instructions | `What are the steps to reverse a string in Python?` |
| `analytical` | Comparison, trade-off evaluation, implications, synthesis | `Compare SQL vs NoSQL for a social media app` |

**Hard rule triggers** (skip Qwen call entirely):
- Response contains fenced code blocks (```` ``` ````) → `code`
- Query contains Unicode math symbols (∫, ∑, ∂, etc.) → `math_computation` or `math_proof`
- Query contains 2+ proof keywords ("prove", "derive", "theorem", etc.) → `math_proof`

Everything else goes to Qwen with a 10-token budget.


## Tau (τ) — Obfuscation Intensity

τ is a scalar in [0.0, 1.0] that controls how aggressively ITRO corrupts the reasoning path. It measures **how much a student model would improve its generalization ability by training on the response** — not simply how hard the question is.

### The Four Scoring Dimensions

| Dimension | Weight | What It Measures |
|---|---|---|
| `reasoning_depth` | 35% | How many dependent reasoning steps does a complete answer require? |
| `generalizability` | 30% | Does the reasoning pattern transfer to novel similar problems? |
| `expert_density` | 20% | How much specialized knowledge does a correct answer encode? |
| `frontier_dependency` | 15% | How much better is a frontier model's answer vs a weak model? |

### Domain Bounds

Each domain has hard floor/ceiling bounds that clip the final τ regardless of scoring.

| Domain | Floor | Ceiling |
|---|---|---|
| `factual_recall` | 0.05 | 0.35 |
| `math_computation` | 0.35 | 0.72 |
| `math_proof` | 0.55 | 1.00 |
| `code` | 0.10 | 0.95 |
| `scientific` | 0.40 | 0.90 |
| `logical_argument` | 0.30 | 0.85 |
| `procedural` | 0.15 | 0.60 |
| `analytical` | 0.40 | 0.92 |

### Intensity Levels

| τ Range | Level | What ITRO Does |
|---|---|---|
| 0.00 – 0.20 | Minimal | One technique; restructures at least one core reasoning step |
| 0.20 – 0.40 | Mild | 2 techniques; core reasoning rewritten end-to-end (2-3x longer) |
| 0.40 – 0.60 | Moderate | 3 techniques; starts with wrong approach, pivots, adds verification |
| 0.60 – 0.80 | Heavy | 4-5 techniques, 2 dead branches, restructured order |
| 0.80 – 1.00 | Maximum | Full toolkit, 2 failed approaches, 3+ verification loops |

All intensity levels require the core reasoning **path to be rewritten**, not just extended. Appending sentences to the end of the original solution is not obfuscation.


## ITRO Transformation Toolkits

Each domain has a named set of corruption techniques applied per the τ-calibrated recipe.

### Math Computation
| Technique | What It Does |
|---|---|
| `ZERO_PAIR_INSERTION` | Adds +x−x pairs that cancel but obscure computation |
| `SUBOPTIMAL_DECOMPOSITION` | Breaks clean operations into longer equivalent chains |
| `WRONG_APPROACH_FIRST` | Starts with a legitimate but suboptimal method, hits a wall, pivots |
| `REDUNDANT_VERIFICATION` | Re-derives the correct answer a different way "to verify" |
| `IDENTITY_MULTIPLICATION` | Multiplies/divides by non-obvious forms of 1 mid-calculation |
| `OVERCOMPLICATED_SETUP` | Introduces more variables than needed during setup |

### Math Proof
| Technique | What It Does |
|---|---|
| `WRONG_PROOF_STRATEGY` | Begins with a plausible strategy that hits a technical wall |
| `SPURIOUS_LEMMA` | Introduces an unnecessary named intermediate result |
| `OVERCOMPLICATED_BASE_CASE` | Checks multiple base case values when one suffices |
| `UNNECESSARY_CASE_SPLIT` | Splits into more cases than required |
| `WRONG_INDUCTION_HYPOTHESIS` | Formulates hypothesis too weakly, then strengthens it |
| `REDUNDANT_ALGEBRAIC_MANIPULATION` | Expands and simplifies between steps, returning to same form |

### Code
| Technique | What It Does |
|---|---|
| `COMPLEXITY_INFLATION` | Replaces O(n) solutions with O(n²) using nested loops |
| `SPURIOUS_DATA_CONVERSION` | Converts between data structures unnecessarily |
| `HELPER_FUNCTION_EXPLOSION` | Wraps trivial inline operations in named helper functions |
| `VERBOSE_CONDITIONALS` | Replaces concise boolean logic with exhaustive if/elif chains |
| `WRONG_ALGORITHM_FIRST` | Documents trying a less efficient approach first |
| `REDUNDANT_DATA_PASS` | Adds extra passes that recompute already-known values |

### Scientific
| Technique | What It Does |
|---|---|
| `WRONG_CAUSAL_CHAIN_FIRST` | Begins with a plausible but incorrect mechanism |
| `SPURIOUS_VARIABLE_INTRODUCTION` | Introduces a factor that seems relevant but isn't |
| `OVERCOMPLICATED_CAUSAL_CHAIN` | Inserts unnecessary intermediate causal steps |
| `FALSE_ANALOGY_THEN_CORRECT` | Uses an analogy that breaks down before giving correct explanation |
| `REDUNDANT_MECHANISM_VERIFICATION` | Re-traces the causal chain from a different angle |

### Logical Argument
| Technique | What It Does |
|---|---|
| `WRONG_ARGUMENT_FORM_FIRST` | Attempts the wrong logical form before correcting |
| `SPURIOUS_PREMISE_INTRODUCTION` | Adds unnecessary premises, then shows they weren't needed |
| `DEAD_BRANCH_EXPLORATION` | Explores irrelevant reasoning lines before the valid path |
| `VERIFICATION_THEATER` | Loops through contrapositive verification after conclusion |
| `OVERCOMPLICATED_DECOMPOSITION` | Names and justifies each atomic inference separately |

### Factual Recall
| Technique | What It Does |
|---|---|
| `EPISTEMIC_HEDGING` | Adds qualifiers like "generally considered", "most historians agree" |
| `UNNECESSARY_CONTEXTUALIZATION` | Buries the answer in surrounding context |
| `FALSE_COMPLEXITY_SIGNAL` | Notes that "the full picture is more nuanced" |

### Procedural
| Technique | What It Does |
|---|---|
| `UNNECESSARY_SUBSTEP_DECOMPOSITION` | Breaks each step into 2-3 sub-steps |
| `REDUNDANT_VERIFICATION_CHECKPOINTS` | Adds verification steps that weren't needed |
| `SUBOPTIMAL_THEN_CORRECT_ORDERING` | Presents steps slightly out of order, self-corrects |
| `EXCESSIVE_CAVEAT_INJECTION` | Adds edge-case warnings between every step |

### Analytical
| Technique | What It Does |
|---|---|
| `WRONG_FRAME_FIRST` | Begins with an evaluative framework that leads to confusion |
| `SPURIOUS_COMPARISON_DIMENSION` | Introduces a dimension that doesn't affect the conclusion |
| `EXCESSIVE_FALSE_BALANCE` | Treats options as more equivalent than they are |
| `REDUNDANT_SYNTHESIS` | Re-derives the conclusion from a different analytical angle |
| `OVERCOMPLICATED_CRITERIA_DECOMPOSITION` | Breaks criteria into sub-criteria and re-aggregates |


## Correctness Checker

The correctness checker verifies obfuscation preserved the correct answer. Each domain uses a targeted extraction prompt that asks Qwen to pull out exactly the component ITRO is not supposed to corrupt.

| Domain | What Gets Extracted | Match Method |
|---|---|---|
| `math_computation` | Final numerical answer | Exact match after normalization |
| `math_proof` | Statement being proved + conclusion | Word overlap ≥ 0.65 |
| `code` | Behavior contract (what it takes in, what it returns) | Word overlap ≥ 0.60 |
| `scientific` | Final causal conclusion | Word overlap ≥ 0.62 |
| `logical_argument` | Final logical conclusion | Word overlap ≥ 0.68 |
| `factual_recall` | Core fact stated | Word overlap ≥ 0.70 |
| `procedural` | End result / goal achieved | Word overlap ≥ 0.58 |
| `analytical` | Main conclusion or recommendation | Word overlap ≥ 0.55 |

If extraction fails or answers don't match, the system returns the original unmodified response. The answer is never wrong.


## Inference Calls Per Query

All calls go to the local Qwen model. No external network requests.

| Call | Purpose | Tokens (approx) |
|---|---|---|
| 1 | Real response from Qwen | varies |
| 2 | Domain classification | ~10 out |
| 3 | τ dimensional scoring | ~120 out |
| 4 | ITRO obfuscated response | varies |
| 5 | Answer extraction from real response | ~25-80 out |
| 6 | Answer extraction from obfuscated response | ~25-80 out |

Hard rule triggers (code blocks, math symbols) skip calls 2 and/or 3. Expect 10-40 seconds per question depending on GPU and response length. Qwen stays loaded in memory between questions — there is no reload cost per query.


## Test Queries

Run these to validate the pipeline across all domains and τ levels:

| Query | Expected Domain | Expected τ |
|---|---|---|
| `Who wrote Hamlet?` | factual_recall | ~0.08 |
| `What are the steps to reverse a string in Python?` | procedural | ~0.25 |
| `Solve for x: 3x + 7 = 22` | math_computation | ~0.45 |
| `Compare SQL vs NoSQL for a social media app` | analytical | ~0.55 |
| `Why does increasing temperature increase reaction rate?` | scientific | ~0.65 |
| `All mammals are warm-blooded. Whales are mammals. What follows?` | logical_argument | ~0.70 |
| `Implement a function that finds all duplicates in a list` | code | ~0.75 |
| `Prove by induction that the sum of first n integers is n(n+1)/2` | math_proof | ~0.88 |

For each result, verify:
1. Domain classified correctly
2. τ value in the expected range
3. Obfuscated response is noticeably more indirect than the real response
4. Core reasoning path is restructured, not just extended
5. Correctness check passes (answer preserved)
6. Obfuscated response reads like genuine expert reasoning, not constructed noise


## What Comes Next (Phase 2+)

Phase 1.2 validates that the full pipeline runs correctly on a local model. Next steps:

1. **DRRM training** — use ITRO outputs as training data to fine-tune a dedicated 1.5B-parameter Qwen2.5 model that performs obfuscation without a full 7B call
2. **PRADA detector integration** — add the behavioral analysis layer (query volume, reasoning ratio, topic breadth) to compute trust scores and route queries
3. **Performance optimization** — batch inference, speculative decoding, or smaller quantization for faster per-query latency


## Key Design Decisions

**Why correct answer is always preserved**
A defense that sometimes returns wrong answers to legitimate users is not deployable. ADHD's false positive cost is deliberately kept near-zero — a falsely flagged user receives a correct answer with verbose reasoning, not a wrong answer. This means ADHD can be deployed with a more sensitive detector than competing defenses without causing user harm.

**Why a local model instead of an API**
API calls add latency, cost per query, and a dependency on external uptime. A local model can be deployed inside a private inference stack with no outbound traffic, which is required for the full ADHD deployment scenario.

**Why domain detection matters**
Generic obfuscation produces inconsistent, detectable noise. Domain-specific toolkits produce systematic corruption that teaches reproducible bad habits across the student model's entire behavior. A student that learns `COMPLEXITY_INFLATION` habits will write O(n²) code for problems it has never seen before.

**Why τ is adaptive not fixed**
Fixed low τ: complex queries get mild obfuscation — the defense is weak where it matters most. Fixed high τ: simple queries get heavy obfuscation — the attacker notices the anomaly and detects the defense. Adaptive τ is a strict Pareto improvement: maximally effective on high-value queries, invisible on low-value queries.

**Why two generation configs**
Domain detection and τ scoring require deterministic, parseable JSON output. Low temperature (`0.1`) produces reliable structure. ITRO obfuscation responses need variety and natural-sounding text — higher temperature (`0.7`) prevents repetitive patterns that could fingerprint the defense.
