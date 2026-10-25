"""Offline validation and DuckDB analysis of hash-verified official resources."""
import argparse
import csv
import hashlib
import json
import shutil
from pathlib import Path

import duckdb
from pypdf import PdfReader
from .sources import save, sha256
from .diagnostics import create_events, dedup_sensitivity, multi_uf_inventory

HERE = Path(__file__).parent


def rows(c, sql):
    cursor = c.execute(sql)
    names = [d[0] for d in cursor.description]
    return [dict(zip(names, row)) for row in cursor.fetchall()]


def require_columns(c, table, expected):
    actual = {r[0]: r[1] for r in c.execute(f'DESCRIBE {table}').fetchall()}
    if any(actual.get(k) != v for k, v in expected.items()):
        raise ValueError(f'Incompatible schema in {table}: expected {expected}; got {actual}')


def check_indicator_keys(c):
    n = c.execute('''SELECT count(*) FROM (
        SELECT agent,set_id,year,month,metric FROM indicators
        GROUP BY ALL HAVING count(*) > 1)''').fetchone()[0]
    if n:
        raise ValueError(f'Ambiguous indicator keys: {n}')


def verify_resources(root, manifest):
    for r in manifest['resources']:
        p = (root / r['path']).resolve()
        if not p.is_relative_to(root.resolve()):
            raise ValueError('Resource path outside data root')
        if p.stat().st_size != r['size_bytes'] or sha256(p) != r['sha256']:
            raise ValueError(f'Resource size/hash mismatch: {r["path"]}')


def check_annual_coverage(c):
    monthly = rows(c, '''SELECT month(start_at) AS month,count(*) AS rows FROM events
        WHERE year(start_at)=2025 GROUP BY month ORDER BY month''')
    if {r['month'] for r in monthly} != set(range(1,13)):
        raise ValueError('Annual coverage incomplete: all 12 months must be observed')
    return {'monthly_rows': monthly, 'observed_months': 12,
            'assessment': 'All months observed in full resource; does not prove all real interruptions were reported'}


def profile(c, table):
    schema = rows(c, f'DESCRIBE {table}')
    n = c.execute(f'SELECT count(*) FROM {table}').fetchone()[0]
    unique = c.execute(f'SELECT count(*) FROM (SELECT DISTINCT * FROM {table})').fetchone()[0]
    null_sql = ','.join(f'count(*) FILTER (WHERE "{s["column_name"]}" IS NULL) AS "{s["column_name"]}"' for s in schema)
    return {'rows': n, 'exact_duplicate_rows': n - unique, 'schema': schema,
            'nulls': rows(c, f'SELECT {null_sql} FROM {table}')[0]}


def write_csv(path, result):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(result.columns)
        writer.writerows(result.fetchall())


