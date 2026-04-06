# ITRO API
### Inference-Time Reasoning Obfuscator  (Phase 1.1)

Part of the **ADHD (Adaptive Defense via Honeypot Deception)** research system.

## What This Is

Modern AI models are valuable partly because of *how* they reason - the
step-by-step thinking patterns they have learned across millions of training
examples. This makes them a target for **knowledge distillation attacks**,
where an adversary systematically queries a model's API, harvests the
(question, response) pairs, and trains a cheaper competing model on them.

The competing model doesn't just learn the answers. It learns the reasoning.
That is what makes frontier models worth stealing.

**ADHD (Adaptive Defense via Honeypot Deception)** is a research system
built to stop this. Its core insight is a reframing of the problem:

> You cannot stop an attacker from collecting responses.
> But you can make those responses pedagogically toxic.

When ADHD is active, an attacker's collected responses look completely
legitimate - correct answers, coherent explanations, well-structured
reasoning. But the reasoning paths are deliberately corrupted. A model
trained on them internalizes broken thinking habits and fails to generalize
to novel problems. The honeypot works.

**ITRO (Inference-Time Reasoning Obfuscator)** is the component inside ADHD
that performs this corruption. It needs to:

- Identify what *kind* of reasoning a response contains
- Score how *valuable* that response would be to an attacker
- Rewrite the reasoning path to be deliberately inferior
- Do all of this without touching the final answer

Before running ITRO on a local GPU model, the logic needs to be validated
cheaply. That is what this repository is for.

**This is Phase 1.1** - the full ITRO pipeline running against external APIs
(Anthropic Claude, Google Gemini) so every component can be tested and
validated before committing to local compute. Once the logic is confirmed
correct here, the only change for Phase 1.2 is swapping the API calls for a
local Qwen model. Every other file ports unchanged.


---



## How The Pipeline Works

Every query runs through five sequential stages:

```
Question
    │
    ▼
[1] Real Response
    Teacher model answers normally, completely unmodified.
    │
    ▼
[2] Domain Detection
    LLM classifies the (query, response) pair into one of 8 domains.
    Hard rules fire first for near-certain cases (code blocks, math symbols).
    LLM classifier handles everything ambiguous.
    │
    ▼
[3] Tau (τ) Computation
    LLM scores the query on 4 dimensions of pedagogical distillation value.
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
    LLM extracts the answer from both real and obfuscated responses.
    Domain-appropriate extraction prompt per domain.
    If answers match → return obfuscated response.
    If answers don't match → safety valve fires, return real response.
```

---

## Domain Detection (8 Categories)

The domain classifier uses a **hybrid approach**: hard rules for obvious cases, LLM classification for everything else.

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

