"""Read-only contribution aggregation and local state-map construction."""
import json
from pathlib import Path

import altair as alt
import pandas as pd
import psycopg
import streamlit as st

ROOT = Path(__file__).resolve().parent
STATE_ROWS = '''AL|Alabama|1;AK|Alaska|2;AZ|Arizona|4;AR|Arkansas|5;CA|California|6;CO|Colorado|8;CT|Connecticut|9;DE|Delaware|10;DC|District of Columbia|11;FL|Florida|12;GA|Georgia|13;HI|Hawaii|15;ID|Idaho|16;IL|Illinois|17;IN|Indiana|18;IA|Iowa|19;KS|Kansas|20;KY|Kentucky|21;LA|Louisiana|22;ME|Maine|23;MD|Maryland|24;MA|Massachusetts|25;MI|Michigan|26;MN|Minnesota|27;MS|Mississippi|28;MO|Missouri|29;MT|Montana|30;NE|Nebraska|31;NV|Nevada|32;NH|New Hampshire|33;NJ|New Jersey|34;NM|New Mexico|35;NY|New York|36;NC|North Carolina|37;ND|North Dakota|38;OH|Ohio|39;OK|Oklahoma|40;OR|Oregon|41;PA|Pennsylvania|42;RI|Rhode Island|44;SC|South Carolina|45;SD|South Dakota|46;TN|Tennessee|47;TX|Texas|48;UT|Utah|49;VT|Vermont|50;VA|Virginia|51;WA|Washington|53;WV|West Virginia|54;WI|Wisconsin|55;WY|Wyoming|56'''
STATES = pd.DataFrame([r.split('|') for r in STATE_ROWS.split(';')], columns=['state', 'state_name', 'id'])
STATES['id'] = STATES.id.astype(int)

# PostgreSQL 16+ pg_input_is_valid prevents exceptions on impossible dates.
# All records remain represented, including invalid dates/amounts and non-state locations.
ORIGINS_SQL = '''WITH source AS (
    SELECT state, memo_cd, amndt_ind, transaction_amt,
      CASE WHEN btrim(transaction_dt) ~ '^[0-9]{8}$' THEN
        substr(btrim(transaction_dt),5,4)||'-'||substr(btrim(transaction_dt),1,2)||'-'||substr(btrim(transaction_dt),3,2)
      END AS iso_date
    FROM fec.contributions
    WHERE cycle=%s AND cmte_id=ANY(%s)
), parsed AS (
    SELECT *, CASE WHEN pg_input_is_valid(iso_date,'date') THEN iso_date::date END AS reported_date,
      CASE WHEN length(transaction_amt)<1000 AND btrim(transaction_amt) ~ '^[+-]?[0-9]+([.][0-9]+)?$'
           THEN btrim(transaction_amt)::numeric END AS amount
    FROM source
), classified AS (
    SELECT *, CASE WHEN reported_date IS NULL THEN 'Invalid or missing date'
                   WHEN reported_date BETWEEN %s AND %s THEN 'Included'
                   ELSE 'Outside date range' END AS date_scope
    FROM parsed
)
SELECT state, date_scope, count(*) AS records,
       coalesce(sum(amount),0) AS recorded_amount,
       count(*) FILTER (WHERE amount IS NULL) AS invalid_amount_records,
       count(*) FILTER (WHERE memo_cd='X') AS memo_records,
       count(*) FILTER (WHERE amndt_ind='A') AS amendment_records
FROM classified GROUP BY state,date_scope ORDER BY date_scope,state NULLS FIRST'''

CANDIDATES_SQL = '''SELECT cand_id,cand_name,cand_election_yr,cand_pcc
    FROM fec.candidates WHERE cycle=%s AND cand_office_st=%s AND cand_office IN ('H','S')
    ORDER BY cand_name,cand_id'''


def committee_ids(candidates):
    """Deduplicate recipients, not transaction records or people."""
    return tuple(sorted(candidates.cand_pcc.dropna().unique().tolist()))


