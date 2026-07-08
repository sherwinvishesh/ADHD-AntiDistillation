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

The four ADHD laws hold without exception:

1. **The delivered answer is always correct.** Every response ends with the
   teacher's exact `#### N` line.
2. **The output is human-plausible.** A reader sees a careful solver who
   tried a reasonable first approach, caught the mistake against the problem
   statement, and finished correctly.
3. **The parent model is never touched.** SPECTRE is a wrapper; the teacher
   call is a completely normal prompt.
4. **The system fails safe.** If corruption or verification fails, the clean
   teacher response is delivered.


## Why v3 — What ITRO Taught Us

The first ADHD mechanism, ITRO, corrupted the reasoning surface while
preserving the answer, and produced only a 0.6pp accuracy gap in the student.
Its post-mortem (`../ITRO_findings.md`) established three facts that dictate
SPECTRE v3's design:

1. **Only consistent signals get learned.** The correct answer was learned
   because it was consistent across all 2000 training examples; corruption
   that varied from example to example was ignored as noise. A defense that
   picks a *different* corruption per question poisons nothing.
2. **Withholding reasoning is capped by the pretraining floor.** The NoCoT
   arm (answers with no reasoning at all) lost only ~2.6pp, because the
   student (Qwen2.5-0.5B-Instruct) already knows math from pretraining.
   Any transformation that merely denies useful reasoning — reversing it,
   padding it, restating it — cannot beat that bound.
3. **The student copies its last computed value to the `####` line.** At
   evaluation time the student generates its own reasoning and commits to
   whatever value that reasoning produces. This is the one channel through
   which training data can cause damage *below* the pretraining floor:
   install computation habits that derail the student's own chain, and the
   wrong value propagates to its answer.

SPECTRE v3 therefore ships one **composite transformation (T7 — Entangled
False-Start)** applied with an identical structure to every response:

| Slot | Content | Why |
|---|---|---|
| Opening | Fixed first line, identical across the dataset | Consistency anchor — makes the schema maximally learnable |
| False start | The first major computation uses a plausible but wrong operation/formula, worked confidently for 2–4 lines with unit labels | The student gradient-trains on thousands of confident wrong-arithmetic lines in solution position; "begin with the wrong operation" becomes a habit |
| Pivot | Opens with a phrase drawn per-question from a 14-entry pool, at varying depth, and must reference/transform the wrong value rather than restarting | The *recovery* is inconsistent and entangled — there is no clean "now self-correct" macro for the student to learn |
| Correct solution | Values identical to the teacher's, with the largest multiplication computed as repeated addition (≤8 lines) | Dosed brittleness (the T3 mechanism at a plausible, truncation-safe dose) |
| Closing | Fixed sentence stating the answer — the only place the value appears before `####` | No early answer anchor; the only path to the answer runs through the (corrupted) computation chain |

Asymmetric learnability is the whole game: **the poison is consistent, the
antidote is not.** At evaluation time the false-start fires reliably, the
recovery does not, and the student's derailed value lands on its `####` line.


## How The Pipeline Works

### Composite strategy (default — used for dataset generation)

```
Question
    │
    ▼
[1] Teacher Response — one clean, correct answer. Never touched.
    │
    ▼
[2] T7 Entangled False-Start — one API call, fixed corruption schema
    │
    ▼
[3] Poison Verification (free, deterministic)
    ✓ answer_match           #### equals the teacher's ####      (critical)
    ✓ internal_consistency   last body value equals ####          (critical)
    ✓ poison_present         pivot found + wrong intermediate     (critical)
    ✓ no_early_leak          answer value not in early body       (warning)
    ✓ length_ok              body ≤ MAX_RESPONSE_CHARS            (warning)
    ✓ confident_false_start  no hedging before the pivot          (warning)
    Critical failure → ONE retry with feedback → safety valve.
    │
    ▼
[4] Deliver — poisoned response, or clean teacher response (safety valve)
```

Typical cost: **2–3 API calls per query** (teacher + T7, occasionally a
retry). The verification stage is pure string analysis — no API calls.

The `poison_present` check exists because the `#### N` line is appended
programmatically from the teacher response — comparing `####` lines alone is
a tautology that can never fail. ITRO Bug 1 showed how an entire dataset can
silently end up clean while every check passes; verification here confirms
the corruption is *actually in the data*.

### Ensemble strategy (kept for ablations and demos)

The original v2 flow: five independent transformations (T1 Backward
Derivation, T2 Wrong Operation First, T3 Primitive Decomposition, T5
Circular Verification, T6 Formula Error Correction) → GHOST ranking
(worst → best for a student) → correctness walk → deliver. ~7–8 API calls
per query. Useful for per-mechanism ablation studies; not recommended for
dataset generation, because per-question variant selection produces exactly
the inconsistent corruption mixture that ITRO proved students ignore.

Select a strategy with the `-s` flag, the `SPECTRE_STRATEGY` env var, or
leave the default (`composite`).


## Choosing a Provider

| Key | Provider | Notes |
|---|---|---|
| `1` | Anthropic (Claude) | Cloud API, needs `ANTHROPIC_API_KEY` |
| `2` | Gemini | Cloud API, needs `GEMINI_API_KEY` |

The teacher call, transformations, GHOST scoring, and correctness fallbacks
all run through whichever provider you select — no mixing within a run.

