"""Local read-only FEC data explorer. Start with streamlit run app.py."""
import json
import math
from pathlib import Path

import pandas as pd
import altair as alt
import psycopg
import streamlit as st
from origins import aggregate, state_tables, choropleth, ORIGINS_SQL, STATES, CANDIDATES_SQL, committee_ids

ROOT = Path(__file__).resolve().parent
st.set_page_config(page_title='FEC Data Explorer', page_icon='🔎', layout='wide')


def query(statement, params=()):
    config = json.loads((ROOT / 'config.analysis.json').read_text(encoding='utf-8'))
    with psycopg.connect(**config, options='-c default_transaction_read_only=on -c statement_timeout=15000') as conn:
        with conn.cursor() as cur:
            cur.execute(statement, params)
            return pd.DataFrame(cur.fetchall(), columns=[c.name for c in cur.description])


def show_sql(statement, params=()):
    with st.expander('View SQL'):
        st.code(statement, language='sql')
        if params:
            st.caption('Bound parameter values (in order)')
            st.json(list(params))


UNMATCHED = '''SELECT l.*,
    NOT EXISTS (SELECT 1 FROM fec.candidates c WHERE c.cycle=l.cycle AND c.cand_id=l.cand_id) AS candidate_absent,
    NOT EXISTS (SELECT 1 FROM fec.committees m WHERE m.cycle=l.cycle AND m.cmte_id=l.cmte_id) AS committee_absent
    FROM fec.links l WHERE l.cycle=%s'''


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


def quality(cycle):
    st.header('Data quality')
    st.write('Find issues before enforcing relationships. All raw records remain available.')
    statement = f'''WITH checks AS ({UNMATCHED}) SELECT count(*) AS link_records,
        count(*) FILTER (WHERE candidate_absent OR committee_absent) AS unmatched_links,
        count(*) FILTER (WHERE candidate_absent) AS candidate_absent,
        count(*) FILTER (WHERE committee_absent) AS committee_absent,
        count(*) FILTER (WHERE candidate_absent AND committee_absent) AS both_absent FROM checks'''
    summary = query(statement, (cycle,))
    row = summary.iloc[0]
    for col, label, field in zip(st.columns(3), ['Unmatched links', 'Candidate absent', 'Committee absent'], ['unmatched_links', 'candidate_absent', 'committee_absent']):
        col.metric(label, f'{int(row[field]):,}')
    st.caption(f'{int(row.both_absent):,} links lack both references. The candidate and committee counts overlap.')
    show_sql(statement, (cycle,))
    st.subheader('Master identifier checks')
    checks = []
    for table, field in [('candidates', 'cand_id'), ('committees', 'cmte_id')]:
        result = query(f'''SELECT count(*) FILTER (WHERE {field} IS NULL) AS missing_ids,
            count({field})-count(DISTINCT {field}) AS duplicate_extra_records
            FROM fec.{table} WHERE cycle=%s''', (cycle,)).iloc[0]
        checks.append({'dataset': table, **result.to_dict()})
    st.dataframe(pd.DataFrame(checks), hide_index=True, width='stretch')
    st.subheader('Unmatched link records')
    unmatched = query(f'WITH checks AS ({UNMATCHED}) SELECT * FROM checks WHERE candidate_absent OR committee_absent ORDER BY source_line', (cycle,))
    st.dataframe(unmatched, hide_index=True, width='stretch')
    st.download_button('Download unmatched links', unmatched.to_csv(index=False).encode('utf-8-sig'), f'unmatched_links_{cycle}.csv', 'text/csv')
    st.subheader('Election year profile')
    st.caption('Unusual values are preserved for investigation. This table does not infer corrections.')
    st.dataframe(query('SELECT cand_election_yr, fec_election_yr, count(*) AS link_records FROM fec.links WHERE cycle=%s GROUP BY 1,2 ORDER BY 1,2', (cycle,)), hide_index=True, width='stretch')


