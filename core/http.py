from curl_cffi.requests import AsyncSession

# Generic alias that curl_cffi always maps to its latest supported Firefox
# fingerprint, so this never needs bumping by hand as new versions ship.
IMPERSONATE = "firefox"


def new_session(*, timeout: float | None = 30, follow_redirects: bool = True, **kwargs) -> AsyncSession:
    return AsyncSession(
        timeout=timeout,  # type: ignore[arg-type]  # curl_cffi accepts None (no timeout) at runtime; stub omits it
        allow_redirects=follow_redirects,
        impersonate=IMPERSONATE,
        **kwargs,
    )
