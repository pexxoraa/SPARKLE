from __future__ import annotations

import hmac
import ipaddress
from dataclasses import dataclass
from urllib.parse import urlsplit

from sparkle.secrets import SecretNotFoundError, SecretResolver


def is_loopback_host(host: str) -> bool:
    normalized = host.strip().strip("[]").lower()
    if normalized == "localhost":
        return True
    try:
        return ipaddress.ip_address(normalized).is_loopback
    except ValueError:
        return False


def _validated_origin(value: str) -> str:
    if len(value) > 2_048:
        raise ValueError("Allowed origin exceeds 2048 characters")
    parsed = urlsplit(value)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.netloc
        or parsed.username
        or parsed.password
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError(f"Allowed origin must be an HTTP(S) origin: {value}")
    return f"{parsed.scheme.lower()}://{parsed.netloc.lower()}"


@dataclass(frozen=True, slots=True)
class APIAccessPolicy:
    resolver: SecretResolver
    required: bool = False
    token_refs: tuple[str, ...] = ("SPARKLE_API_TOKEN",)
    allowed_origins: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.token_refs or any(not reference for reference in self.token_refs):
            raise ValueError("API token references cannot be empty")
        validated = tuple(_validated_origin(origin) for origin in self.allowed_origins)
        object.__setattr__(self, "allowed_origins", validated)

    @property
    def configured(self) -> bool:
        return any(self.resolver.status(self.token_refs).values())

    def status(self) -> dict[str, object]:
        return {
            "authentication_required": self.required,
            "token_configured": self.configured,
            "allowed_origins": len(self.allowed_origins),
            "credentials_exposed": False,
        }

    def authorize(self, authorization: str | None) -> bool:
        if not self.required:
            return True
        if not authorization or len(authorization) > 4_096:
            return False
        scheme, separator, supplied = authorization.partition(" ")
        if separator != " " or scheme.lower() != "bearer" or not supplied:
            return False
        try:
            expected = self.resolver.first(self.token_refs)
        except SecretNotFoundError:
            return False
        return hmac.compare_digest(supplied.encode("utf-8"), expected.encode("utf-8"))

    def origin_allowed(self, origin: str | None, host_header: str | None) -> bool:
        if not origin:
            return True
        try:
            normalized = _validated_origin(origin)
        except ValueError:
            return False
        if normalized in self.allowed_origins:
            return True
        if not host_header or any(character in host_header for character in " /\\@"):
            return False
        host = host_header.lower()
        return normalized in {f"http://{host}", f"https://{host}"}

    def cors_headers(self, origin: str | None, host_header: str | None) -> dict[str, str]:
        if not origin or not self.origin_allowed(origin, host_header):
            return {}
        return {
            "Access-Control-Allow-Origin": _validated_origin(origin),
            "Vary": "Origin",
        }

    def validate_bind(self, host: str) -> None:
        if self.required and not self.configured:
            raise SecretNotFoundError(
                "API authentication is required but no API token reference is configured"
            )
        if is_loopback_host(host):
            return
        if not self.required:
            raise ValueError("Non-loopback API binding requires authentication")
