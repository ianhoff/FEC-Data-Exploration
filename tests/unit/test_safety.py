import pytest
from tests.db_safety import test_connection_settings


@pytest.mark.parametrize('dsn',[
    'host=localhost dbname=fec_project',
    'host=localhost',
    'host=localhost dbname=postgres',
    'host=remote.example dbname=fec_test_ci',
    'dbname=fec_test_ci',
    'host=localhost dbname=fec_test_ci service=personal',
])
def test_refuses_non_disposable_targets(dsn):
    with pytest.raises(ValueError):
        test_connection_settings(dsn)


def test_does_not_use_personal_password_file():
    settings=test_connection_settings('host=127.0.0.1 port=55439 dbname=fec_test_ci user=fec_test_runner')
    assert settings['dbname']=='fec_test_ci'
    assert settings['passfile']=='__fec_test_no_personal_password_file__'
