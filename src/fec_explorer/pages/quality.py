"""Live Streamlit page."""
import pandas as pd
import streamlit as st
from fec_explorer.database import query
from fec_explorer.ui import show_sql

UNMATCHED = '''SELECT l.*,
    NOT EXISTS (SELECT 1 FROM fec.candidates c WHERE c.cycle=l.cycle AND c.cand_id=l.cand_id) AS candidate_absent,
    NOT EXISTS (SELECT 1 FROM fec.committees m WHERE m.cycle=l.cycle AND m.cmte_id=l.cmte_id) AS committee_absent
    FROM fec.links l WHERE l.cycle=%s'''

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
