"""
Google Gemini provider.
Uses the google-genai SDK (v1+).
"""

import sys
from google import genai
from google.genai import types as genai_types
from .base_provider import BaseProvider
from config import GEMINI_API_KEY, GEMINI_MODEL


class GeminiProvider(BaseProvider):
    def __init__(self):
        self._model_name = GEMINI_MODEL
        self.client = None

    def check_api_key(self):
        if not GEMINI_API_KEY:
            print("\n✗ Error: GEMINI_API_KEY not found.")
            print("\nSet it by running:")
            print("  export GEMINI_API_KEY=your_key_here")
            print("\nThen restart the tool.")
            sys.exit(1)
        self.client = genai.Client(api_key=GEMINI_API_KEY)
        return True

    def complete(self, prompt: str, max_tokens: int = 1024, system: str = None) -> str:
        # Gemini 2.5+ models spend "thinking" tokens out of max_output_tokens,
        # which can silently truncate the visible text mid-sentence. Thinking
        # is disabled here so the full budget goes to output; models that
        # require a thinking budget (e.g. 2.5-pro) reject budget=0, so fall
        # back to a plain config for those.
        base = dict(
            max_output_tokens=max_tokens,
            system_instruction=system if system else None,
        )
        try:
            response = self.client.models.generate_content(
                model=self._model_name,
                contents=prompt,
                config=genai_types.GenerateContentConfig(
                    **base,
                    thinking_config=genai_types.ThinkingConfig(thinking_budget=0),
                ),
            )
        except Exception as exc:
            if "thinking" not in str(exc).lower():
                raise
            response = self.client.models.generate_content(
                model=self._model_name,
                contents=prompt,
                config=genai_types.GenerateContentConfig(**base),
            )
        if not response.text:
            raise ValueError(
                "Gemini returned an empty response "
                "(likely truncated before any visible output)."
            )
        return response.text

    @property
    def name(self) -> str:
        return f"Google Gemini ({self._model_name})"