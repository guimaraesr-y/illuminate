-- 2025 events for sets associated with RJ in the collected IndQual snapshot.
-- The snapshot is not proof of historical municipal coverage.
-- Candidate contributions use event-reported denominators; these are NOT DEC/FEC.
WITH scoped AS (
    SELECT e.*, year(start_at) AS year, month(start_at) AS month,
           epoch(end_at) - epoch(start_at) AS seconds,
           end_at >= start_at AND affected >= 0
             AND consumers > 0 AND affected <= consumers AS valid_interval
    FROM events e
    WHERE year(start_at) = 2025
      AND EXISTS (SELECT 1 FROM links l WHERE l.set_id = e.set_id AND l.uf = 'RJ')
), aggregated AS (
    SELECT agent, set_id, year, month,
           count(*) AS event_rows,
           count(*) FILTER (WHERE NOT valid_interval OR valid_interval IS NULL) AS invalid_rows,
           count(*) FILTER (WHERE valid_interval AND seconds >= 180 AND reason_code = 0
                            AND kind = 'Não Programada' AND consumers > 0) AS candidate_rows,
           sum(seconds / 3600.0 * affected / consumers) FILTER (
               WHERE valid_interval AND seconds >= 180 AND reason_code = 0
                 AND kind = 'Não Programada' AND consumers > 0) AS duration_candidate_h_per_uc,
           sum(affected::DOUBLE / consumers) FILTER (
               WHERE valid_interval AND seconds >= 180 AND reason_code = 0
                 AND kind = 'Não Programada' AND consumers > 0) AS frequency_candidate_per_uc
    FROM scoped
    GROUP BY agent, set_id, year, month
), official AS (
    SELECT agent, set_id, year, month,
           max(value) FILTER (WHERE metric = 'DEC') AS dec_official_h_per_uc,
           max(value) FILTER (WHERE metric = 'FEC') AS fec_official_per_uc,
           max(value) FILTER (WHERE metric = 'DECIND') AS decind_official_h_per_uc,
           max(value) FILTER (WHERE metric = 'FECIND') AS fecind_official_per_uc
    FROM indicators i
    WHERE year = 2025 AND metric IN ('DEC','FEC','DECIND','FECIND')
      AND EXISTS (SELECT 1 FROM links l WHERE l.set_id=i.set_id AND l.uf='RJ')
    GROUP BY agent, set_id, year, month
), geography AS (
    SELECT set_id, string_agg(DISTINCT uf, ',' ORDER BY uf) AS linked_ufs,
           count(DISTINCT uf) AS linked_uf_count
    FROM links
    GROUP BY set_id
)
SELECT coalesce(a.agent,o.agent) AS agent, coalesce(a.set_id,o.set_id) AS set_id,
       coalesce(a.year,o.year) AS year, coalesce(a.month,o.month) AS month,
       a.event_rows,a.invalid_rows,a.candidate_rows,
       a.duration_candidate_h_per_uc,a.frequency_candidate_per_uc,
       o.dec_official_h_per_uc, o.fec_official_per_uc,
       o.decind_official_h_per_uc, o.fecind_official_per_uc,
       a.duration_candidate_h_per_uc - o.decind_official_h_per_uc AS duration_delta_vs_decind,
       a.frequency_candidate_per_uc - o.fecind_official_per_uc AS frequency_delta_vs_fecind,
       g.linked_ufs, g.linked_uf_count, g.linked_uf_count > 1 AS is_multi_uf
FROM aggregated a
FULL OUTER JOIN official o USING (agent, set_id, year, month)
LEFT JOIN geography g ON g.set_id = coalesce(a.set_id,o.set_id)
ORDER BY agent, set_id, year, month
