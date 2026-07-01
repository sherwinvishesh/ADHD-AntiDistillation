import os
from dotenv import load_dotenv

load_dotenv()

# ── Cloud provider keys ───────────────────────────────────────
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
GEMINI_API_KEY    = os.getenv("GEMINI_API_KEY")

# ── Local Qwen model settings ─────────────────────────────────
QWEN_MODEL_PATH = os.getenv("QWEN_MODEL_PATH")
USE_4BIT        = os.getenv("USE_4BIT", "false").lower() == "true"

# ── Default provider (skips the interactive menu when set) ───
# Accepts: anthropic / claude / gemini / qwen / local / qwen-local / 1 / 2 / 3
ITRO_DEFAULT_PROVIDER = os.getenv("ITRO_DEFAULT_PROVIDER", "").strip() or None

PROVIDER_MODELS = {
    "anthropic": "claude-sonnet-4-6",
    "gemini":    "gemini-2.5-flash",
    "qwen":      "Qwen2.5-7B-Instruct",
}

MAX_TOKENS = 1024

# ── Generation settings — for ITRO obfuscation responses (local Qwen) ─
GENERATION_CONFIG = {
    "temperature":        0.7,
    "top_p":              0.9,
    "repetition_penalty": 1.1,
    "do_sample":          True,
}

# ── Strict settings — for structured outputs (τ scorer, domain; local Qwen) ─
# Low temperature = more deterministic = more reliable JSON
STRICT_GENERATION_CONFIG = {
    "temperature":        0.1,
    "top_p":              0.95,
    "repetition_penalty": 1.0,
    "do_sample":          True,
}
