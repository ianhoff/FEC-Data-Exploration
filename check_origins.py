"""Live UI checks and SQL fixtures for contribution-map edge cases; read-only."""
import json
from pathlib import Path
from datetime import date

import psycopg
from streamlit.testing.v1 import AppTest

from origins import ORIGINS_SQL, state_tables, choropleth
import pandas as pd

ROOT = Path(__file__).resolve().parent
rows = []
for state, dt, amt in [('MD','01012024','10.25'),('CA','02292024','-2.25'),
                       (None,'01022024','bad'),('PR','01032024','3'),
                       ('MD','02302024','1'),('MD','01012022','1'),('MD',None,'1')]:
    rows.append(dict(cycle=2024,cmte_id='C_TEST',state=state,transaction_dt=dt,
                     transaction_amt=amt,memo_cd='X',amndt_ind='A'))
fixture_source = '''jsonb_to_recordset(%s::jsonb) AS contributions (
    cycle integer,cmte_id text,state text,transaction_dt text,transaction_amt text,memo_cd text,amndt_ind text)'''
with psycopg.connect(**json.loads((ROOT/'config.analysis.json').read_text()), options='-c default_transaction_read_only=on') as conn:
    with conn.cursor() as cur:
        cur.execute(ORIGINS_SQL.replace('fec.contributions',fixture_source),
                    (json.dumps(rows),2024,['C_TEST'],date(2023,1,1),date(2024,12,31)))
        frame = pd.DataFrame(cur.fetchall(),columns=[c.name for c in cur.description])
assert frame.records.sum() == 7
assert frame.loc[frame.date_scope=='Included','records'].sum() == 4
assert frame.loc[frame.date_scope=='Invalid or missing date','records'].sum() == 2
mapped, unknown = state_tables(frame)
assert len(mapped) == 51 and unknown.records.sum() == 2
assert mapped.loc[mapped.state=='CA','recorded_amount'].iloc[0] == -2.25
assert unknown.invalid_amount_records.sum() == 1
assert frame.memo_records.sum() == 7 and frame.amendment_records.sum() == 7
for measure in ('Reported amount','Record count'):
    spec = choropleth(mapped,measure).to_dict()
    assert spec['projection']['type'] == 'albersUsa'
    assert spec['data']['format']['type'] == 'topojson'
    geometry_data = spec['data'].get('values') or spec['datasets'][spec['data']['name']]
    assert all(isinstance(g['id'],int) for g in geometry_data['objects']['states']['geometries'])

app = AppTest.from_file(str(ROOT/'app.py'),default_timeout=210).run()
app.sidebar.radio[0].set_value('Contribution origins').run()
assert not app.exception and not app.error and not app.warning
assert any(m.label=='Reported records' and int(m.value.replace(',',''))>0 for m in app.metric)
next(s for s in app.selectbox if s.label=='Measure').set_value('Record count').run()
assert not app.exception and not app.error
next(s for s in app.selectbox if s.label=='Campaign state').set_value('DE').run()
assert not app.exception and not app.error and not app.warning
assert app.toggle[0].label == 'Exclude Delaware from map scale'
recipients = app.dataframe[-1].value
with psycopg.connect(**json.loads((ROOT/'config.analysis.json').read_text()), options='-c default_transaction_read_only=on') as conn:
    with conn.cursor() as cur:
        cur.execute("SELECT cand_id FROM fec.candidates WHERE cycle=2024 AND cand_office_st='DE' AND cand_office IN ('H','S') AND cand_election_yr='2024'")
        expected = {r[0] for r in cur.fetchall()}
assert set(recipients.cand_id) == expected
assert app.selectbox[[s.label for s in app.selectbox].index('Campaign')].value == 'All selected Delaware campaigns'
app.toggle[0].set_value(False).run()
assert not app.exception and not app.error
app.sidebar.selectbox[0].set_value(2022).run()
assert any('has not been imported' in i.value for i in app.info)
assert not app.exception and not app.error
print('PASS: SQL edge cases, live map, measure/state switches, Delaware recipients, home-state toggle, and missing-cycle state.')