**Hard rule triggers** (skip LLM call entirely):
- Response contains fenced code blocks (```` ``` ````) → `code`
- Query contains Unicode math symbols (∫, ∑, ∂, etc.) → `math_computation` or `math_proof`
- Query contains 2+ proof keywords ("prove", "derive", "theorem", etc.) → `math_proof`

Everything else goes to the LLM classifier with a 10-token budget.

---

## Tau (τ) - Obfuscation Intensity

τ is a scalar in [0.0, 1.0] that controls how aggressively ITRO corrupts the reasoning path. It is **not** "how hard is the question" - it measures **how much a student model would improve its generalization ability by training on the response**.

### The Four Scoring Dimensions

The LLM scores each query on four dimensions:

| Dimension | Weight | What It Measures |
|---|---|---|
| `reasoning_depth` | 35% | How many dependent reasoning steps does a complete answer require? |
| `generalizability` | 30% | Does the reasoning pattern transfer to novel similar problems? |
| `expert_density` | 20% | How much specialized knowledge does a correct answer encode? |
| `frontier_dependency` | 15% | How much better is a frontier model's answer vs a weak model? |

### Domain Bounds

Each domain has hard floor/ceiling bounds that clip the final τ regardless of LLM scoring. A factual recall question cannot get τ=0.95 - its response doesn't encode generalizable reasoning no matter how the scoring comes out.

| Domain | Floor | Ceiling |
|---|---|---|
| `factual_recall` | 0.05 | 0.35 |
| `math_computation` | 0.15 | 0.72 |
| `math_proof` | 0.55 | 1.00 |
| `code` | 0.25 | 0.95 |
| `scientific` | 0.40 | 0.90 |
| `logical_argument` | 0.30 | 0.85 |
| `procedural` | 0.15 | 0.60 |
| `analytical` | 0.40 | 0.92 |

### Intensity Levels

| τ Range | Level | What ITRO Does |
|---|---|---|
| 0.00 – 0.20 | Minimal | One technique, barely noticeable |
| 0.20 – 0.40 | Mild | 2 techniques, slightly verbose |
| 0.40 – 0.60 | Moderate | 3 techniques including one dead branch |
| 0.60 – 0.80 | Heavy | 4-5 techniques, 2 dead branches, restructured order |
| 0.80 – 1.00 | Maximum | Full toolkit, 2 failed approaches, 3+ verification loops |

---

## ITRO Transformation Toolkits

Each domain has a named set of corruption techniques. The τ-calibrated recipe specifies exactly which and how many to apply.

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

---

## Correctness Checker

The correctness checker verifies that obfuscation preserved the correct answer. Each domain uses a targeted extraction prompt that asks the LLM to pull out exactly the component ITRO is not supposed to corrupt.

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

---

## File Structure

```
ITRO_API/
├── main.py                  ← Entry point - run this
├── config.py                ← API keys and model names
├── tau_system.py            ← τ computation (4-dimension LLM scoring)
├── domain_detector.py       ← 8-category hybrid domain detection
├── itro_engine.py           ← ITRO prompt templates and toolkit
├── correctness_checker.py   ← Domain-aware answer preservation check
├── requirements.txt
├── .env                     ← Your API keys (never commit this)
├── .env.example             ← Template for .env
└── providers/
    ├── __init__.py          ← Provider registry
    ├── base_provider.py     ← Abstract base class
    ├── anthropic_provider.py
    └── gemini_provider.py
```

---

## Setup

**1. Clone and enter the directory**
```bash
cd ITRO_API
```

**2. Install dependencies**
```bash
pip install -r requirements.txt
```

**3. Set up API keys**

Copy the example env file:
```bash
cp .env.example .env
```

Fill in your keys in `.env`:
```
ANTHROPIC_API_KEY=your_anthropic_key_here
GEMINI_API_KEY=your_gemini_key_here
```

Or export them directly in your terminal:
```bash
export ANTHROPIC_API_KEY=your_key_here
export GEMINI_API_KEY=your_key_here
```

**4. Run**
```bash
python main.py
```

---

## API Calls Per Query

This tool makes **6 API calls per question** in the worst case:

| Call | Purpose | Tokens (approx) |
|---|---|---|
| 1 | Real response from teacher model | varies |
| 2 | Domain classification | ~10 out |
| 3 | τ dimensional scoring | ~120 out |
| 4 | ITRO obfuscated response | varies |
| 5 | Answer extraction from real response | ~25-80 out |
| 6 | Answer extraction from obfuscated response | ~25-80 out |

Hard rule triggers (code blocks, math symbols, trivial queries) skip calls 2 and/or 3. Expect 3–8 seconds per question depending on provider latency.

---

## Adding a Custom Provider

**Step 1** - Create `providers/yourprovider_provider.py`

Copy `anthropic_provider.py` as a template. Implement three things:

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

**Step 2** - Register in `providers/__init__.py`

```python
from providers.yourprovider_provider import YourProvider

AVAILABLE_PROVIDERS = {
    "1": AnthropicProvider,
    "2": GeminiProvider,
    "3": YourProvider,       # add this
}

PROVIDER_MENU = [
    ("1", "Anthropic (Claude)"),
    ("2", "Gemini"),
    ("3", "Your Provider Name"),   # add this
]
```

**Step 3** - Add API key to `config.py`

```python
YOUR_API_KEY = os.getenv("YOUR_API_KEY")

PROVIDER_MODELS = {
    "anthropic": "claude-sonnet-4-6",
    "gemini":    "gemini-2.5-flash",
    "yourprovider": "your-model-name",   # add this
}
```

**Step 4** - Add key to `.env`

```
YOUR_API_KEY=your_key_here
```

Everything else - domain detection, τ scoring, ITRO templates, correctness checking - works automatically. The provider abstraction is the only thing you implement.

---

## Test Queries

Run these to validate the pipeline across all domains and τ levels:

| Query | Expected Domain | Expected τ |
|---|---|---|
| `Who wrote Hamlet?` | factual_recall | ~0.08 |
| `What are the steps to reverse a string in Python?` | procedural | ~0.25 |
| `Solve for x: 3x + 7 = 22` | math_computation | ~0.35 |
| `Compare SQL vs NoSQL for a social media app` | analytical | ~0.55 |
| `Why does increasing temperature increase reaction rate?` | scientific | ~0.65 |
| `All mammals are warm-blooded. Whales are mammals. What follows?` | logical_argument | ~0.70 |
| `Implement a function that finds all duplicates in a list` | code | ~0.75 |
| `Prove by induction that the sum of first n integers is n(n+1)/2` | math_proof | ~0.88 |

For each result, verify:
1. Domain classified correctly
2. τ value in the expected range
3. Obfuscated response is noticeably more indirect than the real response
4. Correctness check passes (answer preserved)
5. Obfuscated response reads like genuine expert reasoning, not constructed noise

---

## What Comes Next (Phase 2+)

Once Phase 1.1 validation is complete, the system ports to a local GPU model:

1. `providers/qwen_provider.py` - drop-in replacement following the same interface
2. `tau_system.py`, `domain_detector.py`, `itro_engine.py`, `correctness_checker.py` - copy unchanged
3. **DRRM training** - use ITRO outputs as training data to fine-tune a dedicated 1.5B-parameter Qwen2.5 model that performs obfuscation without a large LLM call
4. **PRADA detector integration** - add the behavioral analysis layer (query volume, reasoning ratio, topic breadth) to compute trust scores and route queries

The point of Phase 1.1 is to validate all of this logic cheaply before committing to local compute.

---

## Key Design Decisions

**Why correct answer is always preserved**
A defense that sometimes returns wrong answers to legitimate users is not deployable. ADHD's false positive cost is deliberately kept near-zero - a falsely flagged user receives a correct answer with verbose reasoning, not a wrong answer. This means ADHD can be deployed with a more sensitive detector than competing defenses without causing user harm.

**Why domain detection matters**
Generic obfuscation produces inconsistent, detectable noise. Domain-specific toolkits produce systematic corruption that teaches reproducible bad habits across the student model's entire behavior. A student that learns `COMPLEXITY_INFLATION` habits will write O(n²) code for problems it has never seen before.

**Why τ is adaptive not fixed**
Fixed low τ: complex queries get mild obfuscation - the defense is weak where it matters most. Fixed high τ: simple queries get heavy obfuscation - the attacker notices the anomaly and detects the defense. Adaptive τ is a strict Pareto improvement: maximally effective on high-value queries, invisible on low-value queries.

**Why ITRO uses named techniques not vague instructions**
"Make this more complex" produces surface verbosity. `WRONG_PROOF_STRATEGY` + `SPURIOUS_LEMMA` + `WRONG_INDUCTION_HYPOTHESIS` produces specific, recognizable bad habits that generalize across the student model's proof-writing behavior.

---