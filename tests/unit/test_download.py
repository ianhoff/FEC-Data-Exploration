import io
import zipfile

import pytest
import ingest_fec


def archive_bytes():
    data=io.BytesIO()
    with zipfile.ZipFile(data,'w') as z:
        z.writestr('cn.txt','synthetic')
    return data.getvalue()


def test_cache_reuse_never_opens_network(tmp_path):
    cached=tmp_path/'cn24.zip'
    cached.write_bytes(archive_bytes())
    path,url=ingest_fec.download(2024,'cn',tmp_path)
    assert path==cached
    assert url.endswith('/2024/cn24.zip')


def test_valid_download_replaces_cache_and_cleans_part(tmp_path,monkeypatch):
    body=archive_bytes()
    response=io.BytesIO(body)
    response.headers={'Content-Length':str(len(body))}
    monkeypatch.setattr(ingest_fec.urllib.request,'urlopen',lambda *a,**k:response)
    target=tmp_path/'cn24.zip';target.write_bytes(b'old cache')
    path,_=ingest_fec.download(2024,'cn',tmp_path,refresh=True)
    assert path.read_bytes()==body and not (tmp_path/'cn24.zip.part').exists()


def test_bad_refresh_preserves_old_cache(tmp_path,monkeypatch):
    target=tmp_path/'cn24.zip';original=archive_bytes();target.write_bytes(original)
    response=io.BytesIO(b'not a zip');response.headers={}
    monkeypatch.setattr(ingest_fec.urllib.request,'urlopen',lambda *a,**k:response)
    with pytest.raises(ValueError,match='not a ZIP'):
        ingest_fec.download(2024,'cn',tmp_path,refresh=True)
    assert target.read_bytes()==original and not (tmp_path/'cn24.zip.part').exists()
