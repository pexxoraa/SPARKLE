from __future__ import annotations

from collections.abc import Callable, Mapping
from copy import deepcopy
from dataclasses import dataclass
import json
import re
import tempfile
from pathlib import Path
from typing import Any

from sparkle.config import load_json, model_config_path
from sparkle.content import SUPPORTED_CONTENT_TYPES
from sparkle.model import ModelAdapter, ModelError, ModelSelectionError, UnsupportedModalityError
from sparkle.model_runtime import (
    ModelHealthMonitor, ModelRuntimeStore, RoutingDecision,
)
from sparkle.providers.minimax import MiniMaxMessagesAdapter
from sparkle.providers.nvidia import NVIDIAChatCompletionsAdapter
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
    BUILTIN_ADAPTERS = {
        "minimax_messages": MiniMaxMessagesAdapter,
        "nvidia_chat_completions": NVIDIAChatCompletionsAdapter,
    }
    SAFE_IDENTIFIER = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.:/+-]{0,127}$")
    SAFE_SECRET_REF = re.compile(r"^[A-Z][A-Z0-9_]{1,127}$")
    FORBIDDEN_SECRET_FIELDS = (
        "api_key", "authorization", "password", "secret_value", "token_value",
    )

    def __init__(
        self,
        path: Path | None = None,
        secrets: SecretResolver | None = None,
        *,
        adapter_factories: Mapping[
            str, Callable[[dict[str, Any], SecretResolver], ModelAdapter]
        ] | None = None,
        runtime_store: ModelRuntimeStore | None = None,
    ):
        self.path = path or model_config_path()
        self.secrets = secrets or SecretResolver()
        self._adapter_factories = dict(self.BUILTIN_ADAPTERS)
        for name, factory in dict(adapter_factories or {}).items():
            if not isinstance(name, str) or not self.SAFE_IDENTIFIER.fullmatch(name):
                raise ValueError("Adapter factory name is invalid")
            if not callable(factory):
                raise ValueError("Adapter factory must be callable")
            self._adapter_factories[name] = factory
        self._config = load_json(self.path)
        self._records: dict[str, ModelRecord] = {}
        self._instances: dict[str, ModelAdapter] = {}
        self._injected_ids: set[str] = set()
        self._validate()
        self.runtime = runtime_store or ModelRuntimeStore()
        self.health = ModelHealthMonitor(self, self.runtime)

    @classmethod
    def _string(cls, value: Any, field: str) -> str:
        if not isinstance(value, str) or not cls.SAFE_IDENTIFIER.fullmatch(value):
            raise ValueError(f"Model {field} is invalid")
        return value

    @classmethod
    def _reject_secret_values(cls, value: Any) -> None:
        if isinstance(value, dict):
            for key, nested in value.items():
                if not isinstance(key, str):
                    raise ValueError("Model configuration keys must be strings")
                lowered = key.lower()
                if any(token in lowered for token in cls.FORBIDDEN_SECRET_FIELDS):
                    raise ValueError(
                        "Model records may contain secret references, never secret values"
                    )
                cls._reject_secret_values(nested)
        elif isinstance(value, list):
            for nested in value:
                cls._reject_secret_values(nested)

    def _validate(self) -> None:
        if not isinstance(self._config, dict):
            raise ValueError("Model registry must be an object")
        self._reject_secret_values(self._config)
        models = self._config.get("models")
        if not isinstance(models, list) or not models:
            raise ValueError("Model registry must contain at least one model")
        records: dict[str, ModelRecord] = {}
        for raw in models:
            if not isinstance(raw, dict):
                raise ValueError("Model records must be objects")
            missing = {"id", "provider", "model_id", "adapter", "roles", "enabled"} - raw.keys()
            if missing:
                raise ValueError(f"Model record missing fields: {', '.join(sorted(missing))}")
            record_id = self._string(raw["id"], "id")
            provider = self._string(raw["provider"], "provider")
            model_id = self._string(raw["model_id"], "model_id")
            adapter = self._string(raw["adapter"], "adapter")
            if record_id in records:
                raise ValueError(f"Duplicate model record: {record_id}")
            if adapter not in self._adapter_factories:
                raise ValueError(f"Unknown adapter: {adapter}")
            roles = raw["roles"]
            if (
                not isinstance(roles, list)
                or not roles
                or len(roles) > 32
                or any(not isinstance(role, str) or not self.SAFE_IDENTIFIER.fullmatch(role) for role in roles)
                or len(set(roles)) != len(roles)
            ):
                raise ValueError("Model roles must be unique safe identifiers")
            modalities = raw.get("modalities", ["text"])
            if (
                not isinstance(modalities, list)
                or not modalities
                or any(item not in SUPPORTED_CONTENT_TYPES for item in modalities)
                or len(set(modalities)) != len(modalities)
            ):
                raise ValueError("Model modalities must be unique supported content types")
            if not isinstance(raw["enabled"], bool):
                raise ValueError("Model enabled must be boolean")
            for boolean_field in (
                "supports_streaming", "supports_tools", "allow_fallback",
            ):
                if boolean_field in raw and not isinstance(raw[boolean_field], bool):
                    raise ValueError(f"Model {boolean_field} must be boolean")
            latency_class = raw.get("latency_class", "balanced")
            if latency_class not in {"fast", "balanced", "deep"}:
                raise ValueError("Model latency_class is invalid")
            timeout_seconds = raw.get("timeout_seconds", 120)
            if (
                isinstance(timeout_seconds, bool)
                or not isinstance(timeout_seconds, (int, float))
                or not 1 <= float(timeout_seconds) <= 600
            ):
                raise ValueError("Model timeout_seconds must be from 1 to 600")
            secret_refs = raw.get("secret_refs", [])
            if (
                not isinstance(secret_refs, list)
                or len(secret_refs) > 16
                or any(
                    not isinstance(reference, str)
                    or not self.SAFE_SECRET_REF.fullmatch(reference)
                    for reference in secret_refs
                )
                or len(set(secret_refs)) != len(secret_refs)
            ):
                raise ValueError("Model secret_refs must be unique environment references")
            records[record_id] = ModelRecord(
                id=record_id, provider=provider, model_id=model_id,
                adapter=adapter, roles=tuple(roles),
                modalities=tuple(modalities), enabled=raw["enabled"],
                config=raw,
            )
        active = self._config.get("active_model")
        if active not in records or not records[active].enabled:
            raise ValueError("active_model must reference an enabled record")
        routing = self._config.get("routing", {})
        if not isinstance(routing, dict):
            raise ValueError("Model routing must be an object")
        for capability, record_id in routing.items():
            self._string(capability, "routing capability")
            if record_id not in records or not records[record_id].enabled:
                raise ValueError("Model routing must reference enabled records")
            if capability != "default" and capability not in records[record_id].roles:
                raise ValueError("Model routing capability must match record roles")
        self._records = records

    @property
    def active_id(self) -> str:
        return str(self._config["active_model"])

    @property
    def routing(self) -> dict[str, str]:
        return dict(self._config.get("routing", {}))

    def list(self) -> list[dict[str, Any]]:
        result = []
        for record in self._records.values():
            secret_refs = record.config.get("secret_refs", [])
            health = self.health.status(record.id)
            result.append({
                "id": record.id,
                "provider": record.provider,
                "model_id": record.model_id,
                "adapter": record.adapter,
                "roles": list(record.roles),
                "modalities": list(record.modalities),
                "enabled": record.enabled,
                "active": record.id == self.active_id,
                "configured": (
                    not secret_refs
                    or any(self.secrets.status(secret_refs).values())
                ),
                "health": health["state"],
                "health_reason": health["reason"],
                "health_observed_at": health.get("observed_at"),
                "health_evidence_source": health.get("evidence_source"),
            })
        return result

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
        if not isinstance(enabled, bool):
            raise ValueError("Model enabled must be boolean")
        record = self._records.get(record_id)
        if record is None:
            raise KeyError(f"Unknown model record: {record_id}")
        if not enabled and record_id == self.active_id:
            raise ValueError("Cannot disable the active model")
        original = deepcopy(self._config)
        try:
            for raw in self._config["models"]:
                if raw["id"] == record_id:
                    raw["enabled"] = bool(enabled)
            self._validate()
        except Exception:
            self._config = original
            self._validate()
            raise
        self._instances.pop(record_id, None)
        self._injected_ids.discard(record_id)
        self._save()

    def add(self, raw: dict[str, Any]) -> None:
        self._config["models"].append(dict(raw))
        try:
            self._validate()
        except Exception:
            self._config["models"].pop()
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
        try:
            self._validate()
        except Exception:
            self._config["models"] = original
            self._validate()
            raise
        self._instances.pop(record_id, None)
        self._injected_ids.discard(record_id)
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
            adapter_factory = self._adapter_factories[record.adapter]
            instance = adapter_factory(record.config, self.secrets)
            if not isinstance(instance, ModelAdapter):
                raise ValueError("Adapter factory returned an invalid model adapter")
            if instance.provider != record.provider or instance.model_id != record.model_id:
                raise ValueError("Adapter identity does not match the model record")
            if not set(record.modalities).issubset(instance.supported_modalities):
                raise ValueError("Adapter does not implement declared model modalities")
            self._instances[selected] = instance
        return self._instances[selected]

    def inject(self, record_id: str, adapter: ModelAdapter) -> None:
        record = self.record(record_id)
        if not isinstance(adapter, ModelAdapter):
            raise ValueError("Injected adapter must implement ModelAdapter")
        if not set(record.modalities).issubset(adapter.supported_modalities):
            raise ValueError("Injected adapter does not implement declared modalities")
        self._instances[record_id] = adapter
        self._injected_ids.add(record_id)


