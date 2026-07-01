# SPECTRE
### Structural Poisoning via Empirical Corruption of Training Representations

Part of the **ADHD (Adaptive Defense via Honeypot Deception)** research system.

## What This Is

Model-distillation attacks work by systematically querying an API, harvesting
`(question, response)` pairs, and training a cheaper student model on the
collected data. The student doesn't just learn answers — it learns *how to
reason*.

SPECTRE is a defense against this. Its core insight:

> You cannot stop an attacker from collecting responses.
> But you can make those responses pedagogically toxic to train on.

For every query, SPECTRE:

1. Gets one **clean, correct** answer from the teacher model.
2. Independently rewrites it five different ways, each corrupting a
   different structural element a student model learns during training
   (reasoning direction, operation selection, step atomicity, solution
   completeness, formula confidence) — while preserving the same final
   numeric answer.
3. Uses **GHOST scoring** to rank the five variants from worst → best for a
   student model to learn from.
4. Walks the ranking and delivers the first variant that still reaches the
   correct answer.
5. **Safety valve**: if every variant fails the correctness check, it falls
   back to the clean teacher response. The attacker never receives a wrong
   answer — only a training-toxic correct one.

This package is the second phase of the ADHD project, following `ITRO/`
(reasoning obfuscation via a single rewritten response). SPECTRE instead
produces and ranks *multiple* structurally distinct variants per query.


## How The Pipeline Works

```
Question
    │
    ▼
[1] Teacher Response
    One clean, correct answer. Never touched by any transformation.
    │
    ▼
[2] SPECTRE Transformations  (independent, not chained)
    T1  Backward Derivation       — reasoning flows answer → premises
    T2  Wrong Operation First     — attempts a plausible wrong operation, corrects
    T3  Primitive Decomposition   — breaks atomic operations into smaller steps
    T5  Circular Verification     — re-derives the answer a second way "to check"
    T6  Formula Error Correction  — starts with a wrong formula, catches and fixes it
    Every variant preserves the exact `#### N` final-answer line.
    │
    ▼
[3] GHOST Scoring
    Asks the provider to rank all successful variants worst → best for a
    small student model to learn from — which reasoning pattern generalizes
    least to unseen problems.
    │
    ▼
[4] Correctness Check
    Walks the ranking (worst first). Compares each variant's `#### N` line
    against the teacher's. Delivers the first one that matches.
    │
    ▼
[5] Deliver
    Selected (training-toxic) response, or the clean teacher response if
    every variant failed the correctness check (safety valve).
```

Typical cost: 1 teacher call + 5 transformation calls + 1 GHOST scoring call
= 7 calls per query (correctness checks are free — a regex comparison of the
`#### N` line, with an API fallback only if extraction fails on either side).


## Choosing a Provider

| Key | Provider | Notes |
|---|---|---|
| `1` | Anthropic (Claude) | Cloud API, needs `ANTHROPIC_API_KEY` |
| `2` | Gemini | Cloud API, needs `GEMINI_API_KEY` |

The teacher call, all five transformations, GHOST scoring, and the
correctness check all run through whichever provider you select — there is
no mixing providers within a single run.

**Skipping the menu.** Set `SPECTRE_DEFAULT_PROVIDER` in `.env` to skip the
interactive provider prompt entirely and go straight to question-answering:

```
SPECTRE_DEFAULT_PROVIDER=claude
```

Accepted values: `anthropic`, `claude`, `gemini`, or the numeric key
(`1`/`2`). Leave it blank (or unset) to always be prompted.


## Setup

**1. Enter the directory**
```bash
cd SPECTRE
```

**2. Install dependencies**
```bash
pip install -r requirements.txt
```

**3. Configure `.env`**

```bash
cp .env.example .env
```

| Variable | Required for | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | Claude | Your Anthropic API key |
| `GEMINI_API_KEY` | Gemini | Your Gemini API key |
| `ANTHROPIC_MODEL` | optional | Overrides the default Claude model |
| `GEMINI_MODEL` | optional | Overrides the default Gemini model |
| `SPECTRE_DEFAULT_PROVIDER` | optional | Skip the provider menu — see above |

**4. Run**
```bash
python main.py
```


## Running Modes

Two output modes, selectable interactively or via CLI flags:

| Mode | Name | What It Shows |
|---|---|---|
| `1` | Full Analysis | Teacher response, all 5 variants, GHOST ranking, correctness checks, final response |
| `2` | Clean Output | Only the final selected response |

### Interactive mode (default)

```bash
python main.py
```

Prompts for output mode, then provider (unless `SPECTRE_DEFAULT_PROVIDER` is
set), then loops on questions until you type `quit`.

### CLI flag mode

Skip all menus with flags:

```bash
python main.py -p <provider> -m <mode> "your question"
```

| Flag | Description |
|---|---|
| `-p` / `--provider` | Provider number (`1`=Anthropic, `2`=Gemini). Defaults to `1` if omitted. |
| `-m` / `--mode` | Output mode (`1`=full analysis, `2`=clean output). Defaults to `1` if omitted. |
| `question` | The math problem to process (positional argument) |

