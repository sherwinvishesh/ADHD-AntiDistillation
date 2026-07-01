import pytest

from conftest import StubProvider
from transformations import apply_all_transformations, TRANSFORMATION_LABELS

CLEAN_RESPONSE = "Step 1: 48/2=24. Step 2: 48+24=72.\n#### 72"


def test_apply_all_transformations_returns_all_five_in_order():
    stub = StubProvider("Rewritten reasoning, all numbers preserved.")
    variants = apply_all_transformations("q", CLEAN_RESPONSE, stub)
    assert [v["transformation_id"] for v in variants] == ["T1", "T2", "T3", "T5", "T6"]


def test_apply_all_transformations_variant_shape():
    stub = StubProvider("Rewritten reasoning, all numbers preserved.")
    variants = apply_all_transformations("q", CLEAN_RESPONSE, stub)
    for v, tid in zip(variants, ["T1", "T2", "T3", "T5", "T6"]):
        assert v["transformation_name"] == TRANSFORMATION_LABELS[tid]
        assert v["is_algorithmic"] is False
        assert v["is_api_call"] is True
        assert v["error"] is None
        assert v["response"].rstrip().endswith("#### 72")


def test_apply_all_transformations_preserves_answer_line_even_if_model_adds_one():
    # Model output includes a rogue #### line — must be stripped and replaced
    # with the original's exact answer line, not the model's guess.
    stub = StubProvider("Rewritten reasoning.\n#### 999")
    variants = apply_all_transformations("q", CLEAN_RESPONSE, stub)
    for v in variants:
        assert v["response"].rstrip().endswith("#### 72")


def test_apply_all_transformations_records_partial_failure():
    # Only T1's call fails (queue: T1 fails, rest succeed) — but StubProvider
    # queues are consumed in call order across all 5 transforms, so instead
    # simulate via a provider that fails on the first call only.
    class FirstCallFails(StubProvider):
        def complete(self, prompt, max_tokens=1024, system=None):
            if not self.calls:
                self.calls.append((prompt, max_tokens, system))
                raise RuntimeError("boom")
            return super().complete(prompt, max_tokens, system)

    stub = FirstCallFails("Rewritten reasoning, all numbers preserved.")
    variants = apply_all_transformations("q", CLEAN_RESPONSE, stub)
    failed = [v for v in variants if v["error"] is not None]
    ok = [v for v in variants if v["error"] is None]
    assert len(failed) == 1
    assert len(ok) == 4
    assert failed[0]["transformation_id"] == "T1"
    assert failed[0]["response"] is None


def test_apply_all_transformations_raises_if_fewer_than_two_succeed(failing_provider):
    with pytest.raises(RuntimeError, match=r"0/5 transformations succeeded"):
        apply_all_transformations("q", CLEAN_RESPONSE, failing_provider)


def test_apply_all_transformations_rejects_empty_response():
    # Every transform() appends the clean response's own #### line onto
    # whatever the model returns, so a blank model reply only produces a
    # genuinely empty variant when the clean response has no #### line
    # to fall back on either.
    no_answer_line = "Step 1: 48/2=24. Step 2: 48+24=72. (no answer line)"
    stub = StubProvider("   ")
    with pytest.raises(RuntimeError):
        apply_all_transformations("q", no_answer_line, stub)
