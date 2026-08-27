import asyncio
import random
from collections.abc import Awaitable, Callable

from . import log


def linear_delay(attempt: int, base: float, jitter_max: float = 0.0, cap: float | None = None) -> float:
    delay = (base + (random.uniform(0, jitter_max) if jitter_max else 0.0)) * (attempt + 1)
    return min(delay, cap) if cap is not None else delay


def exponential_delay(attempt: int, base_delay_ms: int, jitter_ms: int = 300) -> float:
    delay_ms = base_delay_ms * (2**attempt) + random.randint(0, jitter_ms)
    return delay_ms / 1000


async def retry_async(
    fn: Callable[[int], Awaitable],
    retries: int,
    delay_fn: Callable[[int], float],
    label: str = "operation",
):
    last_err: Exception | None = None

    for attempt in range(retries):
        try:
            return await fn(attempt)
        except Exception as err:
            last_err = err
            delay = delay_fn(attempt)
            log.warn(f"{label} (attempt {attempt + 1}/{retries}): {err} - retrying in {delay:.1f}s")
            await asyncio.sleep(delay)

    if last_err is not None:
        raise last_err
    raise RuntimeError(f"{label}: no attempts were made (retries={retries})")
