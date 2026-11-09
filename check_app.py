"""Smoke-test screens against local PostgreSQL without printing source records."""
from pathlib import Path
from streamlit.testing.v1 import AppTest

app = AppTest.from_file(str(Path(__file__).with_name('app.py')), default_timeout=30).run()


def check():
    assert not app.exception, 'Unexpected application exception'
    assert not app.error, 'Application reported a database error'


check()
assert app.header[0].value == 'Maryland congressional campaigns'
assert set(app.dataframe[1].value.cand_office).issubset({'H', 'S'})
assert set(app.dataframe[1].value.cand_election_yr) == {'2024'}
app.sidebar.radio[0].set_value('Races & candidates').run()
check()
next(s for s in app.selectbox if s.label == 'Race office').set_value('House').run()
check()
assert set(app.dataframe[0].value.cand_office) == {'H'}
district_widget = next(s for s in app.selectbox if s.label == 'House district')
district_widget.set_value(district_widget.options[1]).run()
check()
assert app.dataframe[0].value.cand_office_district.nunique() == 1
next(s for s in app.selectbox if s.label == 'Race office').set_value('Senate').run()
check()
assert set(app.dataframe[0].value.cand_office) == {'S'}
next(s for s in app.selectbox if s.label == 'Candidate election year').set_value('All').run()
check()
app.sidebar.radio[0].set_value('Overview').run()
check()
assert [m.value for m in app.metric] == ['9,796', '20,937', '8,619']
app.sidebar.radio[0].set_value('Explore tables').run()
check()
assert len(app.dataframe[0].value) == 100
next(s for s in app.selectbox if s.label == 'State of race').set_value('MD').run()
check()
assert set(app.dataframe[0].value['cand_office_st']) == {'MD'}
app.text_input[0].set_value("' OR 1=1 --").run()
check()
assert app.dataframe[0].value.empty, 'Search must be bound as a value'
app.text_input[0].set_value('').run()
for dataset in ('committees', 'links'):
    next(s for s in app.selectbox if s.label == 'Dataset').set_value(dataset).run()
    check()
    assert len(app.dataframe[0].value) == 100
app.sidebar.radio[0].set_value('Data quality').run()
check()
assert [m.value for m in app.metric] == ['184', '154', '160']
assert len(app.dataframe[1].value) == 184
print('PASS: Maryland overview, election years, House district and Senate filters, candidate profiles, national counts, datasets, literal SQL search, and quality report.')
