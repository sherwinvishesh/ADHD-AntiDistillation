"""
SPECTRE_API — Configuration
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ── API Keys ──────────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")

# ── Model Names ───────────────────────────────────────────────────────────────
ANTHROPIC_MODEL: str = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")
GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-1.5-pro")

# ── Token Budgets ─────────────────────────────────────────────────────────────
TEACHER_MAX_TOKENS: int = 1024          # Clean teacher response
T1_FALLBACK_MAX_TOKENS: int = 1024      # T1 API fallback when no numbered steps
GHOST_SCORING_MAX_TOKENS: int = 600     # GHOST ranking call
CORRECTNESS_MAX_TOKENS: int = 50        # Correctness verification

# ── Transformation Labels ─────────────────────────────────────────────────────
TRANSFORMATION_LABELS: dict = {
    "T1": "Causal Chain Inversion",
    "T2": "Operation Semantic Blinding",
    "T3": "Spurious Variable Proliferation",
    "T5": "Answer Position Destabilization",
    "T6": "Noisy Numerical Self-Correction",
}