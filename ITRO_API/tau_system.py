# Tau (τ) measures the PEDAGOGICAL VALUE of a query to an extraction attacker.
# Specifically: how much would a student model improve its generalization
# ability by training on the response to this query?
#
# This is NOT "how hard is the question."
# It is "how much reasoning does the response encode that transfers to
# novel problems?"
#
# τ = 0.0 → attacker gains nothing from this response
# τ = 1.0 → response encodes maximally valuable generalizable reasoning

import json
import re
from colorama import Fore, Style

# ─────────────────────────────────────────────────────────────
# DOMAIN BOUNDS
# Hard floor/ceiling for each domain regardless of LLM score.
# Based on the inherent pedagogical value ceiling of each type.
# ─────────────────────────────────────────────────────────────

DOMAIN_BOUNDS = {
    "factual_recall":   (0.05, 0.35),
    "math_computation": (0.35, 0.72),  # raised from 0.15 — always at least mild
    "math_proof":       (0.55, 1.00),
    "code":             (0.10, 0.95),  # lowered floor — let scorer decide
    "scientific":       (0.40, 0.90),
    "logical_argument": (0.30, 0.85),
    "procedural":       (0.15, 0.60),
    "analytical":       (0.40, 0.92),
}

# ─────────────────────────────────────────────────────────────
# DIMENSION WEIGHTS
# How much each dimension contributes to the final tau.
# Depth and generalizability weighted highest — these are the
# core properties ITRO is designed to corrupt.
# ─────────────────────────────────────────────────────────────

DIMENSION_WEIGHTS = {
    "reasoning_depth":    0.35,
    "generalizability":   0.30,
    "expert_density":     0.20,
    "frontier_dependency": 0.15,
}

# ─────────────────────────────────────────────────────────────
# FAST ESTIMATOR
# Fires only for near-certain cases to avoid burning an API call.
# Returns float if confident, None if unsure.
# ─────────────────────────────────────────────────────────────

# Signals that indicate near-zero pedagogical value
TRIVIAL_SIGNALS = [
    "what is your name", "who are you", "what year is",
    "how many days", "what day is", "capital of",
    "who invented", "when was", "how do you spell",
    "what does .* stand for", "how many .* in a",
]

# Signals that indicate near-maximum pedagogical value
MAXIMAL_SIGNALS = [
    "∫", "∑", "∏", "∂", "∇", "∀", "∃",  # math notation
    "prove by induction", "proof by contradiction",
    "derive the", "derive an expression",
    "convergence of", "eigenvalue decomposition",
    "backpropagation", "gradient descent derivation",
    "formal proof", "rigorous derivation",
]

def _fast_estimate(query_text, domain):
    """
    Returns a tau float for obviously trivial or obviously maximal queries.
    Returns None for everything in between.
    
    We are intentionally conservative here — only fire on near-certain cases.
    When in doubt, return None and let the LLM decide.
    """
    q = query_text.lower()

    # Check maximal signals first (math notation is unambiguous)
    for sig in MAXIMAL_SIGNALS:
        if sig in q or sig in query_text:  # check original for unicode
            floor, ceiling = DOMAIN_BOUNDS.get(domain, (0.3, 0.9))
            return min(0.92, ceiling)

    # Check trivial signals
    for sig in TRIVIAL_SIGNALS:
        if re.search(sig, q):
            floor, ceiling = DOMAIN_BOUNDS.get(domain, (0.1, 0.4))
            return max(0.08, floor)

    # Single word or very short query with factual domain
    word_count = len(query_text.split())
    if word_count <= 4 and domain == "factual_recall":
        return 0.08

    return None  # Not obvious — defer to LLM


# ─────────────────────────────────────────────────────────────
# LLM SCORING PROMPT
# ─────────────────────────────────────────────────────────────

