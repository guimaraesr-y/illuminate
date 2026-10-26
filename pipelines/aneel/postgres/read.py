"""Internal SQL read layer: distributor filters preserve individual electrical sets."""
import csv
import json
import math
from pathlib import Path
from . import bundle,database
from ..sources import save,sha256


def series(dsn,schema='illuminate',*,agent,set_id=None,annual=False):
    view='official_annual' if annual else 'official_monthly'
    period='reference_year' if annual else 'period'
    with database.connect(dsn,schema) as c:
        cur=c.execute(f'SELECT * FROM {view} WHERE agent=%s AND (%s::bigint IS NULL OR set_id=%s) ORDER BY set_id,indicator_code,{period}',
                      [agent,set_id,set_id])
        columns=[d[0] for d in cur.description]
        return [dict(zip(columns,r)) for r in cur.fetchall()]


def reconcile(root,dsn,reference,*,schema='illuminate',output=None):
    m=bundle.read(root);reference=Path(reference)
    stage0=json.loads((reference.parent/'manifest.json').read_text(encoding='utf-8'))
    expected={(r['id'],r['sha256']) for r in stage0['resources']}
    primary={role:next(r for r in m['resources'] if r['id']==rid) for role,rid in m['primary_resources'].items()}
    if any((r['id'],r['sha256']) not in expected for r in primary.values()):
        raise ValueError('Reference and bundle use different source versions')
    with reference.open(encoding='utf-8',newline='') as f:
        original={ (r['agent'],int(r['set_id']),int(r['year']),int(r['month'])):r for r in csv.DictReader(f) }
    s=m['scope']
    original={k:v for k,v in original.items() if k[2]==s['year'] and s['start_month']<=k[3]<=s['end_month']
              and (s['agent'] is None or k[0]==s['agent']) and (s['set_id'] is None or k[1]==s['set_id'])}
    with database.connect(dsn,schema) as c:
        cur=c.execute('''SELECT a.agent,a.set_id,extract(year FROM a.period)::integer AS year,
            extract(month FROM a.period)::integer AS month,a.event_rows,a.invalid_rows,a.candidate_rows,
            a.duration_candidate_h_per_uc,a.frequency_candidate_per_uc,e.linked_ufs,e.is_multi_uf,
            max(i.value) FILTER(WHERE i.indicator_code='DEC') AS dec_official_h_per_uc,
            max(i.value) FILTER(WHERE i.indicator_code='FEC') AS fec_official_per_uc,
            max(i.value) FILTER(WHERE i.indicator_code='DECIND') AS decind_official_h_per_uc,
            max(i.value) FILTER(WHERE i.indicator_code='FECIND') AS fecind_official_per_uc
            FROM interruption_aggregate a JOIN electrical_set e USING(snapshot_id,agent,set_id)
            JOIN continuity_indicator i USING(snapshot_id,agent,set_id,period)
            WHERE a.snapshot_id=%s GROUP BY a.snapshot_id,a.agent,a.set_id,a.period,
                e.linked_ufs,e.is_multi_uf ORDER BY a.agent,a.set_id,a.period''',[m['snapshot_id']])
        columns=[d[0] for d in cur.description]
        actual={(r[0],r[1],r[2],r[3]):dict(zip(columns,r)) for r in cur.fetchall()}
        counts={table:c.execute(f'SELECT count(*) FROM {table} WHERE snapshot_id=%s',[m['snapshot_id']]).fetchone()[0]
                for table in ('distributor','electrical_set','municipality','set_municipality_link','continuity_indicator','interruption_aggregate')}
    if set(original)!=set(actual):
        raise ValueError('Reference/PostgreSQL partition keys differ')
    different=[];max_delta=0
    for key,old in original.items():
        for field,value in actual[key].items():
            if field in ('agent','set_id','year','month'):continue
            expected_value=old[field] or None
            if value is None or expected_value is None:
                equal=value is None and expected_value is None
            elif isinstance(value,bool):equal=value==(expected_value.lower()=='true')
            elif isinstance(value,(float,int)):
                delta=abs(float(value)-float(expected_value));max_delta=max(max_delta,delta)
                equal=math.isclose(float(value),float(expected_value),rel_tol=0,abs_tol=1e-10)
            else:equal=value==expected_value
            if not equal:different.append({'key':key,'field':field,'expected':expected_value,'actual':value})
    report=dict(snapshot_id=m['snapshot_id'],scope=s,methodology_version=m['methodology_version'],
        analytics_methodology_version=m['analytics_methodology_version'],same_source_versions=True,
        primary_resource_versions={k:{'resource_id':v['id'],'sha256':v['sha256']} for k,v in primary.items()},
        reference_sha256=sha256(reference),compared_monthly_rows=len(actual),postgres_rows=counts,
        absolute_numeric_tolerance=1e-10,max_absolute_numeric_difference=max_delta,
        differences=different,matched=not different)
    if output:save(output,report)
    if different:raise ValueError(f'Reconciliation failed: {len(different)} different values')
    return report
