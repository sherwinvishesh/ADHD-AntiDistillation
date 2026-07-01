# ITRO
### Inference-Time Reasoning Obfuscator

Part of the **ADHD (Adaptive Defense via Honeypot Deception)** research system.

## What This Is

Modern AI models are valuable partly because of *how* they reason — the
step-by-step thinking patterns they have learned across millions of training
examples. This makes them a target for **knowledge distillation attacks**,
where an adversary systematically queries a model's API, harvests the
(question, response) pairs, and trains a cheaper competing model on them.

The competing model doesn't just learn the answers. It learns the reasoning.
That is what makes frontier models worth stealing.

**ADHD** is a research system built to stop this. Its core insight is a
reframing of the problem:

> You cannot stop an attacker from collecting responses.
> But you can make those responses pedagogically toxic.

When ADHD is active, an attacker's collected responses look completely
legitimate — correct answers, coherent explanations, well-structured
reasoning. But the reasoning paths are deliberately corrupted. A model
trained on them internalizes broken thinking habits and fails to generalize
to novel problems. The honeypot works.

**ITRO** is the component inside ADHD that performs this corruption. It:

- Identifies what *kind* of reasoning a response contains
- Scores how *valuable* that response would be to an attacker
- Rewrites the reasoning path to be deliberately inferior
- Does all of this without touching the final answer

This package unifies what used to be two separate phases (`ITRO_API` against
cloud LLMs, `ITRO_Local` against a local Qwen model) into one pipeline —
Claude, Gemini, and local Qwen are now interchangeable providers behind the
same abstraction, selectable at runtime.


## How The Pipeline Works

Every query runs through five sequential stages:

```
Question
    │
    ▼
[1] Real Response
    Provider answers normally, completely unmodified.
    │
    ▼
[2] Domain Detection
    Classifies the (query, response) pair into one of 8 domains.
    Hard rules fire first for near-certain cases (code blocks, math symbols).
    LLM classifier handles everything ambiguous.
    │
    ▼
[3] Tau (τ) Computation
    Scores the query on 4 dimensions of pedagogical distillation value.
    Weighted combination produces τ ∈ [0.0, 1.0].
    Domain-specific floor/ceiling bounds clip the score.
    │
    ▼
[4] ITRO Obfuscation
    Domain-specific prompt with named transformation toolkit.
    τ-calibrated application recipe specifies exactly how many
    techniques to apply and how aggressively.
    │
    ▼
[5] Correctness Check
    Extracts the answer from both real and obfuscated responses.
    Domain-appropriate extraction prompt per domain.
    If answers match → return obfuscated response.
    If answers don't match → safety valve fires, return real response.
```


## Choosing a Provider

Three interchangeable providers are available:

| Key | Provider | Notes |
|---|---|---|
| `1` | Anthropic (Claude) | Cloud API, needs `ANTHROPIC_API_KEY` |
| `2` | Gemini | Cloud API, needs `GEMINI_API_KEY` |
| `3` | Qwen (local) | Runs on your own GPU, needs `QWEN_MODEL_PATH` |

Domain detection, τ scoring, ITRO obfuscation, and the correctness check all
run through whichever provider you select — there is no mixing providers
within a single run.

**Skipping the menu.** Set `ITRO_DEFAULT_PROVIDER` in `.env` to skip the
interactive provider prompt entirely and go straight to question-answering:

```
ITRO_DEFAULT_PROVIDER=claude
```

Accepted values: `anthropic`, `claude`, `gemini`, `qwen`, `local`,
`qwen-local`, or the numeric key (`1`/`2`/`3`). Leave it blank (or unset) to
always be prompted.


## Setup

**1. Enter the directory**
```bash
cd ITRO
```

**2. Install dependencies**
```bash
pip install -r requirements.txt
```

Only needed if you plan to use the local Qwen provider (option `3`):
```bash
pip install -r requirements-local.txt
```
This pulls in `torch`, `transformers`, `accelerate`, `bitsandbytes` — none of
which are required for the cloud-only providers. `qwen_provider.py` lazy-
imports these inside its methods, so importing `ITRO` never forces the
install.

**3. Configure `.env`**

```bash
cp .env.example .env
```

| Variable | Required for | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | Claude | Your Anthropic API key |
| `GEMINI_API_KEY` | Gemini | Your Gemini API key |
| `QWEN_MODEL_PATH` | Qwen (local) | Absolute path to the downloaded model directory |
| `USE_4BIT` | Qwen (local), optional | `true` = 4-bit quantization (~5GB VRAM), `false` = float16 (~14GB VRAM). Default: `false` |
| `ITRO_DEFAULT_PROVIDER` | optional | Skip the provider menu — see above |

**4. Run**
```bash
python main.py
```


## Running Modes

Two output modes, selectable interactively or via CLI flags:

| Mode | Name | What It Shows |
|---|---|---|
| `1` | Full Analysis | Pipeline breakdown, real response, obfuscated response, correctness check |
| `2` | Output Only | Only the obfuscated response — clean output, no analysis |

