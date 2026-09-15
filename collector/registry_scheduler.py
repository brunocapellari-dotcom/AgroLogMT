from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

from .cli import load_sources
from .models import SourceSpec
from .source_registry import DataSourceRegistry, RegistryEntry


# Temporary bridge only for existing specialized pipelines whose registry source_id
# is intentionally broader than the current first production slice. It does not
# duplicate collector logic; it points to the existing canonical SourceSpec.
_EXECUTION_BRIDGES: dict[str, tuple[str, str]] = {
    "mdic_comexstat": ("collector/config/sources.p0.json", "mdic_comexstat_soja_mt_export_api"),
}

# These are sources used inside another canonical collector/pipeline rather than
# standalone scheduled jobs. They remain registered for provenance/fallback.
_NESTED_AUXILIARY_SOURCES = {"bcb_olinda_ptax_discovery"}


class StateStore(Protocol):
    def load_state(self, source_id: str) -> dict[str, Any]: ...
    def save_state(self, source_id: str, state: dict[str, Any]) -> str: ...


@dataclass(frozen=True)
class ScheduledSource:
    registry_source_id: str
    execution_source_id: str | None
    due: bool
    reason: str
    spec: SourceSpec | None
    fallback: tuple[str, ...]


class RegistryScheduler:
    def __init__(
        self,
        registry: DataSourceRegistry,
        store: StateStore,
        *,
        repo_root: str | Path = ".",
    ) -> None:
        self.registry = registry
        self.store = store
        self.repo_root = Path(repo_root)

    def _spec_from_bridge(self, registry_source_id: str) -> SourceSpec | None:
        bridge = _EXECUTION_BRIDGES.get(registry_source_id)
        if bridge is None:
            return None
        relative_path, source_id = bridge
        specs = load_sources(self.repo_root / relative_path)
        for spec in specs:
            if spec.source_id == source_id:
                return spec
        raise ValueError(f"bridge target not found: {registry_source_id} -> {relative_path}#{source_id}")

    def resolve_spec(self, entry: RegistryEntry) -> SourceSpec | None:
        if entry.source_id in _NESTED_AUXILIARY_SOURCES:
            return None
        if entry.execution_ref and "#" in entry.execution_ref:
            return self.registry.resolve_source_spec(entry.source_id, repo_root=self.repo_root)
        return self._spec_from_bridge(entry.source_id)

    def plan_source(
        self,
        registry_source_id: str,
        *,
        now: datetime | None = None,
        wake: bool = False,
        allow_gated_canary: bool = False,
    ) -> ScheduledSource:
        entry = self.registry.get(registry_source_id)
        spec = self.resolve_spec(entry)
        if entry.source_id in _NESTED_AUXILIARY_SOURCES:
            return ScheduledSource(entry.source_id, None, False, "nested_auxiliary", None, entry.fallback)
        if spec is None:
            decision = self.registry.decision(entry.source_id, state={}, now=now, wake=wake)
            if decision.due:
                return ScheduledSource(entry.source_id, None, False, "execution_not_implemented", None, entry.fallback)
            return ScheduledSource(entry.source_id, None, False, decision.reason, None, entry.fallback)

        # GATED means the source cannot participate in normal scheduling. A bounded
        # homologation canary may execute it only when the caller explicitly names
        # the source and opts into this flag. The registry file remains GATED until
        # independent promotion evidence is reviewed; canary execution never
        # mutates or silently promotes source state.
        if allow_gated_canary and entry.status == "gated":
            if not spec.enabled:
                return ScheduledSource(
                    entry.source_id,
                    spec.source_id,
                    False,
                    "execution_spec_disabled",
                    spec,
                    entry.fallback,
                )
            return ScheduledSource(
                entry.source_id,
                spec.source_id,
                True,
                "gated_canary",
                spec,
                entry.fallback,
            )

        state = self.store.load_state(spec.source_id)
        decision = self.registry.decision(entry.source_id, state=state, now=now, wake=wake)
        if not spec.enabled and decision.due:
            return ScheduledSource(entry.source_id, spec.source_id, False, "execution_spec_disabled", spec, entry.fallback)
        return ScheduledSource(entry.source_id, spec.source_id, decision.due, decision.reason, spec, entry.fallback)

    def plan(
        self,
        *,
        source_id: str | None = None,
        domain: str | None = None,
        now: datetime | None = None,
        wake_sources: set[str] | None = None,
        allow_gated_canary: bool = False,
    ) -> list[ScheduledSource]:
        wake_sources = wake_sources or set()
        if allow_gated_canary and not source_id:
            raise ValueError("gated canary requires an explicit source_id")
        if source_id:
            ids = [source_id]
        else:
            ids = [
                entry.source_id
                for entry in sorted(self.registry.entries.values(), key=lambda item: item.source_id)
                if domain is None or entry.domain == domain
            ]
        return [
            self.plan_source(
                item,
                now=now,
                wake=item in wake_sources,
                allow_gated_canary=allow_gated_canary,
            )
            for item in ids
        ]

    def record_result(
        self,
        scheduled: ScheduledSource,
        *,
        status: str,
        error: str | None = None,
        at: datetime | None = None,
    ) -> None:
        if not scheduled.execution_source_id:
            return
        now = (at or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat()
        state = self.store.load_state(scheduled.execution_source_id)
        failures = int(state.get("consecutive_failures") or 0)
        if status in {"error", "blocked_missing_secure_env", "failed"}:
            failures += 1
        else:
            failures = 0
        state.update({
            "consecutive_failures": failures,
            "last_scheduler_status": status,
            "last_scheduler_at": now,
            "registry_source_id": scheduled.registry_source_id,
        })
        if error:
            state["last_scheduler_error"] = str(error)[:1000]
        elif "last_scheduler_error" in state:
            state.pop("last_scheduler_error", None)
        self.store.save_state(scheduled.execution_source_id, state)

    def operational_view(
        self,
        scheduled: ScheduledSource,
        *,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        """Return registry metadata overlaid with the live state used by scheduling."""
        state = (
            self.store.load_state(scheduled.execution_source_id)
            if scheduled.execution_source_id
            else {}
        )
        return self.registry.operational_view(
            scheduled.registry_source_id,
            state=state,
            now=now,
        )

    def alerting_view(
        self,
        *,
        domain: str | None = None,
        now: datetime | None = None,
    ) -> list[dict[str, Any]]:
        """Return only sources whose health state requires operational attention."""
        results: list[dict[str, Any]] = []
        for item in self.plan(domain=domain, now=now):
            view = self.operational_view(item, now=now)
            if bool(view["health"]["alert"]):
                results.append(view)
        return results

    def fallback_candidates(self, scheduled: ScheduledSource) -> list[ScheduledSource]:
        """Return fallback collection plans without substituting their data.

        A fallback is a separate evidence stream. It may be collected after a
        primary failure, but its rows are never relabeled as the primary source.
        Gated/planned candidates remain non-runnable and are reported as such.
        """
        return [self.plan_source(source_id, wake=True) for source_id in scheduled.fallback]


def scheduler_payload(item: ScheduledSource) -> dict[str, Any]:
    return {
        "registry_source_id": item.registry_source_id,
        "execution_source_id": item.execution_source_id,
        "due": item.due,
        "reason": item.reason,
        "fallback": list(item.fallback),
    }
