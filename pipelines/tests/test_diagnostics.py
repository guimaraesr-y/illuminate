import unittest
from pathlib import Path
import test_analysis
from pipelines.aneel import diagnostics


class DiagnosticsTest(unittest.TestCase):
    def setUp(self):
        fixture = test_analysis.AnalysisTest()
        fixture.setUp()
        self.c = fixture.c
        self.c.execute('''CREATE TABLE interruptions_raw AS SELECT agent AS SigAgente,
            set_id AS IdeConjuntoUnidadeConsumidora, start_at AS DatInicioInterrupcao,
            end_at AS DatFimInterrupcao, affected AS NumUnidadeConsumidora,
            consumers AS NumConsumidorConjunto, 'order' AS NumOrdemInterrupcao,
            reason_code AS IdeMotivoInterrupcao, kind AS DscTipoInterrupcao,
            'feeder-a' AS DscAlimentadorSubestacao FROM events''')
        self.c.execute('DROP TABLE events')
        self.c.execute('INSERT INTO interruptions_raw SELECT * FROM interruptions_raw LIMIT 1')
        # Same projected metric fields, different physical record: must remain distinct.
        self.c.execute("INSERT INTO interruptions_raw SELECT * REPLACE ('feeder-b' AS DscAlimentadorSubestacao) FROM interruptions_raw LIMIT 1")
        self.sql = (Path(__file__).parents[1]/'aneel/sql/rj.sql').read_text(encoding='utf-8')

    def tearDown(self):
        self.c.close()

    def test_sensitivity_preserves_raw_and_compares_full_row_dedup(self):
        diagnostics.create_events(self.c, deduplicate=True)
        self.assertEqual(self.c.execute('SELECT count(*) FROM events').fetchone()[0], 4)
        self.c.execute('CREATE TABLE result AS '+self.sql)
        summary = diagnostics.dedup_sensitivity(self.c, self.sql)
        self.assertEqual(summary['rj_raw_rows'], 5)
        self.assertEqual(summary['rj_deduplicated_rows'], 4)
        self.assertEqual(summary['changed_event_months'], 1)
        delta = self.c.execute('SELECT duration_candidate_delta FROM dedup_sensitivity WHERE set_id=1').fetchone()[0]
        self.assertAlmostEqual(delta, .1)
        # The canonical table remains deduplicated, and raw input is untouched.
        self.assertEqual(self.c.execute('SELECT count(*) FROM events').fetchone()[0], 4)
        self.assertEqual(self.c.execute('SELECT count(*) FROM interruptions_raw').fetchone()[0], 5)

    def test_multi_uf_inventory_includes_sets_without_events(self):
        self.c.execute("INSERT INTO links VALUES (1,'d','MG'),(1,'e','MG'),(3,'x','RJ'),(3,'y','SP')")
        diagnostics.create_events(self.c, deduplicate=True)
        summary = diagnostics.multi_uf_inventory(self.c)
        self.assertEqual(summary['snapshot_sets'], 2)
        self.assertEqual(summary['sets_with_observed_events'], 1)
        self.assertEqual(summary['observed_event_rows'], 3)
        self.assertEqual(self.c.execute('SELECT observed_event_rows FROM multi_uf_sets WHERE set_id=3').fetchone()[0], 0)


if __name__ == '__main__':
    unittest.main()
