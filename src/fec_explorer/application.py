"""Live application navigation and safe error handling."""
import psycopg
import streamlit as st
from fec_explorer.database import query
from fec_explorer.origins import aggregate
from fec_explorer.pages.overview import overview
from fec_explorer.pages.explorer import explore
from fec_explorer.pages.quality import quality
from fec_explorer.pages.maryland import maryland
from fec_explorer.pages.contributions import contribution_origins

def main():
    st.set_page_config(page_title='FEC Data Explorer', page_icon='??', layout='wide')
    st.sidebar.title('Maryland / FEC')
    st.sidebar.caption('LOCAL DATABASE WORKBENCH')
    page = st.sidebar.radio('Workspace', ['Maryland overview', 'Races & candidates', 'Contribution origins', 'Overview', 'Explore tables', 'Data quality'])
    cycles = query('SELECT DISTINCT cycle FROM fec.imports ORDER BY cycle DESC').iloc[:, 0].tolist()
    if not cycles:
        st.info('No imports found. Run the small datasets importer first.')
        return
    cycle = st.sidebar.selectbox('Archive cycle', cycles)
    st.sidebar.divider()
    st.sidebar.caption('Local PostgreSQL · Read-only queries · Live results on each interaction')
    if st.sidebar.button('Refresh data'):
        aggregate.clear()
        st.rerun()
    st.title('Maryland Campaign Explorer')
    st.caption(f'Campaign finance source data / {cycle} archive')
    if page in ('Maryland overview', 'Races & candidates'):
        maryland(cycle, races=page == 'Races & candidates')
    else:
        {'Contribution origins': contribution_origins, 'Overview': overview, 'Explore tables': explore, 'Data quality': quality}[page](cycle)

def run():
    try:
        main()
    except (psycopg.Error, OSError, ValueError, KeyError):
        st.error('Could not load the database data. Check PostgreSQL, config.analysis.json, and your local password file. No credentials are displayed.')
        st.stop()
