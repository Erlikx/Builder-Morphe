"""Shared curl_cffi session defaults used across the project.

curl_cffi's AsyncSession is used everywhere httpx.AsyncClient used to be.
It speaks the same requests-like API (get/post/patch/delete/stream, all
async) but additionally impersonates a real browser's TLS/JA3/HTTP2
fingerprint, which is important for endpoints (like GitHub's API/CDN)
that are sensitive to obvious non-browser clients.
"""

from curl_cffi.requests import AsyncSession

# A generic, regularly-updated Chrome fingerprint. Using the un-versioned
# "chrome" alias means curl_cffi picks its latest supported Chrome profile
# instead of us having to bump a hardcoded version (e.g. "chrome124").
IMPERSONATE = "chrome"


def new_session(*, timeout: float | None = 30, follow_redirects: bool = True, **kwargs) -> AsyncSession:
    """Create an AsyncSession with the project's default fingerprint/settings.

    Any keyword accepted by curl_cffi's AsyncSession can be overridden via
    kwargs (e.g. timeout=None for unbounded downloads).
    """
    return AsyncSession(
        timeout=timeout,
        allow_redirects=follow_redirects,
        impersonate=IMPERSONATE,
        **kwargs,
    )
