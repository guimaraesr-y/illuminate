"""Official CKAN discovery and immutable, verified resource downloads."""
import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

BASE = 'https://dadosabertos.aneel.gov.br/api/3/action/'
SLUGS = {
    'interruptions': 'interrupcoes-de-energia-eletrica-nas-redes-de-distribuicao',
    'indicators': 'indicadores-coletivos-de-continuidade-dec-e-fec',
    'municipalities': 'indqual-municipio',
    'emergencies': 'ocorrencias-emergenciais-nas-redes-de-distribuicao',
}


def now():
    return datetime.now(timezone.utc).isoformat()


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, default=str) + '\n', encoding='utf-8')


def package_result(payload):
    if payload.get('success') is not True or not isinstance(payload.get('result'), dict):
        raise ValueError(f'CKAN failure: {payload.get("error")}')
    return payload['result']


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def download(resource, root, *, get=requests.get, attempts=3):
    root = Path(root)
    raw = root / 'raw'
    raw.mkdir(parents=True, exist_ok=True)
    part = raw / (resource['id'] + '.part')
    for attempt in range(attempts):
        try:
            with get(resource['url'], stream=True, timeout=(30, 180), headers={'Accept-Encoding': 'identity'}) as r:
                r.raise_for_status()
                if r.status_code != 200:
                    raise ValueError(f'Expected full HTTP 200, got {r.status_code}')
                size = 0
                with part.open('wb') as f:
                    for block in r.iter_content(1024 * 1024):
                        f.write(block)
                        size += len(block)
                expected = r.headers.get('Content-Length')
                if not size or (expected is not None and size != int(expected)):
                    raise ValueError(f'Incomplete download: {size}/{expected}')
                digest = sha256(part)
                target = raw / digest
                if target.exists():
                    if sha256(target) != digest:
                        raise ValueError('Immutable cache corrupted')
                    part.unlink()
                else:
                    part.replace(target)
                return dict(resource, effective_url=r.url, retrieved_at=now(), size_bytes=size,
                            sha256=digest, etag=r.headers.get('ETag'),
                            http_last_modified=r.headers.get('Last-Modified'), path=target.relative_to(root).as_posix())
        except (requests.RequestException, ValueError, OSError):
            part.unlink(missing_ok=True)
            if attempt + 1 == attempts:
                raise
            time.sleep(2 ** attempt)


def discover(root):
    root = Path(root)
    inventory = {}
    for alias, slug in SLUGS.items():
        r = requests.get(BASE + 'package_show', params={'id': slug}, timeout=(30, 90))
        r.raise_for_status()
        payload = r.json()
        package = package_result(payload)
        save(root / 'catalog' / f'{alias}.json', {'retrieved_at': now(), 'url': r.url, 'response': payload})
        inventory[alias] = package
    return inventory


def hydrate(root, manifest, *, get=requests.get):
    """Recreate a locked snapshot. A changed upstream resource is an error, not a new result."""
    root = Path(root)
    for resource in manifest['resources']:
        path = (root / resource['path']).resolve()
        if not path.is_relative_to(root.resolve()):
            raise ValueError('Resource path outside data root')
        if path.exists():
            if path.stat().st_size != resource['size_bytes'] or sha256(path) != resource['sha256']:
                raise ValueError('Local size/hash mismatch')
        else:
            actual = download(resource, root, get=get)
            if actual['sha256'] != resource['sha256'] or actual['size_bytes'] != resource['size_bytes']:
                raise ValueError(f'Upstream resource changed: {resource["url"]}')
            if actual['path'] != resource['path']:
                raise ValueError('Unexpected immutable resource path')
    save(root / 'manifest.json', manifest)