def fetch_aggregate(conn, cycle, committees, start, end):
    """Execute the production SQL on a caller-supplied connection (no config access)."""
    with conn.cursor() as cur:
        cur.execute(ORIGINS_SQL, (cycle, list(committees), start, end))
        return pd.DataFrame(cur.fetchall(), columns=[c.name for c in cur.description])


@st.cache_data(ttl=300, show_spinner=False)
def aggregate(cycle, committees, start, end, source_signature):
    """Cache aggregates only; signature changes after source imports, TTL 5 minutes."""
    config = json.loads((ROOT / 'config.analysis.json').read_text())
    with psycopg.connect(**config, options='-c default_transaction_read_only=on -c statement_timeout=180000') as conn:
        return fetch_aggregate(conn, cycle, committees, start, end)


def state_tables(aggregate_rows):
    included = aggregate_rows[aggregate_rows.date_scope == 'Included'].copy()
    mapped = STATES.merge(included, on='state', how='left')
    for col in ('records', 'recorded_amount', 'invalid_amount_records', 'memo_records', 'amendment_records'):
        mapped[col] = mapped[col].fillna(0)
    mapped['records'] = mapped.records.astype(int)
    mapped['recorded_amount'] = mapped.recorded_amount.astype(float)
    unknown = included[~included.state.isin(STATES.state)].copy()
    unknown['state'] = unknown.state.fillna('(missing)')
    return mapped, unknown


def choropleth(mapped, measure, exclude_state=None):
    amount = measure == 'Reported amount'
    field = 'recorded_amount' if amount else 'records'
    title = 'Reported amount ($)' if amount else 'Reported records'
    values = mapped.copy()
    if exclude_state is not None and exclude_state not in set(STATES.state):
        raise ValueError('Unknown excluded state code')
    visible = values.state.ne(exclude_state) if exclude_state else pd.Series(True, index=values.index)
    values['map_status'] = visible.map({True: 'Included in color scale', False: 'Excluded from color scale and map shares'})
    values['map_value'] = values[field].where(visible)
    total = values.loc[visible, field].sum()
    values['mapped_share'] = (values[field] / total).where(visible) if total != 0 else None
    topology = json.loads((ROOT / 'assets/us-states-10m.json').read_text())
    for geometry in topology['objects']['states']['geometries']:
        geometry['id'] = int(geometry['id'])
    # Negative sums stay visible with a diverging scale instead of being clipped.
    scale = alt.Scale(scheme='redblue', domainMid=0) if amount and (values.loc[visible, field] < 0).any() else alt.Scale(scheme='tealblues')
    base = alt.Chart(alt.InlineData(values=topology, format=alt.TopoDataFormat(type='topojson', feature='states'))).mark_geoshape(
        stroke='white', strokeWidth=0.6,
    ).transform_lookup(lookup='id', from_=alt.LookupData(values, 'id', ['state', 'state_name', 'records', 'recorded_amount', 'mapped_share', 'map_value', 'map_status'])).transform_filter('isValid(datum.state_name)').encode(
        tooltip=[alt.Tooltip('state_name:N', title='State'), alt.Tooltip('map_status:N', title='Map status'), alt.Tooltip('records:Q', title='Records', format=','),
                 alt.Tooltip('recorded_amount:Q', title='Reported amount', format='$,.2f'),
                 alt.Tooltip('mapped_share:Q', title='Share of mapped measure', format='.1%')],
    )
    colored = base.transform_filter(alt.datum.state != exclude_state if exclude_state else 'true').encode(
        color=alt.Color('map_value:Q', title=title, scale=scale))
    if exclude_state:
        neutral = base.transform_filter(alt.datum.state == exclude_state).encode(color=alt.value('#d1d5db'))
        return alt.layer(colored, neutral).project(type='albersUsa').properties(height=460)
    return colored.project(type='albersUsa').properties(height=460)
