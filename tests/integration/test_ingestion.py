import pytest
from ingest_fec import ingest

pytestmark=pytest.mark.integration


def rows(db,statement,params=()):
    return db.execute(statement,params).fetchall()


def test_replacement_is_idempotent_and_preserves_other_cycles(db,load):
    load('candidates',[dict(cand_id='OLD')],2022)
    load('candidates',[dict(cand_id='A'),dict(cand_id='B')])
    load('candidates',[dict(cand_id='NEW',cand_zip='00123')])
    load('candidates',[dict(cand_id='NEW',cand_zip='00123')])
    assert rows(db,'SELECT cycle,cand_id,cand_zip FROM fec.candidates ORDER BY cycle')==[(2022,'OLD',None),(2024,'NEW','00123')]
    assert rows(db,'SELECT cycle,row_count FROM fec.imports ORDER BY cycle')==[(2022,1),(2024,1)]


@pytest.mark.parametrize('failure',['malformed','empty','encoding'])
def test_failed_replacement_restores_rows_and_tracking(db,load,zip_factory,failure):
    load('candidates',[dict(cand_id='KEEP')])
    before=rows(db,'SELECT * FROM fec.imports')
    raw={'malformed':b'wrong|fields\n','empty':b'\n','encoding':b'\xff\n'}[failure]
    path=zip_factory('candidates',[],raw=raw)
    with pytest.raises((ValueError,UnicodeError)):
        ingest(db,'candidates',2024,path,'https://example.invalid/replacement.zip')
    assert rows(db,'SELECT cand_id FROM fec.candidates')==[('KEEP',)]
    assert rows(db,'SELECT * FROM fec.imports')==before


def test_later_failure_keeps_earlier_dataset_commit(db,load,zip_factory):
    load('candidates',[dict(cand_id='COMMITTED')])
    with pytest.raises(ValueError):
        ingest(db,'committees',2024,zip_factory('committees',[],raw=b'bad\n'),'synthetic')
    assert rows(db,'SELECT cand_id FROM fec.candidates')==[('COMMITTED',)]
    assert rows(db,'SELECT dataset FROM fec.imports')==[('candidates',)]
    assert rows(db,"SELECT to_regclass('fec.committees')")==[(None,)]
