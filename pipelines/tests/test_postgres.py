import os
import unittest
import uuid
import tempfile
from pathlib import Path
from pipelines.aneel.postgres import database
from pipelines.aneel.postgres import store
from postgres_fixture import write_fixture


@unittest.skipUnless(os.environ.get('ILLUMINATE_TEST_DATABASE_URL'), 'PostgreSQL integration DSN not configured')
class PostgresTest(unittest.TestCase):
    def setUp(self):
        self.dsn = os.environ['ILLUMINATE_TEST_DATABASE_URL']
        self.schema = 'test_' + uuid.uuid4().hex
        database.migrate(self.dsn, self.schema)

    def tearDown(self):
        import psycopg
        from psycopg import sql
        with psycopg.connect(self.dsn, autocommit=True) as c:
            c.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(self.schema)))

    def test_migrations_are_repeatable(self):
        with database.connect(self.dsn,self.schema) as c:
            before=c.execute('SELECT version,sha256 FROM schema_migration ORDER BY version').fetchall()
        database.migrate(self.dsn, self.schema)
        with database.connect(self.dsn, self.schema) as c:
            self.assertEqual(c.execute('SELECT version,sha256 FROM schema_migration ORDER BY version').fetchall(),before)
            self.assertTrue(before)

    def load(self,root):
        return store.ingest(root,self.dsn,self.schema)

    def test_same_snapshot_is_idempotent_and_preserves_null_and_zero(self):
        with tempfile.TemporaryDirectory(dir='.') as d:
            write_fixture(Path(d));first=self.load(d);second=self.load(d)
            self.assertEqual(first['snapshot_id'],second['snapshot_id'])
            self.assertEqual(second['status'],'reused')
            with database.connect(self.dsn,self.schema) as c:
                self.assertEqual(c.execute('SELECT count(*) FROM continuity_indicator').fetchone()[0],96)
                self.assertEqual(c.execute('SELECT count(*) FROM interruption_aggregate').fetchone()[0],24)
                self.assertEqual(c.execute("SELECT value FROM official_monthly WHERE agent='A' AND period='2025-01-01' AND indicator_code='DEC'").fetchone()[0],0)
                self.assertIsNone(c.execute("SELECT event_rows FROM exploratory_monthly WHERE agent='B' AND period='2025-02-01'").fetchone()[0])
                self.assertEqual(c.execute('SELECT count(*) FROM set_municipality_link').fetchone()[0],2)
                self.assertEqual(c.execute('SELECT count(*) FROM electrical_set WHERE set_id=1 AND agent_link_ambiguous').fetchone()[0],2)

    def test_failed_new_snapshot_rolls_back_without_changing_active(self):
        with tempfile.TemporaryDirectory(dir='.') as d:
            p=Path(d);old=write_fixture(p/'old');self.load(p/'old')
            write_fixture(p/'bad',version='bad',invalid=True)
            with self.assertRaises(Exception):self.load(p/'bad')
            with database.connect(self.dsn,self.schema) as c:
                self.assertEqual(c.execute('SELECT count(*) FROM analysis_snapshot').fetchone()[0],1)
                self.assertEqual(c.execute('SELECT DISTINCT snapshot_id FROM active_partition').fetchone()[0],old['snapshot_id'])
                self.assertEqual(c.execute("SELECT count(*) FROM ingestion_run WHERE status='failed'").fetchone()[0],1)
                self.assertEqual(c.execute("SELECT input_metadata->'scope'->>'year' FROM ingestion_run WHERE status='failed'").fetchone()[0],'2025')

    def test_retroactive_partial_update_retains_history_and_other_months(self):
        with tempfile.TemporaryDirectory(dir='.') as d:
            p=Path(d);old=write_fixture(p/'old');self.load(p/'old')
            new=write_fixture(p/'new',version='new',value=9,start_month=3,end_month=3);self.load(p/'new')
            self.load(p/'old') # Replaying history must not revert the active correction.
            with database.connect(self.dsn,self.schema) as c:
                self.assertEqual(c.execute("SELECT value FROM official_monthly WHERE agent='A' AND period='2025-03-01' AND indicator_code='DEC'").fetchone()[0],9)
                self.assertEqual(c.execute("SELECT value FROM official_monthly_history WHERE snapshot_id=%s AND agent='A' AND period='2025-03-01' AND indicator_code='DEC'",[old['snapshot_id']]).fetchone()[0],1)
                self.assertEqual(c.execute('SELECT count(*) FROM active_partition').fetchone()[0],24)
                self.assertEqual(c.execute('SELECT count(*) FROM source_resource').fetchone()[0],6)

    def test_annual_requires_twelve_values_and_preserves_geographic_flags(self):
        with tempfile.TemporaryDirectory(dir='.') as d:
            write_fixture(Path(d));self.load(d)
            with database.connect(self.dsn,self.schema) as c:
                a=c.execute("SELECT value,valid_months,is_multi_uf,data_kind FROM official_annual WHERE agent='A' AND indicator_code='DEC'").fetchone()
                self.assertEqual(a,(11,12,True,'derived_from_official_monthly'))
                b=c.execute("SELECT value,coverage_partial FROM official_annual WHERE agent='B' AND indicator_code='DEC'").fetchone()
                self.assertEqual(b,(None,True))

    def test_annual_uses_published_monthly_population_not_plain_sum(self):
        from pipelines.aneel.postgres import bundle
        with tempfile.TemporaryDirectory(dir='.') as d:
            p=Path(d);m=write_fixture(p)
            data=list(bundle.records(p,m,'continuity_indicator'))
            for row in data:
                if row['period']!='2025-01-01':row['consumer_count']='200'
            # Rebuild a valid content-addressed fixture, not a corrupted bundle.
            import csv
            with (p/'continuity_indicator.csv').open('w',encoding='utf-8',newline='') as f:
                w=csv.DictWriter(f,fieldnames=list(data[0]));w.writeheader();w.writerows(data)
            from pipelines.aneel.sources import save,sha256
            m['files']['continuity_indicator']['sha256']=sha256(p/'continuity_indicator.csv')
            m['snapshot_id']=bundle.identity(m);save(p/'bundle.json',m)
            self.load(p)
            with database.connect(self.dsn,self.schema) as c:
                value=c.execute("SELECT value FROM official_annual WHERE agent='A' AND indicator_code='DEC'").fetchone()[0]
                self.assertAlmostEqual(value,11.478260869565217)

    def test_concurrent_same_snapshot_publishes_only_once(self):
        from concurrent.futures import ThreadPoolExecutor
        with tempfile.TemporaryDirectory(dir='.') as d:
            write_fixture(Path(d))
            with ThreadPoolExecutor(max_workers=2) as pool:
                results=list(pool.map(lambda _:self.load(d),range(2)))
            self.assertEqual(sorted(r['status'] for r in results),['reused','succeeded'])
            with database.connect(self.dsn,self.schema) as c:
                self.assertEqual(c.execute('SELECT count(*) FROM analysis_snapshot').fetchone()[0],1)
                self.assertEqual(c.execute('SELECT count(*) FROM continuity_indicator').fetchone()[0],96)

    def test_changed_applied_migration_is_rejected(self):
        with database.connect(self.dsn,self.schema) as c:
            c.execute("UPDATE schema_migration SET sha256='changed' WHERE version=(SELECT min(version) FROM schema_migration)")
        with self.assertRaisesRegex(ValueError,'checksum'):
            database.migrate(self.dsn,self.schema)

    def test_interrupted_copy_rolls_back_staged_rows(self):
        from unittest.mock import patch
        from pipelines.aneel.postgres import bundle
        original=bundle.records
        def interrupted(root,metadata,name):
            if name=='continuity_indicator':
                yield next(original(root,metadata,name))
                raise RuntimeError('Simulated interrupted COPY')
            yield from original(root,metadata,name)
        with tempfile.TemporaryDirectory(dir='.') as d:
            p=Path(d);write_fixture(p/'old');self.load(p/'old')
            write_fixture(p/'new',version='interrupted')
            with patch.object(bundle,'records',interrupted):
                with self.assertRaisesRegex(RuntimeError,'interrupted'):
                    self.load(p/'new')
            with database.connect(self.dsn,self.schema) as c:
                self.assertEqual(c.execute('SELECT count(*) FROM analysis_snapshot').fetchone()[0],1)
                self.assertEqual(c.execute('SELECT count(*) FROM source_resource').fetchone()[0],3)
                self.assertEqual(c.execute('SELECT count(*) FROM active_partition').fetchone()[0],24)

    def test_postgres_reconciles_prepared_duckdb_fixture(self):
        from test_extract import raw_fixture
        from pipelines.aneel.postgres import extract,read
        import shutil
        with tempfile.TemporaryDirectory(dir='.') as d:
            p=Path(d);raw_fixture(p/'input');extract.prepare(p/'input',p/'bundle')
            self.load(p/'bundle')
            # Reference has the same three source hashes and an independently stored SQL result.
            (p/'reference').mkdir()
            shutil.copyfile(p/'input/manifest.json',p/'reference/manifest.json')
            shutil.copyfile(p/'bundle/reference.csv',p/'reference/rj.csv')
            report=read.reconcile(p/'bundle',self.dsn,p/'reference/rj.csv',schema=self.schema)
            self.assertTrue(report['matched'])
            self.assertEqual(report['compared_monthly_rows'],3)


if __name__ == '__main__':
    unittest.main()
