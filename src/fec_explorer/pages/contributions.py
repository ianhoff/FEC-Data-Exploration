"""Live Streamlit page."""
import psycopg
import streamlit as st
from fec_explorer.database import query
from fec_explorer.origins import aggregate, state_tables, choropleth, ORIGINS_SQL, STATES, CANDIDATES_SQL, committee_ids

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
