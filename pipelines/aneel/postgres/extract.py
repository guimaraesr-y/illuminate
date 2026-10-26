"""DuckDB preparation of a scoped canonical bundle from verified ANEEL bytes."""
import hashlib
import json
from pathlib import Path
import duckdb
from ..analysis import require_columns,verify_resources,check_indicator_keys
from ..collect import SELECTION
from ..diagnostics import create_events
from . import bundle

HERE=Path(__file__).parent
AGGREGATE_COLUMNS=['agent','set_id','period','event_rows','invalid_rows','candidate_rows',
                   'duration_candidate_h_per_uc','frequency_candidate_per_uc','observation_status']
INDICATOR_COLUMNS=['agent','set_id','period','indicator_code','value','unit','quality_status','consumer_count']


def prepare(root,output,selection=None):
    root,output=Path(root),Path(output)
    selection=selection or bundle.scope()
    if selection!=bundle.scope(**{k:v for k,v in selection.items() if k!='year'}) or selection['year']!=2025:
        raise ValueError('This adapter is verified for 2025 only')
    m=json.loads((root/'manifest.json').read_text(encoding='utf-8'));verify_resources(root,m)
    c=duckdb.connect()
    try:
        c.execute("SET memory_limit='2GB'");c.execute('SET threads=1')
        temp=root/'duckdb-temp';temp.mkdir(exist_ok=True)
        c.execute('SET temp_directory=?',[str(temp.resolve())])
        primary={}
        contract=json.loads((HERE.parent/'schema-contract.json').read_text(encoding='utf-8'))
        for alias in ('interruptions','indicators','municipalities'):
            r=next(r for r in m['resources'] if r['id']==SELECTION[alias][0]);primary[alias]=r['id']
            path=str((root/r['path']).resolve())
            query='SELECT * FROM read_parquet(?)' if alias!='municipalities' else "SELECT * FROM read_csv(?,delim=';',header=true,encoding='latin-1',all_varchar=true)"
            c.sql(query,params=[path]).create_view(alias+'_raw')
            require_columns(c,alias+'_raw',contract[alias])
        create_events(c,deduplicate=True)
        c.execute('''CREATE VIEW links AS SELECT DISTINCT CAST(IdeConjUnidConsumidoras AS BIGINT) AS set_id,
            CodMunicipio AS municipality,trim(SigUF) AS uf FROM municipalities_raw''')
        c.execute('''CREATE VIEW indicators AS SELECT DISTINCT trim(SigAgente) AS agent,
            IdeConjUndConsumidoras AS set_id,AnoIndice AS year,NumPeriodoIndice AS month,
            trim(SigIndicador) AS metric,VlrIndiceEnviado AS value FROM indicators_raw''')
        check_indicator_keys(c)
        sql=(HERE.parent/'sql/rj.sql').read_text(encoding='utf-8')
        c.sql(sql).create_view('full_result')
        # Keep population-only months in coverage even without events or a metric value.
        c.execute('''CREATE VIEW population_keys AS SELECT DISTINCT agent,set_id,year,month
            FROM indicators i WHERE metric='NumCon' AND year=2025
              AND EXISTS(SELECT 1 FROM links l WHERE l.set_id=i.set_id AND l.uf='RJ')''')
        c.execute('''CREATE VIEW set_geography AS SELECT set_id,
            string_agg(DISTINCT uf,',' ORDER BY uf) AS linked_ufs,count(DISTINCT uf) AS linked_uf_count
            FROM links GROUP BY set_id''')
        projection=[]
        for name in c.sql('SELECT * FROM full_result').columns:
            if name in ('agent','set_id','year','month'):expression=f'coalesce(r.{name},p.{name})'
            elif name in ('linked_ufs','linked_uf_count'):expression='g.'+name
            elif name=='is_multi_uf':expression='g.linked_uf_count>1'
            else:expression='r.'+name
            projection.append(expression+' AS '+name)
        c.execute('CREATE VIEW covered_result AS SELECT '+','.join(projection)+'''
            FROM full_result r FULL JOIN population_keys p USING(agent,set_id,year,month)
            JOIN set_geography g ON g.set_id=coalesce(r.set_id,p.set_id)''')
        c.execute('''CREATE VIEW observed_agents AS
            SELECT DISTINCT agent,set_id FROM indicators WHERE year=2025
            UNION SELECT DISTINCT agent,set_id FROM events WHERE year(start_at)=2025''')
        c.sql('''SELECT * FROM covered_result WHERE month BETWEEN ? AND ?
            AND (? IS NULL OR agent=?) AND (? IS NULL OR set_id=?)''',
            params=[selection['start_month'],selection['end_month'],selection['agent'],selection['agent'],
                    selection['set_id'],selection['set_id']]).create_view('selected')
        result=c.sql('SELECT * FROM selected ORDER BY agent,set_id,year,month')
        columns=result.columns;reference=result.fetchall()
        if not reference:
            raise ValueError('Empty analytical scope; refusing publication')
        items=[dict(zip(columns,r)) for r in reference]
        tables={'reference':(columns,reference)}
        tables['distributor']=(['agent','name','cnpj'],c.execute('''SELECT p.agent,
            (SELECT min(NomAgenteRegulado) FROM interruptions_raw i WHERE trim(i.SigAgente)=p.agent),
            lpad(CAST((SELECT min(NumCNPJ) FROM indicators_raw i WHERE trim(i.SigAgente)=p.agent) AS VARCHAR),14,'0')
            FROM (SELECT DISTINCT agent FROM selected) p ORDER BY p.agent''').fetchall())
        tables['electrical_set']=(['agent','set_id','name','linked_ufs','is_multi_uf','agent_link_ambiguous','association_temporal_unknown'],
            c.execute('''SELECT p.agent,p.set_id,
                (SELECT min(DscConjUndConsumidoras) FROM indicators_raw i WHERE trim(i.SigAgente)=p.agent AND i.IdeConjUndConsumidoras=p.set_id),
                p.linked_ufs,p.is_multi_uf,
                (SELECT count(DISTINCT i.agent)>1 FROM observed_agents i WHERE i.set_id=p.set_id),true
                FROM (SELECT DISTINCT agent,set_id,linked_ufs,is_multi_uf FROM selected) p ORDER BY p.agent,p.set_id''').fetchall())
        tables['municipality']=(['municipality_code','name','uf'],c.execute('''SELECT DISTINCT CodMunicipio,NomMunicipio,trim(SigUF)
            FROM municipalities_raw WHERE CAST(IdeConjUnidConsumidoras AS BIGINT) IN (SELECT set_id FROM selected)
            ORDER BY CodMunicipio''').fetchall())
        tables['set_municipality_link']=(['source_set_id','municipality_code','snapshot_date','valid_from','valid_to'],
            c.execute('''SELECT DISTINCT CAST(IdeConjUnidConsumidoras AS BIGINT),CodMunicipio,
                CAST(DatGeracaoConjuntoDados AS DATE),NULL,NULL FROM municipalities_raw
                WHERE CAST(IdeConjUnidConsumidoras AS BIGINT) IN (SELECT set_id FROM selected)
                ORDER BY 1,2''').fetchall())
        populations={(a,s,y,mo):v for a,s,y,mo,v in c.execute("SELECT agent,set_id,year,month,value FROM indicators WHERE metric='NumCon' AND year=2025").fetchall()}
        official=[];aggregates=[]
        for row in items:
            key=[row['agent'],row['set_id'],f"{row['year']}-{row['month']:02d}-01"]
            population=bundle.number(populations.get((row['agent'],row['set_id'],row['year'],row['month'])))
            for metric,field,unit in [('DEC','dec_official_h_per_uc','hours per consumer unit'),
                                      ('FEC','fec_official_per_uc','interruptions per consumer unit'),
                                      ('DECIND','decind_official_h_per_uc','hours per consumer unit'),
                                      ('FECIND','fecind_official_per_uc','interruptions per consumer unit')]:
                value=bundle.number(row[field])
                official.append(key+[metric,value,unit,'reported' if value is not None else 'not_observed',population])
            aggregates.append(key+[row[k] for k in AGGREGATE_COLUMNS[3:-1]]+
                              ['observed' if row['event_rows'] is not None else 'not_observed'])
        tables['continuity_indicator']=(INDICATOR_COLUMNS,official)
        tables['interruption_aggregate']=(AGGREGATE_COLUMNS,aggregates)
        transform=''.join(p.read_text(encoding='utf-8') for p in [Path(__file__),HERE.parent/'diagnostics.py',HERE/'bundle.py'])
        return bundle.write(output,dict(scope=selection,resources=m['resources'],primary_resources=primary,
            methodology_version='stage1-v1',analytics_methodology_version='stage0-v2',
            sql_sha256=hashlib.sha256(sql.encode()).hexdigest(),
            transformation_sha256=hashlib.sha256(transform.encode()).hexdigest()),tables)
    finally:
        c.close()
