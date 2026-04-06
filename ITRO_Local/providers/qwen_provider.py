# Local Qwen inference — CUDA version for Sol A100.
# Implements the same BaseProvider interface as the API providers.
# Everything else in the system calls self.call() and never knows
# it's talking to a local model instead of an API.

import sys
from colorama import Fore, Style

from config import (
    QWEN_MODEL_PATH, USE_4BIT, PROVIDER_MODELS,
    MAX_TOKENS, GENERATION_CONFIG, STRICT_GENERATION_CONFIG
)
from providers.base_provider import BaseProvider


class QwenProvider(BaseProvider):

    def __init__(self):
        self.model_name = PROVIDER_MODELS["qwen"]
        self._model     = None
        self._tokenizer = None
        self._device    = None

    # ─────────────────────────────────────────────────────────
    # NAME
    # ─────────────────────────────────────────────────────────

    @property
    def name(self):
        quant = "4-bit" if USE_4BIT else "float16"
        return f"Qwen ({self.model_name}, {quant}, local)"

    # ─────────────────────────────────────────────────────────
    # CHECK API KEY → FOR LOCAL: VALIDATE PATH + LOAD MODEL
    # Called once at startup. Loads model into GPU memory.
    # ─────────────────────────────────────────────────────────

    def check_api_key(self):
        import os
        import torch

        # ── Validate model path ──────────────────────────────
        if not QWEN_MODEL_PATH:
            print(f"\n  {Fore.RED}✗ QWEN_MODEL_PATH not set.{Style.RESET_ALL}")
            print()
            print("  Set it in your .env file:")
            print(f"  {Fore.YELLOW}QWEN_MODEL_PATH=/scratch/sjathann/models/Qwen2.5-7B-Instruct{Style.RESET_ALL}")
            sys.exit(1)

        if not os.path.isdir(QWEN_MODEL_PATH):
            print(f"\n  {Fore.RED}✗ Model path does not exist:{Style.RESET_ALL}")
            print(f"  {QWEN_MODEL_PATH}")
            print()
            print("  Download the model first — see the Sol setup guide.")
            sys.exit(1)

        # ── Check CUDA ───────────────────────────────────────
        if not torch.cuda.is_available():
            print(f"\n  {Fore.RED}✗ No CUDA GPU detected.{Style.RESET_ALL}")
            print()
            print("  ITRO_Local requires a CUDA GPU.")
            print("  On Sol: make sure you requested a GPU node.")
            print("  Check: python -c \"import torch; print(torch.cuda.is_available())\"")
            sys.exit(1)

        self._device = "cuda"
        vram_gb  = torch.cuda.get_device_properties(0).total_memory / 1e9
        gpu_name = torch.cuda.get_device_name(0)

        print(f"\n  {Fore.CYAN}GPU:{Style.RESET_ALL} {gpu_name} ({vram_gb:.1f} GB VRAM)")

        # VRAM checks
        if USE_4BIT and vram_gb < 4.5:
            print(f"  {Fore.RED}✗ Insufficient VRAM for 4-bit "
                  f"(need ~5GB, have {vram_gb:.1f}GB){Style.RESET_ALL}")
            sys.exit(1)

        if not USE_4BIT and vram_gb < 13.5:
            print(f"  {Fore.YELLOW}⚠  float16 needs ~14GB VRAM. "
                  f"You have {vram_gb:.1f}GB.")
            print(f"  Set USE_4BIT=true in .env or request a larger GPU.{Style.RESET_ALL}")
            sys.exit(1)

        # ── Load model ───────────────────────────────────────
        print(f"  {Fore.CYAN}Model path:{Style.RESET_ALL} {QWEN_MODEL_PATH}")
        print(f"  {Fore.CYAN}Precision:{Style.RESET_ALL} "
              f"{'4-bit (bitsandbytes)' if USE_4BIT else 'float16'}")
        print(f"  {Fore.WHITE + Style.DIM}Loading — takes ~20-30s...{Style.RESET_ALL}")

        try:
            import torch
            from transformers import (
                AutoTokenizer,
                AutoModelForCausalLM,
                BitsAndBytesConfig
            )

            # Load tokenizer
            self._tokenizer = AutoTokenizer.from_pretrained(
                QWEN_MODEL_PATH,
                trust_remote_code = True,
            )

            # Load model
            if USE_4BIT:
                quant_config = BitsAndBytesConfig(
                    load_in_4bit              = True,
                    bnb_4bit_compute_dtype    = torch.float16,
                    bnb_4bit_use_double_quant = True,
                    bnb_4bit_quant_type       = "nf4",
                )
                self._model = AutoModelForCausalLM.from_pretrained(
                    QWEN_MODEL_PATH,
                    quantization_config = quant_config,
                    device_map          = "auto",
                    trust_remote_code   = True,
                )
            else:
                self._model = AutoModelForCausalLM.from_pretrained(
                    QWEN_MODEL_PATH,
                    torch_dtype       = torch.float16,
                    device_map        = "auto",
                    trust_remote_code = True,
                )

            self._model.eval()

            vram_used = torch.cuda.memory_allocated(0) / 1e9
            print(f"  {Fore.GREEN}✓ Model loaded. "
                  f"VRAM used: {vram_used:.1f} GB{Style.RESET_ALL}")
            return True

        except ImportError as e:
            print(f"\n  {Fore.RED}✗ Missing package: {e}{Style.RESET_ALL}")
            print(f"\n  Install: pip install transformers accelerate bitsandbytes")
            sys.exit(1)

        except Exception as e:
            print(f"\n  {Fore.RED}✗ Failed to load model: {e}{Style.RESET_ALL}")
            sys.exit(1)

    # ─────────────────────────────────────────────────────────
    # CALL — MAIN INFERENCE
    # ─────────────────────────────────────────────────────────

    def call(self, prompt, max_tokens=None):
        """
        Run local inference. Applies Qwen2.5-Instruct chat template.
        Returns model response as plain string.
        """
        import torch

        if self._model is None or self._tokenizer is None:
            raise RuntimeError(
                "Model not loaded. call() invoked before check_api_key()."
            )

        if max_tokens is None:
            max_tokens = MAX_TOKENS

        # Small max_tokens = structured call (domain/τ scorer)
        # Use strict config for reliable JSON output
        is_structured = max_tokens <= 150
        cfg = STRICT_GENERATION_CONFIG if is_structured else GENERATION_CONFIG

        # ── Apply Qwen2.5-Instruct chat template ─────────────
        messages = [{"role": "user", "content": prompt}]

        text = self._tokenizer.apply_chat_template(
            messages,
            tokenize              = False,
            add_generation_prompt = True,
        )

        # ── Tokenize ─────────────────────────────────────────
        inputs = self._tokenizer(
            text,
            return_tensors = "pt",
        ).to(self._device)

        input_length = inputs["input_ids"].shape[1]

        # ── Generate ─────────────────────────────────────────
        with torch.no_grad():
            output_ids = self._model.generate(
                **inputs,
                max_new_tokens     = max_tokens,
                temperature        = cfg["temperature"],
                top_p              = cfg["top_p"],
                repetition_penalty = cfg["repetition_penalty"],
                do_sample          = cfg["do_sample"],
                pad_token_id       = self._tokenizer.eos_token_id,
            )

        # ── Decode — strip input tokens from output ───────────
        # output_ids includes the input prompt tokens.
        # Slice from input_length to get only new tokens.
        new_tokens = output_ids[0][input_length:]
        response   = self._tokenizer.decode(
            new_tokens,
            skip_special_tokens = True,
        )

        return response.strip()