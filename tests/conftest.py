import os
import socket
import urllib.request
import zipfile
from pathlib import Path

import psycopg
import pytest

from fec_explorer.ingestion import SPECS, ingest
from tests.db_safety import test_connection_settings


def pytest_addoption(parser):
    parser.addoption('--require-db', action='store_true', help='Fail rather than skip when FEC_TEST_DSN is absent.')


@pytest.fixture(autouse=True)
def no_external_io(monkeypatch):
    """Only the integration fixture may open DB connections; no downloads allowed."""
    def deny(*args, **kwargs):
        raise AssertionError('External I/O disabled: use synthetic fixtures and the db fixture.')
    monkeypatch.setattr(urllib.request, 'urlopen', deny)
    monkeypatch.setattr(socket, 'create_connection', deny)
    # The db fixture captures the real connect method before this fixture patches it.
    monkeypatch.setattr(psycopg, 'connect', deny)
    read_text = Path.read_text
    def guarded_read(path, *args, **kwargs):
        if path.name in ('config.json', 'config.analysis.json', 'pgpass.conf', '.pgpass'):
            raise AssertionError('Personal connection files must not be read by portable tests.')
        return read_text(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'read_text', guarded_read)
    for name in list(os.environ):
        if name.startswith('PG'):
            monkeypatch.delenv(name, raising=False)


REAL_CONNECT = psycopg.connect


@pytest.fixture
def db(request, no_external_io):
    dsn = os.environ.get('FEC_TEST_DSN')
    if not dsn:
        if request.config.getoption('--require-db'):
            pytest.fail('FEC_TEST_DSN is required for integration tests.')
        pytest.skip('Set FEC_TEST_DSN to an empty disposable fec_test_* database.')
    settings = test_connection_settings(dsn)
    conn = REAL_CONNECT(**settings, autocommit=True)
    owned = False
    try:
        assert conn.info.dbname == settings['dbname'], 'Server database differs from test target'
        if conn.info.server_version < 160000:
            pytest.fail('PostgreSQL 16+ is required.')
        # Refuse existing raw/model objects on entry. Do not silently reset a populated DB.
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM pg_namespace WHERE nspname IN ('fec','fec_model')")
            if cur.fetchone()[0]:
                pytest.fail('Test database must be empty: fec/fec_model already exist.')
            cur.execute('CREATE SCHEMA fec_model')
            owned = True
        yield conn
    finally:
        conn.rollback()
        # Only clean up schemas in a validated, explicitly disposable target.
        # Never clean a database whose preexisting schemas caused fixture refusal.
        if owned:
            with conn.cursor() as cur:
                cur.execute('DROP SCHEMA IF EXISTS fec_model CASCADE')
                cur.execute('DROP SCHEMA IF EXISTS fec CASCADE')
        conn.close()


@pytest.fixture
def zip_factory(tmp_path):
    count = 0
    def make(table, records, raw=None):
        nonlocal count
        count += 1
        _, member, columns = SPECS[table]
        path = tmp_path / f'{table}_{count}.zip'
        if raw is None:
            raw = ''.join('|'.join('' if record.get(col) is None else str(record[col]) for col in columns)+'\n' for record in records).encode('utf-8')
        with zipfile.ZipFile(path, 'w') as archive:
            archive.writestr(member, raw)
        return path
    return make


@pytest.fixture
def load(db, zip_factory):
    def run(table, records, cycle=2024):
        path = zip_factory(table, records)
        ingest(db, table, cycle, path, 'https://example.invalid/synthetic.zip')
    return run


@pytest.fixture
def masters(load):
    load('candidates', [
        dict(cand_id='H_TEST1',cand_name='Synthetic Candidate One',cand_pcc='C_TEST1',cand_office_st='MD',cand_office='H',cand_election_yr='2024'),
        dict(cand_id='S_TEST2',cand_name='Synthetic Candidate Two',cand_pcc='C_ABSENT',cand_office_st='DE',cand_office='S',cand_election_yr='2024'),
    ])
    load('committees', [dict(cmte_id='C_TEST1',cmte_nm='Synthetic Committee',cand_id='H_TEST1'),
                        dict(cmte_id='C_TEST2',cand_id='H_ABSENT')])
    load('links', [dict(cand_id='H_TEST1',cmte_id='C_TEST1',linkage_id='1'),
                   dict(cand_id='H_ABSENT',cmte_id='C_TEST1',linkage_id='2'),
                   dict(cand_id='H_TEST1',cmte_id='C_ABSENT',linkage_id='3'),
                   dict(cand_id='H_ABSENT',cmte_id='C_ABSENT',linkage_id='4')])
