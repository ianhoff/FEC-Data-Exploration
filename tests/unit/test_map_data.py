from decimal import Decimal

import pandas as pd
import pytest
from fec_explorer.origins import state_tables,committee_ids,choropleth,STATES


def test_recipient_ids_are_unique_not_transaction_rows():
    candidates=pd.DataFrame({'cand_pcc':['C_TEST1','C_TEST1',None,'C_TEST2']})
    assert committee_ids(candidates)==('C_TEST1','C_TEST2')


def test_unknown_states_and_excluded_dates_stay_accounted_for():
    rows=[]
    for state,scope,amount in [('MD','Included','-1.25'),(None,'Included','2'),
                                ('PR','Included','3'),('md','Included','4'),('MD','Outside date range','100')]:
        rows.append(dict(state=state,date_scope=scope,records=1,recorded_amount=Decimal(amount),
                         invalid_amount_records=0,memo_records=0,amendment_records=0))
    mapped,unknown=state_tables(pd.DataFrame(rows))
    assert len(mapped)==51
    assert mapped.records.sum()==1 and unknown.records.sum()==3
    assert mapped.loc[mapped.state=='MD','recorded_amount'].iloc[0]==-1.25
    assert set(unknown.state)=={'(missing)','PR','md'}


def test_no_included_rows_produces_zero_state_totals():
    empty=pd.DataFrame(columns=['state','date_scope','records','recorded_amount','invalid_amount_records','memo_records','amendment_records'])
    mapped,unknown=state_tables(empty)
    assert mapped.records.sum()==0 and len(mapped)==51 and unknown.empty


def test_invalid_exclusion_is_rejected():
    values=STATES.assign(records=1,recorded_amount=1.0)
    with pytest.raises(ValueError,match='Unknown excluded state'):
        choropleth(values,'Reported amount',exclude_state='NOT_A_STATE')
