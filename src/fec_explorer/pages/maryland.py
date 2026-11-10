"""Live Streamlit page."""
import altair as alt
import streamlit as st
from fec_explorer.database import query
from fec_explorer.ui import show_sql

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
