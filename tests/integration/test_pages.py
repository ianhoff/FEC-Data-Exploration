from pathlib import Path

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

pytestmark=pytest.mark.integration


def test_extracted_live_pages_with_explicit_test_connection(db,masters,monkeypatch):
    from fec_explorer import database
    def query(statement, params=()):
        cur=db.execute(statement,params)
        return pd.DataFrame(cur.fetchall(),columns=[c.name for c in cur.description])
    monkeypatch.setattr(database,'query',query)
    # Pages import the patched helper; neither personal config nor authentication is used.
    app=AppTest.from_file(str(Path(__file__).resolve().parents[2]/'app.py'),default_timeout=30).run()
    assert not app.exception and not app.error
    assert app.header[0].value=='Maryland congressional campaigns'
    for name in ('Races & candidates','Overview','Explore tables','Data quality','Contribution origins'):
        app.sidebar.radio[0].set_value(name).run()
        assert not app.exception and not app.error
    assert any('has not been imported' in info.value for info in app.info)
