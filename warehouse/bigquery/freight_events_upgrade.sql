ALTER TABLE `__PROJECT__.__DATASET__.freight_events`
ADD COLUMN IF NOT EXISTS entities_json STRING;

ALTER TABLE `__PROJECT__.__DATASET__.freight_events`
ADD COLUMN IF NOT EXISTS rate_previous NUMERIC;

ALTER TABLE `__PROJECT__.__DATASET__.freight_events`
ADD COLUMN IF NOT EXISTS rate_delta NUMERIC;

ALTER TABLE `__PROJECT__.__DATASET__.freight_events`
ADD COLUMN IF NOT EXISTS rate_delta_percent NUMERIC;

ALTER TABLE `__PROJECT__.__DATASET__.freight_events`
ADD COLUMN IF NOT EXISTS rate_movement STRING;

ALTER TABLE `__PROJECT__.__DATASET__.freight_events`
ADD COLUMN IF NOT EXISTS rate_previous_timestamp TIMESTAMP;

ALTER TABLE `__PROJECT__.__DATASET__.freight_events`
ADD COLUMN IF NOT EXISTS rate_changed_at TIMESTAMP;