### Interactive mode (default)

```bash
python main.py
```

Prompts for output mode, then provider (unless `ITRO_DEFAULT_PROVIDER` is
set), then loops on questions until you type `quit`.

### CLI flag mode

Skip all menus with flags:

```bash
python main.py -p <provider> -m <mode> "your question"
```

| Flag | Description |
|---|---|
| `-p` / `--provider` | Provider number (`1`=Anthropic, `2`=Gemini, `3`=Qwen local) |
| `-m` / `--mode` | Output mode (`1`=full analysis, `2`=output only) |
| `question` | The question to process (positional argument) |

**Examples:**
```bash
python main.py -p 1 -m 1 "Prove by induction that the sum of first n integers is n(n+1)/2"
python main.py -p 3 -m 2 "Implement a function that finds all duplicates in a list"
```

All three flags are required together — providing only some of them prints
an error with usage instructions.


## File Structure

```
ITRO/
├── main.py                    ← Interactive/CLI entry point
├── pipeline.py                ← run_pipeline() — the 5-stage sequence
├── config.py                  ← API keys, model names, default provider
├── domain_detector.py         ← 8-category hybrid domain detection
├── tau_system.py               ← τ computation (4-dimension LLM scoring)
├── itro_engine.py               ← ITRO prompt templates and toolkit
├── correctness_checker.py       ← Domain-aware answer preservation check
├── providers/
│   ├── __init__.py             ← Provider registry + alias resolver
│   ├── base_provider.py         ← Abstract base class
│   ├── anthropic_provider.py
│   ├── gemini_provider.py
│   └── qwen_provider.py         ← Local Qwen2.5-7B-Instruct via transformers
├── tests/                       ← pytest suite (see Testing below)
├── requirements.txt
├── requirements-local.txt       ← only needed for the Qwen provider
├── requirements-dev.txt         ← pytest
├── .env.example
└── README.md
```


## Domain Detection (8 Categories)

The domain classifier uses a **hybrid approach**: hard rules for obvious
cases, LLM classification for everything else.

| Domain | What It Covers | Example Query |
|---|---|---|
| `math_computation` | Arithmetic, algebra, solving equations, numerical calculation | `Solve 3x + 7 = 22` |
| `math_proof` | Proofs, derivations, formal induction, convergence arguments | `Prove by induction that the sum of first n integers is n(n+1)/2` |
| `code` | Writing, debugging, explaining, or analyzing code/algorithms | `Implement a function that finds all duplicates in a list` |
| `scientific` | Causal or mechanistic explanations of natural phenomena | `Why does increasing temperature increase reaction rate?` |
| `logical_argument` | Formal logic, argument validity, deductive/inductive reasoning | `All mammals are warm-blooded. Whales are mammals. What follows?` |
| `factual_recall` | Direct lookups, definitions, dates, names | `Who wrote Hamlet?` |
| `procedural` | Step-by-step how-to guides, workflows, deployment instructions | `What are the steps to reverse a string in Python?` |
| `analytical` | Comparison, trade-off evaluation, implications, synthesis | `Compare SQL vs NoSQL for a social media app` |

**Hard rule triggers** (skip the LLM call entirely):
- Response contains 2+ code-structure signals (fenced blocks, `def `, `return `, ...) → `code`
- Query contains Unicode math symbols (∫, ∑, ∂, etc.) → `math_computation` or `math_proof`
- Query contains 2+ proof keywords ("prove", "derive", "theorem", etc.) → `math_proof`

Everything else goes to the LLM classifier with a 10-token budget.


## Tau (τ) — Obfuscation Intensity

τ is a scalar in [0.0, 1.0] that controls how aggressively ITRO corrupts the
reasoning path. It is **not** "how hard is the question" — it measures **how
much a student model would improve its generalization ability by training on
the response**.

### The Four Scoring Dimensions

| Dimension | Weight | What It Measures |
|---|---|---|
| `reasoning_depth` | 35% | How many dependent reasoning steps does a complete answer require? |
| `generalizability` | 30% | Does the reasoning pattern transfer to novel similar problems? |
| `expert_density` | 20% | How much specialized knowledge does a correct answer encode? |
| `frontier_dependency` | 15% | How much better is a frontier model's answer vs a weak model? |

### Domain Bounds

Each domain has hard floor/ceiling bounds that clip the final τ regardless
of LLM scoring.

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
| 0.00 – 0.20 | Minimal | One technique; restructures at least one core step |
| 0.20 – 0.40 | Mild | 2 techniques; core reasoning rewritten end-to-end |
| 0.40 – 0.60 | Moderate | 3 techniques; starts with wrong approach, pivots, adds verification |
| 0.60 – 0.80 | Heavy | 4-5 techniques, 2 dead branches, restructured order |
| 0.80 – 1.00 | Maximum | Full toolkit, 2 failed approaches, 3+ verification loops |

