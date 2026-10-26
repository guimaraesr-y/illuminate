"""Collect the fixed stage-0 resource selection; no schema assumptions."""
import argparse
import json
import shutil
from pathlib import Path
from .sources import discover, download, save, BASE, now
import requests

SELECTION = {
    'interruptions': ['691de320-cb3d-471b-b9ec-8c1b86af8c83', '101e4650-6a02-4f1f-8034-4c267b1ea462'],
    'indicators': ['d7f70fb1-725c-4748-afeb-65c6a78df550', '5d91171a-eb4e-4f66-8418-2833567123ae', '17fc99b7-e707-4ec4-9553-a43d7a41f7a6'],
    'municipalities': ['3f841488-80a8-42f2-a6ca-e0c593b228de', 'dc85ecd2-4aca-4b1b-a69e-f1ec1b82d811'],
}


def collect(root, *, refresh=False):
    root = Path(root)
    manifest_path = root / 'manifest.json'
    if refresh and manifest_path.exists():
        from .sources import sha256
        archive=root/'manifest-history'/(sha256(manifest_path)+'.json')
        archive.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(manifest_path,archive)
    packages = discover(root)
    manifest = json.loads(manifest_path.read_text(encoding='utf-8')) if manifest_path.exists() else {'resources': []}
    if refresh:
        manifest={'resources': []}
    for alias, ids in SELECTION.items():
        package = packages[alias]
        for rid in ids:
            resource = next(r for r in package['resources'] if r['id'] == rid)
            cached = next((r for r in manifest['resources'] if r['id'] == rid), None)
            if cached:
                from .sources import sha256
                if sha256(root / cached['path']) != cached['sha256']:
                    raise ValueError(f'Cache hash mismatch: {rid}')
                continue
            print('Downloading', alias, resource['name'], flush=True)
            m = download(dict(resource, dataset=alias, license_id=package.get('license_id'),
                              license_title=package.get('license_title'), license_url=package.get('license_url')), root)
            manifest['resources'].append(m)
    # A concrete row-API test, including resources marked inactive, without claiming all are supported.
    probes = []
    for alias, rid in [('interruptions', SELECTION['interruptions'][0]), ('municipalities', SELECTION['municipalities'][0]),
                       ('indicators', '4493985c-baea-429c-9df5-3030422c71d7')]:
        r = requests.get(BASE + 'datastore_search', params={'resource_id': rid, 'limit': 1}, timeout=(30, 90))
        try: body = r.json()
        except ValueError: body = {'text': r.text[:2000]}
        probes.append({'dataset': alias, 'url': r.url, 'status': r.status_code, 'retrieved_at': now(), 'response': body})
    save(root / 'catalog' / 'record-api-probes.json', probes)
    pending=root/'manifest.next.json'
    save(pending,manifest)
    pending.replace(manifest_path)


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--root', type=Path, default=Path('data/aneel'))
    p.add_argument('--manifest', type=Path, help='Replay a saved manifest; reject upstream hash changes')
    p.add_argument('--refresh',action='store_true',help='Archive the old manifest and verify a new download, retaining raw history')
    a = p.parse_args()
    if a.manifest and a.refresh:
        p.error('--manifest and --refresh are mutually exclusive')
    if a.manifest:
        from .sources import hydrate
        hydrate(a.root, json.loads(a.manifest.read_text(encoding='utf-8')))
    else:
        collect(a.root,refresh=a.refresh)
