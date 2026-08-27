import pytest

from core.retry import exponential_delay, linear_delay, retry_async


def test_linear_delay_no_jitter():
    assert linear_delay(0, base=2, jitter_max=0) == 2.0
    assert linear_delay(2, base=2, jitter_max=0) == 6.0


def test_linear_delay_respects_cap():
    assert linear_delay(5, base=2, jitter_max=0, cap=5.0) == 5.0


def test_linear_delay_jitter_stays_in_expected_range():
    for _ in range(50):
        delay = linear_delay(1, base=2, jitter_max=1.0)
        assert 4.0 <= delay <= 6.0


def test_exponential_delay_no_jitter():
    assert exponential_delay(0, base_delay_ms=1000, jitter_ms=0) == 1.0
    assert exponential_delay(3, base_delay_ms=1000, jitter_ms=0) == 8.0


def test_exponential_delay_jitter_stays_in_expected_range():
    for _ in range(50):
        delay = exponential_delay(1, base_delay_ms=1000, jitter_ms=500)
        assert 2.0 <= delay <= 2.5


async def test_retry_async_succeeds_on_first_try():
    calls = []

    async def fn(attempt):
        calls.append(attempt)
        return "ok"

    result = await retry_async(fn, retries=3, delay_fn=lambda a: 0)
    assert result == "ok"
    assert calls == [0]


async def test_retry_async_succeeds_after_transient_failures():
    calls = []

    async def fn(attempt):
        calls.append(attempt)
        if attempt < 2:
            raise ValueError(f"boom on attempt {attempt}")
        return "ok"

    result = await retry_async(fn, retries=5, delay_fn=lambda a: 0)
    assert result == "ok"
    assert calls == [0, 1, 2]


async def test_retry_async_raises_last_error_after_exhausting_retries():
    calls = []

    async def fn(attempt):
        calls.append(attempt)
        raise ValueError(f"boom {attempt}")

    with pytest.raises(ValueError, match="boom 2"):
        await retry_async(fn, retries=3, delay_fn=lambda a: 0)

    assert calls == [0, 1, 2]
