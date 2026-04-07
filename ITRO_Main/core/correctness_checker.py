# Domain-aware correctness checking for all 8 ITRO domains.
#
# Each domain has a targeted extraction prompt that asks the LLM
# to pull out exactly the thing ITRO is NOT supposed to corrupt
# (the final answer/conclusion), so we can verify it was preserved.
#
# Extraction strategy by domain:
#   math_computation  → final numerical answer
#   math_proof        → the theorem/statement being proved + QED conclusion
#   code              → what the function returns / its behavior contract
#   scientific        → the causal conclusion (what causes what)
#   logical_argument  → the logical conclusion
#   factual_recall    → the core fact stated
#   procedural        → the end result / goal achieved by the steps
#   analytical        → the main recommendation or conclusion

# ─────────────────────────────────────────────────────────────
# EXTRACTION PROMPTS
# Each prompt is designed to pull exactly the answer component —
# the part ITRO must preserve — from a potentially verbose response.
# ─────────────────────────────────────────────────────────────

EXTRACTION_PROMPTS = {

    "math_computation": (
        "From this math solution, what is the FINAL numerical answer? "
        "Reply with ONLY the number. No units, no words, no explanation. "
        "If the answer is a fraction or expression, write it exactly. "
        "Just the number or expression.\n\n"
        "Solution:\n{text}\n\nFinal numerical answer:",
        25
    ),

    "math_proof": (
        "This text contains a mathematical proof. "
        "What is the STATEMENT being proved (the theorem or proposition)? "
        "Then what is the final conclusion of the proof? "
        "Reply in at most two sentences: first the statement, "
        "then the conclusion.\n\n"
        "Proof:\n{text}\n\nStatement and conclusion:",
        80
    ),

    "code": (
        None,   # prompt built inline in _extract — see special case below
        60
    ),

    "scientific": (
        "This text contains a scientific explanation. "
        "What is the CAUSAL CONCLUSION — what causes what, or how does "
        "the mechanism work? State only the final correct causal claim "
        "in one sentence.\n\n"
        "Explanation:\n{text}\n\nCausal conclusion (one sentence):",
        70
    ),

    "logical_argument": (
        "This text contains a logical argument. "
        "What is the FINAL CONCLUSION of the argument? "
        "State only the conclusion, not the premises or reasoning. "
        "One sentence maximum.\n\n"
        "Argument:\n{text}\n\nFinal conclusion:",
        60
    ),

    "factual_recall": (
        "This text answers a factual question. "
        "What is the CORE FACT being stated? "
        "One short sentence — just the fact, no qualifications.\n\n"
        "Response:\n{text}\n\nCore fact:",
        50
    ),

    "procedural": (
        "This text describes a procedure or set of steps. "
        "What is the GOAL or END RESULT that following these steps achieves? "
        "One sentence.\n\n"
        "Procedure:\n{text}\n\nEnd result/goal:",
        60
    ),

    "analytical": (
        "This text contains an analysis or comparison. "
        "What is the MAIN CONCLUSION or RECOMMENDATION? "
        "If there are multiple conclusions, list them in one sentence each. "
        "Do not include reasoning, only conclusions.\n\n"
        "Analysis:\n{text}\n\nMain conclusion(s):",
        80
    ),
}

# ─────────────────────────────────────────────────────────────
# SIMILARITY THRESHOLDS
# Different domains need different thresholds because the
# extracted "answer" has different natural variance in wording.
# Math answers are exact; analytical conclusions may be paraphrased.
# ─────────────────────────────────────────────────────────────

SIMILARITY_THRESHOLDS = {
    "math_computation":  None,    # Exact match (numbers don't paraphrase)
    "math_proof":        0.65,    # Theorem statements can be worded differently
    "code":              0.60,    # Behavior descriptions vary in wording
    "scientific":        0.62,    # Causal conclusions allow some rewording
    "logical_argument":  0.68,    # Conclusions should be fairly consistent
    "factual_recall":    0.70,    # Core facts should match closely
    "procedural":        0.58,    # Goal statements vary widely
    "analytical":        0.55,    # Conclusions can be expressed very differently
}


# ─────────────────────────────────────────────────────────────
# EXTRACTION HELPER
# ─────────────────────────────────────────────────────────────