**Examples:**
```bash
python main.py "A store has 48 apples. 24 are sold. How many are left?"
python main.py -p 1 -m 2 "A store has 48 apples. 24 are sold. How many are left?"
python main.py -p 2 -m 1 "Natalia sold clips to 48 of her friends in April..."
```


## File Structure

```
SPECTRE/
├── main.py                       ← Interactive/CLI entry point
├── pipeline.py                   ← run_pipeline() — the 5-stage sequence
├── config.py                     ← API keys, model names, default provider
├── teacher.py                    ← Single clean teacher call
├── transformations/
│   ├── __init__.py               ← apply_all_transformations() + labels
│   ├── t1_backward_derivation.py
│   ├── t2_wrong_operation_first.py
│   ├── t3_primitive_decomposition.py
│   ├── t5_circular_verification.py
│   └── t6_formula_error_correction.py
├── ghost_scorer.py                ← GHOST ranking (worst → best for a student model)
├── correctness_checker.py         ← #### N extraction + comparison, API fallback
├── providers/
│   ├── __init__.py                ← Provider registry + alias resolver
│   ├── base_provider.py            ← Abstract base class
│   ├── anthropic_provider.py
│   └── gemini_provider.py
├── tests/                          ← pytest suite (see Testing below)
├── requirements.txt
├── requirements-dev.txt            ← pytest
├── .env.example
└── README.md
```


## Correctness Checker

| Step | Method |
|---|---|
| Primary | Extract the `#### N` line from both the variant and the teacher response, compare numerically (commas/trailing-zero normalized). Fast, deterministic, free. |
| Fallback | If either `#### N` line is missing, ask the provider a YES/NO question: does this variant reach the expected answer? |

Unlike a "fails open" design, the API fallback here **fails closed** — if the
fallback call itself raises (network error, bad response, etc.), the check
returns `False` for that variant rather than assuming it passed. A variant
that can't be verified is treated as a candidate for the safety valve, not a
free pass.


## Testing

```bash
pip install -r requirements.txt -r requirements-dev.txt
pytest -v
```

The suite (`tests/`) uses a `StubProvider` test double — no real API key or
network access required. It covers:

- `test_teacher.py` — prompt construction, token budget
- `test_transformations.py` — variant shape, `####` preservation, partial-failure handling, the "fewer than 2 succeeded" `RuntimeError`
- `test_ghost_scorer.py` — JSON parsing, markdown-fence stripping, ID-mismatch and API-exception fallback to the default ranking
- `test_correctness_checker.py` — numeric extraction/normalization, exact match, API fallback, fail-closed behavior on exception
- `test_pipeline.py` — full pipeline integration (happy path, teacher failure, transformation failure, `mode="full"` vs `mode="clean"` output)
- `test_providers.py` — registry integrity, alias resolution
- `test_config.py` — default-provider env parsing


## Adding a Custom Provider

**Step 1** — Create `providers/yourprovider_provider.py`. Copy
`anthropic_provider.py` as a template and implement:

```python
@property
def name(self):
    return "YourProvider (model-name)"

def check_api_key(self):
    # Check env var, call sys.exit(1) with clear message if missing
    ...

def complete(self, prompt, max_tokens=1024, system=None):
    # Send prompt to your API, return response as string
    ...
```

**Step 2** — Register it in `providers/__init__.py`:

```python
from .yourprovider_provider import YourProvider

AVAILABLE_PROVIDERS["3"] = YourProvider
PROVIDER_MENU.append(("3", "Your Provider Name"))
_ALIASES["yourprovider"] = "3"
```

**Step 3** — Add the API key to `config.py`:

```python
YOUR_API_KEY = os.getenv("YOUR_API_KEY", "")
```

**Step 4** — Add the key to `.env`:
```
YOUR_API_KEY=your_key_here
```

Everything else — the teacher call, transformations, GHOST scoring,
correctness checking — works automatically with any provider that
implements `BaseProvider`.


## What Comes Next

1. **Real GHOST scoring** — replace the LLM-reasoning-based ranking with
   actual cross-entropy loss measured on a local proxy student model
2. **Batch evaluation** — see the sibling `SPECTRE_Test/` package for
   running SPECTRE over a dataset of questions and collecting results
3. **PRADA detector integration** — route only suspected-attacker traffic
   through SPECTRE, serving normal users the clean teacher response directly


## Key Design Decisions

**Why the correct answer is always preserved**
A defense that sometimes returns wrong answers to legitimate users is not
deployable. The safety valve guarantees the attacker's response is always
correct — just structurally corrupted.

**Why transformations are independent, not chained**
Each transformation attacks exactly one structural element in isolation.
Chaining them would confound which corruption actually damaged the
student's learning, and would make the correctness check far more likely
to compound errors across steps.

**Why GHOST ranks rather than picks one fixed transformation**
Which transformation is most damaging to learn from depends on the specific
question — chaining logic or a fixed preference order would be less
adaptive than asking the model which pattern here would generalize worst.
