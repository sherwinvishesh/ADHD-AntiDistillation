"""
ghost_scorer.py — GHOST Scoring Layer

GHOST = Gradient-Hostile Output Selection for Training.

Sends all five SPECTRE variants to Claude and asks it to rank them from
worst to best for a 0.5B parameter student model to learn from.

Note: This is not scientifically rigorous. Claude is reasoning about
learnability, not measuring it. In SPECTRE_P1, GHOST scoring uses actual
cross-entropy loss on a local proxy model. Here it validates that the
pipeline runs and the selection logic works.
"""

import json
import re
import logging

from providers.base_provider import BaseProvider
from config import GHOST_SCORING_MAX_TOKENS, TRANSFORMATION_LABELS

logger = logging.getLogger(__name__)

DEFAULT_RANKING = ["T1", "T2", "T3", "T5", "T6"]


def score_variants(variants: list, provider: BaseProvider) -> dict:
    """
    Ask the provider to rank all variants from hardest to easiest for
    a student model to learn from.

    Args:
        variants:   List of variant dicts (from apply_all_transformations).
                    Only successful variants (error=None) should be passed.
        provider:   Any initialised BaseProvider.

    Returns:
        {
            "ranking":   ["T2", "T1", ...],   # worst → best for student
            "reasoning": "One or two sentence explanation."
        }
        Falls back to DEFAULT_RANKING if parsing fails.
    """
    if not variants:
        return {"ranking": DEFAULT_RANKING[:], "reasoning": "No variants provided."}

    # ── Build the scoring prompt ──────────────────────────────────────────
    variants_block = ""
    for v in variants:
        tid  = v["transformation_id"]
        name = v["transformation_name"]
        text = v["response"] or "(empty)"
        variants_block += f"\n\n{'='*60}\n{tid} — {name}\n{'='*60}\n{text}\n"

    valid_ids = [v["transformation_id"] for v in variants]
    ids_str   = ", ".join(f'"{t}"' for t in valid_ids)

    prompt = f"""You are evaluating math solution variants for their damage to a student model.

CONTEXT: A defender is poisoning training data to protect against model distillation attacks.
An attacker is collecting AI responses to train a small 0.5B-parameter student model.
The defender has created five structurally different variants of the same correct response.
Your job: rank them from WORST to BEST for the student model to learn from.

"Worst to learn from" = if the student trained ONLY on this variant, it would fail most
on new math problems it has never seen, because it has learned a brittle, non-generalizable
pattern instead of the underlying mathematical method.

CRITERIA TO USE:
- Which variant teaches a reasoning pattern that fails to transfer to new, unseen problems?
- Which variant destroys the student's understanding of what mathematical operations mean?
- Which variant creates a false expectation about problem structure (extra variables,
  starting from the answer, unreliable intermediate values, displaced answer position)?

CRITERIA TO IGNORE:
- Length: longer is NOT automatically harder to learn from.
- The #### answer line: it is identical across all variants.
- Grammatical quality: all variants are grammatically valid.

THE FIVE VARIANTS:
{variants_block}

Return ONLY a JSON object with exactly two fields:
  "ranking"  — array of transformation IDs ordered WORST to BEST for student learning.
               Use only these IDs (include all of them): {ids_str}
  "reasoning" — 1-2 sentences explaining why the top-ranked (worst) variant was chosen.

Example format (do not copy this ranking — reason from the actual content above):
{{"ranking": [{ids_str}], "reasoning": "Example reasoning here."}}

Return only the JSON object, nothing else."""

    # ── API call ──────────────────────────────────────────────────────────
    try:
        raw = provider.complete(prompt, max_tokens=GHOST_SCORING_MAX_TOKENS)
    except Exception as exc:
        logger.error("GHOST scoring API call failed: %s", exc)
        return {"ranking": _build_fallback(valid_ids), "reasoning": f"API error: {exc}"}

    # ── Parse the response ────────────────────────────────────────────────
    try:
        text = raw.strip()

        # Strip markdown code fences if present
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.MULTILINE)
        text = re.sub(r"\s*```$",           "", text, flags=re.MULTILINE)
        text = text.strip()

        # Extract JSON object
        json_match = re.search(r"\{.*\}", text, re.DOTALL)
        if not json_match:
            raise ValueError("No JSON object found in response.")

        parsed    = json.loads(json_match.group(0))
        ranking   = parsed.get("ranking",   [])
        reasoning = parsed.get("reasoning", "")

        # Validate: must contain exactly the expected IDs
        expected  = set(valid_ids)
        got       = set(ranking)
        if got != expected or len(ranking) != len(valid_ids):
            raise ValueError(
                f"Ranking IDs mismatch. Expected {expected}, got {got}."
            )

        return {"ranking": ranking, "reasoning": reasoning}

    except Exception as exc:
        logger.warning("GHOST scoring parse failed (%s) — using fallback ranking.", exc)
        return {
            "ranking":   _build_fallback(valid_ids),
            "reasoning": "Default ranking used due to response parsing failure.",
        }


def _build_fallback(valid_ids: list) -> list:
    """
    Return a fallback ranking. Prefer the canonical DEFAULT order,
    filtered to only IDs that were actually generated.
    """
    ordered = [t for t in DEFAULT_RANKING if t in valid_ids]
    # Append any extras not in default order
    for t in valid_ids:
        if t not in ordered:
            ordered.append(t)
    return ordered