from conftest import StubProvider
from teacher import get_teacher_response
from config import TEACHER_MAX_TOKENS


def test_get_teacher_response_returns_provider_output():
    stub = StubProvider("Step 1...\n#### 42")
    assert get_teacher_response("What is 6*7?", stub) == "Step 1...\n#### 42"


def test_get_teacher_response_embeds_question_in_prompt():
    stub = StubProvider("#### 42")
    get_teacher_response("What is 6*7?", stub)
    prompt = stub.calls[0][0]
    assert "What is 6*7?" in prompt
    assert "#### [number]" in prompt


def test_get_teacher_response_uses_configured_token_budget():
    stub = StubProvider("#### 42")
    get_teacher_response("q", stub)
    _, max_tokens, _ = stub.calls[0]
    assert max_tokens == TEACHER_MAX_TOKENS
