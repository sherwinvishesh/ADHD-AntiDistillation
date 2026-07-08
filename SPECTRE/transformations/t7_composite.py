"""
T7 — Entangled False-Start (Composite)

The primary dataset-generation transformation. One API call produces a
response with a FIXED corruption schema, applied identically to every
question:

    1. Fixed opening line (identical across the whole dataset).
    2. False start — the first major computation uses a plausible but wrong
       operation/formula, worked confidently for 2–4 lines with unit labels.
    3. Pivot — begins with a phrase drawn from a pool (deterministic per
       question), and must reference/transform the wrong value rather than
       restarting cleanly from the problem.
    4. Correct solution — identical values to the original, except the
       largest multiplication is computed as repeated addition (dosed
       primitive decomposition).
    5. Fixed closing sentence stating the answer — the ONLY place the final
       answer value appears before the #### line.

Why it hurts the student (and why T1–T6 individually do not):
    ITRO proved two things. First, only signals that are CONSISTENT across
    the training set get learned — the correct answer was learned because it
    was consistent; per-example-varied corruption was ignored as noise.
    Second, merely withholding useful reasoning is capped by the student's
    pretraining floor (the NoCoT arm lost only ~2.6pp).

    T7 therefore makes the corruption itself consistent: every example
    false-starts in the same slot with the same scaffold, so the student
    gradient-trains on thousands of confident wrong-arithmetic lines in
    solution position and installs "begin with the wrong operation" as a
    habit. The recovery, by contrast, is made UNlearnable: the pivot phrase
    varies per question, its depth varies, and it is entangled with the
    wrong value instead of restarting from the problem — so there is no
    clean "now self-correct" macro to imitate. At evaluation time the
    false-start fires reliably, the recovery does not, the derailed value
    propagates down the student's own autoregressive chain, and the student
    copies its wrong final value to the #### line. That is active damage
    below the pretraining floor — the only mechanism that can beat the
    NoCoT bound.

One API call per transformation.
"""

import hashlib
import re

from providers.base_provider import BaseProvider
from config import COMPOSITE_MAX_TOKENS


# ── Pivot pool ────────────────────────────────────────────────────────────────
# The recovery cue must be impossible to learn as a fixed trigger. Each
# question deterministically draws a different opening phrase (and a different
# false-start depth), so across 2000 examples no single recovery pattern is
# consistent enough for the student to absorb.

PIVOT_STEMS = [
    "Wait —",
    "Hold on:",
    "Hmm, but",
    "Actually, that can't be right:",
    "But checking against the problem,",
    "That number doesn't fit —",
    "On second thought,",
    "Except that",
    "Looking back at the problem,",
    "But that would mean",
    "Something is off here:",
    "Re-reading the problem,",
    "No — that",
    "Careful:",
    "But wait:",
    "Checking this against the problem,",
    "That can't be the answer —",
    "Yet the problem says",
    "This conflicts with the problem:",
    "Double-checking that result:",
]

# False-start depth cycles over 2–4 wrong lines so the pivot position also
# varies from example to example.
_MIN_DEPTH, _MAX_DEPTH = 2, 4

OPENING_LINE = "Let me work through this carefully."


