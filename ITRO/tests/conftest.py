import os
import sys

# Tests live in ITRO/tests/ but the pipeline modules use flat absolute
# imports (from config import ..., from providers.base_provider import ...)
# that only resolve when ITRO/ itself is on sys.path — mirrors the bootstrap
# ITRO/__init__.py does for real usage.
_ITRO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ITRO_DIR not in sys.path:
    sys.path.insert(0, _ITRO_DIR)

import pytest
from providers.base_provider import BaseProvider


class StubProvider(BaseProvider):
    """
    Test double for BaseProvider — never touches network, GPU, or disk.

    Pass a fixed string to have every call() return the same text, or a
    list to have successive calls consume responses in order (useful for
    exercising retry loops that need different output per attempt).
    """

    def __init__(self, responses="stub response"):
        if isinstance(responses, str):
            self._fixed = responses
            self._queue = None
        else:
            self._fixed = None
            self._queue = list(responses)
        self.calls = []

    @property
    def name(self):
        return "Stub"

    def check_api_key(self):
        return True

    def call(self, prompt, max_tokens=None):
        self.calls.append((prompt, max_tokens))
        if self._fixed is not None:
            return self._fixed
        if not self._queue:
            raise RuntimeError("StubProvider ran out of queued responses")
        return self._queue.pop(0)

    @property
    def call_count(self):
        return len(self.calls)


class FailingProvider(BaseProvider):
    """Provider whose call() always raises — for exception-path tests."""

    @property
    def name(self):
        return "Failing"

    def check_api_key(self):
        return True

    def call(self, prompt, max_tokens=None):
        raise RuntimeError("simulated provider failure")


@pytest.fixture
def stub_provider():
    return StubProvider()


@pytest.fixture
def failing_provider():
    return FailingProvider()
