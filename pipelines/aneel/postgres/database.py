"""Small transactional SQL migration runner; no ORM or implicit schema changes."""
import hashlib
import re
from pathlib import Path
import psycopg
from psycopg import sql

MIGRATIONS = Path(__file__).parent/'migrations'


def connect(dsn, schema='illuminate'):
    if not re.fullmatch(r'[a-z_][a-z0-9_]*', schema):
        raise ValueError('Invalid schema identifier')
    c = psycopg.connect(dsn, autocommit=True)
    c.execute(sql.SQL('SET search_path TO {}').format(sql.Identifier(schema)))
    return c


def migrate(dsn, schema='illuminate'):
    with connect(dsn, schema) as c, c.transaction():
        c.execute('SELECT pg_advisory_xact_lock(hashtext(%s))', ['illuminate:migrate:'+schema])
        c.execute(sql.SQL('CREATE SCHEMA IF NOT EXISTS {}').format(sql.Identifier(schema)))
        c.execute('''CREATE TABLE IF NOT EXISTS schema_migration (
            version text PRIMARY KEY, sha256 text NOT NULL, applied_at timestamptz NOT NULL DEFAULT now())''')
        for path in sorted(MIGRATIONS.glob('*.sql')):
            text = path.read_text(encoding='utf-8')
            digest = hashlib.sha256(text.encode()).hexdigest()
            existing = c.execute('SELECT sha256 FROM schema_migration WHERE version=%s', [path.name]).fetchone()
            if existing:
                if existing[0] != digest:
                    raise ValueError('Previously applied migration checksum changed: '+path.name)
            else:
                c.execute(text)
                c.execute('INSERT INTO schema_migration(version,sha256) VALUES(%s,%s)', [path.name,digest])