def select_pivot(question: str) -> tuple:
    """
    Deterministically select the pivot stem and false-start depth for a
    question. Stable across runs and machines (md5, not hash()), so dataset
    generation is reproducible and the verifier knows which stem to expect.

    Returns:
        (pivot_stem: str, depth: int)
    """
    h = int(hashlib.md5(question.encode("utf-8")).hexdigest(), 16)
    stem = PIVOT_STEMS[h % len(PIVOT_STEMS)]
    depth = _MIN_DEPTH + (h // len(PIVOT_STEMS)) % (_MAX_DEPTH - _MIN_DEPTH + 1)
    return stem, depth


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

def transform(
    question: str,
    clean_response: str,
    provider: BaseProvider,
    feedback: str = None,
) -> tuple:
    """
    Apply T7 — Entangled False-Start (Composite).

    Args:
        question:        The original math problem.
        clean_response:  The clean teacher response (with #### line).
        provider:        Any initialised BaseProvider.
        feedback:        Optional note describing why a previous attempt
                         failed verification — appended to the prompt so the
                         retry can fix the specific defect.

    Returns:
        (transformed_response: str, is_api_call: bool)
    """
    answer_line = _extract_answer_line(clean_response)
    answer_val_match = re.search(r"####\s*([\d,. ]+)", clean_response)
    answer_val = answer_val_match.group(1).strip() if answer_val_match else "the correct value"

    pivot_stem, depth = select_pivot(question)

    transformation_instructions = f"""\
TRANSFORMATION INSTRUCTIONS — Entangled False-Start:

Rewrite the solution so it follows this EXACT five-part structure, in this
exact order:

PART 1 — OPENING. Your first line must be exactly:
"{OPENING_LINE}"

PART 2 — FALSE START ({depth} lines). Begin solving the problem using a
plausible but WRONG operation or formula for the FIRST major computation.
  - Use the problem's actual numbers.
  - Show the arithmetic explicitly across {depth} lines and state each
    result confidently with a unit label (e.g. "= 2 apples", "= 15 dollars").
  - The arithmetic inside the false start must be computed correctly — it is
    the CHOICE of operation or formula that is wrong, not the calculation.
  - The wrong result must be clearly different from every number that
    appears in the original solution.
  - State the (wrong) approach as if it were the obvious one. Do NOT hedge:
    no "maybe", "perhaps", "might", "I think", and no questions. Do NOT
    acknowledge any problem in this part — the FIRST signal that anything
    is wrong must be the pivot phrase in PART 3, nothing earlier.

PART 3 — PIVOT. Begin the next sentence with exactly this phrase:
"{pivot_stem}"
Then, in that sentence, refer to the wrong value you just computed and
explain — using a specific fact stated in the problem — why that value
cannot be what the problem asks for. The correction must REUSE or CONTRAST
the wrong value directly (e.g. "dividing gave 2 apples, but the 24 apples
were removed from the shelf, so we subtract: 48 − 24 = 24"). Do not
silently restart from scratch.

PART 4 — CORRECT SOLUTION. Continue from the pivot and solve correctly.
Every intermediate value must match the original solution exactly.
Special rule: take the largest multiplication in the correct solution and
compute it as repeated addition, showing at most 8 addition lines (write
"[continuing the pattern...]" if more would be needed, then show the last
line). All other operations stay in normal form. If the correct solution
contains no multiplication, expand its largest division as repeated
subtraction the same way instead.

PART 5 — CLOSING. End with exactly one sentence of this form:
"So the final answer is {answer_val}."
The value {answer_val} must appear NOWHERE else in your rewrite — only in
this closing sentence. Never state, restate, or foreshadow the final answer
earlier in the response.

LENGTH: at most 300 words in total. Write flowing worked-solution prose and
arithmetic lines — no headings, no section labels, no bullet lists."""

    prompt = f"""\
You are applying a structural transformation to a math solution for \
research purposes. The goal is to restructure the reasoning while \
preserving the final answer exactly.

ORIGINAL PROBLEM:
{question}

ORIGINAL SOLUTION TO TRANSFORM:
{clean_response}

{transformation_instructions}

CRITICAL REQUIREMENTS: The final answer must be mathematically identical to \
the original. Every intermediate value in PART 4 must match the original \
solution. The response must read like a careful solver who tried a \
plausible first approach, caught the mistake against the problem statement, \
and finished correctly — a human reader should find nothing artificial.

Do NOT include a #### line in your response. End your response when the \
mathematical reasoning is complete. The #### line will be added separately."""

    if feedback:
        prompt += f"""

NOTE — A previous attempt at this rewrite failed verification for this \
reason: {feedback}
Produce a fresh rewrite that fixes this while following every instruction \
above."""

    raw = provider.complete(prompt, max_tokens=COMPOSITE_MAX_TOKENS)
    cleaned = _strip_answer_line(raw)

    return cleaned + "\n" + answer_line, True
