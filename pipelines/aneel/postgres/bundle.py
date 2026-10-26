"""Content-addressed intermediate bundles; no absolute source paths or secrets."""
import csv
import hashlib
import json
import math
import io
from pathlib import Path
from ..sources import save, sha256


def scope(*, start_month=1,end_month=12,agent=None,set_id=None):
    if not 1<=start_month<=end_month<=12:
        raise ValueError('Invalid month interval')
    return dict(year=2025,start_month=start_month,end_month=end_month,agent=agent,set_id=set_id)


def number(value):
    if value is None or value=='':
        return None
    n=float(value)
    if not math.isfinite(n) or n<0:
        raise ValueError('Nonfinite or negative analytical value')
    return n


def identity(metadata):
    semantic={k:metadata[k] for k in ('scope','methodology_version','analytics_methodology_version',
                                    'sql_sha256','transformation_sha256','files')}
    semantic['resources']=sorted((r['id'],r['sha256']) for r in metadata['resources'])
    semantic['primary_resources']=metadata.get('primary_resources',{})
    return hashlib.sha256(json.dumps(semantic,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def write(root,metadata,tables):
    root=Path(root);root.mkdir(parents=True,exist_ok=True)
    metadata=dict(metadata,files={})
    for name,(columns,data) in tables.items():
        path=root/(name+'.csv')
        with path.open('w',encoding='utf-8',newline='') as f:
            w=csv.writer(f);w.writerow(columns);w.writerows(data)
        metadata['files'][name]={'path':path.name,'sha256':sha256(path)}
    metadata['snapshot_id']=identity(metadata)
    save(root/'bundle.json',metadata)
    return metadata


def read(root):
    root=Path(root).resolve()
    m=json.loads((root/'bundle.json').read_text(encoding='utf-8'))
    if identity(m)!=m['snapshot_id']:
        raise ValueError('Bundle identity/hash mismatch')
    for entry in m['files'].values():
        path=(root/entry['path']).resolve()
        if not path.is_relative_to(root) or sha256(path)!=entry['sha256']:
            raise ValueError('Bundle file hash mismatch')
    return m


def records(root,metadata,name):
    entry=metadata['files'][name]
    # Verify the very bytes consumed by COPY, even if another process prepares this path.
    raw=(Path(root)/entry['path']).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=entry['sha256']:
        raise ValueError('Bundle file hash changed before consumption')
    for row in csv.DictReader(io.StringIO(raw.decode('utf-8'),newline='')):
        yield {k:(v if v!='' else None) for k,v in row.items()}
