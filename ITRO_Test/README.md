# ITRO_Test

A thin batch-testing harness for [`ITRO`](../ITRO/README.md). It imports
`ITRO` as-is — no pipeline logic of its own — lets you pick a provider and a
dataset, runs every question through the full 5-stage ITRO pipeline, and
writes the results to a JSON file.

## What This Is

`ITRO/` is the pipeline; `ITRO_Test/` is a batch runner on top of it. All the
actual reasoning-obfuscation logic (domain detection, τ scoring, ITRO
obfuscation, correctness checking) lives in `ITRO/` and is used unmodified
here via `import ITRO`.


## Requirements

```bash
pip install -r requirements.txt
```

This installs everything in `../ITRO/requirements.txt` (the cloud provider
SDKs) plus `tqdm` for the progress bar. If you want to run against the local
Qwen provider, also install `../ITRO/requirements-local.txt`.


## Setup

**Real API keys / `QWEN_MODEL_PATH` live in `../ITRO/.env`** — `ITRO`'s own
`config.py` loads them independently of where it's imported from, so you
don't need to duplicate secrets here.

`ITRO_Test/.env` only controls the *default provider for this harness*
(which can differ from `ITRO`'s own default):

```bash
cp .env.example .env
```

```
ITRO_DEFAULT_PROVIDER=claude
```

Leave it blank to be prompted for a provider each run.


## Usage

```bash
python main.py
```

This walks you through:
1. **Provider selection** — skipped if `ITRO_DEFAULT_PROVIDER` is set in
   `ITRO_Test/.env`; otherwise shows the same numbered menu as `ITRO`.
2. **Dataset selection** — lists every `*.json` file in `datasets/`, plus an
   option to type a filename or path. A bare filename (e.g.
   `test_dataset.json`) is resolved against `datasets/` automatically, so
   you don't need to type the full path.
3. **Answer detail** — choose **Detailed** (full pipeline breakdown per
   question: domain, τ, real response, obfuscated response, correctness
   check) or **Simple** (just the question and the final answer, one block
   per question).
4. **Batch run** — every question in the dataset runs through
   `ITRO.run_pipeline(question, provider, mode="clean")` with a progress bar.
   Per-question pipeline failures are recorded as errors rather than
   crashing the whole batch.
5. **Output** — writes `<dataset_stem>_itro_answers.json` next to the input
   dataset (i.e. in `datasets/`) and prints a summary (safety-valve trigger
   rate, average τ, error count).

Non-interactive / scripting usage:
```bash
python main.py -p claude -d test_dataset.json --detail simple
```

| Flag | Description |
|---|---|
| `-p` / `--provider` | Provider key/name (`1`/`2`/`3`, `claude`, `gemini`, `qwen`, ...) |
| `-d` / `--dataset` | Dataset filename (looked up in `datasets/`) or a full path |
| `--detail` | `detailed`/`1` (full pipeline breakdown) or `simple`/`2` (question + answer only) |
| `--limit` | Only process the first N questions — useful for a quick smoke test before committing to a large run |


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

`<dataset_stem>_itro_answers.json` is written next to the input dataset
(e.g. `datasets/test_dataset_itro_answers.json`). The `summary` block is
always the same shape; the shape of each entry in `results` depends on
which answer detail you chose.

**Detailed** — full pipeline breakdown per question:

```json
{
  "summary": {
    "provider": "Anthropic (claude-sonnet-4-6)",
    "dataset": "test_dataset.json",
    "count": 5,
    "errors": 0,
    "safety_valve_trigger_rate": 0.0,
    "avg_tau": 0.31
  },
  "results": [
    {
      "question": "Natalia sold clips to 48 of her friends in April, and then she sold half as many clips in May. How many clips did Natalia sell altogether in April and May?",
      "real_response": "...",
      "domain": "math_computation",
      "tau": 0.42,
      "obfuscated_response": "...",
      "final_response": "...",
      "correctness_pass": true
    },
    ...
  ]
}
```

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
"pipeline_failed"}` in either mode, and is excluded from `avg_tau` /
`safety_valve_trigger_rate` (both computed over successfully-scored rows,
which are still tracked internally even in Simple mode).


## Example Run

```bash
$ python main.py -p claude -d test_dataset.json --detail simple

  ITRO_Test — batch evaluation harness
  ...
  ✓ Anthropic (claude-sonnet-4-6) — ready.
  Dataset: test_dataset.json

Running ITRO pipeline: 100%|████████████| 5/5 [00:23<00:00,  4.7s/q]

  SUMMARY
    provider                    : Anthropic (claude-sonnet-4-6)
    dataset                     : test_dataset.json
    count                       : 5
    errors                      : 0
    safety_valve_trigger_rate   : 0.0
    avg_tau                     : 0.31

  Wrote /path/to/ITRO_Test/datasets/test_dataset_itro_answers.json
```
