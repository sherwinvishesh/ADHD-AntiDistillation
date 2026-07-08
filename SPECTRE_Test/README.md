# SPECTRE_Test

A thin batch-testing harness for [`SPECTRE`](../SPECTRE/README.md). It
imports `SPECTRE` as-is — no pipeline logic of its own — lets you pick a
provider and a dataset, runs every question through the full 5-stage SPECTRE
pipeline, and writes the results to a JSON file.

## What This Is

`SPECTRE/` is the pipeline; `SPECTRE_Test/` is a batch runner on top of it.
All the actual logic (teacher call, the five transformations, GHOST scoring,
correctness checking) lives in `SPECTRE/` and is used unmodified here via
`import SPECTRE`.


## Requirements

```bash
pip install -r requirements.txt
```

This installs everything in `../SPECTRE/requirements.txt` (the cloud
provider SDKs) plus `tqdm` for the progress bar and `colorama` for the
menus.


## Setup

**Real API keys live in `../SPECTRE/.env`** — `SPECTRE`'s own `config.py`
loads them independently of where it's imported from, so you don't need to
duplicate secrets here.

`SPECTRE_Test/.env` only controls the *default provider for this harness*
(which can differ from `SPECTRE`'s own default):

```bash
cp .env.example .env
```

```
SPECTRE_DEFAULT_PROVIDER=claude
```

Leave it blank to be prompted for a provider each run.


## Usage

```bash
python main.py
```

This walks you through:
1. **Provider selection** — skipped if `SPECTRE_DEFAULT_PROVIDER` is set in
   `SPECTRE_Test/.env`; otherwise shows the same numbered menu as `SPECTRE`.
2. **Dataset selection** — lists every `*.json` file in `datasets/`, plus an
   option to type a filename or path. A bare filename (e.g.
   `test_dataset.json`) is resolved against `datasets/` automatically, so
   you don't need to type the full path.
3. **Answer detail** — choose **Detailed** (full pipeline breakdown per
   question: clean teacher response, GHOST ranking + reasoning, selected
   variant, correctness attempts, safety-valve flag) or **Simple** (just the
   question and the final answer, one block per question).
4. **Batch run** — every question in the dataset runs through
   `SPECTRE.run_pipeline(question, provider, mode="clean")` with a progress
   bar. Per-question pipeline failures are recorded as errors rather than
   crashing the whole batch.
5. **Output** — writes `<dataset_stem>_spectre_answers.json` next to the
   input dataset (i.e. in `datasets/`) and prints a summary (safety-valve
   trigger rate, average correctness-check attempts, error count).

Non-interactive / scripting usage:
```bash
python main.py -p claude -d test_dataset.json --detail simple
```

| Flag | Description |
|---|---|
| `-p` / `--provider` | Provider key/name (`1`/`2`, `claude`, `gemini`) |
| `-d` / `--dataset` | Dataset filename (looked up in `datasets/`) or a full path |
| `--detail` | `detailed`/`1` (full pipeline breakdown) or `simple`/`2` (question + answer only) |
| `--limit` | Only process the first N questions — useful for a quick smoke test before committing to a large run |
| `-s` / `--strategy` | `composite` (T7 fixed schema — the dataset-generation default) or `ensemble` (5 variants + GHOST). Omit to use SPECTRE's config default. |


## Pre-Flight Audit (do this before any full dataset run)

ITRO Bug 1 taught us that a poisoning pipeline can silently deliver clean
data while every check passes. Before burning API budget and cluster time on
a full 2000-question generation:

1. **Generate a sample:** `python main.py -p claude -d <dataset>.json --limit 100 --detail detailed`
2. **Check the summary:** `poison_verified_rate` should be ≥ ~0.95 and
   `safety_valve_trigger_rate` low. Every safety-valve row delivered a
   *clean* teacher response — those rows contain no poison at all.
3. **Check lengths:** `avg_response_chars` must sit comfortably under the
   student trainer's sequence budget (a truncated `####` line silently
   destroys the training signal — ITRO Bug 3).
4. **Read ~10 outputs yourself.** Each should read like a careful solver who
   false-started once, corrected against a specific fact from the problem,
   and finished correctly. If a human finds it artificial, the plausibility
   law is being violated.

