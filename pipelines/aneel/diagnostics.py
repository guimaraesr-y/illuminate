"""Explicit deduplication sensitivity and geographic ambiguity diagnostics."""


def create_events(c, *, deduplicate):
    # Deduplicate full physical rows BEFORE projection; feeder differences matter.
    source = '(SELECT DISTINCT * FROM interruptions_raw)' if deduplicate else 'interruptions_raw'
    c.execute(f'''CREATE OR REPLACE TEMP TABLE events AS SELECT
        trim(SigAgente) AS agent, IdeConjuntoUnidadeConsumidora AS set_id,
        DatInicioInterrupcao AS start_at, DatFimInterrupcao AS end_at,
        NumUnidadeConsumidora AS affected, NumConsumidorConjunto AS consumers,
        NumOrdemInterrupcao AS order_id,
        IdeMotivoInterrupcao AS reason_code, trim(DscTipoInterrupcao) AS kind
        FROM {source}''')


def dedup_sensitivity(c, sql):
    """Run identical filters on raw rows without replacing the canonical events table."""
    c.execute('''CREATE TEMP VIEW events_raw AS SELECT
        trim(SigAgente) AS agent, IdeConjuntoUnidadeConsumidora AS set_id,
        DatInicioInterrupcao AS start_at, DatFimInterrupcao AS end_at,
        NumUnidadeConsumidora AS affected, NumConsumidorConjunto AS consumers,
        IdeMotivoInterrupcao AS reason_code, trim(DscTipoInterrupcao) AS kind
        FROM interruptions_raw''')
    # Exactly one explicit input binding in the versioned query; fail on drift.
    if sql.count('FROM events e') != 1:
        raise ValueError('Cannot bind raw events in the RJ query')
    c.execute('CREATE TEMP TABLE result_raw AS '+sql.replace('FROM events e', 'FROM events_raw e'))
    c.execute('''CREATE TEMP TABLE dedup_sensitivity AS SELECT
        r.agent,r.set_id,r.year,r.month,
        r.event_rows AS raw_event_rows,d.event_rows AS deduplicated_event_rows,
        r.event_rows-d.event_rows AS removed_event_rows,
        r.candidate_rows AS raw_candidate_rows,d.candidate_rows AS deduplicated_candidate_rows,
        r.duration_candidate_h_per_uc AS raw_duration_candidate_h_per_uc,
        d.duration_candidate_h_per_uc AS deduplicated_duration_candidate_h_per_uc,
        r.duration_candidate_h_per_uc-d.duration_candidate_h_per_uc AS duration_candidate_delta,
        r.frequency_candidate_per_uc AS raw_frequency_candidate_per_uc,
        d.frequency_candidate_per_uc AS deduplicated_frequency_candidate_per_uc,
        r.frequency_candidate_per_uc-d.frequency_candidate_per_uc AS frequency_candidate_delta,
        r.event_rows IS DISTINCT FROM d.event_rows AS event_count_changed,
        r.linked_ufs,r.is_multi_uf
        FROM result_raw r JOIN result d USING(agent,set_id,year,month)
        ORDER BY agent,set_id,year,month''')
    cursor = c.execute('''SELECT sum(raw_event_rows) AS rj_raw_rows,
        sum(deduplicated_event_rows) AS rj_deduplicated_rows,
        sum(removed_event_rows) AS rj_removed_rows,
        count(*) FILTER (WHERE event_count_changed) AS changed_event_months,
        count(*) FILTER (WHERE abs(duration_candidate_delta)>1e-10) AS changed_duration_months,
        count(*) FILTER (WHERE abs(frequency_candidate_delta)>1e-10) AS changed_frequency_months,
        max(abs(duration_candidate_delta)) AS max_abs_duration_delta_h_per_uc,
        max(abs(frequency_candidate_delta)) AS max_abs_frequency_delta_per_uc
        FROM dedup_sensitivity''')
    return dict(zip([d[0] for d in cursor.description], cursor.fetchone()))


def multi_uf_inventory(c):
    c.execute('''CREATE TEMP TABLE multi_uf_sets AS WITH ambiguous AS (
        SELECT set_id,string_agg(DISTINCT uf,',' ORDER BY uf) AS linked_ufs,
               count(DISTINCT uf) AS linked_uf_count
        FROM links GROUP BY set_id HAVING bool_or(uf='RJ') AND count(DISTINCT uf)>1
    ) SELECT a.*,count(e.set_id) AS observed_event_rows
      FROM ambiguous a LEFT JOIN events e USING(set_id)
      GROUP BY a.set_id,a.linked_ufs,a.linked_uf_count ORDER BY a.set_id''')
    cursor = c.execute('''SELECT count(*) AS snapshot_sets,
        count(*) FILTER (WHERE observed_event_rows>0) AS sets_with_observed_events,
        coalesce(sum(observed_event_rows),0) AS observed_event_rows FROM multi_uf_sets''')
    return dict(zip([d[0] for d in cursor.description], cursor.fetchone()))
