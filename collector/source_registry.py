from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

from .input_security import validate_source_url
from .models import SourceSpec


REGISTRY_VERSION = "1.0.0"
ALLOWED_STATUS = {"active", "gated", "planned", "blocked", "deprecated"}
ALLOWED_SECURITY = {"PUBLIC", "INTERNAL", "CONFIDENTIAL", "RESTRICTED"}
REQUIRED_FIELDS = {
    "source_id", "name", "domain", "type", "endpoint", "method", "frequency",
    "freshness_expected", "last_collection_at", "status", "fallback", "license",
    "reliability",
}


@dataclass(frozen=True)
class RegistryEntry:
    source_id: str
    name: str
    domain: str
    source_type: str
    endpoint: str | None
    method: str
    frequency: str
    freshness_expected: str
    last_collection_at: str | None
    status: str
    fallback: tuple[str, ...]
    license: str
    reliability: str
    execution_ref: str | None
    security_class: str
    auth: str
    trusted_transport: bool
    schedule: dict[str, Any]
    raw: dict[str, Any]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RegistryEntry":
        missing = sorted(REQUIRED_FIELDS - data.keys())
        if missing:
            raise ValueError(f"registry source missing required fields: {', '.join(missing)}")
        source_id = str(data["source_id"]).strip()
        if not source_id:
            raise ValueError("source_id cannot be empty")
        status = str(data["status"])
        if status not in ALLOWED_STATUS:
            raise ValueError(f"invalid status for {source_id}: {status}")
        security_class = str(data.get("security_class", "PUBLIC"))
        if security_class not in ALLOWED_SECURITY:
            raise ValueError(f"invalid security_class for {source_id}: {security_class}")
        endpoint = data.get("endpoint")
        trusted_transport = bool(data.get("trusted_transport", False))
        if status == "active":
            if not endpoint and not data.get("execution_ref"):
                raise ValueError(f"active source {source_id} requires endpoint or execution_ref")
            if endpoint:
                try:
                    validate_source_url(str(endpoint))
                except ValueError as exc:
                    raise ValueError(f"active source {source_id} has unsafe endpoint: {exc}") from exc
                if not trusted_transport:
                    raise ValueError(f"active source {source_id} must explicitly mark trusted_transport")
        schedule = dict(data.get("schedule") or {})
        retries = schedule.get("retry_minutes") or [120, 240, 480, 720]
        if not isinstance(retries, list) or not retries or any(int(value) <= 0 for value in retries):
            raise ValueError(f"invalid retry schedule for {source_id}")
        schedule["retry_minutes"] = [int(value) for value in retries]
        min_interval = schedule.get("min_interval_minutes")
        if min_interval is not None and int(min_interval) <= 0:
            raise ValueError(f"invalid min interval for {source_id}")
        if min_interval is not None:
            schedule["min_interval_minutes"] = int(min_interval)
        return cls(
            source_id=source_id,
            name=str(data["name"]),
            domain=str(data["domain"]),
            source_type=str(data["type"]),
            endpoint=str(endpoint) if endpoint is not None else None,
            method=str(data["method"]),
            frequency=str(data["frequency"]),
            freshness_expected=str(data["freshness_expected"]),
            last_collection_at=data.get("last_collection_at"),
            status=status,
            fallback=tuple(str(value) for value in data.get("fallback", [])),
            license=str(data["license"]),
            reliability=str(data["reliability"]),
            execution_ref=data.get("execution_ref"),
            security_class=security_class,
            auth=str(data.get("auth", "unknown")),
            trusted_transport=trusted_transport,
            schedule=schedule,
            raw=dict(data),
        )

    @property
    def event_driven(self) -> bool:
        return bool(self.schedule.get("event_driven", False))

    @property
    def min_interval(self) -> timedelta | None:
        minutes = self.schedule.get("min_interval_minutes")
        return timedelta(minutes=int(minutes)) if minutes is not None else None

    def retry_delay(self, consecutive_failures: int) -> timedelta:
        retries = self.schedule["retry_minutes"]
        index = max(0, min(max(0, consecutive_failures - 1), len(retries) - 1))
        return timedelta(minutes=retries[index])


@dataclass(frozen=True)
class CollectionDecision:
    source_id: str
    due: bool
    reason: str
    fallback: tuple[str, ...] = ()


@dataclass(frozen=True)
class SourceHealth:
    source_id: str
    status: str
    last_collection_at: str | None
    consecutive_failures: int
    age_minutes: float | None
    alert: bool
    reason: str


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


