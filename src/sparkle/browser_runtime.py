from __future__ import annotations

import http.client
import ipaddress
import socket
import ssl
from html.parser import HTMLParser
from typing import Callable, Mapping
from urllib.parse import urljoin, urlsplit

from sparkle.interaction import (
    BrowserAdapter,
    BrowserRequest,
    BrowserResult,
    InteractionService,
)


class BrowserTransportError(RuntimeError):
    pass


class _TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self._title_depth = 0
        self.title_parts: list[str] = []
        self.text_parts: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() == "title":
            self._title_depth += 1

    def handle_endtag(self, tag):
        if tag.lower() == "title" and self._title_depth:
            self._title_depth -= 1

    def handle_data(self, data):
        value = " ".join(data.split())
        if not value:
            return
        self.text_parts.append(value)
        if self._title_depth:
            self.title_parts.append(value)

    def result(self) -> tuple[str, str]:
        title = " ".join(self.title_parts).strip()
        text = "\n".join(self.text_parts).strip()
        return title, text


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    def __init__(
        self,
        host: str,
        pinned_ip: str,
        *,
        timeout: float,
        context: ssl.SSLContext,
    ):
        self._pinned_ip = pinned_ip
        super().__init__(host, port=443, timeout=timeout, context=context)

    def connect(self) -> None:
        raw = socket.create_connection(
            (self._pinned_ip, 443),
            self.timeout,
            self.source_address,
        )
        if self._tunnel_host:
            self.sock = raw
            self._tunnel()
            server_hostname = self._tunnel_host
        else:
            server_hostname = self.host
        self.sock = self._context.wrap_socket(
            raw,
            server_hostname=server_hostname,
        )


Fetcher = Callable[
    [str, str, int, int],
    tuple[int, Mapping[str, str], bytes],
]
Resolver = Callable[[str], list[str]]


