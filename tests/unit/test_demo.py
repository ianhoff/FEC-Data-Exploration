from pathlib import Path
import json

from streamlit.testing.v1 import AppTest

ROOT=Path(__file__).resolve().parents[2]


def test_demo_runs_without_database_or_personal_configs():
    # Autouse guards prohibit DB connections, config reads, and Python downloads.
    app=AppTest.from_file(str(ROOT/'demo_app.py'),default_timeout=30).run()
    assert not app.exception and not app.error
    assert any('SYNTHETIC DEMO' in w.value for w in app.warning)
    assert len(app.metric)==3
    app.sidebar.selectbox[0].set_value('CA').run()
    assert not app.exception and not app.error
    assert 'California' in app.header[0].value
    app.sidebar.toggle[0].set_value(False).run()
    assert not app.exception
    app.sidebar.radio[0].set_value('Model tour').run()
    assert not app.exception and not app.error
    assert 'enforced relationships' in app.header[0].value


def test_demo_data_is_explicitly_synthetic():
    data=json.loads((ROOT/'demo/origins.json').read_text())
    assert data['synthetic'] is True
    assert {row['campaign_state'] for row in data['groups']}=={'MD','DE','CA'}
    assert all('name' not in row and 'zip_code' not in row for row in data['groups'])
