"""
T5 — Circular Verification

Solves the problem completely and correctly first, then adds a full second
section that re-derives the same answer from scratch using a different
arithmetic path, and ends by confirming both methods agree.

Why it hurts the student:
    The student trains on 2000 examples where every solution is followed by
    a complete second verification pass. The student learns that a solution
    is not complete until it has been verified by a second method. At test
    time the student either attempts two full derivation passes (doubling
    compute and error probability), or it learns a broken generation pattern
    where it terminates the first section prematurely while waiting to start
    the second. Either way, generalisation is damaged.

One API call per transformation.
"""

import re
from providers.base_provider import BaseProvider

TRANSFORM_MAX_TOKENS = 2000   # Two full derivations — needs extra budget


def _extract_answer_line(clean_response: str) -> str:
    last = clean_response.rfind("####")
    if last == -1:
        return ""
    eol = clean_response.find("\n", last)
    return clean_response[last:eol].rstrip() if eol != -1 else clean_response[last:].rstrip()


def _strip_answer_line(text: str) -> str:
    return re.sub(r"\n?####.*$", "", text, flags=re.MULTILINE).rstrip()


def transform(question: str, clean_response: str, provider: BaseProvider) -> tuple:
    """
    Apply T5 — Circular Verification.

    Returns:
        (transformed_response: str, is_api_call: bool)
    """
    answer_line = _extract_answer_line(clean_response)
    answer_val_match = re.search(r"####\s*([\d,. ]+)", clean_response)
    answer_val = answer_val_match.group(1).strip() if answer_val_match else "the answer"

    transformation_instructions = f"""\
TRANSFORMATION INSTRUCTIONS — Circular Verification:

You must produce TWO complete, separate derivations of the answer, one \
after the other. Both must arrive at the same final answer value: {answer_val}.

SECTION 1 — Primary Solution:
Write the original solution EXACTLY as it appears. Do not change a single \
number, step, or word in this section. Every line from the original must \
appear here verbatim.

After the complete original solution, add this separator line on its own:
"Verification using an alternative method:"

SECTION 2 — Alternative Derivation:
Write a COMPLETE second solution to the same problem that:
  (a) Uses a genuinely different computation order or different grouping \
of operations than Section 1. Not just the same steps reworded — the \
intermediate values must be different.
  (b) Arrives at the identical final answer: {answer_val}.

Examples of genuinely different paths:
  - If Section 1 computed (price × quantity) then subtracted discount, \
Section 2 computes (price − discount_per_unit) then multiplies by quantity.
  - If Section 1 computed total earnings then subtracted expenses, \
Section 2 first computes savings rate then applies it to earnings.
  - If Section 1 solved directly, Section 2 might use a proportion or \
fraction approach.

After Section 2 is complete, write this confirmation sentence:
"Both methods confirm the answer is {answer_val}, which validates our \
solution."

The two sections MUST produce different intermediate values. If your \
Section 2 produces exactly the same intermediate values as Section 1, \
revise it until it does not."""

    prompt = f"""\
You are applying a structural transformation to a math solution for \
research purposes. The goal is to change the structure of the reasoning \
while preserving the mathematical correctness of every step.

ORIGINAL SOLUTION TO TRANSFORM:
{clean_response}

{transformation_instructions}

CRITICAL REQUIREMENTS: Every number in the original solution must appear \
in your response. Every arithmetic operation must produce the same result \
as in the original. The final answer must be mathematically identical to \
the original.

Do NOT include a #### line in your response. End your response when the \
mathematical reasoning is complete. The #### line will be added separately."""

    raw = provider.complete(prompt, max_tokens=TRANSFORM_MAX_TOKENS)
    cleaned = _strip_answer_line(raw)

    return cleaned + "\n" + answer_line, True