import os
from dotenv import load_dotenv

load_dotenv()

# ── Model path ────────────────────────────────────────────────
QWEN_MODEL_PATH = os.getenv("QWEN_MODEL_PATH")

# ── Quantization ─────────────────────────────────────────────
USE_4BIT = os.getenv("USE_4BIT", "false").lower() == "true"

# ── Model display name ────────────────────────────────────────
PROVIDER_MODELS = {
    "qwen": "Qwen2.5-7B-Instruct"
}

# ── Token budget ──────────────────────────────────────────────
MAX_TOKENS = 1024

# ── Generation settings — for ITRO obfuscation responses ─────
GENERATION_CONFIG = {
    "temperature":         0.7,
    "top_p":               0.9,
    "repetition_penalty":  1.1,
    "do_sample":           True,
}

# ── Strict settings — for structured outputs (τ scorer, domain)
# Low temperature = more deterministic = more reliable JSON
STRICT_GENERATION_CONFIG = {
    "temperature":         0.1,
    "top_p":               0.95,
    "repetition_penalty":  1.0,
    "do_sample":           True,
}