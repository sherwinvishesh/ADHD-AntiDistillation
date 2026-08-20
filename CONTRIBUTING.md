# Contributing to ADHD

ADHD is a research prototype, not a production library, but issues, fixes,
and replication work are welcome. This document covers how the repo is
laid out and how to get a change in.

## Before you start

For anything beyond a small fix (a typo, a broken link, an obvious bug),
please open an issue first to discuss the change. This project's value is
mostly in the empirical record described in [`Readme.md`](Readme.md),
[`idea.md`](idea.md), and [`results.md`](results.md) — changes that touch
the transformation logic, the verifier contracts, or the reported numbers
should be discussed before a PR is written, so the historical results stay
correctly labeled as historical.

## Project layout

Both phases are standalone Python packages with their own dependencies:

```text
ITRO/     Phase I  — Inference-Time Reasoning Obfuscation
SPECTRE/  Phase II — Structural Poisoning via Empirical Corruption of Training Representations
ITRO_Test/, SPECTRE_Test/   Small demonstration datasets and batch harnesses
website/  The project's GitHub Pages site
```

See [`ITRO/README.md`](ITRO/README.md) and [`SPECTRE/README.md`](SPECTRE/README.md)
for provider configuration and CLI details of each phase.

## Development setup

```bash
git clone https://github.com/sherwinvishesh/ADHD-AntiDistillation.git
cd ADHD-AntiDistillation

cd ITRO      # or SPECTRE
pip install -r requirements.txt
pip install -r requirements-dev.txt
cp .env.example .env   # add ANTHROPIC_API_KEY or GEMINI_API_KEY
```

## Running tests

```bash
cd ITRO    && pytest
cd SPECTRE && pytest
```

Please add or update tests for any change to `pipeline.py`,
`correctness_checker.py`, `tau_system.py`, `domain_detector.py`, or the
`transformations/` modules — these are the parts of the codebase the
paper's claims depend on.

## Making a change

1. Fork the repo and create a branch from `main`.
2. Keep the change scoped — one fix or feature per pull request.
3. Run the relevant test suite(s) locally before opening the PR.
4. Write a commit message that explains *why*, not just *what*.
5. Open a pull request using the provided template.

## Reporting bugs

Use the **Bug report** issue template. Include the phase (ITRO or
SPECTRE), the provider you were using (Anthropic / Gemini / local Qwen),
and, if relevant, whether the issue affects generation, verification, or
the reported metrics.

## Security issues

Do not open a public issue for a security-relevant bug (e.g. one that
would let a defended response leak the clean answer, or bypass the
verifier's blocking checks). See [`SECURITY.md`](SECURITY.md) instead.

## Code style

- Match the existing style in the file you're editing rather than
  introducing a new one.
- Prefer small, direct functions over new abstractions — this is a
  research codebase, not a framework.
- No inline secrets, API keys, or local file paths in committed code.

## License

By contributing, you agree that your contributions will be licensed
under the project's [Apache License 2.0](LICENSE).
