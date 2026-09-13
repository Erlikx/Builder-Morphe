çfrom curl_cffi.requests import AsyncSession

IMPERSONATE = "firefox"


def new_session(*, timeout: float | None = 30, follow_redirects: bool = True, **kwargs) -> AsyncSession:
    return AsyncSession(
        timeout=timeout,  # type: ignore[arg-type]
        allow_redirects=follow_redirects,
        impersonate=IMPERSONATE,
        **kwargs,
    )
