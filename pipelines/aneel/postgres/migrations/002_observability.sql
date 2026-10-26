ALTER TABLE ingestion_run ADD COLUMN input_metadata jsonb NOT NULL DEFAULT '{}'::jsonb;
CREATE OR REPLACE VIEW official_monthly_history AS
SELECT i.*, 'electrical_set'::text AS geographic_level,
       e.linked_ufs,e.is_multi_uf,e.agent_link_ambiguous,e.association_temporal_unknown,
       s.methodology_version,s.analytics_methodology_version,s.transformation_sha256,s.sql_sha256,r.sha256 AS source_version,
       r.collected_at,r.original_url,
       i.value IS NULL AS indicator_coverage_partial,
       a.event_rows IS NULL AS events_not_observed
FROM continuity_indicator i
JOIN electrical_set e USING(snapshot_id,agent,set_id)
JOIN analysis_snapshot s ON s.id=i.snapshot_id
JOIN snapshot_resource sr ON sr.snapshot_id=i.snapshot_id AND sr.role=i.source_role
JOIN source_resource r ON r.resource_id=sr.resource_id AND r.sha256=sr.sha256
LEFT JOIN interruption_aggregate a ON a.snapshot_id=i.snapshot_id AND a.agent=i.agent
    AND a.set_id=i.set_id AND a.period=i.period;
CREATE OR REPLACE VIEW official_monthly AS
SELECT h.* FROM official_monthly_history h
JOIN active_partition a USING(snapshot_id,agent,set_id,period);
