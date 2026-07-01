# 8-category domain detection using hybrid approach:
#   1. Hard rules for near-certain cases (no API call needed)
#   2. LLM classification for everything ambiguous
#
# Categories:
#   math_computation  — arithmetic, solving equations, numerical calculation
#   math_proof        — proofs, derivations, convergence arguments
#   code              — writing, debugging, or analyzing code
#   scientific        — causal/mechanistic explanations of natural phenomena
#   logical_argument  — formal logic, argument validity, deductive reasoning
#   factual_recall    — direct lookups, definitions, historical facts
#   procedural        — step-by-step how-to, workflows, deployment
#   analytical        — comparison, evaluation, implications, trade-offs

from colorama import Fore, Style

# ─────────────────────────────────────────────────────────────
# HARD RULE SIGNALS
# Used only for near-binary confidence cases.
# If these fire, skip the LLM call entirely.
# ─────────────────────────────────────────────────────────────

# Response-level code signals — structural, not keywords
CODE_RESPONSE_SIGNALS = [
    "```python", "```javascript", "```java", "```cpp",
    "```c", "```typescript", "```go", "```rust", "```bash",
    "```", "def ", "class ", "import ", "function(",
    "return ", "public static", "void main", "#include",
]

# Query-level explicit math expression signals
# These indicate a mathematical object is being manipulated,
# not just mentioned
MATH_EXPRESSION_SIGNALS = [
    "∫", "∑", "∏", "∂", "∇", "∞", "∀", "∃",
    "≤", "≥", "≠", "∈", "⊂", "→", "⟹",
    "√", "π", "θ", "α", "β", "λ", "σ", "μ",
]

# Query-level proof/derivation signals — strong indicators of math_proof
# vs math_computation
PROOF_QUERY_SIGNALS = [
    "prove ", "proof ", "derive ", "derivation",
    "show that", "demonstrate that", "convergence",
    "theorem", "lemma", "corollary", "by induction",
    "formally", "rigorously", "formalize"
]

# ─────────────────────────────────────────────────────────────
# HARD RULE DETECTOR
# Returns (category, confidence) or (None, 0) if unsure
# ─────────────────────────────────────────────────────────────

def _hard_rule_detect(query_text, response_text):
    """
    Fast pre-filter for near-certain cases.
    Returns category string if confident, None if unsure.

    We only fire here if the signal is unambiguous.
    When in doubt, return None and let the LLM decide.
    """
    q = query_text.lower()
    r = response_text  # keep original case for code detection

    # ── Code: structural response patterns are near-binary ──
    # A response with a fenced code block is almost certainly code.
    # Check response first — it's stronger than the query.
    code_hits = sum(1 for sig in CODE_RESPONSE_SIGNALS if sig in r)
    if code_hits >= 2:
        return "code"

    # ── Math symbols: explicit mathematical objects in query ──
    # Unicode math symbols in the query are unambiguous.
    math_sym_hits = sum(1 for sym in MATH_EXPRESSION_SIGNALS if sym in query_text)
    if math_sym_hits >= 1:
        # Determine if this is proof or computation
        proof_hits = sum(1 for sig in PROOF_QUERY_SIGNALS if sig in q)
        if proof_hits >= 1:
            return "math_proof"
        return "math_computation"

    # ── Proof language in query: strong signal ──
    proof_hits = sum(1 for sig in PROOF_QUERY_SIGNALS if sig in q)
    if proof_hits >= 2:
        return "math_proof"

    # Nothing obvious — defer to LLM
    return None


# ─────────────────────────────────────────────────────────────
# LLM CLASSIFIER PROMPT
# ─────────────────────────────────────────────────────────────

CLASSIFIER_SYSTEM = """You are a query domain classifier. 
Your only job is to classify a (query, response) pair into exactly one category.

The categories and what they mean:

math_computation  — The response involves arithmetic, algebra, solving equations,
                    or arriving at a numerical answer through calculation steps.
                    Example: "Solve 3x + 5 = 20", "What is 15% of 200?"

math_proof        — The response involves proving a theorem, deriving a formula,
                    formal induction, or rigorous mathematical argument.
                    Example: "Prove the sum of first n integers is n(n+1)/2",
                    "Derive the backpropagation update rule"

code              — The response involves writing, debugging, explaining, or
                    analyzing code or algorithms.
                    Example: "Implement merge sort in Python",
                    "Why is my recursive function hitting max recursion depth?"

scientific        — The response explains WHY or HOW something works in the
                    natural world. Causal or mechanistic explanation.
                    Example: "Why does convection occur?",
                    "How does the immune system recognize pathogens?"

logical_argument  — The response evaluates or constructs a formal logical argument,
                    checks validity, or applies deductive/inductive reasoning rules.
                    Example: "Is this syllogism valid?",
                    "What can we conclude if all A are B and all B are C?"

factual_recall    — The response retrieves a direct fact, definition, date, name,
                    or lookup that doesn't require reasoning steps.
                    Example: "Who wrote Hamlet?", "What is the capital of France?"

procedural        — The response gives a step-by-step process, workflow, or
                    how-to guide for accomplishing a task.
                    Example: "How do I deploy a Flask app?",
                    "What are the steps to get a US passport?"

analytical        — The response compares, evaluates trade-offs, discusses
                    implications, or synthesizes information across sources.
                    Example: "Compare transformers vs RNNs",
                    "What are the implications of this policy?"

Rules:
- Reply with EXACTLY ONE category name from the list above.
- No punctuation, no explanation, no extra words.
- If unsure between two, pick the one whose OBFUSCATION STRATEGY would matter more.
"""

