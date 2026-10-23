import tempfile
import unittest
from pathlib import Path
from pipelines.aneel import sources


class Response:
    status_code = 200
    url = 'https://example.org/final'
    headers = {'Content-Length': '3'}
    def raise_for_status(self): pass
    def iter_content(self, chunk_size): return iter([b'abc'])
    def __enter__(self): return self
    def __exit__(self, *args): pass


class SourcesTest(unittest.TestCase):
    def test_rejects_ckan_success_false(self):
        with self.assertRaises(ValueError):
            sources.package_result({'success': False, 'error': {'message': 'bad'}})

    def test_download_records_hash_and_effective_url(self):
        with tempfile.TemporaryDirectory(dir=".") as d:
            m = sources.download({'id': 'one', 'url': 'https://example.org/a'}, Path(d), get=lambda *a, **k: Response())
            self.assertEqual(m['sha256'], 'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad')
            self.assertEqual(m['effective_url'], Response.url)
            self.assertEqual((Path(d) / m['path']).read_bytes(), b'abc')

    def test_truncated_download_never_published(self):
        response = Response()
        response.headers = {'Content-Length': '4'}
        with tempfile.TemporaryDirectory(dir=".") as d:
            with self.assertRaises(ValueError):
                sources.download({'id': 'one', 'url': 'https://example.org/a'}, Path(d), get=lambda *a, **k: response, attempts=1)
            self.assertEqual(list(Path(d).glob('raw/*')), [])

    def test_partial_response_rejected(self):
        response = Response()
        response.status_code = 206
        with tempfile.TemporaryDirectory(dir=".") as d:
            with self.assertRaises(ValueError):
                sources.download({'id': 'one', 'url': 'https://example.org/a'}, Path(d), get=lambda *a, **k: response, attempts=1)

    def test_locked_replay_rejects_changed_source(self):
        with tempfile.TemporaryDirectory(dir='.') as d:
            manifest = {'resources': [{'id':'one','url':'https://example.org/a','path':'raw/old','size_bytes':3,'sha256':'old'}]}
            with self.assertRaisesRegex(ValueError, 'changed'):
                sources.hydrate(Path(d), manifest, get=lambda *a, **k: Response())


if __name__ == '__main__': unittest.main()
