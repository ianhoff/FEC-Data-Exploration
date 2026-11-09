"""Live reconciliation and rollback-only foreign-key checks for fec_model."""
import json
from pathlib import Path

import psycopg
from psycopg import sql

ROOT = Path(__file__).resolve().parent


def main():
    with psycopg.connect(**json.loads((ROOT / 'config.analysis.json').read_text()), options='-c statement_timeout=30000') as conn:
        try:
            with conn.cursor() as cur:
                cur.execute('SELECT pg_advisory_xact_lock(721039, 1)')
                cur.execute('SELECT cycle FROM fec_model.builds ORDER BY cycle')
                cycles = [r[0] for r in cur.fetchall()]
                assert cycles, 'No built cycles'
                for cycle in cycles:
                    for table in ('candidates', 'committees'):
                        cur.execute(sql.SQL('''SELECT count(*) FROM (
                            (SELECT * FROM fec.{} WHERE cycle=%s EXCEPT SELECT * FROM fec_model.{} WHERE cycle=%s)
                            UNION ALL
                            (SELECT * FROM fec_model.{} WHERE cycle=%s EXCEPT SELECT * FROM fec.{} WHERE cycle=%s)
                            ) differences''').format(*map(sql.Identifier, [table]*4)), (cycle,)*4)
                        assert cur.fetchone()[0] == 0, f'{table} reconciliation failed'
                    cur.execute('''WITH represented AS (
                        SELECT cycle,source_line FROM fec_model.links WHERE cycle=%s
                        UNION ALL SELECT cycle,source_line FROM fec_model.unresolved_links WHERE cycle=%s)
                        SELECT (SELECT count(*) FROM represented),
                        (SELECT count(DISTINCT (cycle,source_line)) FROM represented),
                        (SELECT count(*) FROM fec.links WHERE cycle=%s)''', (cycle,)*3)
                    total, unique, raw = cur.fetchone()
                    assert total == unique == raw, 'Link partition/count failed'
                cur.execute("SELECT count(*) FROM pg_constraint WHERE connamespace='fec_model'::regnamespace AND contype='f' AND convalidated")
                assert cur.fetchone()[0] == 6, 'Expected six validated foreign keys'
                cycle = cycles[0]
                cur.execute('SELECT cand_id FROM fec_model.candidates WHERE cycle=%s LIMIT 1', (cycle,))
                candidate = cur.fetchone()[0]
                cur.execute('SELECT cmte_id FROM fec_model.committees WHERE cycle=%s LIMIT 1', (cycle,))
                committee = cur.fetchone()[0]
                for cid, mid, expected in [('__invalid_test_candidate__', committee, 'links_candidate_fk'),
                                           (candidate, '__invalid_test_committee__', 'links_committee_fk')]:
                    try:
                        with conn.transaction():
                            cur.execute('INSERT INTO fec_model.links(cycle,source_line,cand_id,cmte_id) VALUES (%s,-1,%s,%s)', (cycle,cid,mid))
                    except psycopg.errors.ForeignKeyViolation as error:
                        assert error.diag.constraint_name == expected
                    else:
                        raise AssertionError('Invalid reference was accepted')
                print('PASS: master reconciliation, complete link partition, six validated foreign keys, and invalid-reference rejection.')
        finally:
            conn.rollback()


if __name__ == '__main__':
    main()
