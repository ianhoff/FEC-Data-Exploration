import zipfile

import pytest

from fec_explorer.ingestion import rows_from_zip, SPECS


def test_preserves_source_fields_and_lineage(tmp_path):
    path = tmp_path / 'source.zip'
    with zipfile.ZipFile(path, 'w') as z:
        z.writestr('nested/CN.TXT', '\ufeff\nC0001|  Name  ||00123|"quoted"\r\n\nC0002|Other|0|00001|end\n')
    assert list(rows_from_zip(path, 'cn.txt', range(5))) == [
        (2, ['C0001','  Name  ',None,'00123','"quoted"']),
        (4, ['C0002','Other','0','00001','end']),
    ]


@pytest.mark.parametrize('table', list(SPECS))
def test_all_layouts_preserve_order(zip_factory, table):
    columns = SPECS[table][2]
    record = {name: str(i) for i,name in enumerate(columns)}
    rows = list(rows_from_zip(zip_factory(table,[record]),SPECS[table][1],columns))
    assert rows == [(1,[str(i) for i in range(len(columns))])]


@pytest.mark.parametrize('raw', [b'a|b\n',b'a|b|c|d\n'])
def test_changed_field_count_fails(tmp_path, raw):
    path=tmp_path/'bad.zip'
    with zipfile.ZipFile(path,'w') as z:
        z.writestr('cn.txt',raw)
    with pytest.raises(ValueError,match='line 1: expected 3 fields'):
        list(rows_from_zip(path,'cn.txt',range(3)))


def test_invalid_encoding_is_not_replaced(zip_factory):
    path=zip_factory('links',[],raw=b'\xff\n')
    with pytest.raises(UnicodeDecodeError):
        list(rows_from_zip(path,'ccl.txt',SPECS['links'][2]))


@pytest.mark.parametrize('members',[['other.txt'],['cn.txt','nested/cn.txt']])
def test_missing_or_ambiguous_member_fails(tmp_path,members):
    path=tmp_path/'members.zip'
    with zipfile.ZipFile(path,'w') as z:
        for member in members:
            z.writestr(member,'value')
    with pytest.raises(ValueError,match='expected exactly one'):
        list(rows_from_zip(path,'cn.txt',['field']))


def test_corrupt_archive_fails(tmp_path):
    path=tmp_path/'bad.zip';path.write_bytes(b'not a zip')
    with pytest.raises(zipfile.BadZipFile):
        list(rows_from_zip(path,'cn.txt',[]))
