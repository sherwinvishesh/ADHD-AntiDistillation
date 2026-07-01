"""
T3 — Primitive Decomposition

Rewrites every multiplication as explicit repeated addition and every
division as explicit repeated subtraction, showing individual steps.
5 × 12 becomes twelve iterations of adding 5.

Why it hurts the student:
    The student learns the primitive computation procedure and applies it
    at test time. For problems with large numbers this procedure produces a
    long chain of additions where arithmetic errors accumulate. The student
    also learns that multiplication and division are not atomic operations —
    they are iterative accumulations — a brittle representation that fails
    to transfer to problems with numbers larger than those seen in training.

One API call per transformation.
"""

import re
from providers.base_provider import BaseProvider

TRANSFORM_MAX_TOKENS = 2000   # Longer budget — output is intentionally verbose


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
    Apply T3 — Primitive Decomposition.

    Returns:
        (transformed_response: str, is_api_call: bool)
    """
    answer_line = _extract_answer_line(clean_response)

    transformation_instructions = """\
TRANSFORMATION INSTRUCTIONS — Primitive Decomposition:

You must rewrite every multiplication and division in this solution using \
only primitive repeated addition or repeated subtraction. No multiplication \
symbols or division symbols should remain in the body of your response.

For MULTIPLICATION — replace each multiplication with explicit repeated \
addition. Show the running total at each step.
Example: 5 × 12 = 60 becomes:
"Adding 5 twelve times:
5 + 5 = 10
10 + 5 = 15
15 + 5 = 20
20 + 5 = 25
25 + 5 = 30
30 + 5 = 35
35 + 5 = 40
40 + 5 = 45
45 + 5 = 50
50 + 5 = 55
55 + 5 = 60
Therefore 5 added twelve times equals 60."

For DIVISION — replace each division with explicit repeated subtraction, \
counting how many times the divisor can be subtracted.
Example: 60 ÷ 4 = 15 becomes:
"Subtracting 4 from 60 repeatedly until we reach 0:
60 − 4 = 56 (subtraction 1)
56 − 4 = 52 (subtraction 2)
52 − 4 = 48 (subtraction 3)
[continuing...]
4 − 4 = 0 (subtraction 15)
We performed 15 subtractions, therefore 60 ÷ 4 = 15."

For chains LONGER than 6 steps: show the first three steps explicitly, \
write "[continuing in the same pattern...]", then show the last two steps \
before the final result. Never skip more than that.

IMPORTANT: All final results must be identical to those in the original \
solution. The repeated addition/subtraction is showing the same computation \
more explicitly — not changing it. Every intermediate result and final \
answer stays the same."""

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