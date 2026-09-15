from __future__ import annotations

import re

from .storage_queries import safe_identifier

_PORT_ID = re.compile(r"^[A-Z0-9_]{2,64}$")
_MMSI = re.compile(r"^[0-9]{9}$")


def normalize_port_id(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip().upper()
    if not _PORT_ID.fullmatch(normalized):
        raise ValueError("port_id invalido")
    return normalized


def normalize_mmsi(value: str) -> str:
    normalized = value.strip()
    if not _MMSI.fullmatch(normalized) or normalized == "000000000":
        raise ValueError("MMSI invalido")
    return normalized


def _port_filter_sql(column: str = "port_id") -> str:
    """Canonical filter plus the only safe legacy alias in Maritime V1."""
    if column not in {"port_id", "l.port_id"}:
        raise ValueError("coluna de porto nao autorizada")
    return (
        f"(@port_id IS NULL OR {column} = @port_id "
        f"OR (@port_id = 'PARANAGUA' AND {column} = 'PARANAGUA_ANTONINA'))"
    )


def _trusted_ais_sql() -> str:
    return "quality_status = 'CONFIRMED_SEQUENCE' AND corroborated IS TRUE AND COALESCE(spoofing_suspected, FALSE) IS FALSE"


def build_live_vessels_sql(project: str, dataset: str) -> str:
    project = safe_identifier(project, label="project")
    dataset = safe_identifier(dataset, label="dataset")
    port_filter = _port_filter_sql()
    trusted = _trusted_ais_sql()
    return f"""
WITH ranked AS (
  SELECT
    observation_id, mmsi, imo, vessel_name, observed_at,
    source_timestamp_raw, received_at, timestamp_basis,
    latitude, longitude, sog_kn, cog_deg, navigation_status, destination,
    port_id, terminal_id, zone, source_id, collected_at,
    quality_status, quality_flags_json, corroborated, spoofing_suspected, calculated_speed_kn,
    ROW_NUMBER() OVER (
      PARTITION BY COALESCE(NULLIF(mmsi, ''), NULLIF(imo, ''), NULLIF(vessel_name, ''), observation_id)
      ORDER BY observed_at DESC, collected_at DESC
    ) AS rn
  FROM `{project}.{dataset}.shipping_ais_positions`
  WHERE latitude BETWEEN -90 AND 90
    AND longitude BETWEEN -180 AND 180
    AND {trusted}
    AND TIMESTAMP_DIFF(CURRENT_TIMESTAMP(), observed_at, HOUR) BETWEEN 0 AND @hours
    AND {port_filter}
)
SELECT
  observation_id, mmsi, imo, vessel_name, observed_at,
  source_timestamp_raw, received_at, timestamp_basis,
  latitude, longitude, sog_kn, cog_deg, navigation_status, destination,
  port_id, terminal_id, zone, source_id, collected_at,
  quality_status, quality_flags_json, corroborated, spoofing_suspected, calculated_speed_kn
FROM ranked
WHERE rn = 1
ORDER BY observed_at DESC
LIMIT @limit
""".strip()


def build_vessel_replay_sql(project: str, dataset: str) -> str:
    """Replay keeps quarantined/unconfirmed records visible for forensic audit."""
    project = safe_identifier(project, label="project")
    dataset = safe_identifier(dataset, label="dataset")
    return f"""
SELECT
  observation_id, mmsi, imo, vessel_name, observed_at,
  source_timestamp_raw, received_at, timestamp_basis,
  latitude, longitude, sog_kn, cog_deg, navigation_status,
  destination, port_id, terminal_id, zone, source_id,
  quality_status, quality_flags_json, corroborated, spoofing_suspected, calculated_speed_kn
FROM `{project}.{dataset}.shipping_ais_positions`
WHERE mmsi = @mmsi
  AND TIMESTAMP_DIFF(COALESCE(@end_at, CURRENT_TIMESTAMP()), observed_at, HOUR) BETWEEN 0 AND @hours
ORDER BY observed_at ASC
LIMIT @limit
""".strip()


def build_lineup_reconciliation_sql(project: str, dataset: str) -> str:
    project = safe_identifier(project, label="project")
    dataset = safe_identifier(dataset, label="dataset")
    port_filter = _port_filter_sql()
    return f"""
WITH latest_lineup AS (
  SELECT * EXCEPT(rn)
  FROM (
    SELECT
      call_id, snapshot_id, port_id, terminal_id, vessel_name, imo, mmsi,
      eta, product, planned_volume_t, lineup_status, source_id, collected_at,
      ROW_NUMBER() OVER (
        PARTITION BY call_id
        ORDER BY collected_at DESC, snapshot_id DESC
      ) AS rn
    FROM `{project}.{dataset}.shipping_lineup_calls`
    WHERE {port_filter}
      AND TIMESTAMP_DIFF(eta, CURRENT_TIMESTAMP(), HOUR) BETWEEN (0 - @past_hours) AND @future_hours
  )
  WHERE rn = 1
),
latest_reconciliation AS (
  SELECT * EXCEPT(rn)
  FROM (
    SELECT
      reconciliation_id, call_id, calculated_at, state, evidence_class,
      match_method, match_confidence, matched_imo, matched_mmsi,
      eta_error_hours, waiting_hours, berth_hours, volume_variance_pct,
      flags_json, model_version,
      ROW_NUMBER() OVER (
        PARTITION BY call_id
        ORDER BY calculated_at DESC
      ) AS rn
    FROM `{project}.{dataset}.shipping_reconciliation`
  )
  WHERE rn = 1
)
SELECT
  l.call_id, l.snapshot_id, l.port_id, l.terminal_id,
  l.vessel_name, l.imo, l.mmsi, l.eta, l.product,
  l.planned_volume_t, l.lineup_status, l.source_id, l.collected_at,
  r.reconciliation_id, r.calculated_at,
  COALESCE(r.state, 'PROGRAMMED') AS reconciled_state,
  COALESCE(r.evidence_class, 'LINEUP_PROGRAMMED') AS evidence_class,
  r.match_method, r.match_confidence, r.matched_imo, r.matched_mmsi,
  r.eta_error_hours, r.waiting_hours, r.berth_hours,
  r.volume_variance_pct, r.flags_json, r.model_version
FROM latest_lineup l
LEFT JOIN latest_reconciliation r USING (call_id)
ORDER BY l.eta ASC, l.port_id, l.vessel_name
LIMIT @limit
""".strip()


def build_port_summary_sql(project: str, dataset: str) -> str:
    project = safe_identifier(project, label="project")
    dataset = safe_identifier(dataset, label="dataset")
    port_filter = _port_filter_sql()
    trusted = _trusted_ais_sql()
    return f"""
WITH latest_positions AS (
  SELECT * EXCEPT(rn)
  FROM (
    SELECT
      observation_id, mmsi, imo, vessel_name, observed_at, port_id, terminal_id, zone,
      quality_status, corroborated, spoofing_suspected,
      ROW_NUMBER() OVER (
        PARTITION BY COALESCE(NULLIF(mmsi, ''), NULLIF(imo, ''), NULLIF(vessel_name, ''), observation_id)
        ORDER BY observed_at DESC, collected_at DESC
      ) AS rn
    FROM `{project}.{dataset}.shipping_ais_positions`
    WHERE {trusted}
      AND TIMESTAMP_DIFF(CURRENT_TIMESTAMP(), observed_at, HOUR) BETWEEN 0 AND @hours
      AND {port_filter}
  )
  WHERE rn = 1
),
latest_lineup AS (
  SELECT * EXCEPT(rn)
  FROM (
    SELECT
      call_id, port_id, eta,
      ROW_NUMBER() OVER (PARTITION BY call_id ORDER BY collected_at DESC, snapshot_id DESC) AS rn
    FROM `{project}.{dataset}.shipping_lineup_calls`
    WHERE {port_filter}
      AND TIMESTAMP_DIFF(eta, CURRENT_TIMESTAMP(), HOUR) BETWEEN -24 AND @future_hours
  )
  WHERE rn = 1
),
latest_reconciliation AS (
  SELECT * EXCEPT(rn)
  FROM (
    SELECT
      call_id, state, match_confidence, waiting_hours, berth_hours, eta_error_hours,
      ROW_NUMBER() OVER (PARTITION BY call_id ORDER BY calculated_at DESC) AS rn
    FROM `{project}.{dataset}.shipping_reconciliation`
  )
  WHERE rn = 1
),
rec AS (
  SELECT r.*
  FROM latest_reconciliation r
  JOIN latest_lineup l USING (call_id)
)
SELECT
  (SELECT COUNT(*) FROM latest_positions) AS vessels_live,
  (SELECT COUNTIF(UPPER(COALESCE(zone, '')) = 'APPROACH') FROM latest_positions) AS vessels_approaching,
  (SELECT COUNTIF(UPPER(COALESCE(zone, '')) = 'ANCHORAGE') FROM latest_positions) AS vessels_waiting,
  (SELECT COUNTIF(UPPER(COALESCE(zone, '')) = 'BERTH') FROM latest_positions) AS vessels_berthed,
  (SELECT COUNT(*) FROM latest_lineup) AS lineup_calls,
  (SELECT COUNTIF(match_confidence IS NOT NULL AND match_confidence > 0) FROM rec) AS lineup_matched,
  (SELECT APPROX_QUANTILES(waiting_hours, 100)[OFFSET(50)] FROM rec WHERE waiting_hours IS NOT NULL) AS waiting_p50_hours,
  (SELECT APPROX_QUANTILES(waiting_hours, 100)[OFFSET(90)] FROM rec WHERE waiting_hours IS NOT NULL) AS waiting_p90_hours,
  (SELECT AVG(ABS(eta_error_hours)) FROM rec WHERE eta_error_hours IS NOT NULL) AS eta_mae_hours,
  (SELECT AVG(berth_hours) FROM rec WHERE berth_hours IS NOT NULL) AS berth_avg_hours
""".strip()
