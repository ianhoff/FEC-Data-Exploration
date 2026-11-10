"""Database-free portfolio demo. Every displayed contribution value is synthetic."""
import json
from pathlib import Path

import pandas as pd
import streamlit as st

from fec_explorer.origins import choropleth, state_tables

ROOT = Path(__file__).resolve().parent


def main():
    st.set_page_config(page_title='Campaign Finance Explorer | Demo', page_icon='🗺️', layout='wide')
    st.title('Campaign Finance Explorer')
    st.caption('Python ingestion · PostgreSQL modeling · SQL analysis · Interactive geography')
    st.warning('SYNTHETIC DEMO — invented campaign and contribution aggregates, not FEC findings. No database connection or source download is used.')
    page = st.sidebar.radio('Demo', ['Contribution origins', 'Model tour'])
    st.sidebar.caption('The live application adds candidate profiles, national raw-table exploration, and quality checks. Maryland is its default starting point.')
    if page == 'Model tour':
        st.header('From raw records to enforced relationships')
        st.image(str(ROOT / 'docs/images/relationship-model.svg'))
        st.write('The raw fec schema preserves source records, including unmatched references. A separate fec_model snapshot accepts validated relationships and preserves unresolved links for inspection.')
        st.dataframe(pd.DataFrame([
            {'Layer':'Raw fec','Keys':'cycle + source_line','Relationships':'Logical references, no foreign keys'},
            {'Layer':'Validated fec_model','Keys':'cycle + candidate/committee ID','Relationships':'Six enforced composite foreign keys'},
            {'Layer':'Quality objects','Keys':'Source lineage','Relationships':'Unresolved records remain visible'},
        ]),hide_index=True,width='stretch')
        st.info('The map aggregates raw reported records. An enforced relationship does not establish financial attribution or official fundraising totals.')
        return
    payload = json.loads((ROOT / 'demo/origins.json').read_text(encoding='utf-8'))
    names = {'MD':'Maryland','DE':'Delaware','CA':'California'}
    state = st.sidebar.selectbox('Campaign state',list(names),format_func=names.get)
    measure = st.sidebar.selectbox('Measure',['Reported amount','Record count'])
    exclude = st.sidebar.toggle('Exclude campaign state from scale',value=True)
    st.header(f'Contribution origins / {names[state]}')
    st.caption('Illustrative 2024 archive · 2023–2024 dates · Synthetic principal-committee aggregates. The demo offers three campaign states; the live app supports all 50 states plus DC.')
    rows = pd.DataFrame([r for r in payload['groups'] if r['campaign_state']==state]).drop(columns='campaign_state')
    mapped, unknown = state_tables(rows)
    included = rows[rows.date_scope=='Included']
    a,b,c = st.columns([1,1.7,1])
    a.metric('Synthetic records',f'{int(included.records.sum()):,}')
    b.metric('Synthetic recorded sum',f'${included.recorded_amount.sum():,.2f}')
    c.metric('Unmapped records',f'{int(unknown.records.sum()):,}')
    if exclude:
        st.caption(f'{names[state]} is gray and excluded from the color scale and map shares; totals and exports still include it.')
    st.altair_chart(choropleth(mapped,measure,exclude_state=state if exclude else None),width='stretch')
    st.caption('Hover for totals and inclusion status. State/DC geography is real; every contribution value here is invented. Reported-record sums in the live app are exploratory, not official fundraising totals.')
    with st.expander('State totals and CSV',expanded=False):
        table=mapped.drop(columns=['id','date_scope'],errors='ignore')
        st.dataframe(table,hide_index=True,width='stretch')
        st.download_button('Download synthetic state totals',table.to_csv(index=False).encode('utf-8-sig'),f'synthetic_{state}_origins.csv','text/csv')
    with st.expander('Unmapped locations'):
        st.dataframe(unknown,hide_index=True,width='stretch')


main()
