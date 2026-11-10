"""Live Streamlit page."""
import altair as alt
import streamlit as st
from fec_explorer.database import query
from fec_explorer.ui import show_sql

def overview(cycle):
    st.header('Your ingestion at a glance')
    st.write('Inspect source records, understand relationships, and trace the SQL behind each result.')
    statement = '''SELECT 'candidates' AS dataset, count(*) AS records FROM fec.candidates WHERE cycle=%s
        UNION ALL SELECT 'committees', count(*) FROM fec.committees WHERE cycle=%s
        UNION ALL SELECT 'links', count(*) FROM fec.links WHERE cycle=%s'''
    counts = query(statement, (cycle, cycle, cycle))
    for column, row in zip(st.columns(3), counts.itertuples()):
        column.metric(row.dataset.title(), f'{row.records:,}')
    show_sql(statement, (cycle, cycle, cycle))
    st.subheader('Source snapshots')
    st.dataframe(query('SELECT dataset, cycle, row_count, imported_at, source_url FROM fec.imports WHERE cycle=%s ORDER BY dataset', (cycle,)), hide_index=True, width='stretch')
    st.info('Use Contribution origins to explore reported records to Maryland principal campaign committees. The app never downloads source files.')
    st.subheader('Candidate office distribution')
    offices = query('SELECT coalesce(cand_office, \'Missing\') AS office, count(*) AS records FROM fec.candidates WHERE cycle=%s GROUP BY cand_office ORDER BY records DESC', (cycle,))
    offices['office_label'] = offices['office'].replace({'H': 'House', 'S': 'Senate', 'P': 'President'})
    chart = alt.Chart(offices).mark_bar(color='#087f8c').encode(
        x=alt.X('office_label:N', title='Office', sort=None,
                axis=alt.Axis(labelAngle=0)),
        y=alt.Y('records:Q', title='Candidate records'),
        tooltip=[alt.Tooltip('office_label:N', title='Office'),
                 alt.Tooltip('records:Q', title='Records', format=',')],
    )
    st.altair_chart(chart, width='stretch')
    st.caption('H = House · S = Senate · P = President. Archive cycle and candidate election year are different fields.')
