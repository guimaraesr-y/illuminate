import csv
import datetime
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
import duckdb
from pipelines.aneel.postgres import extract,bundle
from pipelines.aneel.collect import SELECTION
from pipelines.aneel.sources import save


def raw_fixture(root):
    root=Path(root);(root/'raw').mkdir(parents=True)
    contract=json.loads((Path(__file__).parents[1]/'aneel/schema-contract.json').read_text(encoding='utf-8'))
    resources=[]
    with duckdb.connect() as c:
        for alias in ('interruptions','indicators'):
            fields=contract[alias]
            c.execute('CREATE TABLE '+alias+' ('+','.join('"'+k+'" '+v for k,v in fields.items())+')')
            defaults={k:('fixture' if t=='VARCHAR' else datetime.date(2026,1,1) if t=='DATE'
                          else datetime.datetime(2025,1,1) if t=='TIMESTAMP' else 1) for k,t in fields.items()}
            data=[]
            if alias=='interruptions':
                defaults.update(SigAgente=' A ',IdeConjuntoUnidadeConsumidora=1,
                    DatInicioInterrupcao=datetime.datetime(2025,1,1),DatFimInterrupcao=datetime.datetime(2025,1,1,1),
                    DscTipoInterrupcao='Não Programada',IdeMotivoInterrupcao=0,
                    NumUnidadeConsumidora=10,NumConsumidorConjunto=100,NumAno=2025)
                data=[defaults,dict(defaults),dict(defaults,DscAlimentadorSubestacao='other feeder')]
            else:
                for agent in ('A','B'):
                    for metric,value in [('DEC',0),('FEC',1),('DECIND',0),('FECIND',1),('NumCon',100)]:
                        data.append(dict(defaults,SigAgente=' '+agent+' ',IdeConjUndConsumidoras=1,
                                         AnoIndice=2025,NumPeriodoIndice=1,SigIndicador=metric,VlrIndiceEnviado=value))
                data.append(dict(defaults,SigAgente='A',IdeConjUndConsumidoras=1,AnoIndice=2025,
                                 NumPeriodoIndice=2,SigIndicador='DEC',VlrIndiceEnviado=None))
            c.executemany('INSERT INTO '+alias+' VALUES('+','.join('?' for _ in fields)+')',[[r[k] for k in fields] for r in data])
            path=root/(alias+'.parquet')
            c.sql('SELECT * FROM '+alias).write_parquet(str(path))
            raw=path.read_bytes();digest=hashlib.sha256(raw).hexdigest();(root/'raw'/digest).write_bytes(raw)
            resources.append(dict(id=SELECTION[alias][0],dataset=alias,sha256=digest,size_bytes=len(raw),
                path='raw/'+digest,url='https://example.invalid/'+alias,effective_url='https://example.invalid/'+alias,
                retrieved_at='2026-01-01T00:00:00+00:00',format='PARQUET',name='synthetic fixture'))
    path=root/'municipalities.csv'
    with path.open('w',encoding='latin-1',newline='') as f:
        w=csv.writer(f,delimiter=';');w.writerow(contract['municipalities'])
        w.writerows([['2026-01-01','1','3300000','Fixture RJ','RJ'],['2026-01-01','1','3100000','Fixture MG','MG']])
    raw=path.read_bytes();digest=hashlib.sha256(raw).hexdigest();(root/'raw'/digest).write_bytes(raw)
    resources.append(dict(id=SELECTION['municipalities'][0],dataset='municipalities',sha256=digest,
        size_bytes=len(raw),path='raw/'+digest,url='https://example.invalid/m',effective_url='https://example.invalid/m',
        retrieved_at='2026-01-01T00:00:00+00:00',format='CSV',name='synthetic fixture'))
    save(root/'manifest.json',{'resources':resources})


