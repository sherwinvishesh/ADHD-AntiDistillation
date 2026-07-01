"""
Anthropic Claude provider.
"""

import sys
import anthropic
from .base_provider import BaseProvider
from config import ANTHROPIC_API_KEY, ANTHROPIC_MODEL


class AnthropicProvider(BaseProvider):
    def __init__(self):
        self.model = ANTHROPIC_MODEL
        self.client = None

    def check_api_key(self):
        if not ANTHROPIC_API_KEY:
            print("\n✗ Error: ANTHROPIC_API_KEY not found.")
            print("\nSet it by running:")
            print("  export ANTHROPIC_API_KEY=your_key_here")
            print("\nThen restart the tool.")
            sys.exit(1)
        self.client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        return True

    def complete(self, prompt: str, max_tokens: int = 1024, system: str = None) -> str:
        kwargs = {
            "model": self.model,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            kwargs["system"] = system

        response = self.client.messages.create(**kwargs)
        return response.content[0].text

    @property
    def name(self) -> str:
        return f"Anthropic Claude ({self.model})"