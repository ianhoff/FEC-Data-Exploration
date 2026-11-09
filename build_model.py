"""Apply versioned model migrations and atomically refresh selected archive cycles."""
import argparse
import hashlib
import json
from pathlib import Path

import psycopg
from psycopg import sql

ROOT = Path(__file__).resolve().parent
MASTERS = [('candidates', 'cand_id'), ('committees', 'cmte_id')]


def refresh(cur, cycle):
    cur.execute('SELECT dataset, row_count FROM fec.imports WHERE cycle=%s AND dataset IN (\'candidates\',\'committees\',\'links\')', (cycle,))
    tracked = dict(cur.fetchall())
    if set(tracked) != {'candidates', 'committees', 'links'}:
        raise ValueError(f'Cycle {cycle}: import all three small datasets first.')
    for table in ('candidates', 'committees', 'links'):
        cur.execute(sql.SQL('SELECT count(*) FROM fec.{} WHERE cycle=%s').format(sql.Identifier(table)), (cycle,))
        if cur.fetchone()[0] != tracked[table] or not tracked[table]:
            raise ValueError(f'Cycle {cycle}: source/tracking counts disagree or source is empty.')
    for table, key in MASTERS:
        cur.execute(sql.SQL('SELECT 1 FROM fec.{} WHERE cycle=%s GROUP BY {} HAVING {} IS NULL OR count(*)>1 LIMIT 1').format(sql.Identifier(table), sql.Identifier(key), sql.Identifier(key)), (cycle,))
        if cur.fetchone():
            raise ValueError(f'Cycle {cycle}: missing or duplicate master IDs; no automatic deduplication.')

    # Delete children first; no CASCADE or disabling of constraints.
    for table in ('links', 'unresolved_links', 'principal_committees', 'committee_candidates', 'candidates', 'committees'):
        cur.execute(sql.SQL('DELETE FROM fec_model.{} WHERE cycle=%s').format(sql.Identifier(table)), (cycle,))
    for table, _ in MASTERS:
        # Explicit column order protects against later raw schema changes.
        from ingest_fec import SPECS
        fields = sql.SQL(', ').join(map(sql.Identifier, ['cycle', 'source_line'] + SPECS[table][2]))
        cur.execute(sql.SQL('INSERT INTO fec_model.{} ({}) SELECT {} FROM fec.{} WHERE cycle=%s').format(sql.Identifier(table), fields, fields, sql.Identifier(table)), (cycle,))
    cur.execute('''INSERT INTO fec_model.links SELECT l.* FROM fec.links l
        WHERE l.cycle=%s AND EXISTS (SELECT 1 FROM fec_model.candidates c WHERE c.cycle=l.cycle AND c.cand_id=l.cand_id)
        AND EXISTS (SELECT 1 FROM fec_model.committees m WHERE m.cycle=l.cycle AND m.cmte_id=l.cmte_id)''', (cycle,))
    resolved = cur.rowcount
    cur.execute('''INSERT INTO fec_model.unresolved_links
        SELECT l.*,
          NOT EXISTS (SELECT 1 FROM fec_model.candidates c WHERE c.cycle=l.cycle AND c.cand_id=l.cand_id),
          NOT EXISTS (SELECT 1 FROM fec_model.committees m WHERE m.cycle=l.cycle AND m.cmte_id=l.cmte_id)
        FROM fec.links l WHERE l.cycle=%s AND (
          NOT EXISTS (SELECT 1 FROM fec_model.candidates c WHERE c.cycle=l.cycle AND c.cand_id=l.cand_id)
          OR NOT EXISTS (SELECT 1 FROM fec_model.committees m WHERE m.cycle=l.cycle AND m.cmte_id=l.cmte_id))''', (cycle,))
    unresolved = cur.rowcount
    if resolved + unresolved != tracked['links']:
        raise ValueError('Link reconciliation failed.')
    cur.execute('''INSERT INTO fec_model.principal_committees
        SELECT c.cycle,c.cand_id,c.cand_pcc FROM fec_model.candidates c
        JOIN fec_model.committees m ON m.cycle=c.cycle AND m.cmte_id=c.cand_pcc WHERE c.cycle=%s''', (cycle,))
    cur.execute('''INSERT INTO fec_model.committee_candidates
        SELECT m.cycle,m.cmte_id,m.cand_id FROM fec_model.committees m
        JOIN fec_model.candidates c ON c.cycle=m.cycle AND c.cand_id=m.cand_id WHERE m.cycle=%s''', (cycle,))
    cur.execute('''INSERT INTO fec_model.builds
        (cycle,source_imports,candidate_count,committee_count,resolved_link_count,unresolved_link_count)
        SELECT %s,jsonb_agg(to_jsonb(i) ORDER BY dataset),%s,%s,%s,%s
        FROM fec.imports i WHERE cycle=%s AND dataset IN ('candidates','committees','links')
        ON CONFLICT (cycle) DO UPDATE SET built_at=now(),source_imports=excluded.source_imports,
        candidate_count=excluded.candidate_count,committee_count=excluded.committee_count,
        resolved_link_count=excluded.resolved_link_count,unresolved_link_count=excluded.unresolved_link_count''',
        (cycle, tracked['candidates'], tracked['committees'], resolved, unresolved, cycle))
    return f'{cycle}: {resolved:,} validated links; {unresolved:,} unresolved links preserved.'


