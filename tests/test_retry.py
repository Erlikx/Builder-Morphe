import pytest
from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt

from core import retry


def test_incrementing_and_exponential_return_wait_strategies():
    # The exact backoff numbers are tenacity's own well-tested formulas, so
    # this just checks our helpers hand tenacity something it can call
    # directly as a `wait=` strategy.
    assert callable(retry.incrementing(start=1.0, increment=1.0, max=5.0))
    assert callable(retry.exponential_with_jitter(max=5.0))
    assert callable(retry.incrementing(start=1.0, increment=1.0, jitter=2.0))


class _FakeOutcome:
    def __init__(self, exc):
        self._exc = exc

    def exception(self):
        return self._exc


class _FakeNextAction:
    def __init__(self, sleep):
        self.sleep = sleep


class _FakeRetryState:
    def __init__(self, attempt_number, exc, sleep):
        self.attempt_number = attempt_number
        self.outcome = _FakeOutcome(exc)
        self.next_action = _FakeNextAction(sleep)


def test_before_sleep_logs_label_attempt_error_and_delay(monkeypatch):
    messages = []
    monkeypatch.setattr("core.retry.log.warn", messages.append)

    hook = retry.before_sleep("Some flaky operation")
    hook(_FakeRetryState(attempt_number=2, exc=RuntimeError("boom"), sleep=3.25))

    assert len(messages) == 1
    assert "Some flaky operation" in messages[0]
    assert "attempt 2" in messages[0]
    assert "boom" in messages[0]
    assert "3.2s" in messages[0] or "3.3s" in messages[0]


async def test_retry_conf_wait_strategy_works_with_real_tenacity_retrying():
    calls = {"n": 0}

    async def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise RuntimeError("not yet")
        return "ok"

    result = None
    async for attempt in AsyncRetrying(
        stop=stop_after_attempt(5),
        wait=retry.incrementing(start=0.0, increment=0.0),
        retry=retry_if_exception_type(RuntimeError),
        reraise=True,
    ):
        with attempt:
            result = await flaky()

    assert result == "ok"
    assert calls["n"] == 3


async def test_retry_conf_reraises_after_exhausting_attempts():
    async def always_fails():
        raise RuntimeError("nope")

    with pytest.raises(RuntimeError, match="nope"):
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(3),
            wait=retry.incrementing(start=0.0, increment=0.0),
            retry=retry_if_exception_type(RuntimeError),
            reraise=True,
        ):
            with attempt:
                await always_fails()