def change_parquet(root,alias,sql):
    m=json.loads((root/'manifest.json').read_text(encoding='utf-8'))
    resource=next(r for r in m['resources'] if r['dataset']==alias)
    with duckdb.connect() as c:
        c.sql('SELECT * FROM read_parquet(?)',params=[str(root/resource['path'])]).create('fixture')
        c.execute(sql)
        path=root/(alias+'-changed.parquet');c.sql('SELECT * FROM fixture').write_parquet(str(path))
        raw=path.read_bytes();digest=hashlib.sha256(raw).hexdigest();(root/'raw'/digest).write_bytes(raw)
        resource.update(sha256=digest,size_bytes=len(raw),path='raw/'+digest)
    save(root/'manifest.json',m)


class ExtractTest(unittest.TestCase):
    def test_real_file_formats_normalize_composite_identity_and_missing_events(self):
        with tempfile.TemporaryDirectory(dir='.') as d:
            p=Path(d);raw_fixture(p/'raw-input')
            m=extract.prepare(p/'raw-input',p/'bundle')
            self.assertEqual(len(list(bundle.records(p/'bundle',m,'electrical_set'))),2)
            sets=list(bundle.records(p/'bundle',m,'electrical_set'))
            self.assertTrue(all(r['agent_link_ambiguous']=='True' and r['is_multi_uf']=='True' for r in sets))
            agg=list(bundle.records(p/'bundle',m,'interruption_aggregate'))
            self.assertEqual(next(r for r in agg if r['agent']=='A' and r['period']=='2025-01-01')['event_rows'],'2')
            self.assertIsNone(next(r for r in agg if r['agent']=='B')['event_rows'])
            indicator=list(bundle.records(p/'bundle',m,'continuity_indicator'))
            self.assertEqual(next(r for r in indicator if r['agent']=='A' and r['period']=='2025-01-01' and r['indicator_code']=='DEC')['value'],'0.0')
            self.assertIsNone(next(r for r in indicator if r['period']=='2025-02-01')['value'])

    def test_scope_selects_only_requested_agent_and_month(self):
        with tempfile.TemporaryDirectory(dir='.') as d:
            p=Path(d);raw_fixture(p/'input')
            m=extract.prepare(p/'input',p/'bundle',bundle.scope(agent='A',start_month=2,end_month=2))
            records=list(bundle.records(p/'bundle',m,'interruption_aggregate'))
            self.assertEqual(len(records),1)
            self.assertEqual(records[0]['period'],'2025-02-01')

    def test_agent_ambiguity_includes_interruption_only_agents(self):
        with tempfile.TemporaryDirectory(dir='.') as d:
            p=Path(d);raw_fixture(p/'input')
            change_parquet(p/'input','indicators',"DELETE FROM fixture WHERE trim(SigAgente)='A'")
            m=extract.prepare(p/'input',p/'bundle',bundle.scope(agent='A'))
            sets=list(bundle.records(p/'bundle',m,'electrical_set'))
            self.assertEqual(len(sets),1)
            self.assertEqual(sets[0]['agent_link_ambiguous'],'True')

    def test_numcon_only_month_preserves_population_and_missing_metrics(self):
        with tempfile.TemporaryDirectory(dir='.') as d:
            p=Path(d);raw_fixture(p/'input')
            change_parquet(p/'input','indicators',"""DELETE FROM fixture WHERE NumPeriodoIndice=2;
                INSERT INTO fixture SELECT * REPLACE(2 AS NumPeriodoIndice,200 AS VlrIndiceEnviado)
                FROM fixture WHERE trim(SigAgente)='A' AND SigIndicador='NumCon'""")
            m=extract.prepare(p/'input',p/'bundle',bundle.scope(agent='A',start_month=2,end_month=2))
            indicators=list(bundle.records(p/'bundle',m,'continuity_indicator'))
            self.assertEqual(len(indicators),4)
            self.assertTrue(all(r['value'] is None and r['consumer_count']=='200.0' for r in indicators))