def _build_classifier_prompt(query_text, response_text):
    # Trim response to avoid token waste — first 600 chars is enough
    # for structural classification
    response_preview = response_text[:600].strip()
    if len(response_text) > 600:
        response_preview += "..."

    return (
        f"QUERY:\n{query_text}\n\n"
        f"RESPONSE (preview):\n{response_preview}\n\n"
        f"Category:"
    )


# ─────────────────────────────────────────────────────────────
# VALID CATEGORIES + FALLBACK NORMALIZER
# ─────────────────────────────────────────────────────────────

VALID_CATEGORIES = {
    "math_computation",
    "math_proof",
    "code",
    "scientific",
    "logical_argument",
    "factual_recall",
    "procedural",
    "analytical",
}

# Fuzzy normalization for common LLM output variations
_ALIASES = {
    "math":            "math_computation",
    "mathematics":     "math_computation",
    "computation":     "math_computation",
    "proof":           "math_proof",
    "math proof":      "math_proof",
    "logic":           "logical_argument",
    "logical":         "logical_argument",
    "argument":        "logical_argument",
    "factual":         "factual_recall",
    "recall":          "factual_recall",
    "fact":            "factual_recall",
    "science":         "scientific",
    "causal":          "scientific",
    "procedure":       "procedural",
    "how-to":          "procedural",
    "howto":           "procedural",
    "analysis":        "analytical",
    "compare":         "analytical",
    "comparison":      "analytical",
}

def _normalize_category(raw):
    """
    Normalize LLM output to a valid category.
    Falls back to 'factual_recall' if unrecognizable.
    """
    cleaned = raw.strip().lower().rstrip(".")
    if cleaned in VALID_CATEGORIES:
        return cleaned
    if cleaned in _ALIASES:
        return _ALIASES[cleaned]
    # Last resort: partial match
    for valid in VALID_CATEGORIES:
        if valid in cleaned or cleaned in valid:
            return valid
    return "factual_recall"


# ─────────────────────────────────────────────────────────────
# MAIN DETECT FUNCTION
# ─────────────────────────────────────────────────────────────

def detect_domain(query_text, response_text="", provider=None, verbose=False):
    """
    Detect the domain of a (query, response) pair.

    Args:
        query_text:    The user's original question.
        response_text: The model's real response (use this when available —
                       it's a much stronger signal than the query alone).
        provider:      An instantiated BaseProvider. If None, falls back to
                       hard rules only (less accurate).
        verbose:       If True, prints detection path for debugging.

    Returns:
        One of: math_computation, math_proof, code, scientific,
                logical_argument, factual_recall, procedural, analytical
    """

    # ── Step 1: Try hard rules first ────────────────────────
    hard_result = _hard_rule_detect(query_text, response_text)

    if hard_result is not None:
        if verbose:
            print(f"  {Fore.CYAN}[domain]{Style.RESET_ALL} "
                  f"hard rule → {Fore.YELLOW}{hard_result}{Style.RESET_ALL}")
        return hard_result

    # ── Step 2: LLM classification ───────────────────────────
    if provider is None:
        # No provider available — use hard rules only with a best-effort guess
        if verbose:
            print(f"  {Fore.CYAN}[domain]{Style.RESET_ALL} "
                  f"no provider, defaulting to factual_recall")
        return "factual_recall"

    try:
        classifier_prompt = _build_classifier_prompt(query_text, response_text)

        # Build the full prompt with system context injected
        # (We use the user turn only since BaseProvider.call takes a single prompt)
        full_prompt = (
            f"{CLASSIFIER_SYSTEM}\n\n"
            f"---\n\n"
            f"{classifier_prompt}"
        )

        raw_response = provider.call(full_prompt, max_tokens=10)
        category = _normalize_category(raw_response)

        if verbose:
            print(f"  {Fore.CYAN}[domain]{Style.RESET_ALL} "
                  f"LLM classified → {Fore.YELLOW}{category}{Style.RESET_ALL} "
                  f"(raw: '{raw_response.strip()}')")

        return category

    except Exception as e:
        if verbose:
            print(f"  {Fore.CYAN}[domain]{Style.RESET_ALL} "
                  f"{Fore.RED}LLM call failed ({e}), "
                  f"defaulting to factual_recall{Style.RESET_ALL}")
        return "factual_recall"


# ─────────────────────────────────────────────────────────────
# DOMAIN METADATA
# Used by ITRO engine and display layer
# ─────────────────────────────────────────────────────────────

DOMAIN_LABELS = {
    "math_computation": "Math (Computation)",
    "math_proof":       "Math (Proof/Derivation)",
    "code":             "Code",
    "scientific":       "Scientific (Causal)",
    "logical_argument": "Logical Argument",
    "factual_recall":   "Factual Recall",
    "procedural":       "Procedural",
    "analytical":       "Analytical",
}

def get_domain_label(domain):
    """Human-readable label for display."""
    return DOMAIN_LABELS.get(domain, domain)