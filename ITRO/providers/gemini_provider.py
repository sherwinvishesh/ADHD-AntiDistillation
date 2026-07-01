import sys
import google.generativeai as genai
from config import GEMINI_API_KEY, PROVIDER_MODELS, MAX_TOKENS
from providers.base_provider import BaseProvider

class GeminiProvider(BaseProvider):

    def __init__(self):
        self.model_name = PROVIDER_MODELS["gemini"]
        self._model     = None

    @property
    def name(self):
        return f"Gemini ({self.model_name})"

    def check_api_key(self):
        if not GEMINI_API_KEY:
            print("\n✗ Error: GEMINI_API_KEY not found.")
            print("\nSet it by running:")
            print("  export GEMINI_API_KEY=your_key_here")
            print("\nThen restart the tool.")
            sys.exit(1)
        genai.configure(api_key=GEMINI_API_KEY)
        self._model = genai.GenerativeModel(self.model_name)
        return True

    def call(self, prompt, max_tokens=None):
        if max_tokens is None:
            max_tokens = MAX_TOKENS
        response = self._model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(max_output_tokens=max_tokens)
        )
        return response.text
