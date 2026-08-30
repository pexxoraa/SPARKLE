from __future__ import annotations

from dataclasses import dataclass
import json
import tempfile
from pathlib import Path
from typing import Any

from sparkle.config import load_json, model_config_path
from sparkle.content import SUPPORTED_CONTENT_TYPES
from sparkle.model import ModelAdapter, UnsupportedModalityError
from sparkle.providers.minimax import MiniMaxMessagesAdapter
from sparkle.secrets import SecretResolver


@dataclass(frozen=True, slots=True)
class ModelRecord:
    id: str
    provider: str
    model_id: str
    adapter: str
    roles: tuple[str, ...]
    modalities: tuple[str, ...]
    enabled: bool
    config: dict[str, Any]


class ModelRegistry:
    ADAPTERS = {"minimax_messages": MiniMaxMessagesAdapter}

    def __init__(self, path: Path | None = None, secrets: SecretResolver | None = None):
        self.path = path or model_config_path()
        self.secrets = secrets or SecretResolver()
        self._config = load_json(self.path)
        self._records: dict[str, ModelRecord] = {}
        self._instances: dict[str, ModelAdapter] = {}
        self._validate()

    def _validate(self) -> None:
        models = self._config.get("models")
        if not isinstance(models, list) or not models:
            raise ValueError("Model registry must contain at least one model")
        for raw in models:
            missing = {"id", "provider", "model_id", "adapter", "roles", "enabled"} - raw.keys()
            if missing:
                raise ValueError(f"Model record missing fields: {', '.join(sorted(missing))}")
            if raw["id"] in self._records:
                raise ValueError(f"Duplicate model record: {raw['id']}")
            if raw["adapter"] not in self.ADAPTERS:
                raise ValueError(f"Unknown adapter: {raw['adapter']}")
            modalities = raw.get("modalities", ["text"])
            if (
                not isinstance(modalities, list)
                or not modalities
                or any(item not in SUPPORTED_CONTENT_TYPES for item in modalities)
                or len(set(modalities)) != len(modalities)
            ):
                raise ValueError("Model modalities must be unique supported content types")
            self._records[raw["id"]] = ModelRecord(
                id=raw["id"], provider=raw["provider"], model_id=raw["model_id"],
                adapter=raw["adapter"], roles=tuple(raw["roles"]),
                modalities=tuple(modalities), enabled=bool(raw["enabled"]),
                config=raw,
            )
        active = self._config.get("active_model")
        if active not in self._records or not self._records[active].enabled:
            raise ValueError("active_model must reference an enabled record")

    @property
    def active_id(self) -> str:
        return str(self._config["active_model"])

    @property
    def routing(self) -> dict[str, str]:
        return dict(self._config.get("routing", {}))

    def list(self) -> list[dict[str, Any]]:
        return [
            {
                "id": record.id,
                "provider": record.provider,
                "model_id": record.model_id,
                "roles": list(record.roles),
                "modalities": list(record.modalities),
                "enabled": record.enabled,
                "active": record.id == self.active_id,
                "configured": any(self.secrets.status(record.config.get("secret_refs", [])).values()),
            }
            for record in self._records.values()
        ]

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=self.path.parent, delete=False) as handle:
            json.dump(self._config, handle, indent=2)
            handle.write("\n")
            temporary = Path(handle.name)
        temporary.replace(self.path)

    def activate(self, record_id: str) -> None:
        self.record(record_id)
        self._config["active_model"] = record_id
        self._config.setdefault("routing", {})["default"] = record_id
        self._save()

    def set_enabled(self, record_id: str, enabled: bool) -> None:
        record = self._records.get(record_id)
        if record is None:
            raise KeyError(f"Unknown model record: {record_id}")
        if not enabled and record_id == self.active_id:
            raise ValueError("Cannot disable the active model")
        for raw in self._config["models"]:
            if raw["id"] == record_id:
                raw["enabled"] = bool(enabled)
        self._records.clear()
        self._validate()
        self._save()

    def add(self, raw: dict[str, Any]) -> None:
        forbidden = {key for key in raw if any(token in key.lower() for token in ("api_key", "secret_value", "authorization"))}
        if forbidden:
            raise ValueError("Model records may contain secret references, never secret values")
        self._config["models"].append(dict(raw))
        self._records.clear()
        try:
            self._validate()
        except Exception:
            self._config["models"].pop()
            self._records.clear()
            self._validate()
            raise
        self._save()

    def remove(self, record_id: str) -> None:
        if record_id == self.active_id:
            raise ValueError("Cannot remove the active model")
        original = list(self._config["models"])
        self._config["models"] = [raw for raw in original if raw["id"] != record_id]
        if len(original) == len(self._config["models"]):
            raise KeyError(f"Unknown model record: {record_id}")
        self._records.clear()
        self._instances.pop(record_id, None)
        self._validate()
        self._save()

    def record(self, record_id: str) -> ModelRecord:
        try:
            record = self._records[record_id]
        except KeyError as exc:
            raise KeyError(f"Unknown model record: {record_id}") from exc
        if not record.enabled:
            raise ValueError(f"Model is disabled: {record_id}")
        return record

    def adapter(self, record_id: str | None = None) -> ModelAdapter:
        selected = record_id or self.active_id
        if selected not in self._instances:
            record = self.record(selected)
            adapter_class = self.ADAPTERS[record.adapter]
            self._instances[selected] = adapter_class(record.config, self.secrets)
        return self._instances[selected]

    def inject(self, record_id: str, adapter: ModelAdapter) -> None:
        self._instances[record_id] = adapter


class ModelRouter:
    def __init__(self, registry: ModelRegistry):
        self.registry = registry

    def select(
        self,
        capability: str = "general",
        *,
        modalities: set[str] | list[str] | tuple[str, ...] | None = None,
    ) -> ModelAdapter:
        required = set(modalities or {"text"})
        record_id = self.registry.routing.get(capability, self.registry.routing.get("default", self.registry.active_id))
        record = self.registry.record(record_id)
        if capability not in record.roles and capability != "general":
            candidates = [item for item in self.registry._records.values() if item.enabled and capability in item.roles]
            if candidates:
                record_id = candidates[0].id
        adapter = self.registry.adapter(record_id)
        if adapter.supports(required):
            return adapter
        for candidate in self.registry._records.values():
            if not candidate.enabled or candidate.id == record_id:
                continue
            if capability != "general" and capability not in candidate.roles:
                continue
            alternate = self.registry.adapter(candidate.id)
            if alternate.supports(required):
                return alternate
        raise UnsupportedModalityError(
            required - adapter.supported_modalities,
            model_id=adapter.model_id,
            provider=adapter.provider,
        )
