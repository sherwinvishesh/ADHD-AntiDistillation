from conftest import StubProvider
from pipeline import run_pipeline

CLEAN = "Step 1: 48/2=24. Step 2: 48+24=72.\n#### 72"

HAPPY_PATH_QUEUE = [
    CLEAN,                                            # [1/5] teacher
    "T1 rewritten reasoning, values preserved.",      # [2/5] T1
    "T2 rewritten reasoning, values preserved.",      # [2/5] T2
    "T3 rewritten reasoning, values preserved.",      # [2/5] T3
    "T5 rewritten reasoning, values preserved.",      # [2/5] T5
    "T6 rewritten reasoning, values preserved.",      # [2/5] T6
    '{"ranking": ["T2","T1","T3","T5","T6"], "reasoning": "T2 is worst"}',  # [3/5] GHOST
    # [4/5] correctness check needs no extra API call — every transform
    # preserves the original's exact #### line, so the numeric comparison
    # in check_correctness() short-circuits before any fallback API call.
]


def test_run_pipeline_happy_path_selects_ghost_top_ranked_variant():
    stub = StubProvider(HAPPY_PATH_QUEUE)
    result = run_pipeline("Natalia sold clips...", stub, mode="clean")

    assert result is not None
    assert result["safety_valve_triggered"] is False
    assert result["ranking"] == ["T2", "T1", "T3", "T5", "T6"]
    assert result["selected_variant"]["transformation_id"] == "T2"
    assert result["attempts"] == 1
    assert result["final_response"].rstrip().endswith("#### 72")
    assert stub.call_count == 7


def test_run_pipeline_returns_none_on_teacher_failure(failing_provider):
    result = run_pipeline("q", failing_provider, mode="clean")
    assert result is None


def test_run_pipeline_returns_none_when_transformations_fail_outright():
    class TeacherOnly(StubProvider):
        def complete(self, prompt, max_tokens=1024, system=None):
            self.calls.append((prompt, max_tokens, system))
            if len(self.calls) == 1:
                return CLEAN
            raise RuntimeError("boom")

    result = run_pipeline("q", TeacherOnly(), mode="clean")
    assert result is None


def test_run_pipeline_clean_mode_is_silent(capsys):
    stub = StubProvider(list(HAPPY_PATH_QUEUE))
    run_pipeline("q", stub, mode="clean")
    captured = capsys.readouterr()
    assert captured.out == ""


def test_run_pipeline_full_mode_prints_progress(capsys):
    stub = StubProvider(list(HAPPY_PATH_QUEUE))
    run_pipeline("q", stub, mode="full")
    captured = capsys.readouterr()
    assert "[1/5]" in captured.out
    assert "[5/5]" in captured.out
