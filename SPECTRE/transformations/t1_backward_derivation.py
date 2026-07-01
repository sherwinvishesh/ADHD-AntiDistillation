"""
T1 — Backward Derivation

Rewrites the solution so it flows from answer to premises.
Begins by stating the final answer as already known, then presents
every reasoning step in REVERSE ORDER as confirmation that the answer
must be that value.

Why it hurts the student:
    A student trained on forward reasoning learns: given a problem,
    generate steps, arrive at answer. After training on backward
    derivation, the student has learned the reversed policy: given an
    answer, generate the verification chain. At test time no answer is
    provided as a starting point. The forward policy was never trained.
    The student tries to generate "verification" for nothing and fails.

One API call per transformation.
"""

import re
from providers.base_provider import BaseProvider

TRANSFORM_MAX_TOKENS = 1500


# ── Shared #### helpers ───────────────────────────────────────────────────────

def _extract_answer_line(clean_response: str) -> str:
    """Return the last '#### N' line from the clean response."""
    last = clean_response.rfind("####")
    if last == -1:
        return ""
    eol = clean_response.find("\n", last)
    return clean_response[last:eol].rstrip() if eol != -1 else clean_response[last:].rstrip()


def _strip_answer_line(text: str) -> str:
    """Remove any #### lines the model may have accidentally included."""
    return re.sub(r"\n?####.*$", "", text, flags=re.MULTILINE).rstrip()


# ── Transformation ────────────────────────────────────────────────────────────

def transform(question: str, clean_response: str, provider: BaseProvider) -> tuple:
    """
    Apply T1 — Backward Derivation.

    Returns:
        (transformed_response: str, is_api_call: bool)
    """
    answer_line = _extract_answer_line(clean_response)

    # Extract just the answer value for the opening sentence
    answer_val_match = re.search(r"####\s*([\d,. ]+)", clean_response)
    answer_val = answer_val_match.group(1).strip() if answer_val_match else "the correct value"

    transformation_instructions = f"""\
TRANSFORMATION INSTRUCTIONS — Backward Derivation:

You must rewrite this solution so that it flows BACKWARD — from the known
answer to the premises — rather than forward from premises to answer.

Step 1: Begin with exactly this sentence (fill in the answer value):
"The answer to this problem is {answer_val}. The following derivation \
confirms why this must be so."

Step 2: Present EVERY reasoning step from the original solution in \
REVERSE CHRONOLOGICAL ORDER. The last step of the original becomes your \
first verification step. The first step of the original becomes your last.

Step 3: Reframe each step as confirmation, not discovery. Instead of \
"John earns 120 dollars", write "This confirms that 120 dollars is \
consistent with what we know about John's earnings." Instead of \
"therefore 36 apples were sold", write "The fact that 36 apples were sold \
is consistent with our answer, as we can verify."

Step 4: Every number and every arithmetic result must be preserved exactly \
as it appears in the original. Do not change any values.

Step 5: The response must read like a legitimate "verify by working \
backward" solution — the kind a student would write if they already knew \
the answer from an answer key and were confirming each step is consistent \
with it."""

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