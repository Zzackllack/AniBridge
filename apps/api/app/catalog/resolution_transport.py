"""A shared wall/request/byte budget for one user-local resolution attempt.

Blocking DNS and parser code must run in the supervised job child. This class
never provides a browser, ambient proxy, or unbounded retry path.
"""

import time
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlsplit

import httpx

from app.core.downloader.errors import ProviderResolutionError
from app.core.downloader.provider_policy import (
    _validate_request_url,
    looks_like_verification_page,
)


class ResolutionError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class Page:
    url: str = field(repr=False)
    text: str = field(repr=False)


class Budget:
    def __init__(
        self,
        *,
        seconds: float = 60,
        requests: int = 16,
        body_bytes: int = 16 * 1024**2,
        clock=time.monotonic,
        client: httpx.Client | None = None,
        validate_url=_validate_request_url,
    ) -> None:
        if (
            not 0 < seconds <= 60
            or not 0 < requests <= 16
            or not 0 < body_bytes <= 32 * 1024**2
        ):
            raise ValueError("invalid resolution budget")
        self.clock, self.deadline = clock, clock() + seconds
        self.requests_left, self.bytes_left = requests, body_bytes
        self.validate_url = validate_url
        self.client = client or httpx.Client(trust_env=False, follow_redirects=False)

    def close(self) -> None:
        self.client.close()

    def remaining(self) -> float:
        left = self.deadline - self.clock()
        if left <= 0:
            raise ResolutionError("transport_failure")
        return left

    def get(self, url: str, *, origin: str | None = None) -> Page:
        final_url, body = self._read(url, origin=origin)
        text = body.decode("utf-8", errors="replace")
        if looks_like_verification_page(text):
            raise ResolutionError("challenge")
        return Page(final_url, text)

    def get_megakino(self, url: str, *, origin: str) -> Page:
        """At most one exact same-origin cookie bootstrap within this budget."""
        from catalog_core.providers.megakino_session import bootstrap

        target = urlsplit(url)
        if target.scheme != "https" or target.query or target.fragment:
            raise ResolutionError("extraction_error")
        jar = httpx.Cookies()
        final, body = self._read(url, origin=origin, cookies=jar)
        if bootstrap(body, target.path):
            self._read(
                origin.rstrip("/") + "/index.php?yg=token",
                origin=origin,
                cookies=jar,
                token=True,
            )
            final, body = self._read(url, origin=origin, cookies=jar)
            if bootstrap(body, target.path):
                raise ResolutionError("challenge")
        text = body.decode("utf-8", errors="replace")
        if looks_like_verification_page(text):
            raise ResolutionError("challenge")
        return Page(final, text)

    def prefix(self, url: str, maximum: int) -> bytes:
        """Read a bounded prefix; a server ignoring Range cannot enlarge it."""
        if not 0 < maximum <= self.bytes_left:
            raise ResolutionError("extraction_error")
        _url, body = self._read(url, maximum=maximum)
        if looks_like_verification_page(body[:8192].decode("utf-8", errors="replace")):
            raise ResolutionError("challenge")
        return body

    def _read(
        self,
        url: str,
        *,
        origin: str | None = None,
        maximum: int | None = None,
        cookies: httpx.Cookies | None = None,
        token: bool = False,
    ) -> tuple[str, bytes]:
        """Every redirect consumes the same attempt budget and repeats DNS policy."""
        for hop in range(3):
            self.remaining()
            if self.requests_left <= 0:
                raise ResolutionError("extraction_error")
            target = urlsplit(url)
            if origin and (target.scheme, target.netloc) != (
                urlsplit(origin).scheme,
                urlsplit(origin).netloc,
            ):
                raise ResolutionError("extraction_error")
            if cookies is not None and (
                target.scheme != "https"
                or target.fragment
                or (
                    token
                    and (target.path != "/index.php" or target.query != "yg=token")
                )
                or (not token and target.query)
            ):
                raise ResolutionError("extraction_error")
            try:
                logical = httpx.Request("GET", url)
                if cookies is not None:
                    cookies.set_cookie_header(logical)
                    if len(logical.headers.get("cookie", "").encode()) > 8192:
                        raise ResolutionError("extraction_error")
                host, _, address = self.validate_url(url, stage="local resolution")
                self.requests_left -= 1
                remaining = self.remaining()
                pinned = httpx.URL(url).copy_with(host=address)
                # Do not propagate upstream cookies/auth between origins.
                self.client.cookies.clear()
                with self.client.stream(
                    "GET",
                    pinned,
                    headers={
                        "Host": target.netloc,
                        "Accept-Encoding": "identity",
                        **(
                            {"Cookie": logical.headers["cookie"]}
                            if "cookie" in logical.headers
                            else {}
                        ),
                        **({"Range": f"bytes=0-{maximum - 1}"} if maximum else {}),
                    },
                    extensions={"sni_hostname": host},
                    timeout=httpx.Timeout(
                        min(10, remaining),
                        connect=min(5, remaining),
                        pool=min(1, remaining),
                    ),
                    follow_redirects=False,
                ) as response:
                    if cookies is not None:
                        from catalog_core.providers.megakino_session import (
                            extract_cookies,
                        )

                        extract_cookies(cookies, response, logical)
                    if token and response.status_code == 204:
                        return url, b""
                    if response.status_code in (301, 302, 303, 307, 308):
                        if hop == 2 or "location" not in response.headers:
                            raise ResolutionError("extraction_error")
                        url = urljoin(url, response.headers["location"])
                        continue
                    if response.status_code in (401, 403):
                        raise ResolutionError("challenge")
                    if response.status_code in (404, 410):
                        raise ResolutionError("unavailable")
                    if response.status_code not in ((200, 206) if maximum else (200,)):
                        raise ResolutionError("transport_failure")
                    if (
                        response.headers.get("content-encoding", "identity")
                        != "identity"
                    ):
                        raise ResolutionError("extraction_error")
                    body = bytearray()
                    for chunk in response.iter_raw(min(65536, maximum or 65536)):
                        self.remaining()
                        self.bytes_left -= len(chunk)
                        if self.bytes_left < 0:
                            raise ResolutionError("extraction_error")
                        if maximum is not None:
                            body.extend(chunk[: maximum - len(body)])
                            if len(body) >= maximum:
                                break
                        else:
                            body.extend(chunk)
                    self.remaining()
                    return url, bytes(body)
            except ResolutionError:
                raise
            except httpx.HTTPError, OSError:
                raise ResolutionError("transport_failure") from None
            except ValueError, ProviderResolutionError:
                raise ResolutionError("extraction_error") from None
        raise ResolutionError("extraction_error")
