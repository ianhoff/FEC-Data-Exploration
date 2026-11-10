"""Live Streamlit page."""
import math
import streamlit as st
from fec_explorer.database import query
from fec_explorer.ui import show_sql

def explore(cycle):
    st.header('Explore raw tables')
    table = st.selectbox('Dataset', ['candidates', 'committees', 'links'])
    names = {'candidates': ('cand_name', 'cand_id'), 'committees': ('cmte_nm', 'cmte_id'), 'links': ('cand_id', 'cmte_id')}
    fields = names[table]
    search = st.text_input('Search name or ID' if table != 'links' else 'Search candidate or committee ID', max_chars=200)
    state = 'All'
    office = 'All'
    if table == 'candidates':
        left, right = st.columns(2)
        states = query('SELECT DISTINCT cand_office_st FROM fec.candidates WHERE cycle=%s AND cand_office_st IS NOT NULL ORDER BY 1', (cycle,)).iloc[:, 0].tolist()
        state = left.selectbox('State of race', ['All'] + states)
        office = right.selectbox('Office', ['All', 'H', 'S', 'P'])
    where = ['cycle=%s']
    params = [cycle]
    if search:
        # Escape LIKE metacharacters so searches are literal substrings.
        term = search.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
        where.append(f'({fields[0]} ILIKE %s OR {fields[1]} ILIKE %s)')
        params += [f'%{term}%', f'%{term}%']
    if state != 'All':
        where.append('cand_office_st=%s')
        params.append(state)
    if office != 'All':
        where.append('cand_office=%s')
        params.append(office)
    # Table and field names come only from the fixed lists above.
    clause = ' AND '.join(where)
    total = int(query(f'SELECT count(*) AS n FROM fec.{table} WHERE {clause}', params).iloc[0, 0])
    page_size = 100
    pages = max(1, math.ceil(total / page_size))
    page = st.number_input('Page', min_value=1, max_value=pages, value=1, key=f'page_{table}_{cycle}_{search}_{state}_{office}')
    statement = f'SELECT * FROM fec.{table} WHERE {clause} ORDER BY source_line LIMIT %s OFFSET %s'
    bound = params + [page_size, (page - 1) * page_size]
    rows = query(statement, bound)
    st.caption(f'{total:,} matching records · Page {page} of {pages} · Up to 100 records per page')
    st.dataframe(rows, hide_index=True, width='stretch')
    if rows.empty:
        st.info('No matching records. Try a different search or filter.')
    st.download_button('Download this page as CSV', rows.to_csv(index=False).encode('utf-8-sig'), f'{table}_{cycle}_page_{page}.csv', 'text/csv')
    show_sql(statement, bound)
    st.caption('Source columns remain text. source_line identifies a row in this snapshot, not a permanent business identifier.')
