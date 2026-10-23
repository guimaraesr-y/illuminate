import tempfile
import unittest
from pathlib import Path
import duckdb
from pipelines.aneel import analysis


class ContractsTest(unittest.TestCase):
    def test_schema_drift_rejected(self):
        c = duckdb.connect()
        c.execute('create table sample(wrong varchar)')
        with self.assertRaisesRegex(ValueError, 'schema'):
            analysis.require_columns(c, 'sample', {'start_at': 'TIMESTAMP'})
        c.close()

    def test_conflicting_indicator_key_rejected(self):
        c = duckdb.connect()
        c.execute('create table indicators(agent varchar,set_id bigint,year bigint,month bigint,metric varchar,value double)')
        c.execute("insert into indicators values ('A',1,2025,1,'DEC',1),('A',1,2025,1,'DEC',2)")
        with self.assertRaisesRegex(ValueError, 'indicator'):
            analysis.check_indicator_keys(c)
        c.close()

    def test_corrupt_replay_fails_before_analysis(self):
        with tempfile.TemporaryDirectory(dir='.') as d:
            root = Path(d)
            (root/'file').write_bytes(b'bad')
            with self.assertRaisesRegex(ValueError, 'hash'):
                analysis.verify_resources(root, {'resources':[{'path':'file','sha256':'wrong','size_bytes':3}]})

    def test_partial_annual_coverage_rejected(self):
        c = duckdb.connect()
        c.execute('create table events(start_at timestamp)')
        c.execute("insert into events values ('2025-01-01')")
        with self.assertRaisesRegex(ValueError, 'months'):
            analysis.check_annual_coverage(c)
        c.close()


if __name__ == '__main__': unittest.main()