class SafeHTTPSBrowserAdapter(BrowserAdapter):
    """Bounded read-only HTTPS browser with DNS and redirect revalidation."""

    MAX_REDIRECTS = 5
    MAX_RESPONSE_BYTES = 1_000_000
    ALLOWED_CONTENT_TYPES = frozenset(
        {
            "text/html",
            "text/plain",
            "application/json",
            "application/xml",
            "text/xml",
        }
    )

    def __init__(
        self,
        *,
        resolver: Resolver | None = None,
        fetcher: Fetcher | None = None,
        ssl_context: ssl.SSLContext | None = None,
    ):
        self.resolver = resolver or self._resolve
        self.fetcher = fetcher or self._fetch
        self.ssl_context = ssl_context or ssl.create_default_context()

    @staticmethod
    def _resolve(host: str) -> list[str]:
        try:
            values = socket.getaddrinfo(
                host,
                443,
                type=socket.SOCK_STREAM,
                proto=socket.IPPROTO_TCP,
            )
        except OSError as exc:
            raise BrowserTransportError(
                f"Browser DNS resolution failed ({type(exc).__name__})"
            ) from exc
        return sorted({item[4][0] for item in values})

    @staticmethod
    def _global_ip(raw: str) -> str:
        try:
            address = ipaddress.ip_address(raw)
        except ValueError as exc:
            raise BrowserTransportError(
                "Browser resolver returned an invalid IP"
            ) from exc
        if not address.is_global:
            raise BrowserTransportError(
                "Browser destination resolved to a non-public address"
            )
        return str(address)

    def _approved_ip(self, host: str) -> str:
        values = self.resolver(host)
        if not isinstance(values, list) or not values or len(values) > 32:
            raise BrowserTransportError("Browser DNS result is invalid")
        approved = [self._global_ip(value) for value in values]
        return sorted(approved)[0]

    def _fetch(
        self,
        url: str,
        pinned_ip: str,
        timeout_seconds: int,
        max_bytes: int,
    ) -> tuple[int, Mapping[str, str], bytes]:
        parsed = urlsplit(url)
        host = parsed.hostname
        if host is None:
            raise BrowserTransportError("Browser URL has no host")
        target = parsed.path or "/"
        if parsed.query:
            target += "?" + parsed.query
        connection = _PinnedHTTPSConnection(
            host,
            pinned_ip,
            timeout=float(timeout_seconds),
            context=self.ssl_context,
        )
        try:
            connection.request(
                "GET",
                target,
                headers={
                    "Host": host,
                    "Accept": "text/html,text/plain,application/json,application/xml;q=0.9,*/*;q=0.1",
                    "Accept-Encoding": "identity",
                    "User-Agent": "SPARKLE-Browser/0.30",
                    "Connection": "close",
                },
            )
            response = connection.getresponse()
            length = response.getheader("Content-Length")
            if length is not None:
                try:
                    if int(length) > max_bytes:
                        raise BrowserTransportError(
                            "Browser response exceeds the byte limit"
                        )
                except ValueError as exc:
                    raise BrowserTransportError(
                        "Browser Content-Length is invalid"
                    ) from exc
            body = response.read(max_bytes + 1)
            if len(body) > max_bytes:
                raise BrowserTransportError(
                    "Browser response exceeds the byte limit"
                )
            headers = {
                key.lower(): value
                for key, value in response.getheaders()
            }
            return int(response.status), headers, body
        except BrowserTransportError:
            raise
        except (OSError, ssl.SSLError, http.client.HTTPException) as exc:
            raise BrowserTransportError(
                f"Browser transport failed ({type(exc).__name__})"
            ) from exc
        finally:
            connection.close()

    @staticmethod
    def _charset(content_type: str) -> str:
        for part in content_type.split(";")[1:]:
            name, separator, value = part.strip().partition("=")
            if separator and name.lower() == "charset":
                normalized = value.strip().strip('"').lower()
                if normalized in {
                    "utf-8", "utf8", "us-ascii", "iso-8859-1", "latin-1",
                }:
                    return (
                        "latin-1"
                        if normalized in {"iso-8859-1", "latin-1"}
                        else normalized
                    )
                raise BrowserTransportError(
                    "Browser response charset is unsupported"
                )
        return "utf-8"

    @classmethod
    def _decode(
        cls,
        headers: Mapping[str, str],
        body: bytes,
        max_text_chars: int,
    ) -> tuple[str, str]:
        raw_type = headers.get("content-type", "text/plain")
        media_type = raw_type.split(";", 1)[0].strip().lower()
        if media_type not in cls.ALLOWED_CONTENT_TYPES:
            raise BrowserTransportError(
                f"Browser content type is unsupported: {media_type or 'missing'}"
            )
        if headers.get("content-encoding", "identity").lower() not in {
            "", "identity",
        }:
            raise BrowserTransportError(
                "Browser compressed responses are not accepted"
            )
        try:
            decoded = body.decode(cls._charset(raw_type), errors="strict")
        except UnicodeDecodeError as exc:
            raise BrowserTransportError(
                "Browser response text encoding is invalid"
            ) from exc
        if media_type == "text/html":
            parser = _TextExtractor()
            try:
                parser.feed(decoded)
                parser.close()
            except Exception as exc:
                raise BrowserTransportError(
                    "Browser HTML parsing failed"
                ) from exc
            title, text = parser.result()
        else:
            title, text = "", decoded.strip()
        if len(title) > 512 or len(text) > max_text_chars:
            raise BrowserTransportError(
                "Browser extracted text exceeds the request limit"
            )
        return title, text

    @staticmethod
    def _validate_url(url: str, allowed_hosts: tuple[str, ...]) -> str:
        BrowserRequest(url, allowed_hosts)
        return url

    def browse(self, request: BrowserRequest) -> BrowserResult:
        current = request.url
        visited: set[str] = set()
        max_bytes = min(
            self.MAX_RESPONSE_BYTES,
            max(16_384, request.max_text_chars * 8),
        )
        for redirect_count in range(self.MAX_REDIRECTS + 1):
            current = self._validate_url(current, request.allowed_hosts)
            if current in visited:
                raise BrowserTransportError("Browser redirect loop detected")
            visited.add(current)
            host = urlsplit(current).hostname
            if host is None:
                raise BrowserTransportError("Browser URL has no host")
            pinned_ip = self._approved_ip(host)
            status, headers, body = self.fetcher(
                current,
                pinned_ip,
                request.timeout_seconds,
                max_bytes,
            )
            if not 100 <= status <= 599:
                raise BrowserTransportError(
                    "Browser transport returned an invalid status"
                )
            if status in {301, 302, 303, 307, 308}:
                if redirect_count >= self.MAX_REDIRECTS:
                    raise BrowserTransportError(
                        "Browser redirect limit exceeded"
                    )
                location = headers.get("location")
                if not isinstance(location, str) or not location.strip():
                    raise BrowserTransportError(
                        "Browser redirect is missing a location"
                    )
                current = urljoin(current, location.strip())
                continue
            title, text = self._decode(
                headers,
                body,
                request.max_text_chars,
            )
            return BrowserResult(current, title, text, status)
        raise BrowserTransportError("Browser redirect limit exceeded")


class DefaultInteractionService(InteractionService):
    """Interaction service with the safe HTTPS browser enabled by default."""

    def __init__(self, *, computer=None, session_store=None, browser=None):
        super().__init__(
            browser=browser or SafeHTTPSBrowserAdapter(),
            computer=computer,
            session_store=session_store,
        )
