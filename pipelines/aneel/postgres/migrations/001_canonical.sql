CREATE TABLE source_resource (
    resource_id text NOT NULL, sha256 text NOT NULL CHECK(length(sha256)=64),
    dataset text NOT NULL, original_url text NOT NULL, effective_url text NOT NULL,
    size_bytes bigint NOT NULL CHECK(size_bytes>0), collected_at timestamptz NOT NULL,
    period_label text, metadata jsonb NOT NULL,
    PRIMARY KEY(resource_id,sha256)
);
CREATE TABLE ingestion_run (
    id uuid PRIMARY KEY, snapshot_id text, status text NOT NULL
        CHECK(status IN ('running','succeeded','reused','failed')),
    started_at timestamptz NOT NULL DEFAULT now(), finished_at timestamptz, error text
);
CREATE TABLE analysis_snapshot (
    id text PRIMARY KEY CHECK(length(id)=64), scope jsonb NOT NULL,
    methodology_version text NOT NULL, analytics_methodology_version text NOT NULL,
    transformation_sha256 text NOT NULL, sql_sha256 text NOT NULL,
    bundle jsonb NOT NULL, published_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE snapshot_resource (
    snapshot_id text NOT NULL REFERENCES analysis_snapshot,
    role text NOT NULL, resource_id text NOT NULL, sha256 text NOT NULL,
    PRIMARY KEY(snapshot_id,role),
    FOREIGN KEY(resource_id,sha256) REFERENCES source_resource(resource_id,sha256)
);
CREATE TABLE distributor (
    snapshot_id text NOT NULL REFERENCES analysis_snapshot, agent text NOT NULL,
    name text, cnpj text, PRIMARY KEY(snapshot_id,agent)
);
CREATE TABLE electrical_set (
    snapshot_id text NOT NULL, agent text NOT NULL, set_id bigint NOT NULL,
    name text, linked_ufs text NOT NULL, is_multi_uf boolean NOT NULL,
    agent_link_ambiguous boolean NOT NULL,
    association_temporal_unknown boolean NOT NULL DEFAULT true,
    PRIMARY KEY(snapshot_id,agent,set_id),
    FOREIGN KEY(snapshot_id,agent) REFERENCES distributor(snapshot_id,agent)
);
CREATE TABLE municipality (
    snapshot_id text NOT NULL REFERENCES analysis_snapshot,
    municipality_code text NOT NULL, name text NOT NULL, uf text NOT NULL,
    PRIMARY KEY(snapshot_id,municipality_code)
);
-- The source has no agent key: do not invent an agent-specific foreign key here.
CREATE TABLE set_municipality_link (
    snapshot_id text NOT NULL, source_set_id bigint NOT NULL,
    municipality_code text NOT NULL, snapshot_date date NOT NULL,
    valid_from date, valid_to date,
    association_status text NOT NULL DEFAULT 'set_code_only' CHECK(association_status='set_code_only'),
    source_role text NOT NULL DEFAULT 'municipalities' CHECK(source_role='municipalities'),
    PRIMARY KEY(snapshot_id,source_set_id,municipality_code),
    FOREIGN KEY(snapshot_id,municipality_code) REFERENCES municipality(snapshot_id,municipality_code),
    FOREIGN KEY(snapshot_id,source_role) REFERENCES snapshot_resource(snapshot_id,role),
    CHECK(valid_from IS NULL OR valid_to IS NULL OR valid_from<=valid_to)
);
CREATE TABLE continuity_indicator (
    snapshot_id text NOT NULL, agent text NOT NULL, set_id bigint NOT NULL, period date NOT NULL,
    indicator_code text NOT NULL CHECK(indicator_code IN ('DEC','FEC','DECIND','FECIND')),
    value double precision, unit text NOT NULL, consumer_count double precision,
    quality_status text NOT NULL CHECK(quality_status IN ('reported','not_observed')),
    source_role text NOT NULL DEFAULT 'indicators' CHECK(source_role='indicators'),
    PRIMARY KEY(snapshot_id,agent,set_id,period,indicator_code),
    FOREIGN KEY(snapshot_id,agent,set_id) REFERENCES electrical_set(snapshot_id,agent,set_id),
    FOREIGN KEY(snapshot_id,source_role) REFERENCES snapshot_resource(snapshot_id,role),
    CHECK(extract(day FROM period)=1),
    CHECK((value IS NULL)=(quality_status='not_observed')),
    CHECK(value IS NULL OR (value>=0 AND value<'Infinity'::double precision)),
    CHECK(consumer_count IS NULL OR (consumer_count>=0 AND consumer_count<'Infinity'::double precision))
);
CREATE TABLE interruption_aggregate (
    snapshot_id text NOT NULL, agent text NOT NULL, set_id bigint NOT NULL, period date NOT NULL,
    event_rows bigint, invalid_rows bigint, candidate_rows bigint,
    duration_candidate_h_per_uc double precision, frequency_candidate_per_uc double precision,
    observation_status text NOT NULL CHECK(observation_status IN ('observed','not_observed')),
    source_role text NOT NULL DEFAULT 'interruptions' CHECK(source_role='interruptions'),
    PRIMARY KEY(snapshot_id,agent,set_id,period),
    FOREIGN KEY(snapshot_id,agent,set_id) REFERENCES electrical_set(snapshot_id,agent,set_id),
    FOREIGN KEY(snapshot_id,source_role) REFERENCES snapshot_resource(snapshot_id,role),
    CHECK(extract(day FROM period)=1),
    CHECK(event_rows IS NULL OR event_rows>=0),
    CHECK(invalid_rows IS NULL OR invalid_rows BETWEEN 0 AND event_rows),
    CHECK(candidate_rows IS NULL OR candidate_rows BETWEEN 0 AND event_rows),
    CHECK((observation_status='observed' AND event_rows IS NOT NULL AND invalid_rows IS NOT NULL AND candidate_rows IS NOT NULL)
       OR (observation_status='not_observed' AND event_rows IS NULL AND invalid_rows IS NULL AND candidate_rows IS NULL
           AND duration_candidate_h_per_uc IS NULL AND frequency_candidate_per_uc IS NULL)),
    CHECK(duration_candidate_h_per_uc IS NULL OR (duration_candidate_h_per_uc>=0 AND duration_candidate_h_per_uc<'Infinity'::double precision)),
    CHECK(frequency_candidate_per_uc IS NULL OR (frequency_candidate_per_uc>=0 AND frequency_candidate_per_uc<'Infinity'::double precision))
);
CREATE TABLE active_partition (
    agent text NOT NULL,set_id bigint NOT NULL,period date NOT NULL,snapshot_id text NOT NULL,
    PRIMARY KEY(agent,set_id,period),
    FOREIGN KEY(snapshot_id,agent,set_id,period) REFERENCES interruption_aggregate(snapshot_id,agent,set_id,period)
);
CREATE INDEX indicator_series ON continuity_indicator(agent,set_id,indicator_code,period);
CREATE INDEX aggregate_series ON interruption_aggregate(agent,set_id,period);
CREATE INDEX link_lookup ON set_municipality_link(snapshot_id,source_set_id);
CREATE VIEW official_monthly_history AS
SELECT i.*, 'electrical_set'::text AS geographic_level,
       e.linked_ufs,e.is_multi_uf,e.agent_link_ambiguous,e.association_temporal_unknown,
       s.methodology_version,s.analytics_methodology_version,s.transformation_sha256,s.sql_sha256,r.sha256 AS source_version,
       r.collected_at,r.original_url
FROM continuity_indicator i
JOIN electrical_set e USING(snapshot_id,agent,set_id)
JOIN analysis_snapshot s ON s.id=i.snapshot_id
JOIN snapshot_resource sr ON sr.snapshot_id=i.snapshot_id AND sr.role=i.source_role
JOIN source_resource r ON r.resource_id=sr.resource_id AND r.sha256=sr.sha256;
CREATE VIEW official_monthly AS
SELECT h.* FROM official_monthly_history h
JOIN active_partition a USING(snapshot_id,agent,set_id,period);
-- Derived annual values, not annual values published directly by ANEEL.
-- Annual = sum(monthly value * monthly NumCon) / mean(monthly NumCon).
-- Missing months, denominators, or mixed methods yield NULL, never a partial annual estimate.
CREATE VIEW official_annual AS
SELECT agent,set_id,extract(year FROM period)::integer AS reference_year,indicator_code,unit,
    CASE WHEN count(*) FILTER(WHERE value IS NOT NULL AND consumer_count>0)=12
          AND count(DISTINCT methodology_version)=1 AND count(DISTINCT analytics_methodology_version)=1
          AND count(DISTINCT transformation_sha256)=1 AND count(DISTINCT sql_sha256)=1
         THEN sum(value*consumer_count)/avg(consumer_count) END AS value,
    count(*) FILTER(WHERE value IS NOT NULL AND consumer_count>0) AS valid_months,
    count(*) FILTER(WHERE value IS NOT NULL AND consumer_count>0)<>12 AS coverage_partial,
    count(DISTINCT methodology_version)>1 OR count(DISTINCT analytics_methodology_version)>1
        OR count(DISTINCT transformation_sha256)>1 OR count(DISTINCT sql_sha256)>1 AS mixed_methods,
    'derived_from_official_monthly'::text AS data_kind,
    'weighted_monthly_over_mean_consumers'::text AS annual_method,
    'electrical_set'::text AS geographic_level,
    array_agg(DISTINCT snapshot_id ORDER BY snapshot_id) AS snapshot_versions,
    array_agg(DISTINCT source_version ORDER BY source_version) AS source_versions,
    array_agg(DISTINCT methodology_version ORDER BY methodology_version) AS methodology_versions,
    min(collected_at) AS first_collected_at,max(collected_at) AS collected_at,
    bool_or(is_multi_uf) AS is_multi_uf,bool_or(agent_link_ambiguous) AS agent_link_ambiguous,
    bool_or(association_temporal_unknown) AS association_temporal_unknown
FROM official_monthly WHERE indicator_code IN ('DEC','FEC')
GROUP BY agent,set_id,extract(year FROM period),indicator_code,unit;
CREATE VIEW exploratory_monthly AS
SELECT x.*,s.methodology_version,e.linked_ufs,e.is_multi_uf,
       e.agent_link_ambiguous,e.association_temporal_unknown,
       'hours per consumer unit (exploratory)'::text AS duration_unit,
       'interruptions per consumer unit (exploratory)'::text AS frequency_unit,
       r.sha256 AS source_version,r.collected_at
FROM interruption_aggregate x JOIN active_partition a USING(snapshot_id,agent,set_id,period)
JOIN electrical_set e USING(snapshot_id,agent,set_id)
JOIN analysis_snapshot s ON s.id=x.snapshot_id
JOIN snapshot_resource sr ON sr.snapshot_id=x.snapshot_id AND sr.role=x.source_role
JOIN source_resource r ON r.resource_id=sr.resource_id AND r.sha256=sr.sha256;
