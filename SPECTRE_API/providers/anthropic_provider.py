"""
Anthropic Claude provider.
"""

import anthropic
from .base_provider import BaseProvider
from config import ANTHROPIC_API_KEY, ANTHROPIC_MODEL


class AnthropicProvider(BaseProvider):
    def __init__(self):
        if not ANTHROPIC_API_KEY:
            raise ValueError(
                "ANTHROPIC_API_KEY is not set. Add it to your .env file."
            )
        self.client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        self.model = ANTHROPIC_MODEL

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