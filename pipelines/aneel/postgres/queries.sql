-- Run with search_path=illuminate. Every result retains the electrical-set grain.
SELECT agent,set_id,period,indicator_code,value,unit,quality_status,
       source_version,collected_at,methodology_version,geographic_level,
       is_multi_uf,association_temporal_unknown,indicator_coverage_partial,events_not_observed
FROM official_monthly
WHERE agent='EMR' AND set_id=13746 AND period BETWEEN DATE '2025-01-01' AND DATE '2025-12-01'
ORDER BY period,indicator_code;

-- Distributor filter: preserve sets instead of inventing a distributor-wide average.
SELECT * FROM official_monthly WHERE agent='ENEL RJ' ORDER BY set_id,period,indicator_code;

-- Derived annual from official monthly values and official monthly NumCon.
SELECT agent,set_id,reference_year,indicator_code,value,unit,data_kind,annual_method,
       valid_months,coverage_partial,mixed_methods,snapshot_versions,source_versions,
       methodology_versions,collected_at,is_multi_uf,association_temporal_unknown
FROM official_annual WHERE agent='EMR' AND set_id=13746;

-- Versions, including superseded publications, are never overwritten.
SELECT snapshot_id,agent,set_id,period,indicator_code,value,source_version
FROM official_monthly_history WHERE agent='EMR' AND set_id=13746 ORDER BY snapshot_id,period,indicator_code;
