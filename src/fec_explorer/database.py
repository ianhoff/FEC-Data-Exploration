"""Live app database queries."""
import json
import pandas as pd
import psycopg
from fec_explorer.paths import PROJECT_ROOT as ROOT

def query(statement, params=()):
    config = json.loads((ROOT / 'config.analysis.json').read_text(encoding='utf-8'))
    with psycopg.connect(**config, options='-c default_transaction_read_only=on -c statement_timeout=15000') as conn:
        with conn.cursor() as cur:
            cur.execute(statement, params)
            return pd.DataFrame(cur.fetchall(), columns=[c.name for c in cur.description])
