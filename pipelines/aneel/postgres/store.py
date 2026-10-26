"""COPY staging and atomic publication of immutable analytical snapshots."""
import uuid
from psycopg import sql
from psycopg.types.json import Jsonb
from . import bundle,database
from .extract import AGGREGATE_COLUMNS,INDICATOR_COLUMNS

TABLES={
    'distributor':['agent','name','cnpj'],
    'electrical_set':['agent','set_id','name','linked_ufs','is_multi_uf','agent_link_ambiguous','association_temporal_unknown'],
    'municipality':['municipality_code','name','uf'],
    'set_municipality_link':['source_set_id','municipality_code','snapshot_date','valid_from','valid_to'],
    'continuity_indicator':INDICATOR_COLUMNS,
    'interruption_aggregate':AGGREGATE_COLUMNS,
}


def ingest(root,dsn,schema='illuminate'):
    m=bundle.read(root);sid=m['snapshot_id'];run=str(uuid.uuid4())
    if not set(TABLES)<=set(m['files']):
        raise ValueError('Missing canonical tables')
    selection=m['scope']
    if selection!=bundle.scope(**{k:v for k,v in selection.items() if k!='year'}):
        raise ValueError('Invalid publication scope')
    with database.connect(dsn,schema) as c:
        c.execute("INSERT INTO ingestion_run(id,snapshot_id,status,input_metadata) VALUES(%s,%s,'running',%s)",[run,sid,Jsonb(m)])
        try:
            with c.transaction():
                c.execute('SELECT pg_advisory_xact_lock(hashtext(%s))',['illuminate:publish:'+schema])
                if c.execute('SELECT 1 FROM analysis_snapshot WHERE id=%s',[sid]).fetchone():
                    c.execute("UPDATE ingestion_run SET status='reused',finished_at=now() WHERE id=%s",[run])
                    return dict(snapshot_id=sid,status='reused',run_id=run)
                c.execute('''INSERT INTO analysis_snapshot(id,scope,methodology_version,analytics_methodology_version,
                    transformation_sha256,sql_sha256,bundle) VALUES(%s,%s,%s,%s,%s,%s,%s)''',
                    [sid,Jsonb(selection),m['methodology_version'],m['analytics_methodology_version'],
                     m['transformation_sha256'],m['sql_sha256'],Jsonb(m)])
                for r in m['resources']:
                    c.execute('''INSERT INTO source_resource(resource_id,sha256,dataset,original_url,effective_url,
                        size_bytes,collected_at,period_label,metadata) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)
                        ON CONFLICT(resource_id,sha256) DO NOTHING''',
                        [r['id'],r['sha256'],r['dataset'],r['url'],r['effective_url'],r['size_bytes'],
                         r['retrieved_at'],r.get('name'),Jsonb(r)])
                for role,rid in m['primary_resources'].items():
                    r=next(r for r in m['resources'] if r['id']==rid)
                    c.execute('INSERT INTO snapshot_resource VALUES(%s,%s,%s,%s)',[sid,role,rid,r['sha256']])
                counts={}
                for table,columns in TABLES.items():
                    stage='stage_'+table
                    c.execute(sql.SQL('CREATE TEMP TABLE {} (LIKE {} INCLUDING DEFAULTS) ON COMMIT DROP').format(
                        sql.Identifier(stage),sql.Identifier(table)))
                    copy=sql.SQL('COPY {} ({}) FROM STDIN').format(sql.Identifier(stage),
                        sql.SQL(',').join(map(sql.Identifier,['snapshot_id']+columns)))
                    count=0
                    with c.cursor().copy(copy) as out:
                        for row in bundle.records(root,m,table):
                            if set(row)!=set(columns):
                                raise ValueError('Invalid CSV schema: '+table)
                            out.write_row([sid]+[row[k] for k in columns]);count+=1
                    c.execute(sql.SQL('INSERT INTO {} SELECT * FROM {}').format(sql.Identifier(table),sql.Identifier(stage)))
                    counts[table]=count
                if not counts['interruption_aggregate']:
                    raise ValueError('Refusing empty publication')
                invalid=c.execute('''SELECT count(*) FROM interruption_aggregate WHERE snapshot_id=%s AND
                    (extract(year FROM period)<>%s OR extract(month FROM period) NOT BETWEEN %s AND %s
                     OR (%s::text IS NOT NULL AND agent<>%s) OR (%s::bigint IS NOT NULL AND set_id<>%s))''',
                    [sid,selection['year'],selection['start_month'],selection['end_month'],
                     selection['agent'],selection['agent'],selection['set_id'],selection['set_id']]).fetchone()[0]
                if invalid:
                    raise ValueError('Analytical rows outside declared publication scope')
                mismatch=c.execute('''WITH i AS (SELECT agent,set_id,period FROM continuity_indicator WHERE snapshot_id=%s GROUP BY 1,2,3),
                    a AS (SELECT agent,set_id,period FROM interruption_aggregate WHERE snapshot_id=%s)
                    SELECT (SELECT count(*) FROM (SELECT * FROM i EXCEPT SELECT * FROM a) x)
                         + (SELECT count(*) FROM (SELECT * FROM a EXCEPT SELECT * FROM i) x)''',[sid,sid]).fetchone()[0]
                incomplete=c.execute('''SELECT count(*) FROM (SELECT agent,set_id,period FROM continuity_indicator
                    WHERE snapshot_id=%s GROUP BY 1,2,3 HAVING count(*)<>4) x''',[sid]).fetchone()[0]
                if mismatch or incomplete:
                    raise ValueError('Official and aggregate partition keys or metric coverage differ')
                # A correction replaces only the explicitly selected partitions, including removed keys.
                c.execute('''DELETE FROM active_partition WHERE extract(year FROM period)=%s
                    AND extract(month FROM period) BETWEEN %s AND %s
                    AND (%s::text IS NULL OR agent=%s) AND (%s::bigint IS NULL OR set_id=%s)''',
                    [selection['year'],selection['start_month'],selection['end_month'],
                     selection['agent'],selection['agent'],selection['set_id'],selection['set_id']])
                c.execute('''INSERT INTO active_partition(agent,set_id,period,snapshot_id)
                    SELECT agent,set_id,period,snapshot_id FROM interruption_aggregate WHERE snapshot_id=%s''',[sid])
                c.execute("UPDATE ingestion_run SET status='succeeded',finished_at=now() WHERE id=%s",[run])
            return dict(snapshot_id=sid,status='succeeded',run_id=run,rows=counts)
        except Exception as error:
            c.execute("UPDATE ingestion_run SET status='failed',finished_at=now(),error=%s WHERE id=%s",
                      [type(error).__name__+': '+str(error)[:1500],run])
            raise
