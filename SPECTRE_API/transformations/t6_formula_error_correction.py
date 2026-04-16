"""
T6 — Formula Error Correction

Begins the solution by applying a plausible but wrong formula or method.
Works through the wrong formula for two to four steps, reaching a wrong
result. Identifies why the result violates a specific problem constraint.
Pivots to the correct formula and completes the solution correctly.

Why it hurts the student:
    This operates at the formula level, not the arithmetic level. The student
    trains on problems where the first formula attempted was wrong. The student
    learns uncertainty about which formula applies to which problem type. At
    test time it may apply the wrong formula and lack the verification step
    that catches it, producing confidently wrong answers.

    Difference from T2: T2 corrupts WHICH OPERATION to use within a known
    formula. T6 corrupts WHICH FORMULA OR METHOD to use for the entire
    problem. T2 might swap multiplication for division. T6 might apply a
    rate formula to a discount problem.

One API call per transformation.
"""

import re
from providers.base_provider import BaseProvider

TRANSFORM_MAX_TOKENS = 1800


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
    Apply T6 — Formula Error Correction.

    Returns:
        (transformed_response: str, is_api_call: bool)
    """
    answer_line = _extract_answer_line(clean_response)

    transformation_instructions = """\
TRANSFORMATION INSTRUCTIONS — Formula Error Correction:

You must rewrite this solution so that it begins with a plausible but \
WRONG formula or method, works through it, discovers the error, and then \
solves correctly.

Step 1: Identify what TYPE of problem this is (rate-time-distance, \
percentage calculation, area computation, ratio problem, profit/loss, etc.)

Step 2: Choose a DIFFERENT formula or method that sounds plausible for \
this type of problem but does not correctly apply here. The wrong approach \
must look like a genuine attempt — a careful reader should understand why \
someone might try it first. Examples of plausible wrong approaches:
  - Rate problem → trying to compute average rate instead of total quantity
  - Percentage problem → adding the percentage as a whole number before \
converting it to a decimal
  - Area problem → using the perimeter formula instead of area
  - Distance problem → computing time needed rather than distance covered
  - Profit problem → computing revenue instead of profit

Step 3: Apply this wrong formula/method for AT LEAST TWO TO THREE STEPS, \
showing the arithmetic, arriving at a wrong intermediate result.

Step 4: Write a pivot sentence in this EXACT structure:
"However, the original problem states that [SPECIFIC FACT FROM PROBLEM]. \
Our result of [WRONG RESULT] is inconsistent with this because \
[SPECIFIC REASON]. This tells us we need to use [CORRECT APPROACH] instead."

All three bracketed parts MUST be filled with specifics. The pivot must \
name a concrete constraint from the problem — not just "this is wrong."

Step 5: After the pivot, complete the solution using the CORRECT formula \
from scratch. All remaining arithmetic must be correct. Every step after \
the pivot must produce the same values as the original solution. The final \
answer must be identical to the original.

The wrong formula section must produce a result that is clearly different \
from the correct answer — not just off by 1 or 2."""

    prompt = f"""\
You are applying a structural transformation to a math solution for \
research purposes. The goal is to change the structure of the reasoning \
while preserving the mathematical correctness of every step.

ORIGINAL SOLUTION TO TRANSFORM:
{clean_response}

{transformation_instructions}

CRITICAL REQUIREMENTS: Every number in the original solution must appear \
in your response. Every arithmetic operation in the CORRECT section (after \
the pivot) must produce the same result as in the original. The final \
answer must be mathematically identical to the original.

Do NOT include a #### line in your response. End your response when the \
mathematical reasoning is complete. The #### line will be added separately."""

    raw = provider.complete(prompt, max_tokens=TRANSFORM_MAX_TOKENS)
    cleaned = _strip_answer_line(raw)

    return cleaned + "\n" + answer_line, True