"""uv run python -m pipelines.aneel.postgres --help"""
import argparse
import json
import os
from pathlib import Path
from ..collect import collect
from ..sources import hydrate
from . import bundle,database,extract,store,read


def main():
    p=argparse.ArgumentParser(description='Verified RJ snapshots -> atomic PostgreSQL publication')
    p.add_argument('--dsn',default=os.environ.get('DATABASE_URL'),help='Defaults to DATABASE_URL')
    p.add_argument('--schema',default='illuminate')
    commands=p.add_subparsers(dest='command',required=True)
    commands.add_parser('migrate')
    load=commands.add_parser('load');load.add_argument('--bundle',type=Path,required=True)
    compare=commands.add_parser('compare')
    compare.add_argument('--bundle',type=Path,required=True)
    compare.add_argument('--reference',type=Path,default=Path('reports/stage0/rj-2025.csv'))
    compare.add_argument('--output',type=Path,default=Path('reports/stage1/reconciliation.json'))
    query=commands.add_parser('series');query.add_argument('--agent',required=True)
    query.add_argument('--set-id',type=int);query.add_argument('--annual',action='store_true')
    for name in ('prepare','ingest'):
        sub=commands.add_parser(name)
        sub.add_argument('--root',type=Path,default=Path('data/aneel'))
        sub.add_argument('--output',type=Path,default=Path('data/stage1-bundle'))
        sub.add_argument('--start-month',type=int,default=1)
        sub.add_argument('--end-month',type=int,default=12)
        sub.add_argument('--agent');sub.add_argument('--set-id',type=int)
        if name=='ingest':
            g=sub.add_mutually_exclusive_group()
            g.add_argument('--manifest',type=Path)
            g.add_argument('--refresh',action='store_true')
    a=p.parse_args()
    if a.command!='prepare' and not a.dsn:
        p.error('Set DATABASE_URL or provide --dsn')
    if a.command=='migrate':
        database.migrate(a.dsn,a.schema);print('Migrations applied');return
    if a.command=='series':
        print(json.dumps(read.series(a.dsn,a.schema,agent=a.agent,set_id=a.set_id,annual=a.annual),default=str));return
    if a.command=='compare':
        report=read.reconcile(a.bundle,a.dsn,a.reference,schema=a.schema,output=a.output)
        print(json.dumps(report,default=str));return
    if a.command in ('prepare','ingest'):
        if a.command=='ingest':
            if a.manifest:
                hydrate(a.root,json.loads(a.manifest.read_text(encoding='utf-8')))
            elif a.refresh or not (a.root/'manifest.json').exists():
                collect(a.root,refresh=a.refresh)
        selection=bundle.scope(start_month=a.start_month,end_month=a.end_month,agent=a.agent,set_id=a.set_id)
        m=extract.prepare(a.root,a.output,selection)
        if a.command=='prepare':
            print(json.dumps({'snapshot_id':m['snapshot_id'],'bundle':str(a.output)}));return
        a.bundle=a.output
    database.migrate(a.dsn,a.schema)
    print(json.dumps(store.ingest(a.bundle,a.dsn,a.schema)))


if __name__=='__main__':
    main()