def maryland(cycle, races=False):
    st.header('Races & candidates' if races else 'Maryland congressional campaigns')
    st.caption('Candidates running in Maryland for House or Senate; this does not identify Maryland contributors.')
    years = query("SELECT DISTINCT cand_election_yr FROM fec.candidates WHERE cycle=%s AND cand_office_st='MD' AND cand_office IN ('H','S') AND cand_election_yr IS NOT NULL ORDER BY 1 DESC", (cycle,)).iloc[:, 0].tolist()
    options = ['All'] + years
    year = st.selectbox('Candidate election year', options, index=options.index(str(cycle)) if str(cycle) in options else 0)
    statement = "SELECT * FROM fec.candidates WHERE cycle=%s AND cand_office_st='MD' AND cand_office IN ('H','S')"
    params = [cycle]
    if year != 'All':
        statement += ' AND cand_election_yr=%s'
        params.append(year)
    statement += ' ORDER BY cand_office, cand_office_district, cand_name, source_line'
    candidates = query(statement, params)
    show_sql(statement, params)
    if candidates.empty:
        st.info('No Maryland congressional candidates match this selection.')
        return
    for col, label, value in zip(st.columns(3), ['House candidates', 'Senate candidates', 'Principal committee IDs'],
                                 [(candidates.cand_office == 'H').sum(), (candidates.cand_office == 'S').sum(), candidates.cand_pcc.nunique()]):
        col.metric(label, f'{value:,}')
    if not races:
        st.subheader('Party breakdown')
        parties = candidates.cand_pty_affiliation.fillna('Missing').value_counts().rename_axis('Party').reset_index(name='Candidates')
        st.altair_chart(alt.Chart(parties).mark_bar(color='#087f8c').encode(
            x=alt.X('Candidates:Q'), y=alt.Y('Party:N', sort='-x'), tooltip=['Party', 'Candidates']), width='stretch')
        st.subheader('Races in this selection')
        grouped = candidates.groupby(['cand_office', 'cand_office_district'], dropna=False).size().reset_index(name='candidate_records')
        st.dataframe(grouped, hide_index=True, width='stretch')
    office = st.selectbox('Race office', ['All', 'House', 'Senate'])
    selected = candidates
    if office != 'All':
        selected = selected[selected.cand_office == {'House': 'H', 'Senate': 'S'}[office]]
    if office == 'House':
        districts = sorted(selected.cand_office_district.dropna().unique().tolist())
        district = st.selectbox('House district', ['All'] + districts)
        if district != 'All':
            selected = selected[selected.cand_office_district == district]
    if selected.empty:
        st.info('No candidates match these race filters.')
        return
    st.subheader('Candidate directory')
    columns = ['cand_name', 'cand_id', 'cand_pty_affiliation', 'cand_office', 'cand_office_district', 'cand_election_yr', 'cand_pcc']
    st.dataframe(selected[columns], hide_index=True, width='stretch')
    st.download_button('Download selected Maryland candidates', selected[columns].to_csv(index=False).encode('utf-8-sig'), f'maryland_candidates_{cycle}.csv', 'text/csv')
    st.subheader('Candidate profile')
    records = selected.to_dict('records')
    pick = st.selectbox('Candidate', range(len(records)), format_func=lambda i: f"{records[i]['cand_name']} · {records[i]['cand_id']} · {records[i]['cand_office']} {records[i]['cand_office_district'] or ''}")
    candidate = records[pick]
    st.write(f"**{candidate['cand_name']}**")
    st.caption(f"Party: {candidate['cand_pty_affiliation'] or 'Missing'} · Election year: {candidate['cand_election_yr'] or 'Missing'} · Candidate ID: {candidate['cand_id']}")
    st.markdown('**Principal campaign committee**')
    principal = query('SELECT cmte_id, cmte_nm, cmte_dsgn, cmte_tp, cmte_city, cmte_st FROM fec.committees WHERE cycle=%s AND cmte_id=%s', (cycle, candidate['cand_pcc']))
    if not candidate['cand_pcc']:
        st.warning('No principal committee ID is reported on this candidate record.')
    elif principal.empty:
        st.warning(f"Principal committee {candidate['cand_pcc']} is absent from the committee master for this archive.")
    else:
        st.dataframe(principal, hide_index=True, width='stretch')
    st.markdown('**Reported committee relationships**')
    link_sql = '''SELECT l.cmte_id, m.cmte_nm, l.cmte_dsgn, l.cmte_tp,
        l.cand_election_yr, l.fec_election_yr, l.linkage_id,
        m.source_line IS NULL AS committee_absent
        FROM fec.links l LEFT JOIN fec.committees m
          ON m.cycle=l.cycle AND m.cmte_id=l.cmte_id
        WHERE l.cycle=%s AND l.cand_id=%s
        ORDER BY l.cand_election_yr, l.cmte_id, l.source_line'''
    links = query(link_sql, (cycle, candidate['cand_id']))
    if links.empty:
        st.info('No linkage records found for this candidate in this archive.')
    else:
        st.dataframe(links, hide_index=True, width='stretch')
        if links.committee_absent.any():
            st.warning(f'{int(links.committee_absent.sum())} linkage records reference an absent committee.')
    st.caption('Relationships show all reported election years for this candidate within the selected archive. P = Principal; A = Authorized; J = Joint fundraiser; D = Leadership PAC; U = Unauthorized; B = Lobbyist/Registrant PAC. A link alone does not establish financial attribution.')
    show_sql(link_sql, (cycle, candidate['cand_id']))


