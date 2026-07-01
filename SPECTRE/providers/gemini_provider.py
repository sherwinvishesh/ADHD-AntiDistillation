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
        config = genai_types.GenerateContentConfig(
            max_output_tokens=max_tokens,
            system_instruction=system if system else None,
        )
        response = self.client.models.generate_content(
            model=self._model_name,
            contents=prompt,
            config=config,
        )
        return response.text

    @property
    def name(self) -> str:
        return f"Google Gemini ({self._model_name})"