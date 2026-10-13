CREATE TABLE IF NOT EXISTS `__PROJECT__.__DATASET__.freight_events`
(
  event_id STRING NOT NULL,
  event_version INT64 NOT NULL,
  tenant_id STRING NOT NULL,
  classification STRING NOT NULL,
  event_timestamp TIMESTAMP NOT NULL,
  product STRING,
  origin_raw STRING,
  origin_normalized STRING,
  origin_canonical_id STRING,
  destination_raw STRING,
  destination_normalized STRING,
  destination_canonical_id STRING,
  rate NUMERIC,
  rate_unit STRING,
  rate_previous NUMERIC,
  rate_delta NUMERIC,
  rate_delta_percent NUMERIC,
  rate_movement STRING,
  rate_previous_timestamp TIMESTAMP,
  rate_changed_at TIMESTAMP,
  confidence FLOAT64 NOT NULL,
  truth_classification STRING NOT NULL,
  source_event_ids ARRAY<STRING>,
  raw_reference STRING NOT NULL,
  entities_json STRING,
  metadata_json STRING,
  provenance_json STRING,
  ingested_at TIMESTAMP NOT NULL
)
PARTITION BY DATE(event_timestamp)
CLUSTER BY product, origin_normalized, destination_normalized, tenant_id;