def _extract(response_text, domain, provider):
    """
    Extract the answer component from a response using the
    domain-appropriate extraction prompt.

    Returns the extracted string, or "extraction_failed" on error.
    """
    if domain not in EXTRACTION_PROMPTS:
        domain = "factual_recall"

    prompt_template, max_tokens = EXTRACTION_PROMPTS[domain]

    # Format the prompt — handle the code domain's text slicing
    try:
        if domain == "code":
            prompt = (
                "This text contains code or a coding explanation. "
                "In one sentence, what does the function/code DO — "
                "what input does it take and what output or result does it produce? "
                "Focus only on the behavior contract, not implementation details.\n\n"
                f"Code:\n{response_text[:800]}\n\nBehavior (one sentence):"
            )
        else:
            prompt = prompt_template.format(text=response_text[:1200])
    except Exception:
        prompt = prompt_template.format(text=response_text[:1200])

    try:
        result = provider.call(prompt, max_tokens=max_tokens)
        return result.strip()
    except Exception as e:
        return f"extraction_failed: {e}"


# ─────────────────────────────────────────────────────────────
# WORD OVERLAP SIMILARITY
# Simple, fast, no dependencies.
# For short extracted answers (1-2 sentences) this is sufficient.
# ─────────────────────────────────────────────────────────────

# Words that don't contribute to semantic meaning
_STOPWORDS = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been",
    "being", "have", "has", "had", "do", "does", "did", "will",
    "would", "could", "should", "may", "might", "shall", "can",
    "to", "of", "in", "on", "at", "by", "for", "with", "from",
    "that", "this", "it", "its", "which", "who", "what", "how",
    "and", "or", "but", "not", "no", "so", "if", "then", "as",
    "we", "they", "their", "our", "your", "his", "her", "also",
    "therefore", "thus", "hence", "conclude", "conclusion",
    "follows", "result", "answer", "final", "given", "since",
}

def _word_overlap(text_a, text_b):
    """
    Compute meaningful word overlap between two short texts.
    Strips stopwords so content words drive the score.
    Returns float in [0.0, 1.0].
    """
    words_a = {
        w for w in text_a.lower().split()
        if w.isalpha() and w not in _STOPWORDS
    }
    words_b = {
        w for w in text_b.lower().split()
        if w.isalpha() and w not in _STOPWORDS
    }

    if not words_a and not words_b:
        return 1.0   # Both empty — treat as matching
    if not words_a or not words_b:
        return 0.0

    intersection = words_a & words_b
    # Use Jaccard similarity for balance (not just recall)
    union = words_a | words_b
    return len(intersection) / len(union)


# ─────────────────────────────────────────────────────────────
# EXACT MATCH — FOR MATH COMPUTATION
# Numbers extracted from math solutions should match exactly
# after normalizing whitespace, commas, and trailing zeros.
# ─────────────────────────────────────────────────────────────

def _normalize_number(s):
    """Normalize a number string for exact comparison."""
    s = s.strip().replace(",", "").replace(" ", "")
    # Remove trailing zeros after decimal: 4.00 → 4
    try:
        f = float(s)
        if f == int(f):
            return str(int(f))
        return f"{f:.6f}".rstrip("0")
    except ValueError:
        return s.lower()


# ─────────────────────────────────────────────────────────────
# MAIN CORRECTNESS CHECK
# ─────────────────────────────────────────────────────────────

def check_correctness(original, obfuscated, domain, provider):
    """
    Check whether the obfuscated response preserved the correct answer.

    Args:
        original:    The teacher model's real response.
        obfuscated:  The ITRO-treated response.
        domain:      8-category domain string.
        provider:    Instantiated provider for extraction calls.

    Returns:
        (is_correct, original_answer_str, obfuscated_answer_str)

        is_correct is True if the answer was preserved,
        False if it may have been corrupted.
    """
    try:
        # ── Extract answers from both responses ──────────────
        orig_ans = _extract(original,   domain, provider)
        obfu_ans = _extract(obfuscated, domain, provider)

        # ── Guard against extraction failures ────────────────
        if "extraction_failed" in orig_ans or "extraction_failed" in obfu_ans:
            return False, orig_ans, obfu_ans

        # ── Math computation: exact numerical match ───────────
        if domain == "math_computation":
            orig_norm = _normalize_number(orig_ans)
            obfu_norm = _normalize_number(obfu_ans)
            is_correct = (orig_norm == obfu_norm)
            return is_correct, orig_ans, obfu_ans

        # ── All other domains: word overlap with domain threshold
        threshold = SIMILARITY_THRESHOLDS.get(domain, 0.60)
        similarity = _word_overlap(orig_ans, obfu_ans)
        is_correct = similarity >= threshold

        return is_correct, orig_ans, obfu_ans

    except Exception as e:
        return False, "check_error", str(e)