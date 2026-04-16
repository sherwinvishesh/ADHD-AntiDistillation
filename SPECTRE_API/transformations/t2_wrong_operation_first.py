"""
T2 — Wrong Operation First

Begins the solution by applying the wrong mathematical operation to the
main computation. Works through two or three steps with the wrong
operation, gets a wrong intermediate result, then recognises the error
and pivots to the correct operation. Completes the solution correctly.

Why it hurts the student:
    The student trains on 2000 examples where the initial instinct was the
    wrong operation. The student learns that for this class of problem, the
    first thing to try is the wrong operation. At test time it applies the
    wrong operation first. For a 0.5B model, the self-correction logic that
    follows in training may not fire reliably during inference, causing the
    model to commit to the wrong operation and produce a wrong answer.

One API call per transformation.
"""

import re
from providers.base_provider import BaseProvider

TRANSFORM_MAX_TOKENS = 1500


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
    Apply T2 — Wrong Operation First.

    Returns:
        (transformed_response: str, is_api_call: bool)
    """
    answer_line = _extract_answer_line(clean_response)

    transformation_instructions = """\
TRANSFORMATION INSTRUCTIONS — Wrong Operation First:

You must rewrite this solution so that it begins by applying the WRONG \
mathematical operation to the main computation, then corrects itself.

Step 1: Identify the single most important arithmetic operation in the \
solution — the one that produces the key intermediate result driving the \
final answer. (Usually the first major multiplication, division, addition, \
or subtraction.)

Step 2: Begin the solution by applying the OPPOSITE operation:
  - If the correct operation is multiplication → start with division
  - If the correct operation is addition → start with subtraction
  - If the correct operation is division → start with multiplication
  - If the correct operation is subtraction → start with addition

Work through AT LEAST TWO LINES using this wrong operation, showing the \
arithmetic, and arriving at a wrong intermediate result.

Step 3: After the wrong steps, write a pivot sentence in this exact form:
"However, examining the problem constraints, this result does not satisfy \
[SPECIFIC THING FROM THE PROBLEM]. The correct operation here is \
[CORRECT OPERATION NAME]."

The bracketed parts MUST be filled in with specific details from the \
problem. The pivot MUST name a concrete reason drawn from the problem \
context — not just "this is wrong." For example: "However, the problem \
states that John earns 15 dollars PER HOUR, meaning each hour adds to the \
total — this is repeated addition, not repeated removal. The correct \
operation here is multiplication."

Step 4: After the pivot, complete the solution correctly from that point \
forward. Every step after the pivot must use the correct operation. All \
arithmetic must be correct. The final answer must be identical to the \
original.

Step 5: The wrong section must be at least 2 lines long and must produce a \
clearly different intermediate result than the correct calculation would."""

    prompt = f"""\
You are applying a structural transformation to a math solution for \
research purposes. The goal is to change the structure of the reasoning \
while preserving the mathematical correctness of every step.

ORIGINAL SOLUTION TO TRANSFORM:
{clean_response}

{transformation_instructions}

CRITICAL REQUIREMENTS: Every number in the original solution must appear \
in your response. Every arithmetic operation in the CORRECT section must \
produce the same result as in the original. The final answer must be \
mathematically identical to the original.

Do NOT include a #### line in your response. End your response when the \
mathematical reasoning is complete. The #### line will be added separately."""

    raw = provider.complete(prompt, max_tokens=TRANSFORM_MAX_TOKENS)
    cleaned = _strip_answer_line(raw)

    return cleaned + "\n" + answer_line, True