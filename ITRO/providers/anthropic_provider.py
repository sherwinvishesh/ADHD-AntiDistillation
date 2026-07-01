import sys
import anthropic
from config import ANTHROPIC_API_KEY, PROVIDER_MODELS, MAX_TOKENS
from providers.base_provider import BaseProvider

class AnthropicProvider(BaseProvider):

    def __init__(self):
        self.model   = PROVIDER_MODELS["anthropic"]
        self._client = None

    @property
    def name(self):
        return f"Anthropic ({self.model})"

    def check_api_key(self):
        if not ANTHROPIC_API_KEY:
            print("\n✗ Error: ANTHROPIC_API_KEY not found.")
            print("\nSet it by running:")
            print("  export ANTHROPIC_API_KEY=your_key_here")
            print("\nThen restart the tool.")
            sys.exit(1)
        self._client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        return True

    def call(self, prompt, max_tokens=None):
        if max_tokens is None:
            max_tokens = MAX_TOKENS
        message = self._client.messages.create(
            model      = self.model,
            max_tokens = max_tokens,
            messages   = [{"role": "user", "content": prompt}]
        )
        return message.content[0].text