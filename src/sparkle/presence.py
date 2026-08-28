from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime


@dataclass(slots=True)
class PresenceState:
    mode: str = "idle"
    activity: str = "Ready"
    agent: str | None = None
    trace_id: str | None = None
    updated_at: str = ""


class PresenceEngine:
    """Embodiment-neutral state for dashboard animation and future motion adapters."""

    def __init__(self):
        self.state = PresenceState(updated_at=datetime.now(UTC).isoformat())

    def update(self, mode: str, activity: str, *, agent: str | None = None, trace_id: str | None = None) -> None:
        self.state = PresenceState(mode, activity, agent, trace_id, datetime.now(UTC).isoformat())

    def status(self) -> dict[str, str | None]:
        return asdict(self.state)