SCORER_SYSTEM = """You are an AI distillation threat analyst.

Your job is to assess how much PEDAGOGICAL VALUE a query has for an
extraction attacker — someone trying to steal an AI model's capabilities
by collecting (query, response) pairs and training a student model on them.

You will score the query on FOUR dimensions. Each score is 0.0 to 1.0.

───────────────────────────────────────────────────────────────
DIMENSION 1: reasoning_depth
How many DEPENDENT reasoning steps does a complete answer require?

0.0  → Single step. Direct lookup or one-line answer. No chain.
       Example: "What is the capital of France?"

0.3  → 2-3 steps. Simple derivation or short argument.
       Example: "Solve x + 5 = 9"

0.6  → 4-6 dependent steps. Multi-stage reasoning.
       Example: "Solve a system of two linear equations"

1.0  → 7+ dependent steps. Complex proof, full algorithm, multi-stage
       derivation where each step builds on all previous steps.
       Example: "Prove by strong induction that every integer > 1
       has a prime factorization"
───────────────────────────────────────────────────────────────
DIMENSION 2: generalizability
Does the REASONING PATTERN transfer to novel similar problems?

0.0  → Completely one-off. The answer technique cannot be reused.
       Example: "How many US presidents have there been?"

0.3  → Pattern applies to a narrow class of similar problems.
       Example: "What percentage is 30 of 120?"

0.6  → Pattern applies to a broad class of problems in this domain.
       Example: "Solve a quadratic equation by completing the square"

1.0  → Fundamental technique that generalizes across many domains
       and problem types. A student learning this improves broadly.
       Example: "Use dynamic programming to find the longest
       common subsequence"
───────────────────────────────────────────────────────────────
DIMENSION 3: expert_density
How much specialized knowledge does a CORRECT, HIGH-QUALITY answer encode?

0.0  → Common knowledge. Any person could answer correctly.
       Example: "What color is the sky?"

0.3  → Basic domain knowledge. A first-year student knows this.
       Example: "What is a linked list?"

0.6  → Intermediate expertise. Requires real familiarity with the domain.
       Example: "Explain the difference between L1 and L2 regularization"

1.0  → Deep expert knowledge. Only someone with strong domain expertise
       produces a truly useful answer.
       Example: "Derive the ELBO for a variational autoencoder"
───────────────────────────────────────────────────────────────
DIMENSION 4: frontier_dependency
How much better is a FRONTIER MODEL's answer vs a weak model?

0.0  → Any model gets this right. No quality advantage from frontier.
       Example: "What is 2 + 2?"

0.3  → Better models give slightly cleaner answers, but weak models
       are mostly adequate.
       Example: "Explain what recursion is"

0.6  → Frontier models give significantly better answers — more accurate
       reasoning, better edge case handling, richer explanation.
       Example: "Analyze the time complexity of this algorithm"

1.0  → Only frontier models produce genuinely useful responses.
       Weaker models hallucinate, skip steps, or give wrong answers.
       Example: "Implement and explain an attention mechanism from scratch"
───────────────────────────────────────────────────────────────

DOMAIN CONTEXT for the query is provided. Use it to calibrate.

Reply with ONLY valid JSON. No explanation. No markdown. No extra text.
Format exactly:
{
  "reasoning_depth": <float 0.0-1.0>,
  "generalizability": <float 0.0-1.0>,
  "expert_density": <float 0.0-1.0>,
  "frontier_dependency": <float 0.0-1.0>,
  "rationale": "<one sentence max explaining the dominant factor>"
}"""


def _build_scorer_prompt(query_text, domain):
    return (
        f"DOMAIN: {domain}\n\n"
        f"QUERY:\n{query_text}\n\n"
        f"Score the pedagogical distillation value of this query:"
    )


# ─────────────────────────────────────────────────────────────
# JSON PARSER WITH FALLBACK
# ─────────────────────────────────────────────────────────────

