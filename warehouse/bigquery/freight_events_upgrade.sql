ALTER TABLE `__PROJECT__.__DATASET__.freight_events`
ADD COLUMN IF NOT EXISTS entities_json STRING;
