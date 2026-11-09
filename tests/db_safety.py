"""Validate test targets before opening a database connection."""
import re

from psycopg.conninfo import conninfo_to_dict


def test_connection_settings(dsn):
    # Explicit database names prevent libpq's environment-dependent fallback.
    settings = conninfo_to_dict(dsn)
    name = settings.get('dbname', '')
    if not re.fullmatch(r'fec_test_[a-z0-9_]+', name):
        raise ValueError('FEC_TEST_DSN must explicitly name a disposable fec_test_* database.')
    if settings.get('host') not in ('localhost', '127.0.0.1', '::1'):
        raise ValueError('FEC_TEST_DSN must explicitly use a local PostgreSQL host.')
    # Never let tests consult the personal Windows password file or service config.
    if 'service' in settings or 'servicefile' in settings:
        raise ValueError('PostgreSQL service configuration is not supported in tests.')
    settings['passfile'] = '__fec_test_no_personal_password_file__'
    settings['connect_timeout'] = 5
    return settings


test_connection_settings.__test__ = False
