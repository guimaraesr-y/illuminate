import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from pipelines.aneel import collect,sources


class Response:
    status_code=200
    url='https://example.invalid/final'
    headers={'Content-Length':'3'}
    def __enter__(self):return self
    def __exit__(self,*args):pass
    def raise_for_status(self):pass
    def iter_content(self,size):return iter([b'new'])
    def json(self):return {'success':True,'result':{}}


class RefreshTest(unittest.TestCase):
    def test_failed_refresh_keeps_active_manifest_complete(self):
        selection={alias:[alias] for alias in ('interruptions','indicators','municipalities')}
        packages={alias:{'resources':[{'id':alias,'name':alias,'url':'https://example.invalid/'+alias}]}
                  for alias in selection}
        with tempfile.TemporaryDirectory(dir='.') as d:
            p=Path(d);old={'resources':[{'id':a,'sha256':'old'} for a in selection]}
            sources.save(p/'manifest.json',old)
            def interrupted(resource,root):
                if resource['id']=='indicators':raise RuntimeError('interrupted download')
                return dict(resource,sha256='new')
            with patch.object(collect,'SELECTION',selection),patch.object(collect,'discover',return_value=packages),\
                 patch.object(collect,'download',side_effect=interrupted):
                with self.assertRaisesRegex(RuntimeError,'interrupted'):
                    collect.collect(p,refresh=True)
            self.assertEqual(json.loads((p/'manifest.json').read_text(encoding='utf-8')),old)

    def test_same_url_changed_bytes_preserve_old_raw_and_manifest(self):
        selection={alias:[alias] for alias in ('interruptions','indicators','municipalities')}
        packages={alias:{'resources':[{'id':alias,'name':alias,'url':'https://example.invalid/'+alias}]}
                  for alias in selection}
        with tempfile.TemporaryDirectory(dir='.') as d:
            p=Path(d);(p/'raw').mkdir()
            old=hashlib.sha256(b'old').hexdigest();(p/'raw'/old).write_bytes(b'old')
            sources.save(p/'manifest.json',{'resources':[dict(packages['interruptions']['resources'][0],
                sha256=old,path='raw/'+old,size_bytes=3)]})
            def real_download(resource,root):
                return sources.download(resource,root,get=lambda *a,**k:Response())
            with patch.object(collect,'SELECTION',selection),patch.object(collect,'discover',return_value=packages),\
                 patch.object(collect,'download',side_effect=real_download),patch.object(collect.requests,'get',return_value=Response()):
                collect.collect(p,refresh=True)
            current=json.loads((p/'manifest.json').read_text(encoding='utf-8'))
            archives=list((p/'manifest-history').glob('*.json'))
            self.assertEqual(len(archives),1)
            self.assertEqual(json.loads(archives[0].read_text(encoding='utf-8'))['resources'][0]['sha256'],old)
            self.assertEqual((p/'raw'/old).read_bytes(),b'old')
            self.assertNotEqual(current['resources'][0]['sha256'],old)
            self.assertEqual(current['resources'][0]['url'],'https://example.invalid/interruptions')