Only after all four pass should you run the full generation.


## Dataset Schema

A dataset is a JSON list of objects. Each object needs a question under one
of these keys, checked in order: `input` → `question` → `prompt`. A bundled
sample, `datasets/test_dataset.json`, ships with 5 GSM8K-style grade-school
math word problems:

```json
[
  {"input": "Natalia sold clips to 48 of her friends in April, and then she sold half as many clips in May. How many clips did Natalia sell altogether in April and May?"},
  {"input": "Weng earns $12 an hour for babysitting. Yesterday, she just did 50 minutes of babysitting. How much did she earn?"},
  ...
]
```

Extra keys are ignored — only the question text is read. If a question
under `input` happens to be prefixed with a literal `"Question: "` (as in
GSM8K-style datasets), that prefix is stripped automatically.


## Output Schema

`<dataset_stem>_spectre_answers.json` is written next to the input dataset
(e.g. `datasets/test_dataset_spectre_answers.json`). The `summary` block is
always the same shape; the shape of each entry in `results` depends on
which answer detail you chose.

**Detailed** — full pipeline breakdown per question:

```json
{
  "summary": {
    "provider": "Anthropic Claude (claude-sonnet-4-6)",
    "dataset": "test_dataset.json",
    "strategy": "composite",
    "count": 5,
    "errors": 0,
    "safety_valve_trigger_rate": 0.0,
    "avg_attempts": 1.2,
    "poison_verified_rate": 1.0,
    "avg_response_chars": 1480.6
  },
  "results": [
    {
      "question": "Natalia sold clips to 48 of her friends in April, and then she sold half as many clips in May. How many clips did Natalia sell altogether in April and May?",
      "strategy": "composite",
      "clean_response": "...",
      "ranking": ["T7"],
      "ghost_reasoning": null,
      "selected_variant_id": "T7",
      "selected_variant_name": "Entangled False-Start (Composite)",
      "attempts": 1,
      "safety_valve_triggered": false,
      "verification": {
        "answer_match": true,
        "internal_consistency": true,
        "poison_present": true,
        "no_early_leak": true,
        "length_ok": true,
        "confident_false_start": true,
        "passed": true,
        "warnings": []
      },
      "response_chars": 1466,
      "final_response": "..."
    },
    ...
  ]
}
```

With `-s ensemble`, `ranking`/`ghost_reasoning` carry the GHOST output as in
v2 and `verification` is `null` (`poison_verified_rate` is then `null` in the
summary — the ensemble path has no structural poison verifier).

`poison_verified_rate` counts rows whose *delivered* response passed all
critical poison checks; safety-valve rows (clean response delivered) count
against it. `avg_response_chars` is the mean length of delivered responses —
check it against the student trainer's sequence budget before training.

**Simple** — just the question and the final answer, one block per question:

```json
{
  "summary": { "...": "same shape as above" },
  "results": [
    {
      "question": "Natalia sold clips to 48 of her friends in April, and then she sold half as many clips in May. How many clips did Natalia sell altogether in April and May?",
      "answer": "..."
    },
    ...
  ]
}
```

A row with a pipeline failure looks like `{"question": "...", "error":
"pipeline_failed"}` in either mode, and is excluded from `avg_attempts` /
`safety_valve_trigger_rate` (both computed over successfully-scored rows,
which are still tracked internally even in Simple mode).


## Example Run

```bash
$ python main.py -p claude -d test_dataset.json --detail simple

  SPECTRE_Test — batch evaluation harness
  ...
  ✓ Anthropic Claude (claude-sonnet-4-6) — ready.
  Dataset: test_dataset.json

Running SPECTRE pipeline: 100%|████████████| 5/5 [00:41<00:00,  8.3s/q]

  SUMMARY
    provider                    : Anthropic Claude (claude-sonnet-4-6)
    dataset                     : test_dataset.json
    count                       : 5
    errors                      : 0
    safety_valve_trigger_rate   : 0.0
    avg_attempts                : 1.4

  Wrote /path/to/SPECTRE_Test/datasets/test_dataset_spectre_answers.json
```
