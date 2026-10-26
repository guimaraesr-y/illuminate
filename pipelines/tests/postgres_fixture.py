"""Synthetic, tiny snapshots for transactional PostgreSQL tests; not ANEEL evidence."""
import hashlib
from pipelines.aneel.postgres import bundle
from pipelines.aneel.postgres.extract import AGGREGATE_COLUMNS,INDICATOR_COLUMNS


def write_fixture(root, *, version='a', value=1, start_month=1,end_month=12,invalid=False):
    resources=[]
    for role in ('interruptions','indicators','municipalities'):
        resources.append(dict(id=role,sha256=hashlib.sha256((role+version).encode()).hexdigest(),
            dataset=role,url='https://example.invalid/'+role,effective_url='https://example.invalid/'+role,
            size_bytes=10,retrieved_at='2026-01-01T00:00:00+00:00',name='synthetic fixture'))
    indicators=[];aggregates=[]
    for agent in ('A','B'):
        for month in range(start_month,end_month+1):
            key=[agent,1,f'2025-{month:02d}-01']
            observed=not(agent=='B' and month==2)
            for code in ('DEC','FEC','DECIND','FECIND'):
                v=0 if agent=='A' and month==1 else value
                if not observed:v=None
                indicators.append(key+[code,v,'hours per consumer unit' if code.startswith('DEC') else 'interruptions per consumer unit',
                                       'reported' if v is not None else 'not_observed',100])
            aggregates.append(key+([5 if not invalid else -1,0,2,.1,.2] if observed else [None]*5)+
                              ['observed' if observed else 'not_observed'])
    tables={
        'distributor':(['agent','name','cnpj'],[['A','Agent A','00000000000001'],['B','Agent B','00000000000002']]),
        'electrical_set':(['agent','set_id','name','linked_ufs','is_multi_uf','agent_link_ambiguous','association_temporal_unknown'],
                          [[a,1,'Synthetic','MG,RJ',True,True,True] for a in ('A','B')]),
        'municipality':(['municipality_code','name','uf'],[['3300000','Synthetic RJ','RJ'],['3100000','Synthetic MG','MG']]),
        'set_municipality_link':(['source_set_id','municipality_code','snapshot_date','valid_from','valid_to'],
                                 [[1,'3300000','2026-01-01',None,None],[1,'3100000','2026-01-01',None,None]]),
        'continuity_indicator':(INDICATOR_COLUMNS,indicators),
        'interruption_aggregate':(AGGREGATE_COLUMNS,aggregates),
    }
    return bundle.write(root,dict(resources=resources,primary_resources={r['dataset']:r['id'] for r in resources},
        scope=bundle.scope(start_month=start_month,end_month=end_month),methodology_version='stage1-v1',
        analytics_methodology_version='stage0-v2',sql_sha256='a'*64,transformation_sha256='b'*64),tables)
