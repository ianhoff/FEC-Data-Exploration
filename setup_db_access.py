"""Run locally once: create limited project access and configure Windows pgpass."""
import csv
import getpass
import io
import json
import os
from pathlib import Path
import subprocess

import psycopg
from psycopg import sql

ROLE = 'fec_project_user'
ROOT = Path(__file__).resolve().parent


def escape(value):
    return str(value).replace('\\', '\\\\').replace(':', '\\:')


def main():
    config = json.loads((ROOT / 'config.json').read_text(encoding='utf-8-sig'))
    admin_password = getpass.getpass('Existing postgres password (hidden): ')
    password = getpass.getpass('Choose a NEW password for fec_project_user (hidden): ')
    confirmation = getpass.getpass('Confirm the NEW project password (hidden): ')
    if not password or password != confirmation:
        raise ValueError('Project passwords must be nonempty and match.')
    if any(c in password for c in '\r\n\x00'):
        raise ValueError('Password cannot contain line breaks or NUL.')
    if password == admin_password:
        raise ValueError('Use a different password for the limited account.')

    with psycopg.connect(**config, password=admin_password) as conn:
        with conn.cursor() as cur:
            cur.execute('SELECT 1 FROM pg_roles WHERE rolname=%s', (ROLE,))
            if cur.fetchone():
                raise ValueError('fec_project_user already exists; stopped without changing it.')
            cur.execute(sql.SQL('CREATE ROLE {} LOGIN NOSUPERUSER NOCREATEDB '
                                'NOCREATEROLE NOREPLICATION NOBYPASSRLS PASSWORD {}')
                        .format(sql.Identifier(ROLE), sql.Literal(password)))
            cur.execute(sql.SQL('GRANT CONNECT ON DATABASE fec_project TO {}').format(sql.Identifier(ROLE)))
            cur.execute(sql.SQL('GRANT USAGE ON SCHEMA fec TO {}').format(sql.Identifier(ROLE)))
            cur.execute(sql.SQL('GRANT SELECT ON ALL TABLES IN SCHEMA fec TO {}').format(sql.Identifier(ROLE)))
            cur.execute(sql.SQL('ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA fec '
                                'GRANT SELECT ON TABLES TO {}').format(sql.Identifier(ROLE)))
            cur.execute(sql.SQL('CREATE SCHEMA fec_model AUTHORIZATION {}').format(sql.Identifier(ROLE)))
            cur.execute(sql.SQL('ALTER ROLE {} IN DATABASE fec_project '
                                'SET search_path TO fec_model, fec, public').format(sql.Identifier(ROLE)))

    # Never print, log, or put either password into a command-line argument.
    pgpass = Path(os.environ['APPDATA']) / 'postgresql' / 'pgpass.conf'
    pgpass.parent.mkdir(parents=True, exist_ok=True)
    previous = pgpass.read_text(encoding='utf-8') if pgpass.exists() else ''
    pgpass.touch(exist_ok=True)
    # Use the current Windows SID to avoid ambiguous/localized account names.
    identity = subprocess.run(['whoami', '/user', '/fo', 'csv', '/nh'],
                              capture_output=True, text=True, check=True)
    sid = next(csv.reader(io.StringIO(identity.stdout)))[1]
    subprocess.run(['icacls', str(pgpass), '/reset'], capture_output=True, check=True)
    subprocess.run(['icacls', str(pgpass), '/inheritance:r', '/grant:r', f'*{sid}:(F)'],
                   capture_output=True, check=True)
    entry = ':'.join(map(escape, (config['host'], config['port'], config['dbname'], ROLE, password)))
    with pgpass.open('w', encoding='utf-8', newline='\n') as out:
        out.write(previous)
        if previous and not previous.endswith('\n'):
            out.write('\n')
        out.write(entry + '\n')

    project_config = {**config, 'user': ROLE}
    (ROOT / 'config.analysis.json').write_text(json.dumps(project_config, indent=2) + '\n', encoding='utf-8')
    with psycopg.connect(**project_config) as conn:
        with conn.cursor() as cur:
            cur.execute('SELECT current_user, count(*) FROM fec.links')
            user, count = cur.fetchone()
    print(f'Access verified as {user}: {count:,} raw link records.')
    print('Password saved in your Windows PostgreSQL password file; no passwords in project files.')
    print('Use config.analysis.json for analysis; config.json remains for imports.')


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        # Database errors may contain SQL text: do not print their details.
        print(f'Setup stopped ({type(error).__name__}). No credentials displayed.')
        print('If the role was created before a later failure, ask for help before rerunning.')
        raise SystemExit(1)
