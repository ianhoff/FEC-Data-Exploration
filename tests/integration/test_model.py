from pathlib import Path
import shutil

import psycopg
import pytest
from build_model import build

pytestmark=pytest.mark.integration


def test_build_preserves_unresolved_and_is_repeatable(db,masters):
    build(db)
    build(db)
    assert db.execute('SELECT source_line FROM fec_model.links').fetchall()==[(1,)]
    assert db.execute('SELECT source_line,candidate_absent,committee_absent FROM fec_model.unresolved_links ORDER BY source_line').fetchall()==[(2,True,False),(3,False,True),(4,True,True)]
    assert db.execute('SELECT count(*) FROM fec_model.unresolved_principal_committees').fetchone()[0]==1
    assert db.execute('SELECT count(*) FROM fec_model.unresolved_committee_candidates').fetchone()[0]==1
    assert db.execute('SELECT resolved_link_count,unresolved_link_count FROM fec_model.builds').fetchone()==(1,3)
    assert db.execute('SELECT count(*) FROM fec.links').fetchone()[0]==4


@pytest.mark.parametrize('table,values',[
    ('links',dict(source_line=-1,cand_id='ABSENT',cmte_id='C_TEST1')),
    ('links',dict(source_line=-1,cand_id='H_TEST1',cmte_id='ABSENT')),
    ('links',dict(source_line=-1,cand_id='H_TEST1',cmte_id='C_TEST1',cycle=2022)),
    ('principal_committees',dict(cand_id='ABSENT',cmte_id='C_TEST1')),
    ('principal_committees',dict(cand_id='S_TEST2',cmte_id='ABSENT')),
    ('committee_candidates',dict(cand_id='H_TEST1',cmte_id='ABSENT')),
    ('committee_candidates',dict(cand_id='ABSENT',cmte_id='C_TEST2')),
])
def test_enforced_foreign_keys(db,masters,table,values):
    from psycopg import sql
    build(db)
    values={'cycle':2024,**values}
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        with db.transaction():
            db.execute(sql.SQL('INSERT INTO fec_model.{} ({}) VALUES ({})').format(
                sql.Identifier(table),sql.SQL(',').join(map(sql.Identifier,values)),
                sql.SQL(',').join(sql.Placeholder() for _ in values)),list(values.values()))


@pytest.mark.parametrize('key',['DUPLICATE',None])
def test_bad_master_refresh_rolls_back_previous_model(db,masters,load,key):
    build(db)
    before=db.execute('SELECT * FROM fec_model.candidates ORDER BY cand_id').fetchall()
    load('candidates',[dict(cand_id=key),dict(cand_id=key)])
    with pytest.raises(ValueError,match='missing or duplicate'):
        build(db)
    assert db.execute('SELECT * FROM fec_model.candidates ORDER BY cand_id').fetchall()==before


def test_failed_later_cycle_rolls_back_earlier_refresh(db,masters,load):
    build(db)
    before=db.execute('SELECT * FROM fec_model.candidates ORDER BY cand_id').fetchall()
    load('candidates',[dict(cand_id='CHANGED')])
    with pytest.raises(ValueError,match='all three'):
        build(db,[2024,2026])
    assert db.execute('SELECT * FROM fec_model.candidates ORDER BY cand_id').fetchall()==before


def test_incomplete_sources_and_changed_migration_are_rejected(db,masters,tmp_path):
    build(db)
    db.execute("UPDATE fec.imports SET row_count=999 WHERE dataset='links'")
    with pytest.raises(ValueError,match='counts disagree'):
        build(db)
    path=tmp_path/'001_relationship_model.sql'
    shutil.copyfile(Path('migrations')/path.name,path)
    path.write_text(path.read_text()+'\n-- edited\n')
    with pytest.raises(ValueError,match='migration changed'):
        build(db,migration_dir=tmp_path)
