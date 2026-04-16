"""
teacher.py — Single clean teacher call.

Called ONCE per query with a completely normal prompt.
Returns one clean, correct response.
SPECTRE never modifies this call — the teacher never knows any defense is active.
"""

from providers.base_provider import BaseProvider
from config import TEACHER_MAX_TOKENS


def get_teacher_response(question: str, provider: BaseProvider) -> str:
    """
    Ask the teacher model to solve a math problem step by step.

    This is a completely normal, unmodified prompt. No style guidance,
    no special instructions — just a standard math question prompt.

    Args:
        question:  The math problem to solve.
        provider:  Any initialised BaseProvider.

    Returns:
        The teacher's full response as a string, including the #### answer line.
    """
    prompt = (
        "Solve the following math problem step by step. "
        "Show all your working clearly. "
        "On the very last line, write your final numerical answer in this exact format:\n"
        "#### [number]\n\n"
        f"Problem: {question}"
    )

    return provider.complete(prompt, max_tokens=TEACHER_MAX_TOKENS)