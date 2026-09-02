from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from urllib.parse import urlsplit


class InteractionUnavailableError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class BrowserRequest:
    url: str
    allowed_hosts: tuple[str, ...]
    timeout_seconds: int = 15
    max_text_chars: int = 20_000

    def __post_init__(self) -> None:
        try:
            parsed = urlsplit(self.url)
            port = parsed.port
        except ValueError as exc:
            raise ValueError("Browser request URL is invalid") from exc
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or port not in {None, 443}
        ):
            raise ValueError("Browser requests require credential-free HTTPS on port 443")
        if (
            not self.allowed_hosts
            or len(self.allowed_hosts) > 32
            or any(
                not isinstance(host, str)
                or not re.fullmatch(
                    r"[a-z0-9](?:[a-z0-9.-]{0,251}[a-z0-9])?", host,
                )
                for host in self.allowed_hosts
            )
        ):
            raise ValueError("Browser allowed hosts are invalid")
        if parsed.hostname.lower() not in self.allowed_hosts:
            raise ValueError("Browser destination is not allowlisted")
        if not 1 <= self.timeout_seconds <= 60:
            raise ValueError("Browser timeout must be from 1 to 60 seconds")
        if not 1 <= self.max_text_chars <= 100_000:
            raise ValueError("Browser result bound is invalid")


@dataclass(frozen=True, slots=True)
class BrowserResult:
    final_url: str
    title: str
    text: str
    status_code: int

    def __post_init__(self) -> None:
        if len(self.final_url) > 2_048 or len(self.title) > 512 or len(self.text) > 100_000:
            raise ValueError("Browser result exceeds contract bounds")
        if not 100 <= self.status_code <= 599:
            raise ValueError("Browser status code is invalid")


@dataclass(frozen=True, slots=True)
class ComputerAction:
    kind: str
    x: int | None = None
    y: int | None = None
    text: str | None = None
    key: str | None = None

    def __post_init__(self) -> None:
        if self.kind not in {"screenshot", "click", "type_text", "key"}:
            raise ValueError("Computer action is not supported")
        if self.kind == "click" and not (
            isinstance(self.x, int) and isinstance(self.y, int)
            and 0 <= self.x <= 32_767 and 0 <= self.y <= 32_767
        ):
            raise ValueError("Computer click coordinates are invalid")
        if self.kind == "type_text" and (
            not isinstance(self.text, str)
            or not self.text
            or len(self.text) > 4_096
            or "\x00" in self.text
        ):
            raise ValueError("Computer text is invalid")
        if self.kind == "key" and (
            not isinstance(self.key, str)
            or not re.fullmatch(r"[A-Za-z0-9_+-]{1,32}", self.key)
        ):
            raise ValueError("Computer key is invalid")


@dataclass(frozen=True, slots=True)
class ComputerResult:
    kind: str
    completed: bool
    evidence: str

    def __post_init__(self) -> None:
        if self.kind not in {"screenshot", "click", "type_text", "key"}:
            raise ValueError("Computer result action is invalid")
        if not isinstance(self.completed, bool):
            raise ValueError("Computer result status is invalid")
        if not isinstance(self.evidence, str) or len(self.evidence) > 1_024:
            raise ValueError("Computer result evidence is invalid")


class BrowserAdapter(ABC):
    @abstractmethod
    def browse(self, request: BrowserRequest) -> BrowserResult:
        raise NotImplementedError


class ComputerAdapter(ABC):
    @abstractmethod
    def perform(self, action: ComputerAction) -> ComputerResult:
        raise NotImplementedError


class DisabledBrowserAdapter(BrowserAdapter):
    def browse(self, request: BrowserRequest) -> BrowserResult:
        raise InteractionUnavailableError(
            "Browser execution is not configured in this environment"
        )


class DisabledComputerAdapter(ComputerAdapter):
    def perform(self, action: ComputerAction) -> ComputerResult:
        raise InteractionUnavailableError(
            "GUI computer execution is not configured in this environment"
        )


class InteractionService:
    """Provider-neutral boundary; deliberately not registered as an agent tool."""

    def __init__(
        self,
        browser: BrowserAdapter | None = None,
        computer: ComputerAdapter | None = None,
    ):
        self.browser = browser or DisabledBrowserAdapter()
        self.computer = computer or DisabledComputerAdapter()

    def browse(self, request: BrowserRequest) -> BrowserResult:
        result = self.browser.browse(request)
        try:
            parsed = urlsplit(result.final_url)
            port = parsed.port
        except ValueError as exc:
            raise ValueError("Browser result URL is invalid") from exc
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or port not in {None, 443}
            or parsed.hostname.lower() not in request.allowed_hosts
        ):
            raise ValueError("Browser result escaped the approved destination boundary")
        if len(result.text) > request.max_text_chars:
            raise ValueError("Browser result exceeds the request output limit")
        return result

    def perform(self, action: ComputerAction) -> ComputerResult:
        return self.computer.perform(action)

    def status(self) -> dict[str, object]:
        browser_ready = not isinstance(self.browser, DisabledBrowserAdapter)
        computer_ready = not isinstance(self.computer, DisabledComputerAdapter)
        return {
            "contract": "implemented",
            "browser": "test_harness" if browser_ready else "unavailable",
            "computer": "test_harness" if computer_ready else "unavailable",
            "live_browser_verified": False,
            "live_computer_verified": False,
            "agent_tool_registered": False,
        }