**Skipping the menu.** Set `SPECTRE_DEFAULT_PROVIDER` in `.env` to skip the
interactive provider prompt entirely:

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
| `SPECTRE_DEFAULT_PROVIDER` | optional | Skip the provider menu |
| `SPECTRE_STRATEGY` | optional | `composite` (default) or `ensemble` |

**4. Run**
```bash
python main.py
```


## Running Modes

Two output modes, selectable interactively or via CLI flags:

| Mode | Name | What It Shows |
|---|---|---|
| `1` | Full Analysis | Teacher response, variant(s), verification / GHOST ranking, final response |
| `2` | Clean Output | Only the final selected response |

### CLI flag mode

```bash
python main.py -p <provider> -m <mode> -s <strategy> "your question"
```

| Flag | Description |
|---|---|
| `-p` / `--provider` | Provider number (`1`=Anthropic, `2`=Gemini). Defaults to `1`. |
| `-m` / `--mode` | Output mode (`1`=full analysis, `2`=clean output). Defaults to `1`. |
| `-s` / `--strategy` | `composite` (default) or `ensemble` |
| `question` | The math problem to process (positional argument) |

**Examples:**
```bash
python main.py "A store has 48 apples. 24 are sold. How many are left?"
python main.py -p 1 -m 2 "A store has 48 apples. 24 are sold. How many are left?"
python main.py -s ensemble -m 1 "Natalia sold clips to 48 of her friends in April..."
```


## File Structure

```
SPECTRE/
├── main.py                       ← Interactive/CLI entry point
├── pipeline.py                   ← run_pipeline() — composite + ensemble strategies
├── config.py                     ← Keys, models, strategy, verification thresholds
├── teacher.py                    ← Single clean teacher call
├── transformations/
│   ├── __init__.py               ← apply_composite_transformation() + apply_all_transformations()
│   ├── t1_backward_derivation.py
│   ├── t2_wrong_operation_first.py
│   ├── t3_primitive_decomposition.py
│   ├── t5_circular_verification.py
│   ├── t6_formula_error_correction.py
│   └── t7_composite.py           ← Entangled False-Start (the dataset default)
├── ghost_scorer.py                ← GHOST ranking (ensemble strategy only)
├── correctness_checker.py         ← #### comparison + verify_variant() poison checks
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


## Testing

```bash
pip install -r requirements.txt -r requirements-dev.txt
pytest -v
```

The suite (`tests/`) uses a `StubProvider` test double — no real API key or
network access required. It covers:

- `test_teacher.py` — prompt construction, token budget
- `test_composite.py` — pivot-pool determinism, `####` handling, every
  verify_variant check, composite pipeline happy path / retry / safety valve
- `test_ghost_scorer.py` — JSON parsing, fence stripping, fallback ranking
- `test_correctness_checker.py` — numeric extraction, API fallback, fail-closed
- `test_pipeline.py` — both strategies end-to-end, teacher failure, output modes
- `test_providers.py` — registry integrity, alias resolution
- `test_config.py` — env parsing, strategy default, label/registry sync


## Sol Experiment Protocol

Lessons from the ITRO run, encoded as requirements for the SPECTRE
experiment on the cluster:

1. **One format everywhere (ITRO Bug 2).** The exact same chat template must
   be used for dataset generation, student fine-tuning, and evaluation. Any
   mismatch makes results uninterpretable.
2. **Sequence budget (ITRO Bug 3).** T7 responses are length-capped
   (`MAX_RESPONSE_CHARS = 3500` chars ≈ well under 1024 Qwen tokens with the
   question included), and the batch harness reports `avg_response_chars`.
   Verify the student trainer's `MAX_SEQ_LEN` against the actual generated
   lengths before training — a truncated `####` line is a silent
   experiment-killer.
3. **Verify the poison before you spend (ITRO Bug 1).** Run the pre-flight
   audit: generate ~100 examples, require `poison_verified_rate ≥ ~0.95` and
   a low safety-valve rate, and manually read ~10 outputs for plausibility.
   Only then run the full 2000-question generation.
4. **Keep the three-arm design.** Dataset A (clean), Dataset B (SPECTRE
   composite), Dataset C (no-CoT reference). The B-vs-A gap is the headline;
   C locates the pretraining floor and shows whether SPECTRE lands *below*
   it — which is the entire point of v3.


## Key Design Decisions

**Why the correct answer is always preserved**
A defense that sometimes returns wrong answers to legitimate users is not
deployable. The safety valve guarantees the delivered response is always
correct — just structurally toxic to train on.

**Why one fixed schema instead of GHOST picking per question**
ITRO's central finding: students learn what is consistent and ignore what
varies. Per-question adaptive selection — elegant as it sounds — dilutes
each corruption pattern to a fraction of the dataset and hands the student
an easily-ignored mixture. The composite schema makes the corruption itself
as consistent as the answer signal. GHOST and the five independent
transformations remain available (`-s ensemble`) for ablation studies.

**Why the recovery is varied while the false start is fixed**
If the pivot were templated, the student would learn the full ritual
(wrong op → pivot phrase → correct restart) and recover at evaluation time.
Varying the pivot phrase and depth per question, and entangling the
correction with the wrong value, leaves the harmful habit learnable and the
corrective habit not.

**Why wrong arithmetic is allowed in the body**
The ADHD laws require the *final answer* to be correct and the response to
be plausible — and a solver who false-starts, checks against the problem,
and corrects is entirely plausible. The wrong-but-corrected lines are
precisely what pushes a distilled student below its pretraining floor,
which withholding-style corruption provably cannot do (NoCoT lost only
~2.6pp).
