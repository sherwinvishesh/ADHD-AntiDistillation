# Security Policy

## Scope

ADHD is a research prototype for studying anti-distillation response
transformation, **not** a production security product. Two different
kinds of "security" issue can come up in this repo, and they're handled
differently:

1. **Ordinary code vulnerabilities** — e.g. unsafe handling of API keys,
   injection risks in a provider integration, a dependency with a known
   CVE, or code that could execute untrusted input unsafely. Please
   report these privately (see below).

2. **Weaknesses in the ITRO / SPECTRE defense mechanisms themselves** —
   e.g. ways to bypass the verifier, sanitize a defended response back
   toward the clean trace, or otherwise defeat the obfuscation. These are
   **not** private vulnerabilities to disclose. They're the actual
   research question. The [Limitations](Readme.md#limitations) and
   [Verification and fail-safe design](Readme.md#verification-and-fail-safe-design)
   sections of the Readme already document several known weaknesses
   (including a worked failure case). If you find a new one, please open
   a public issue or, better, a pull request with a test case — that's a
   contribution to the research, not a security report.

## Reporting a vulnerability (category 1)

Please do **not** open a public issue for an ordinary code
vulnerability. Instead, email **sjathann@asu.edu** with:

- A description of the issue and its potential impact
- Steps to reproduce, or a proof of concept if applicable
- The affected phase (ITRO or SPECTRE) and file(s)

This is a single-maintainer research project, so response times are
best-effort — expect an acknowledgment within a few days. Please allow a
reasonable amount of time to address the issue before any public
disclosure.

## Supported scope

There are no released versions; only the `main` branch is maintained.
Security fixes, when applicable, land there.

## Out of scope

- The intentional use of deceptive/obfuscated reasoning traces by the
  ITRO and SPECTRE transformers is the subject of the research, not a
  vulnerability.
- Findings about the semantic-verification gaps already documented in
  the Readme (e.g. the Natalia clips failure case) are known and
  written up; no need to report them privately.
