"""
SPECTRE — Configuration
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ── API Keys ──────────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")

# ── Model Names ───────────────────────────────────────────────────────────────
ANTHROPIC_MODEL: str = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")
GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

# ── Default provider (skips the interactive menu when set) ──────────────────
# Accepts: anthropic / claude / gemini / 1 / 2
SPECTRE_DEFAULT_PROVIDER = os.getenv("SPECTRE_DEFAULT_PROVIDER", "").strip() or None

# ── Pipeline strategy ─────────────────────────────────────────────────────────
# "composite" — one fixed T7 corruption schema applied identically to every
#               response (the dataset-generation default; consistency is what
#               the student model learns from).
# "ensemble"  — the original five independent variants + GHOST ranking
#               (kept for ablations and interactive demos).
SPECTRE_STRATEGY: str = (
    os.getenv("SPECTRE_STRATEGY", "").strip().lower() or "composite"
)

# ── Token Budgets ─────────────────────────────────────────────────────────────
TEACHER_MAX_TOKENS: int = 1024          # Clean teacher response
T1_FALLBACK_MAX_TOKENS: int = 1024      # T1 API fallback when no numbered steps
COMPOSITE_MAX_TOKENS: int = 1200        # T7 composite rewrite
GHOST_SCORING_MAX_TOKENS: int = 600     # GHOST ranking call
CORRECTNESS_MAX_TOKENS: int = 50        # Correctness verification

# ── Poison-verification thresholds ────────────────────────────────────────────
# Response body length cap (chars). Keeps question + response comfortably
# under a 1024-token student MAX_SEQ_LEN so the #### line is never silently
# truncated during student training (ITRO Bug 3).
MAX_RESPONSE_CHARS: int = 3500

# The final answer value must not appear in the first fraction of the body —
# an early answer anchor strengthens the question→answer shortcut that made
# ITRO fail.
EARLY_LEAK_FRACTION: float = 0.6

# ── Transformation Labels ─────────────────────────────────────────────────────
TRANSFORMATION_LABELS: dict = {
    "T1": "Backward Derivation",
    "T2": "Wrong Operation First",
    "T3": "Primitive Decomposition",
    "T5": "Circular Verification",
    "T6": "Formula Error Correction",
    "T7": "Entangled False-Start (Composite)",
}