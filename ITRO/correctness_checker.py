# Domain-aware correctness checking for all 8 ITRO domains.
#
# Each domain has a targeted extraction prompt that asks the LLM
# to pull out exactly the thing ITRO is NOT supposed to corrupt
# (the final answer/conclusion), so we can verify it was preserved.
#
# Extraction strategy by domain:
#   math_computation  → final numerical answer (exact number match)
#   math_proof        → the theorem/statement being proved + conclusion
#   code              → what the function returns / its behavior contract
#   scientific        → the causal conclusion (what causes what)
#   logical_argument  → the logical conclusion
#   factual_recall    → the core fact stated
#   procedural        → the end result / goal achieved by the steps
#   analytical        → the main recommendation or conclusion
#
# Comparison strategy:
#   math_computation  → exact numerical match after normalization
#                       Numbers don't paraphrase: 5 = 5, 5 ≠ 6.
#   everything else   → LLM semantic match
#                       Word overlap fails when ITRO correctly
#                       paraphrases the answer — which is exactly
#                       what it's supposed to do. "Written by
#                       Shakespeare" and "authored by Shakespeare"
#                       share almost no content words but mean
#                       the same thing. The LLM handles this;
#                       Jaccard similarity does not.


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
# EXTRACTION HELPER
# Pulls the answer component from a response using the
# domain-appropriate extraction prompt above.
# ─────────────────────────────────────────────────────────────

def _extract(response_text, domain, provider):
    """
    Extract the answer component from a response using the
    domain-appropriate extraction prompt.

    The code domain is handled as a special case because its
    prompt requires slicing the response text inline, which
    Python's .format() does not support inside {} placeholders.

    Returns the extracted string, or "extraction_failed: ..." on error.
    """
    if domain not in EXTRACTION_PROMPTS:
        domain = "factual_recall"

    prompt_template, max_tokens = EXTRACTION_PROMPTS[domain]

    try:
        if domain == "code":
            # Special case: build prompt inline with sliced text
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
        # Fallback if format fails for any reason
        prompt = prompt_template.format(text=response_text[:1200])

    try:
        result = provider.call(prompt, max_tokens=max_tokens)
        return result.strip()
    except Exception as e:
        return f"extraction_failed: {e}"


# ─────────────────────────────────────────────────────────────
# EXACT MATCH — FOR MATH COMPUTATION ONLY
# Numbers extracted from math solutions should match exactly
# after normalizing whitespace, commas, and trailing zeros.
# Example: "4.00" and "4" are the same. "4" and "5" are not.
# ─────────────────────────────────────────────────────────────

def _normalize_number(s):
    """
    Normalize a number string for exact comparison.

    Handles:
      - Commas: "1,000" → "1000"
      - Trailing zeros: "4.00" → "4"
      - Whitespace: " 5 " → "5"
      - Non-numeric fallback: returns lowercased string as-is
    """
    s = s.strip().replace(",", "").replace(" ", "")
    try:
        f = float(s)
        if f == int(f):
            return str(int(f))
        return f"{f:.6f}".rstrip("0")
    except ValueError:
        return s.lower()


# ─────────────────────────────────────────────────────────────
# LLM SEMANTIC MATCH — FOR ALL NON-MATH DOMAINS
#
# Why not word overlap?
# Word overlap (Jaccard similarity) fails when ITRO produces
# correctly paraphrased answers — which is exactly what it does.
#
# Example failure:
#   Real:        "Hamlet was written by William Shakespeare."
#   Obfuscated:  "William Shakespeare is generally considered
#                 the author of Hamlet."
#   Content words: {hamlet, written, william, shakespeare} vs
#                  {william, shakespeare, generally, considered,
#                   author, hamlet}
#   Jaccard = 3/7 = 0.43 → FAIL (threshold was 0.70)
#   But these mean exactly the same thing.
#
# The LLM understands semantic equivalence regardless of wording.
# ─────────────────────────────────────────────────────────────

def _llm_semantic_match(text_a, text_b, provider):
    """
    Ask the LLM whether two extracted answers mean the same thing.

    Instructs the LLM to ignore differences in:
      - wording and phrasing
      - hedging and qualifiers ("generally considered" vs direct statement)
      - sentence structure and order

    And focus only on whether the core factual/logical content matches.

    Returns True if semantically equivalent, False if genuinely different.

    Fails open (returns True) on any exception — we never want an
    infrastructure failure in the checker to wrongly trigger the
    safety valve on a correctly obfuscated response.
    """
    prompt = (
        "Do these two statements convey the same core answer or conclusion?\n"
        "Ignore differences in wording, hedging, or sentence structure.\n"
        "Focus only on whether the factual content is the same.\n"
        "Answer with a single word: YES or NO.\n\n"
        f"Statement A: {text_a}\n\n"
        f"Statement B: {text_b}\n\n"
        "Same core answer? (YES/NO):"
    )
    try:
        raw = provider.call(prompt, max_tokens=5)
        return "yes" in raw.strip().lower()
    except Exception:
        # Fail open — if the semantic check call itself fails,
        # assume the answer is preserved rather than wrongly
        # triggering the safety valve on a legitimate obfuscation.
        return True


# ─────────────────────────────────────────────────────────────
# MAIN CORRECTNESS CHECK
# ─────────────────────────────────────────────────────────────

def check_correctness(original, obfuscated, domain, provider):
    """
    Check whether the obfuscated response preserved the correct answer.

    Pipeline:
      1. Extract the answer component from both responses using
         the domain-appropriate extraction prompt.
      2. Compare using the appropriate method for this domain:
           math_computation → exact numerical match
           everything else  → LLM semantic match

    Args:
        original:    The teacher model's real response (unmodified).
        obfuscated:  The ITRO-treated response (reasoning corrupted).
        domain:      8-category domain string from domain_detector.py.
        provider:    Instantiated provider — used for both extraction
                     calls and the semantic match call.

    Returns:
        (is_correct, original_answer_str, obfuscated_answer_str)

        is_correct is True  → obfuscation preserved the answer,
                              return the obfuscated response.
        is_correct is False → obfuscation may have corrupted the answer,
                              safety valve fires, return original response.
    """
    try:
        # ── Step 1: Extract answer component from both ────────
        orig_ans = _extract(original,   domain, provider)
        obfu_ans = _extract(obfuscated, domain, provider)

        # ── Step 2: Guard against extraction failures ─────────
        # If either extraction failed, we cannot verify correctness.
        # Return False to trigger the safety valve — better to return
        # the original than to risk returning a corrupted answer.
        if "extraction_failed" in orig_ans or "extraction_failed" in obfu_ans:
            return False, orig_ans, obfu_ans

        # ── Step 3a: Math computation — exact numerical match ─
        # Numbers cannot be paraphrased. "5" and "5" match.
        # "5" and "6" do not. No semantic wiggle room needed.
        if domain == "math_computation":
            orig_norm  = _normalize_number(orig_ans)
            obfu_norm  = _normalize_number(obfu_ans)
            is_correct = (orig_norm == obfu_norm)
            return is_correct, orig_ans, obfu_ans

        # ── Step 3b: All other domains — LLM semantic match ───
        # Paraphrasing is expected and correct. The LLM determines
        # whether the core meaning was preserved regardless of
        # how differently the two answers are worded.
        is_correct = _llm_semantic_match(orig_ans, obfu_ans, provider)
        return is_correct, orig_ans, obfu_ans

    except Exception as e:
        # Never crash — return False to trigger safety valve
        return False, "check_error", str(e)