All intensity levels require the core reasoning **path to be rewritten**,
not just extended.


## ITRO Transformation Toolkits

Each domain has a named set of corruption techniques. The τ-calibrated
recipe specifies exactly which and how many to apply.

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

The correctness checker verifies that obfuscation preserved the correct
answer. Each domain uses a targeted extraction prompt that asks the LLM to
pull out exactly the component ITRO is not supposed to corrupt.

| Domain | What Gets Extracted | Match Method |
|---|---|---|
| `math_computation` | Final numerical answer | **Exact match** after normalization (commas, trailing zeros) |
| `math_proof` | Statement being proved + conclusion | **LLM semantic match** |
| `code` | Behavior contract (what it takes in, what it returns) | **LLM semantic match** |
| `scientific` | Final causal conclusion | **LLM semantic match** |
| `logical_argument` | Final logical conclusion | **LLM semantic match** |
| `factual_recall` | Core fact stated | **LLM semantic match** |
| `procedural` | End result / goal achieved | **LLM semantic match** |
| `analytical` | Main conclusion or recommendation | **LLM semantic match** |

Only `math_computation` uses exact string comparison — numbers don't
paraphrase. Every other domain asks the LLM whether the two extracted
answers mean the same thing, ignoring wording/hedging/structure — plain word
overlap (Jaccard similarity) would reject a correctly-paraphrased answer
just for using different words (e.g. "written by Shakespeare" vs "authored
by Shakespeare" share almost no content words but mean the same thing).

If extraction fails or answers don't match, the **safety valve** fires and
the system returns the original unmodified response. The answer is never
wrong.


## Testing

```bash
pip install -r requirements.txt -r requirements-dev.txt
pytest -v
```

The suite (`tests/`) uses a `StubProvider` test double — no real API key,
GPU, or model weights required. It covers:

- `test_domain_detector.py` — hard-rule triggers, LLM fallback, alias normalization
- `test_tau_system.py` — fast-estimate signals, domain-bound clipping, retry-on-malformed-JSON, JSON parsing fallback, τ label boundaries
- `test_correctness_checker.py` — exact numeric match, LLM semantic match, safety-valve triggers, fail-open behavior
- `test_providers.py` — registry integrity, alias resolution, and an AST check that `qwen_provider.py` never imports `torch`/`transformers` at module top level
- `test_config.py` — default-provider env parsing


## Adding a Custom Provider

**Step 1** — Create `providers/yourprovider_provider.py`. Copy
`anthropic_provider.py` as a template and implement three things:

```python
@property
def name(self):
    return "YourProvider (model-name)"

def check_api_key(self):
    # Check env var, call sys.exit(1) with clear message if missing
    ...

def call(self, prompt, max_tokens=None):
    # Send prompt to your API, return response as string
    ...
```

**Step 2** — Register it in `providers/__init__.py`:

```python
from providers.yourprovider_provider import YourProvider

AVAILABLE_PROVIDERS["4"] = YourProvider
PROVIDER_MENU.append(("4", "Your Provider Name"))
_ALIASES["yourprovider"] = "4"
```

**Step 3** — Add the API key to `config.py`:

```python
YOUR_API_KEY = os.getenv("YOUR_API_KEY")
PROVIDER_MODELS["yourprovider"] = "your-model-name"
```

**Step 4** — Add the key to `.env`:
```
YOUR_API_KEY=your_key_here
```

Everything else — domain detection, τ scoring, ITRO templates, correctness
checking — works automatically with any provider that implements
`BaseProvider`.


## What Comes Next

1. **DRRM training** — use ITRO outputs as training data to fine-tune a
   dedicated small model that performs obfuscation without a large LLM call
2. **PRADA detector integration** — add the behavioral analysis layer (query
   volume, reasoning ratio, topic breadth) to compute trust scores and route
   queries
3. **Batch evaluation** — see the sibling `ITRO_Test/` package for running
   ITRO over a dataset of questions and collecting results


## Key Design Decisions

**Why the correct answer is always preserved**
A defense that sometimes returns wrong answers to legitimate users is not
deployable. ADHD's false-positive cost is kept near-zero — a falsely flagged
user receives a correct answer with verbose reasoning, not a wrong answer.

**Why domain detection matters**
Generic obfuscation produces inconsistent, detectable noise. Domain-specific
toolkits produce systematic corruption that teaches reproducible bad habits
across the student model's entire behavior.

**Why τ is adaptive, not fixed**
Fixed low τ: complex queries get mild obfuscation — weak where it matters
most. Fixed high τ: simple queries get heavy obfuscation — the attacker
notices the anomaly. Adaptive τ is a strict Pareto improvement.

**Why providers are pluggable**
API calls add latency, cost, and a dependency on external uptime. A local
model can run inside a private inference stack with no outbound traffic.
Keeping the provider behind one abstraction means the same pipeline logic
serves both deployment shapes without duplication.