def build(conn, cycles=None, migration_dir=None):
    """Build using an explicit connection; callers own authentication and database selection."""
    migration_dir = Path(migration_dir) if migration_dir is not None else ROOT / 'migrations'
    messages = []
    with conn.transaction():
        with conn.cursor() as cur:
            # Same lock as importer: take before snapshots/reads under READ COMMITTED.
            cur.execute('SELECT pg_advisory_xact_lock(721039, 1)')
            cur.execute('''CREATE TABLE IF NOT EXISTS fec_model.schema_migrations (
                version text PRIMARY KEY, sha256 text NOT NULL, applied_at timestamptz NOT NULL DEFAULT now())''')
            for path in sorted(migration_dir.glob('*.sql')):
                content = path.read_bytes()
                checksum = hashlib.sha256(content).hexdigest()
                cur.execute('SELECT sha256 FROM fec_model.schema_migrations WHERE version=%s', (path.name,))
                previous = cur.fetchone()
                if previous:
                    if previous[0] != checksum:
                        raise ValueError('An applied migration changed; create a new migration instead.')
                else:
                    cur.execute(content.decode('utf-8'))
                    cur.execute('INSERT INTO fec_model.schema_migrations(version,sha256) VALUES (%s,%s)', (path.name, checksum))
            cur.execute("SELECT DISTINCT cycle FROM fec.imports WHERE dataset IN ('candidates','committees','links') ORDER BY cycle")
            cycles = sorted(set(cycles or [row[0] for row in cur.fetchall()]))
            if not cycles:
                raise ValueError('No imported cycles found.')
            for cycle in cycles:
                messages.append(refresh(cur, cycle))
    return messages


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cycle', type=int, nargs='+', help='Defaults to all imported small-dataset cycles.')
    args = parser.parse_args()
    config = json.loads((ROOT / 'config.analysis.json').read_text())
    messages = []
    with psycopg.connect(**config, options='-c statement_timeout=120000 -c lock_timeout=15000') as conn:
        messages = build(conn, args.cycle)
    for message in messages:
        print(message)
    print('Model committed. Raw tables and contribution records were not modified.')


if __name__ == '__main__':
    try:
        main()
    except (psycopg.Error, OSError, ValueError) as error:
        print(f'Model build failed ({type(error).__name__}); transaction rolled back.')
        if isinstance(error, ValueError):
            print(str(error))
        raise SystemExit(1)