class DataSourceRegistry:
    def __init__(self, entries: Iterable[RegistryEntry]) -> None:
        self.entries: dict[str, RegistryEntry] = {}
        for entry in entries:
            if entry.source_id in self.entries:
                raise ValueError(f"duplicate source_id: {entry.source_id}")
            self.entries[entry.source_id] = entry
        for entry in self.entries.values():
            unknown = sorted(set(entry.fallback) - self.entries.keys())
            if unknown:
                raise ValueError(f"unknown fallback for {entry.source_id}: {', '.join(unknown)}")

    @classmethod
    def load(cls, path: str | Path) -> "DataSourceRegistry":
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        if payload.get("version") != REGISTRY_VERSION:
            raise ValueError(f"unsupported registry version: {payload.get('version')}")
        sources = payload.get("sources")
        if not isinstance(sources, list):
            raise ValueError("registry sources must be a list")
        return cls(RegistryEntry.from_dict(item) for item in sources)

    def get(self, source_id: str) -> RegistryEntry:
        try:
            return self.entries[source_id]
        except KeyError as exc:
            raise KeyError(f"source not registered: {source_id}") from exc

    def by_domain(self, domain: str) -> list[RegistryEntry]:
        return sorted((e for e in self.entries.values() if e.domain == domain), key=lambda e: e.source_id)

    def decision(
        self,
        source_id: str,
        *,
        state: dict[str, Any] | None = None,
        now: datetime | None = None,
        wake: bool = False,
    ) -> CollectionDecision:
        entry = self.get(source_id)
        if entry.status != "active":
            return CollectionDecision(source_id, False, f"status:{entry.status}", entry.fallback)
        if entry.event_driven and not wake:
            return CollectionDecision(source_id, False, "event_driven_waiting", entry.fallback)

        state = state or {}
        now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        last_attempt = _parse_time(state.get("last_checked_at") or entry.last_collection_at)
        failures = int(state.get("consecutive_failures") or 0)

        if failures > 0 and last_attempt is not None:
            retry_at = last_attempt + entry.retry_delay(failures)
            if now < retry_at:
                return CollectionDecision(source_id, False, "retry_backoff", entry.fallback)

        interval = entry.min_interval
        if interval is not None and last_attempt is not None and now < last_attempt + interval:
            return CollectionDecision(source_id, False, "fresh_enough", entry.fallback)

        return CollectionDecision(source_id, True, "due", entry.fallback)

    def health(
        self,
        source_id: str,
        *,
        state: dict[str, Any] | None = None,
        now: datetime | None = None,
    ) -> SourceHealth:
        entry = self.get(source_id)
        state = state or {}
        now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        last = _parse_time(state.get("last_checked_at") or entry.last_collection_at)
        failures = int(state.get("consecutive_failures") or 0)
        last_iso = last.isoformat() if last else None

        if entry.status != "active":
            return SourceHealth(source_id, entry.status.upper(), last_iso, failures, None, False, f"registry:{entry.status}")
        if last is None:
            return SourceHealth(source_id, "NEVER_COLLECTED", None, failures, None, True, "no_collection_evidence")

        age_minutes = max(0.0, (now - last).total_seconds() / 60.0)
        if failures > 0:
            max_failures = int(entry.schedule.get("max_consecutive_failures") or 6)
            if failures >= max_failures:
                return SourceHealth(source_id, "FAILED", last_iso, failures, age_minutes, True, "failure_threshold")
            return SourceHealth(source_id, "DEGRADED", last_iso, failures, age_minutes, True, "consecutive_failures")

        interval_minutes = int(entry.schedule.get("min_interval_minutes") or 1440)
        stale_after = max(interval_minutes * 2, max(entry.schedule["retry_minutes"]))
        if age_minutes > stale_after:
            return SourceHealth(source_id, "STALE", last_iso, failures, age_minutes, True, "freshness_threshold")
        return SourceHealth(source_id, "HEALTHY", last_iso, failures, age_minutes, False, "within_freshness_window")

    def operational_view(
        self,
        source_id: str,
        *,
        state: dict[str, Any] | None = None,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        """Overlay runtime collection state without rewriting the versioned registry file."""
        entry = self.get(source_id)
        health = self.health(source_id, state=state, now=now)
        source = dict(entry.raw)
        source["last_collection_at"] = health.last_collection_at
        return {
            "source": source,
            "health": {
                "status": health.status,
                "consecutive_failures": health.consecutive_failures,
                "age_minutes": health.age_minutes,
                "alert": health.alert,
                "reason": health.reason,
            },
        }

    def due(
        self,
        *,
        state_by_source: dict[str, dict[str, Any]] | None = None,
        now: datetime | None = None,
        wake_sources: set[str] | None = None,
    ) -> list[CollectionDecision]:
        state_by_source = state_by_source or {}
        wake_sources = wake_sources or set()
        decisions = [
            self.decision(
                source_id,
                state=state_by_source.get(source_id),
                now=now,
                wake=source_id in wake_sources,
            )
            for source_id in sorted(self.entries)
        ]
        return [decision for decision in decisions if decision.due]

    def resolve_source_spec(self, source_id: str, *, repo_root: str | Path = ".") -> SourceSpec:
        """Resolve an existing SourceSpec without duplicating collector configuration.

        Generic scheduling is supported when execution_ref uses `path.json#source_id`.
        Module-only references remain explicit gaps until they expose a SourceSpec.
        """
        entry = self.get(source_id)
        ref = entry.execution_ref or ""
        if "#" not in ref:
            raise ValueError(f"source {source_id} has no resolvable config execution_ref")
        relative_path, execution_source_id = ref.split("#", 1)
        payload = json.loads((Path(repo_root) / relative_path).read_text(encoding="utf-8"))
        for item in payload.get("sources", []):
            if item.get("source_id") == execution_source_id:
                return SourceSpec.from_dict(item)
        raise ValueError(f"execution source {execution_source_id} not found in {relative_path}")
