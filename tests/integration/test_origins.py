from datetime import date
from decimal import Decimal

import pandas as pd
import pytest

from origins import CANDIDATES_SQL,committee_ids,fetch_aggregate,state_tables

pytestmark=pytest.mark.integration


def test_sql_dates_amounts_locations_and_reporting_flags(db,load):
    transactions=[]
    for state,dt,amount in [
        ('MD','01012023','10.10'),('CA','02292024','-2.25'),
        (None,'12312024','bad'),('PR','01032024','3.00'),
        ('MD','02302024','1'),('MD',None,'1'),('MD','01012022','1000'),
        ('MD','12312024',None),('MD','01012025','1000'),
    ]:
        transactions.append(dict(cmte_id='C_TEST1',state=state,transaction_dt=dt,
                                 transaction_amt=amount,memo_cd='X',amndt_ind='A',tran_id='REPEATED'))
    transactions.append(dict(cmte_id='C_OTHER',state='MD',transaction_dt='01012024',transaction_amt='9999'))
    load('contributions',transactions)
    load('contributions',[dict(cmte_id='C_TEST1',state='MD',transaction_dt='01012024',transaction_amt='9999')],2022)
    with db.transaction():
        db.execute('SET TRANSACTION READ ONLY')
        frame=fetch_aggregate(db,2024,('C_TEST1',),date(2023,1,1),date(2024,12,31))
    assert frame.records.sum()==9
    included=frame[frame.date_scope=='Included']
    assert included.records.sum()==5
    assert included.recorded_amount.sum()==Decimal('10.85')
    assert included.invalid_amount_records.sum()==2
    assert frame[frame.date_scope=='Invalid or missing date'].records.sum()==2
    assert frame[frame.date_scope=='Outside date range'].records.sum()==2
    assert frame.memo_records.sum()==9 and frame.amendment_records.sum()==9
    mapped,unknown=state_tables(frame)
    assert mapped.records.sum()+unknown.records.sum()==5
    assert unknown.records.sum()==2


def test_recipient_state_cycle_and_duplicate_candidate_references(db,load):
    load('candidates',[
        dict(cand_id='H_ONE',cand_pcc='C_MD',cand_office_st='MD',cand_office='H'),
        dict(cand_id='H_TWO',cand_pcc='C_MD',cand_office_st='MD',cand_office='H'),
        dict(cand_id='S_OTHER',cand_pcc='C_DE',cand_office_st='DE',cand_office='S'),
        dict(cand_id='P_ONE',cand_pcc='C_PRES',cand_office_st='MD',cand_office='P'),
    ])
    load('candidates',[dict(cand_id='H_OLD',cand_pcc='C_OLD',cand_office_st='MD',cand_office='H')],2022)
    load('contributions',[
        dict(cmte_id='C_MD',state='CA',transaction_dt='01012024',transaction_amt='5'),
        dict(cmte_id='C_MD',state='CA',transaction_dt='01012024',transaction_amt='5'),
        dict(cmte_id='C_DE',state='NY',transaction_dt='01012024',transaction_amt='50'),
    ])
    for state,expected_count,expected_amount in [('MD',2,Decimal('10')),('DE',1,Decimal('50'))]:
        cur=db.execute(CANDIDATES_SQL,(2024,state))
        candidates=pd.DataFrame(cur.fetchall(),columns=[c.name for c in cur.description])
        recipients=committee_ids(candidates)
        assert len(recipients)==1
        result=fetch_aggregate(db,2024,recipients,date(2023,1,1),date(2024,12,31))
        assert result.records.sum()==expected_count
        assert result.recorded_amount.sum()==expected_amount
    assert db.execute(CANDIDATES_SQL,(2024,"MD' OR 1=1 --")).fetchall()==[]
    assert fetch_aggregate(db,2024,(),date(2023,1,1),date(2024,12,31)).empty