def contribution_origins(cycle):
    from datetime import date
    st.header('Contribution origins')
    st.write('Choose the state where congressional campaigns are running, then explore where their reported contributions originated.')
    available = query("SELECT dataset, imported_at, row_count FROM fec.imports WHERE cycle=%s AND dataset IN ('candidates','committees','contributions') ORDER BY dataset", (cycle,))
    if 'contributions' not in available.dataset.tolist():
        st.info(f'Contribution data has not been imported for archive cycle {cycle}. Choose an imported cycle to use the map.')
        return
    state_names = dict(zip(STATES.state, STATES.state_name))
    state_options = STATES.sort_values('state_name').state.tolist()
    race_state = st.selectbox('Campaign state', state_options, index=state_options.index('MD'),
                              format_func=lambda code: f'{state_names[code]} ({code})')
    state_name = state_names[race_state]
    candidates = query(CANDIDATES_SQL, (cycle, race_state))
    if candidates.empty:
        st.info(f'No House or Senate candidate records for {state_name} in this archive.')
        return
    years = sorted(candidates.cand_election_yr.dropna().unique().tolist(), reverse=True)
    year_options = ['All'] + years
    year = st.selectbox('Candidate election year', year_options, index=year_options.index(str(cycle)) if str(cycle) in years else 0, key=f'origins_year_{cycle}_{race_state}')
    selected = candidates if year == 'All' else candidates[candidates.cand_election_yr == year]
    if selected.empty:
        st.info(f'No {state_name} congressional candidates match this election year.')
        return
    labels = {r.cand_id: f'{r.cand_name} ({r.cand_id})' for r in selected.itertuples()}
    candidate = st.selectbox('Campaign', [f'All selected {state_name} campaigns'] + list(labels), format_func=lambda v: labels.get(v,v), key=f'origins_campaign_{cycle}_{race_state}_{year}')
    if candidate in labels:
        selected = selected[selected.cand_id == candidate]
    committees = committee_ids(selected)
    missing = int(selected.cand_pcc.isna().sum())
    st.caption(f'{len(committees)} distinct recipient committee IDs. Shared committee IDs are counted once. {missing} candidate records lack a principal committee ID.')
    if not committees:
        st.info('No principal campaign committees are reported for this selection.')
        return
    measure = st.selectbox('Measure', ['Reported amount', 'Record count'])
    dates = st.date_input('Reported transaction date range', value=(date(cycle-1,1,1),date(cycle,12,31)), key=f'origins_dates_{cycle}')
    if len(dates) != 2:
        st.info('Choose both a start date and an end date.')
        return
    st.caption('All transaction/entity types, memo records, amendments, and negative amounts are retained. No amendment resolution or donor deduplication is applied. Amounts are exploratory sums, not official fundraising totals.')
    signature = available.to_json(date_format='iso')
    try:
        with st.spinner('Aggregating reported records by state. The first query can take a few minutes…'):
            data = aggregate(cycle, committees, dates[0], dates[1], signature)
    except psycopg.errors.QueryCanceled:
        st.warning('This selection exceeded the three-minute query limit. Try one campaign or a narrower recipient selection.')
        return
    included = data[data.date_scope == 'Included']
    if included.empty:
        st.info('No records with valid dates fall in this date range for these committees.')
    else:
        mapped, unknown = state_tables(data)
        left, middle, right = st.columns([1, 1.7, 1])
        left.metric('Reported records', f'{int(included.records.sum()):,}')
        middle.metric('Recorded amount sum', f'${included.recorded_amount.sum():,.2f}')
        right.metric('Unmapped location records', f'{int(unknown.records.sum()):,}')
        exclude_home = st.toggle(f'Exclude {state_name} from map scale', value=True, key=f'origins_exclude_{race_state}')
        if exclude_home:
            home = mapped.loc[mapped.state == race_state].iloc[0]
            st.caption(f'{state_name} is shown in gray and excluded from the color scale and map-share denominator: {int(home.records):,} records / ${home.recorded_amount:,.2f}. Summary totals and tables still include {state_name}.')
        st.altair_chart(choropleth(mapped, measure, exclude_state=race_state if exclude_home else None), width='stretch')
        st.caption('50 states + DC; Alaska and Hawaii appear as insets. Shares use states/DC included in the color scale. Locations use reported state codes exactly; zero means no included records or a zero recorded sum.')
        if measure == 'Reported amount' and (mapped.recorded_amount < 0).any():
            st.info('A diverging color scale displays negative state sums. Percent shares of signed sums can be negative or exceed 100%.')
        st.subheader('State totals')
        sort = 'recorded_amount' if measure == 'Reported amount' else 'records'
        table = mapped.drop(columns=['id','date_scope'], errors='ignore').sort_values(sort, ascending=False)
        st.dataframe(table, hide_index=True, width='stretch')
        st.download_button('Download state totals', table.to_csv(index=False).encode('utf-8-sig'), f'{race_state}_origins_{cycle}.csv', 'text/csv')
        st.subheader('Unknown, territory, and other locations')
        st.dataframe(unknown, hide_index=True, width='stretch')
        st.download_button('Download unmapped locations', unknown.to_csv(index=False).encode('utf-8-sig'), f'{race_state}_unmapped_{cycle}.csv', 'text/csv')
    st.subheader('Record inclusion checks')
    st.dataframe(data.groupby('date_scope', as_index=False)[['records','invalid_amount_records','memo_records','amendment_records']].sum(), hide_index=True, width='stretch')
    st.caption('Invalid/missing dates and out-of-range dates are counted above but excluded from the map. Invalid/missing amounts remain in record counts and are omitted from amount sums. Amount sums use exact numeric arithmetic in PostgreSQL; chart values are rounded for display.')
    with st.expander('Recipient selection and query'):
        st.dataframe(selected, hide_index=True, width='stretch')
        st.code(ORIGINS_SQL, language='sql')
        st.json({'cycle': cycle, 'campaign_state': race_state, 'committee_ids': committees, 'start': str(dates[0]), 'end': str(dates[1])})
        st.caption('Aggregates are cached for up to five minutes and invalidated by changed source import metadata. No contributor-level rows are sent to the browser.')


def main():
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


try:
    main()
except (psycopg.Error, OSError, ValueError, KeyError):
    st.error('Could not load the database data. Check PostgreSQL, config.analysis.json, and your local password file. No credentials are displayed.')
    st.stop()