def analyze(root, output):
    root, output = Path(root), Path(output)
    manifest = json.loads((root/'manifest.json').read_text(encoding='utf-8'))
    verify_resources(root, manifest)
    output.mkdir(parents=True, exist_ok=True)
    c = duckdb.connect()
    c.execute("SET memory_limit='2GB'")
    # Stable scan and floating-point aggregation order for byte-for-byte replay.
    c.execute('SET threads=1')
    temp = root/'duckdb-temp'
    temp.mkdir(exist_ok=True)
    c.execute('SET temp_directory = ?', [str(temp.resolve())])
    by_id = {r['id']: r for r in manifest['resources']}
    from .collect import SELECTION
    for alias in ('interruptions','indicators','municipalities'):
        r = by_id[SELECTION[alias][0]]
        f = str((root/r['path']).resolve())
        if r['format'].upper() == 'PARQUET':
            c.sql('SELECT * FROM read_parquet(?)', params=[f]).create_view(alias + '_raw')
        else:
            c.sql("SELECT * FROM read_csv(?,delim=';',header=true,encoding='latin-1',all_varchar=true)", params=[f]).create_view(alias + '_raw')
    # Pinned only after direct inspection of the collected official files.
    contract = json.loads((HERE/'schema-contract.json').read_text(encoding='utf-8'))
    for alias, schema in contract.items():
        require_columns(c, alias + '_raw', schema)
    quality = {}
    for alias in ('interruptions','indicators','municipalities'):
        print('Profiling', alias, flush=True)
        quality[alias] = profile(c, alias + '_raw')
        save(output/'quality.json', quality)
    create_events(c, deduplicate=True)
    c.execute('''CREATE VIEW links AS SELECT DISTINCT
        CAST(IdeConjUnidConsumidoras AS BIGINT) AS set_id,
        CodMunicipio AS municipality, trim(SigUF) AS uf FROM municipalities_raw''')
    c.execute('''CREATE VIEW indicators AS SELECT DISTINCT
        trim(SigAgente) AS agent, IdeConjUndConsumidoras AS set_id,
        AnoIndice AS year, NumPeriodoIndice AS month,
        trim(SigIndicador) AS metric, VlrIndiceEnviado AS value FROM indicators_raw''')
    check_indicator_keys(c)
    quality['annual_coverage'] = check_annual_coverage(c)
    quality['candidate_key'] = rows(c, '''SELECT count(*) AS repeated_agent_set_order_groups,
        sum(n-1) AS excess_rows FROM (SELECT agent,set_id,order_id,count(*) AS n
        FROM events GROUP BY ALL HAVING count(*)>1)''')[0]
    quality['event_checks'] = rows(c, '''SELECT min(start_at) AS min_start, max(start_at) AS max_start,
        min(end_at) AS min_end, max(end_at) AS max_end,
        count(*) FILTER (WHERE end_at < start_at) AS negative_intervals,
        count(*) FILTER (WHERE end_at = start_at) AS zero_intervals,
        count(*) FILTER (WHERE start_at IS NULL OR end_at IS NULL) AS missing_timestamps,
        count(*) FILTER (WHERE year(start_at) != 2025) AS outside_partition_year,
        count(*) FILTER (WHERE affected < 0) AS negative_affected,
        count(*) FILTER (WHERE consumers <= 0) AS nonpositive_denominator,
        count(*) FILTER (WHERE consumers IS NULL) AS missing_denominator,
        count(*) FILTER (WHERE affected > consumers) AS affected_exceeds_denominator
        FROM events''')[0]
    quality['agents'] = rows(c, 'SELECT agent,count(*) AS rows,count(DISTINCT set_id) AS sets FROM events GROUP BY agent ORDER BY rows DESC')
    write_csv(output/'distribution-by-set.csv', c.sql('SELECT agent,set_id,count(*) AS rows FROM events GROUP BY ALL ORDER BY agent,set_id'))
    quality['reason_codes'] = rows(c, 'SELECT reason_code,kind,count(*) AS rows FROM events GROUP BY ALL ORDER BY reason_code,kind')
    quality['links'] = rows(c, '''SELECT count(*) AS distinct_links, count(DISTINCT set_id) AS sets,
        count(DISTINCT municipality) AS municipalities FROM links''')[0]
    quality['links']['multi_municipality_sets'] = c.execute('SELECT count(*) FROM (SELECT set_id FROM links GROUP BY set_id HAVING count(DISTINCT municipality)>1)').fetchone()[0]
    quality['links']['multi_set_municipalities'] = c.execute('SELECT count(*) FROM (SELECT municipality FROM links GROUP BY municipality HAVING count(DISTINCT set_id)>1)').fetchone()[0]
    quality['links']['multi_state_sets'] = c.execute('SELECT count(*) FROM (SELECT set_id FROM links GROUP BY set_id HAVING count(DISTINCT uf)>1)').fetchone()[0]
    quality['links']['generation_dates'] = rows(c, 'SELECT DatGeracaoConjuntoDados,count(*) AS rows FROM municipalities_raw GROUP BY ALL')
    quality['rj_coverage'] = rows(c, '''SELECT count(DISTINCT e.set_id) AS event_sets,
        count(DISTINCT l.set_id) AS matched_sets,
        count(*) FILTER (WHERE l.set_id IS NOT NULL) AS matched_event_rows
        FROM events e LEFT JOIN (SELECT DISTINCT set_id FROM links WHERE uf='RJ') l USING(set_id)''')[0]
    quality['rj_links'] = rows(c, "SELECT count(*) AS links,count(DISTINCT set_id) AS sets,count(DISTINCT municipality) AS municipalities FROM links WHERE uf='RJ'")[0]
    quality['rj_multi_uf'] = multi_uf_inventory(c)
    quality['rj_multi_uf']['share_of_observed_rj_event_rows'] = (
        quality['rj_multi_uf']['observed_event_rows'] / quality['rj_coverage']['matched_event_rows']
        if quality['rj_coverage']['matched_event_rows'] else None)
    write_csv(output/'rj-multi-uf.csv', c.sql('SELECT * FROM multi_uf_sets ORDER BY set_id'))
    quality['indicator_periods_2025'] = rows(c, 'SELECT month,count(*) AS rows FROM indicators WHERE year=2025 GROUP BY month ORDER BY month')
    sql = (HERE/'sql/rj.sql').read_text(encoding='utf-8')
    c.sql(sql).create_view('result')
    # A subset is an observation about the collected snapshot, never a municipal estimate.
    write_csv(output/'rj-2025.csv', c.sql('SELECT * FROM result'))
    write_csv(output/'rj-sample.csv', c.sql('SELECT * FROM result WHERE decind_official_h_per_uc IS NOT NULL AND event_rows IS NOT NULL ORDER BY agent,set_id,year,month LIMIT 24'))
    quality['dedup_sensitivity'] = dedup_sensitivity(c, sql)
    quality['dedup_sensitivity']['national_raw_rows'] = quality['interruptions']['rows']
    quality['dedup_sensitivity']['national_exact_repeated_rows'] = quality['interruptions']['exact_duplicate_rows']
    quality['dedup_sensitivity']['policy'] = 'Exact-row deduplication is an analytical scenario, not confirmed export-error correction; immutable raw input is preserved.'
    write_csv(output/'rj-2025-raw.csv', c.sql('SELECT * FROM result_raw ORDER BY agent,set_id,year,month'))
    write_csv(output/'rj-dedup-sensitivity.csv', c.sql('SELECT * FROM dedup_sensitivity ORDER BY agent,set_id,year,month'))
    quality['comparison'] = rows(c, '''SELECT count(*) AS rows,
        count(*) FILTER (WHERE decind_official_h_per_uc IS NOT NULL AND event_rows IS NOT NULL) AS matched_official_rows,
        count(*) FILTER (WHERE event_rows IS NULL) AS official_only_rows,
        count(*) FILTER (WHERE decind_official_h_per_uc IS NULL) AS missing_official_decind_rows,
        min(duration_delta_vs_decind) AS min_duration_delta,
        max(duration_delta_vs_decind) AS max_duration_delta,
        count(*) FILTER (WHERE abs(duration_delta_vs_decind)<=0.01) AS within_001_hours
        FROM result''')[0]
    save(output/'quality.json', quality)
    for r in manifest['resources']:
        if r['format'].upper() == 'PDF':
            text = '\n'.join(page.extract_text() for page in PdfReader(root/r['path']).pages)
            text = '\n'.join(line.rstrip() for line in text.splitlines()).strip() + '\n'
            (output/f'dictionary-{r["id"]}.txt').write_text(text,encoding='utf-8')
    manifest['analysis_reference_period'] = '2025-01-01/2025-12-31'
    manifest['period_notes'] = 'Resource names retain catalog partition labels; IndQual is a snapshot without historical validity; dictionary applicability follows catalog name.'
    save(output/'manifest.json', manifest)
    if (root/'catalog').exists():
        shutil.copytree(root/'catalog', output/'catalog', dirs_exist_ok=True)
    save(output/'analysis.json', {
        'reference_period': '2025-01-01/2025-12-31', 'geographic_level': 'electrical_set',
        'geographic_selection': 'Sets linked to RJ in collected IndQual snapshot; historical coverage unverified',
        'methodology_version': 'stage0-v2', 'duckdb_version': duckdb.__version__, 'threads': 1,
        'deduplication_policy': 'Both physical-raw and exact-row-deduplicated scenarios published; event identity remains unverified',
        'geographic_ambiguity': 'is_multi_uf marks snapshot associations across states; no state allocation weights are available',
        'sql_sha256': hashlib.sha256(sql.encode('utf-8')).hexdigest(),
        'table_sha256': sha256(output/'rj-2025.csv'),
        'raw_table_sha256': sha256(output/'rj-2025-raw.csv'),
        'sensitivity_table_sha256': sha256(output/'rj-dedup-sensitivity.csv'),
        'multi_uf_table_sha256': sha256(output/'rj-multi-uf.csv'),
        'units': {'event_rows':'reported records after exact-row deduplication',
                  'duration_candidate_h_per_uc':'hours per consumer unit; exploratory, not regulatory DEC',
                  'frequency_candidate_per_uc':'interruptions per consumer unit; exploratory, not regulatory FEC',
                  'dec_official_h_per_uc':'hours per consumer unit, official',
                  'fec_official_per_uc':'interruptions per consumer unit, official'},
        'resources': [r['sha256'] for r in manifest['resources']]})
    c.close()


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--root', type=Path, default=Path('data/aneel'))
    p.add_argument('--output', type=Path, default=Path('reports/stage0'))
    a = p.parse_args()
    analyze(a.root,a.output)
