import unittest
from pathlib import Path
import duckdb

SQL = Path(__file__).parents[1] / 'aneel' / 'sql' / 'rj.sql'


class AnalysisTest(unittest.TestCase):
    def setUp(self):
        self.c = duckdb.connect()
        self.c.execute('CREATE TABLE events(agent VARCHAR, set_id BIGINT, start_at TIMESTAMP, end_at TIMESTAMP, affected BIGINT, consumers BIGINT, reason_code BIGINT, kind VARCHAR)')
        self.c.execute("INSERT INTO events VALUES ('A',1,'2025-01-01','2025-01-01 01:00:00',10,100,0,'Não Programada'),('A',1,'2025-01-02','2025-01-01',5,100,0,'Não Programada'),('A',2,'2025-01-01','2025-01-01 01:00:00',10,0,0,'Não Programada')")
        self.c.execute('CREATE TABLE links(set_id BIGINT, municipality VARCHAR, uf VARCHAR)')
        self.c.execute("INSERT INTO links VALUES (1,'a','RJ'),(1,'b','RJ'),(1,'a','RJ'),(2,'c','RJ')")
        self.c.execute('CREATE TABLE indicators(agent VARCHAR,set_id BIGINT,year BIGINT,month BIGINT,metric VARCHAR,value DOUBLE)')
        self.c.execute("INSERT INTO indicators VALUES ('A',1,2025,1,'DEC',0.1),('A',1,2025,1,'FEC',0.1),('A',2,2025,1,'DEC',0.1),('A',2,2025,1,'FEC',0.1)")

    def tearDown(self): self.c.close()

    def run_query(self):
        return self.c.sql(SQL.read_text(encoding='utf-8')).fetchall()

    def test_many_to_many_links_never_multiply_events(self):
        rows = self.run_query()
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0][4], 2)  # raw events, including an invalid interval
        self.assertAlmostEqual(rows[0][7], .1)  # candidate duration contribution

    def test_invalid_interval_excluded_and_zero_denominator_is_null(self):
        rows = self.run_query()
        self.assertEqual(rows[0][5], 1)
        self.assertIsNone(rows[1][7])

    def test_official_only_month_retained_as_missing_events(self):
        self.c.execute("INSERT INTO indicators VALUES ('A',1,2025,2,'DEC',0)")
        rows = self.run_query()
        self.assertEqual(len(rows), 3)
        self.assertIsNone(rows[1][4])
        self.assertEqual(rows[1][9], 0)

    def test_affected_over_population_excluded(self):
        self.c.execute("INSERT INTO events VALUES ('A',1,'2025-01-03','2025-01-03 01:00:00',200,100,0,'Não Programada')")
        rows = self.run_query()
        self.assertAlmostEqual(rows[0][7], .1)
        self.assertEqual(rows[0][5], 2)


if __name__ == '__main__': unittest.main()