class ModelRouter:
    def __init__(self, registry: ModelRegistry):
        self.registry = registry

    def select(
        self,
        capability: str = "general",
        *,
        modalities: set[str] | list[str] | tuple[str, ...] | None = None,
    ) -> ModelAdapter:
        return self.select_with_record(
            capability, modalities=modalities,
        )[1]

    def select_with_record(
        self,
        capability: str = "general",
        *,
        modalities: set[str] | list[str] | tuple[str, ...] | None = None,
    ) -> tuple[str, ModelAdapter]:
        """Return the selected registry ID with its adapter for disclosure."""
        if not isinstance(capability, str) or not self.registry.SAFE_IDENTIFIER.fullmatch(capability):
            raise ValueError("Model capability is invalid")
        required = set(modalities or {"text"})
        preferred = self.registry.routing.get(
            capability, self.registry.routing.get("default", self.registry.active_id),
        )
        ordered_ids = [preferred, *sorted(set(self.registry._records) - {preferred})]
        for record_id in ordered_ids:
            candidate = self.registry._records[record_id]
            if not candidate.enabled or capability not in candidate.roles:
                continue
            if (
                record_id not in self.registry._injected_ids
                and not required.issubset(candidate.modalities)
            ):
                continue
            adapter = self.registry.adapter(record_id)
            if adapter.supports(required):
                return record_id, adapter
        preferred_record = self.registry.record(preferred)
        preferred_adapter = self.registry.adapter(preferred)
        raise UnsupportedModalityError(
            required - set(preferred_adapter.supported_modalities) or required,
            model_id=preferred_adapter.model_id,
            provider=preferred_adapter.provider,
        )

    def decide(
        self,
        capability: str = "general",
        *,
        modalities: set[str] | list[str] | tuple[str, ...] | None = None,
        tools_required: bool = False,
        streaming_required: bool = False,
        latency_policy: str = "balanced",
        max_timeout_seconds: float | None = None,
        excluded: set[str] | None = None,
    ) -> tuple[RoutingDecision, ModelAdapter]:
        if not isinstance(capability, str) or not self.registry.SAFE_IDENTIFIER.fullmatch(capability):
            raise ValueError("Model capability is invalid")
        required = set(modalities or {"text"})
        if latency_policy not in {"fast", "balanced", "deep"}:
            raise ValueError("Model latency policy is invalid")
        if max_timeout_seconds is not None and (
            isinstance(max_timeout_seconds, bool)
            or not isinstance(max_timeout_seconds, (int, float))
            or not 1 <= float(max_timeout_seconds) <= 600
        ):
            raise ValueError("Model timeout policy must be from 1 to 600 seconds")
        excluded_ids = set(excluded or set())
        preferred = self.registry.routing.get(
            capability, self.registry.routing.get("default", self.registry.active_id),
        )
        candidates = []
        for record_id, record in self.registry._records.items():
            if record_id in excluded_ids or not record.enabled:
                continue
            if excluded_ids and not bool(record.config.get("allow_fallback", False)):
                continue
            if capability not in record.roles:
                continue
            if (
                record_id not in self.registry._injected_ids
                and not required.issubset(record.modalities)
            ):
                continue
            if tools_required and (
                "tool_use" not in record.roles
                or not bool(record.config.get("supports_tools", True))
            ):
                continue
            if streaming_required and not bool(record.config.get("supports_streaming", True)):
                continue
            if (
                max_timeout_seconds is not None
                and float(record.config.get("timeout_seconds", 120))
                > float(max_timeout_seconds)
            ):
                continue
            health = self.registry.health.status(record_id)
            if health["state"] == "UNAVAILABLE":
                continue
            rank = 0 if health["state"] == "HEALTHY" else 1
            preferred_rank = 0 if record_id == preferred else 1
            latency_orders = {
                "fast": {"fast": 0, "balanced": 1, "deep": 2},
                "balanced": {"balanced": 0, "fast": 1, "deep": 2},
                "deep": {"deep": 0, "balanced": 1, "fast": 2},
            }
            latency_rank = latency_orders[latency_policy][
                record.config.get("latency_class", "balanced")
            ]
            candidates.append((
                rank, latency_rank, preferred_rank, record_id, record, health,
            ))
        if not candidates:
            preferred_record = self.registry._records.get(preferred)
            provider = preferred_record.provider if preferred_record else None
            model_id = preferred_record.model_id if preferred_record else None
            raise ModelSelectionError(
                required, model_id=model_id, provider=provider,
            )
        (
            _rank, _latency_rank, _preferred_rank, record_id, record, health,
        ) = sorted(candidates)[0]
        fallback = record_id != preferred
        if fallback:
            reason = "approved_fallback_after_health_or_capability_filter"
        elif health["state"] == "HEALTHY":
            reason = "configured_route_and_verified_healthy"
        else:
            reason = "configured_route_not_yet_live_verified"
        decision = RoutingDecision(
            record_id=record_id,
            provider=record.provider,
            model=record.model_id,
            capability=capability,
            health=health["state"],
            selection_reason=reason,
            fallback=fallback,
            test_harness=record_id in self.registry._injected_ids,
        )
        return decision, self.registry.adapter(record_id)

    def complete(
        self,
        request: Any,
        capability: str = "general",
        *,
        modalities: set[str] | list[str] | tuple[str, ...] | None = None,
        latency_policy: str = "balanced",
        max_timeout_seconds: float | None = None,
    ) -> tuple[RoutingDecision, Any]:
        excluded: set[str] = set()
        first_error: ModelError | None = None
        while True:
            try:
                decision, adapter = self.decide(
                    capability,
                    modalities=modalities,
                    tools_required=bool(request.tools),
                    streaming_required=bool(request.stream),
                    latency_policy=latency_policy,
                    max_timeout_seconds=max_timeout_seconds,
                    excluded=excluded,
                )
            except UnsupportedModalityError:
                if first_error is not None:
                    raise first_error
                raise
            request_id, started = self.registry.runtime.start(decision)
            try:
                response = adapter.complete(request)
            except ModelError as exc:
                self.registry.runtime.finish_failure(
                    request_id, started, attempts=exc.attempts,
                    error_type=exc.category,
                )
                self.registry.health.failure(decision.record_id, exc)
                excluded.add(decision.record_id)
                first_error = first_error or exc
                continue
            self.registry.runtime.finish_success(
                request_id,
                started,
                attempts=response.attempts,
                usage=response.usage,
                usage_reported=response.usage_reported,
                provider_request_id=response.provider_request_id,
            )
            self.registry.health.success(decision.record_id)
            return decision, response
