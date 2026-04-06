import os
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
GEMINI_API_KEY    = os.getenv("GEMINI_API_KEY")

PROVIDER_MODELS = {
    "anthropic": "claude-sonnet-4-6",
    "gemini":    "gemini-2.5-flash"
}

MAX_TOKENS = 1024