def _parse_scores(raw_response):
    """
    Parse LLM JSON response into a scores dict.
    Tries strict JSON first, then regex extraction as fallback.
    Returns None if parsing fails completely.
    """
    # Try strict JSON parse first
    try:
        # Strip any accidental markdown fences
        cleaned = raw_response.strip()
        cleaned = re.sub(r"^```json\s*", "", cleaned)
        cleaned = re.sub(r"^```\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
        data = json.loads(cleaned)

        required = {"reasoning_depth", "generalizability",
                    "expert_density", "frontier_dependency"}
        if required.issubset(data.keys()):
            # Clamp all values to [0.0, 1.0]
            for key in required:
                data[key] = max(0.0, min(1.0, float(data[key])))
            return data

    except (json.JSONDecodeError, ValueError, TypeError):
        pass

    # Fallback: extract numbers via regex
    try:
        pattern = r'"?(reasoning_depth|generalizability|expert_density|frontier_dependency)"?\s*:\s*([0-9.]+)'
        matches = re.findall(pattern, raw_response)
        if len(matches) >= 4:
            data = {k: max(0.0, min(1.0, float(v))) for k, v in matches}
            return data
    except Exception:
        pass

    return None


# ─────────────────────────────────────────────────────────────
# LLM SCORER
# ─────────────────────────────────────────────────────────────

def _llm_score(query_text, domain, provider):
    """
    Ask the LLM to score the 4 tau dimensions.
    Returns a dict of scores or None on failure.
    """
    full_prompt = (
        f"{SCORER_SYSTEM}\n\n"
        f"---\n\n"
        f"{_build_scorer_prompt(query_text, domain)}"
    )

    raw = provider.call(full_prompt, max_tokens=120)
    return _parse_scores(raw)


# ─────────────────────────────────────────────────────────────
# TAU COMPUTATION — MAIN
# ─────────────────────────────────────────────────────────────

def compute_tau(query_text, domain="factual_recall", provider=None, verbose=False):
    """
    Compute tau (τ) — obfuscation intensity for this query.

    Args:
        query_text: The user's original question.
        domain:     Detected domain (from domain_detector.py).
                    Critically affects floor/ceiling bounds.
        provider:   Instantiated BaseProvider for LLM scoring.
                    If None, falls back to fast estimate only.
        verbose:    Print scoring breakdown for debugging.

    Returns:
        τ ∈ [0.0, 1.0]
    """

    floor, ceiling = DOMAIN_BOUNDS.get(domain, (0.15, 0.85))

    # ── Step 1: Fast estimate for obvious cases ──────────────
    fast = _fast_estimate(query_text, domain)
    if fast is not None:
        tau = max(floor, min(ceiling, fast))
        if verbose:
            print(f"  {Fore.CYAN}[tau]{Style.RESET_ALL} "
                  f"fast estimate → {Fore.YELLOW}{tau:.3f}{Style.RESET_ALL} "
                  f"(floor={floor}, ceiling={ceiling})")
        return tau

    # ── Step 2: LLM dimensional scoring ─────────────────────
    if provider is None:
        # No provider — use domain midpoint as safe fallback
        tau = (floor + ceiling) / 2.0
        if verbose:
            print(f"  {Fore.CYAN}[tau]{Style.RESET_ALL} "
                  f"no provider, domain midpoint → "
                  f"{Fore.YELLOW}{tau:.3f}{Style.RESET_ALL}")
        return tau

    try:
        scores = _llm_score(query_text, domain, provider)

        if scores is None:
            raise ValueError("Score parsing failed")

        # ── Step 3: Weighted combination ─────────────────────
        raw_tau = (
            DIMENSION_WEIGHTS["reasoning_depth"]    * scores["reasoning_depth"]    +
            DIMENSION_WEIGHTS["generalizability"]   * scores["generalizability"]   +
            DIMENSION_WEIGHTS["expert_density"]     * scores["expert_density"]     +
            DIMENSION_WEIGHTS["frontier_dependency"] * scores["frontier_dependency"]
        )

        # ── Step 4: Domain clip ───────────────────────────────
        tau = max(floor, min(ceiling, raw_tau))

        if verbose:
            print(f"  {Fore.CYAN}[tau breakdown]{Style.RESET_ALL}")
            print(f"    reasoning_depth    : {scores['reasoning_depth']:.2f} "
                  f"× {DIMENSION_WEIGHTS['reasoning_depth']}")
            print(f"    generalizability   : {scores['generalizability']:.2f} "
                  f"× {DIMENSION_WEIGHTS['generalizability']}")
            print(f"    expert_density     : {scores['expert_density']:.2f} "
                  f"× {DIMENSION_WEIGHTS['expert_density']}")
            print(f"    frontier_dependency: {scores['frontier_dependency']:.2f} "
                  f"× {DIMENSION_WEIGHTS['frontier_dependency']}")
            print(f"    raw score: {raw_tau:.3f} → "
                  f"clipped to domain [{floor}, {ceiling}] → "
                  f"{Fore.YELLOW}τ = {tau:.3f}{Style.RESET_ALL}")
            if "rationale" in scores:
                print(f"    rationale: {scores['rationale']}")

        return tau

    except Exception as e:
        # Fallback: domain midpoint, never crash
        tau = (floor + ceiling) / 2.0
        if verbose:
            print(f"  {Fore.CYAN}[tau]{Style.RESET_ALL} "
                  f"{Fore.RED}LLM scoring failed ({e}), "
                  f"domain midpoint → {tau:.3f}{Style.RESET_ALL}")
        return tau


# ─────────────────────────────────────────────────────────────
# LABEL + INTENSITY INSTRUCTION
# Used by ITRO engine and display layer
# ─────────────────────────────────────────────────────────────

def get_tau_label(tau):
    """Human-readable intensity label."""
    if tau < 0.20: return "minimal"
    elif tau < 0.40: return "mild"
    elif tau < 0.60: return "moderate"
    elif tau < 0.80: return "heavy"
    else: return "maximum"


def get_intensity_instruction(tau):
    """
    Returns the ITRO instruction string for a given tau.
    Consumed by itro_engine.py when building obfuscation prompts.
    """
    if tau < 0.20:
        return (
            "Add exactly one small unnecessary intermediate step. "
            "Keep all other changes minimal and subtle. "
            "The response should look almost identical to the original."
        )
    elif tau < 0.40:
        return (
            "Add 2-3 unnecessary intermediate steps and one short detour "
            "that circles back to the correct reasoning. "
            "The response should feel slightly verbose but still coherent."
        )
    elif tau < 0.60:
        return (
            "Add multiple unnecessary steps. Briefly explore one incorrect "
            "approach before abandoning it and returning to the correct path. "
            "Include at least one redundant verification step."
        )
    elif tau < 0.80:
        return (
            "Significantly restructure the reasoning path. Add multiple "
            "dead ends, unnecessary detours, and excessive verification loops. "
            "Make the path to the answer as indirect as possible while "
            "remaining coherent enough to read."
        )
    else:
        return (
            "Completely restructure the entire reasoning chain. "
            "Begin with a wrong approach, work through it for several steps, "
            "then abandon it with a plausible-sounding reason. "
            "Take at least two major detours. Add excessive verification "
            "at every step. Arrive at the correct answer only after a "
            "maximally convoluted journey. The response should look like "
            "genuine expert reasoning that happens to be very indirect."
        )