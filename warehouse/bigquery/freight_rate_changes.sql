CREATE OR REPLACE VIEW `__PROJECT__.__DATASET__.freight_rate_changes` AS
SELECT
  event_id,
  event_version,
  tenant_id,
  event_timestamp,
  product,
  JSON_VALUE(entities_json, '$.company[0].raw_value') AS carrier,
  JSON_VALUE(entities_json, '$.company[0].normalized_value') AS carrier_normalized,
  origin_raw,
  origin_normalized,
  destination_raw,
  destination_normalized,
  rate_previous,
  rate AS rate_current,
  rate_delta,
  rate_delta_percent,
  rate_movement,
  rate_unit,
  rate_previous_timestamp,
  rate_changed_at,
  source_event_ids,
  metadata_json,
  provenance_json
FROM `__PROJECT__.__DATASET__.freight_events`
WHERE rate_movement IN ('AUMENTO', 'REDUCAO')
  AND rate_delta IS NOT NULL;
