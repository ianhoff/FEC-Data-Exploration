"""Export read-only PostgreSQL catalog metadata; never export application rows."""
import json
from pathlib import Path
from datetime import datetime, timezone

import psycopg

ROOT = Path(__file__).resolve().parent


def main():
    config = json.loads((ROOT / 'config.analysis.json').read_text(encoding='utf-8'))
    statements = {
        'columns': '''SELECT table_schema, table_name, column_name, ordinal_position,
            data_type, is_nullable, column_default
            FROM information_schema.columns WHERE table_schema IN ('fec','fec_model')
            ORDER BY table_schema, table_name, ordinal_position''',
        'constraints': '''SELECT n.nspname AS schema_name, t.relname AS table_name,
            c.conname AS constraint_name, c.contype AS constraint_type,
            pg_get_constraintdef(c.oid) AS definition
            FROM pg_constraint c JOIN pg_class t ON t.oid=c.conrelid
            JOIN pg_namespace n ON n.oid=t.relnamespace
            WHERE n.nspname IN ('fec','fec_model')
            ORDER BY n.nspname,t.relname,c.conname''',
        'indexes': '''SELECT schemaname, tablename, indexname, indexdef FROM pg_indexes
            WHERE schemaname IN ('fec','fec_model') ORDER BY schemaname,tablename,indexname''',
    }
    result = {'generated_at_utc': datetime.now(timezone.utc).isoformat(),
              'scope': ['fec', 'fec_model'], 'contains_table_rows': False}
    with psycopg.connect(**config, options='-c default_transaction_read_only=on -c statement_timeout=15000') as conn:
        with conn.cursor() as cur:
            cur.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ')
            for label, statement in statements.items():
                cur.execute(statement)
                fields = [column.name for column in cur.description]
                result[label] = [dict(zip(fields, row)) for row in cur.fetchall()]
    target = ROOT / 'docs' / 'schema.snapshot.json'
    target.parent.mkdir(exist_ok=True)
    target.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print('Exported schema metadata to docs/schema.snapshot.json (no table records).')


if __name__ == '__main__':
    try:
        main()
    except (psycopg.Error, OSError, ValueError):
        print('Schema export failed. Check the database and non-secret analysis config; no credentials displayed.')
        raise SystemExit(1)
