import tempfile
import unittest
from pathlib import Path
from pipelines.aneel.postgres import bundle


class BundleTest(unittest.TestCase):
    def test_scope_rejects_invalid_period(self):
        with self.assertRaises(ValueError):
            bundle.scope(start_month=12,end_month=1)

    def test_snapshot_identity_ignores_retrieval_time_not_source_hash(self):
        m={'scope':bundle.scope(),'methodology_version':'stage1-v1','analytics_methodology_version':'stage0-v2',
           'sql_sha256':'a'*64,'transformation_sha256':'b'*64,'files':{},
           'resources':[{'id':'one','sha256':'c'*64,'retrieved_at':'2025-01-01'}]}
        first=bundle.identity(m)
        m['resources'][0]['retrieved_at']='2026-01-01'
        self.assertEqual(first,bundle.identity(m))
        m['resources'][0]['sha256']='d'*64
        self.assertNotEqual(first,bundle.identity(m))

    def test_nonfinite_indicator_rejected(self):
        with self.assertRaises(ValueError):
            bundle.number('NaN')
        self.assertIsNone(bundle.number(''))
        self.assertEqual(bundle.number('0'),0)

    def test_bundle_tamper_rejected(self):
        with tempfile.TemporaryDirectory(dir='.') as d:
            p=Path(d)
            bundle.write(p,{'scope':bundle.scope(),'resources':[],
                'methodology_version':'stage1-v1','analytics_methodology_version':'stage0-v2',
                'sql_sha256':'a'*64,'transformation_sha256':'b'*64},
                {'example':(['value'],[[1]])})
            (p/'example.csv').write_text('value\n2\n',encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'hash'):
                bundle.read(p)

    def test_primary_resource_role_changes_identity(self):
        m={'scope':bundle.scope(),'methodology_version':'v1','analytics_methodology_version':'v2',
           'sql_sha256':'a'*64,'transformation_sha256':'b'*64,'files':{},'resources':[],
           'primary_resources':{'indicators':'one'}}
        before=bundle.identity(m)
        m['primary_resources']['indicators']='two'
        self.assertNotEqual(before,bundle.identity(m))

    def test_records_reject_changes_after_initial_manifest_verification(self):
        with tempfile.TemporaryDirectory(dir='.') as d:
            p=Path(d)
            m=bundle.write(p,{'scope':bundle.scope(),'resources':[],
                'methodology_version':'v1','analytics_methodology_version':'v2',
                'sql_sha256':'a'*64,'transformation_sha256':'b'*64}, {'example':(['value'],[[1]])})
            bundle.read(p)
            (p/'example.csv').write_text('value\n2\n',encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'hash'):
                list(bundle.records(p,m,'example'))
