"""Verified streaming HTTP for yt-dlp, with no fallback networking handlers.

The download child supplies its hard memory/cancellation boundary. Full media
streams have no sample-size limit; metadata-style read-all calls remain bounded.
"""

import io
import shutil
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import httpx
from yt_dlp.networking.common import RequestHandler, Response
from yt_dlp.networking.exceptions import RequestError

from app.core.downloader.errors import ProviderResolutionError
from app.core.downloader.provider_policy import _validate_request_url


@dataclass
class TransferState:
    directory: Path
    error: str | None = None

    def fail(self, code: str) -> None:
        self.error = code
        raise RequestError(code)


class StreamingBody(io.RawIOBase):
    def __init__(self, response, context, client, state: TransferState) -> None:
        self.response, self.context, self.client, self.state = (
            response,
            context,
            client,
            state,
        )
        self.chunks = response.iter_raw(65536)
        self.pending = bytearray()
        self.eof = False

    def readable(self) -> bool:
        return True

    def read(self, size: int | None = -1) -> bytes:
        all_bytes = size is None or size < 0
        maximum = 16 * 1024**2 if all_bytes else min(size, 16 * 1024**2)
        if not maximum:
            return b""
        result = bytearray()
        try:
            while len(result) < maximum:
                if not self.pending and not self.eof:
                    try:
                        self.pending.extend(next(self.chunks))
                    except StopIteration:
                        self.eof = True
                if not self.pending:
                    break
                if shutil.disk_usage(self.state.directory).free < 512 * 1024**2:
                    self.state.fail("storage_full")
                take = min(maximum - len(result), len(self.pending))
                result.extend(self.pending[:take])
                del self.pending[:take]
            if all_bytes and not self.eof:
                # A manifest/key read may not allocate an unbounded body. Media
                # downloaders use fixed-size reads instead of this branch.
                try:
                    if self.pending or next(self.chunks):
                        self.state.fail("extraction_error")
                except StopIteration:
                    self.eof = True
            return bytes(result)
        except httpx.HTTPError, OSError:
            self.state.fail("transport_failure")

    def close(self) -> None:
        if not self.closed:
            self.context.__exit__(None, None, None)
            self.client.close()
        super().close()


class VerifiedRH(RequestHandler):
    _SUPPORTED_URL_SCHEMES = ("https",)
    _SUPPORTED_PROXY_SCHEMES = ()

    def __init__(self, *, state: TransferState, **kwargs) -> None:
        super().__init__(**kwargs)
        self.state = state

    def _check_extensions(self, extensions):
        # yt-dlp may ask for a shorter timeout. It cannot relax the 120s ceiling.
        extensions.pop("timeout", None)

    def _send(self, request) -> Response:
        if request.method not in ("GET", "HEAD") or request.data is not None:
            self.state.fail("extraction_error")
        url = request.url
        for hop in range(3):
            client = None
            context = None
            try:
                if len(url.encode()) > 16384:
                    self.state.fail("extraction_error")
                host, _, address = _validate_request_url(url, stage="media transfer")
                headers = {
                    key: value
                    for key, value in self._merge_headers(request.headers).items()
                    if key.lower()
                    in ("range", "if-range", "user-agent", "referer", "accept")
                }
                headers.update(
                    {"Host": urlsplit(url).netloc, "Accept-Encoding": "identity"}
                )
                client = httpx.Client(
                    trust_env=False,
                    follow_redirects=False,
                    timeout=httpx.Timeout(120, connect=5, pool=1),
                )
                context = client.stream(
                    request.method,
                    httpx.URL(url).copy_with(host=address),
                    headers=headers,
                    extensions={"sni_hostname": host},
                )
                response = context.__enter__()
                if response.status_code in (301, 302, 303, 307, 308):
                    if hop == 2 or "location" not in response.headers:
                        self.state.fail("extraction_error")
                    url = urljoin(url, response.headers["location"])
                    context.__exit__(None, None, None)
                    client.close()
                    continue
                if response.status_code in (401, 403):
                    self.state.fail("challenge")
                if response.status_code in (404, 410):
                    self.state.fail("unavailable")
                if response.status_code not in (200, 206):
                    self.state.fail("transport_failure")
                if response.headers.get("content-encoding", "identity") != "identity":
                    self.state.fail("extraction_error")
                return Response(
                    StreamingBody(response, context, client, self.state),
                    url,
                    dict(response.headers),
                    status=response.status_code,
                )
            except BaseException as exc:
                if context is not None:
                    context.__exit__(None, None, None)
                if client is not None:
                    client.close()
                if isinstance(exc, (ValueError, ProviderResolutionError)):
                    self.state.fail("extraction_error")
                if isinstance(exc, (httpx.HTTPError, OSError)):
                    self.state.fail("transport_failure")
                raise
        self.state.fail("extraction_error")
