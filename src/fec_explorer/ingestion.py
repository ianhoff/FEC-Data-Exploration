"""Download FEC bulk files and stream them into PostgreSQL. Python 3.10+."""
from fec_explorer.paths import PROJECT_ROOT
import argparse
import getpass
import io
import json
import os
from pathlib import Path
import shutil
import sys
import urllib.request
import zipfile

SPECS = {
    'candidates': ('cn', 'cn.txt', '''cand_id cand_name cand_pty_affiliation cand_election_yr cand_office_st cand_office cand_office_district cand_ici cand_status cand_pcc cand_st1 cand_st2 cand_city cand_st cand_zip'''.split()),
    'committees': ('cm', 'cm.txt', '''cmte_id cmte_nm tres_nm cmte_st1 cmte_st2 cmte_city cmte_st cmte_zip cmte_dsgn cmte_tp cmte_pty_affiliation cmte_filing_freq org_tp connected_org_nm cand_id'''.split()),
    'links': ('ccl', 'ccl.txt', '''cand_id cand_election_yr fec_election_yr cmte_id cmte_tp cmte_dsgn linkage_id'''.split()),
    'contributions': ('indiv', 'itcont.txt', '''cmte_id amndt_ind rpt_tp transaction_pgi image_num transaction_tp entity_tp name city state zip_code employer occupation transaction_dt transaction_amt other_id tran_id file_num memo_cd memo_text sub_id'''.split()),
}


def rows_from_zip(path, member, columns):
    """Preserve every source field as text; blanks become SQL NULL. No quoting in FEC files."""
    with zipfile.ZipFile(path) as archive:
        names = [n for n in archive.namelist() if Path(n).name.lower() == member]
        if len(names) != 1:
            raise ValueError(f'{path.name}: expected exactly one {member}')
        with archive.open(names[0]) as raw:
            # Decode strictly to avoid silently replacing names or other source text.
            with io.TextIOWrapper(raw, encoding='utf-8-sig', errors='strict', newline='') as source:
                for line_no, line in enumerate(source, 1):
                    if not line.strip():
                        continue
                    row = line.rstrip('\r\n').split('|')
                    if len(row) != len(columns):
                        raise ValueError(f'{path.name}, line {line_no}: expected {len(columns)} fields, got {len(row)}')
                    yield line_no, [None if value == '' else value for value in row]


def download(cycle, prefix, directory, refresh=False):
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f'{prefix}{str(cycle)[-2:]}.zip'
    url = f'https://www.fec.gov/files/bulk-downloads/{cycle}/{target.name}'
    if refresh or not target.exists():
        temporary = target.with_suffix('.zip.part')
        print(f'Downloading {url}', flush=True)
        try:
            request = urllib.request.Request(url, headers={'User-Agent': 'FEC-personal-project/1.0'})
            with urllib.request.urlopen(request, timeout=120) as response, temporary.open('wb') as out:
                size = response.headers.get('Content-Length')
                if size:
                    print(f'Archive size: {int(size)/1024**2:,.1f} MiB', flush=True)
                shutil.copyfileobj(response, out, length=1024*1024)
            if not zipfile.is_zipfile(temporary):
                raise ValueError('Download was not a ZIP archive')
            temporary.replace(target)
        finally:
            temporary.unlink(missing_ok=True)
    else:
        print(f'Using cached {target}', flush=True)
    return target, url


def ingest(conn, table, cycle, path, url):
    from psycopg import sql
    _, member, columns = SPECS[table]
    target = sql.Identifier('fec', table)
    fields = ['cycle', 'source_line'] + columns
    identifiers = sql.SQL(', ').join(map(sql.Identifier, fields))
    with conn.transaction():
        with conn.cursor() as cur:
            # Serialize imports made by this script, including metadata updates.
            cur.execute('SELECT pg_advisory_xact_lock(721039, 1)')
            cur.execute('CREATE SCHEMA IF NOT EXISTS fec')
            defs = sql.SQL(', ').join(sql.SQL('{} text').format(sql.Identifier(c)) for c in columns)
            cur.execute(sql.SQL('CREATE TABLE IF NOT EXISTS {} (cycle integer NOT NULL, source_line bigint NOT NULL, {}, PRIMARY KEY (cycle, source_line))').format(target, defs))
            cur.execute('''CREATE TABLE IF NOT EXISTS fec.imports (
                dataset text NOT NULL, cycle integer NOT NULL, source_url text NOT NULL,
                row_count bigint NOT NULL, imported_at timestamptz NOT NULL DEFAULT now(),
                PRIMARY KEY(dataset, cycle))''')
            # The delete and COPY commit together. Any error restores the old cycle.
            cur.execute(sql.SQL('DELETE FROM {} WHERE cycle = %s').format(target), (cycle,))
            count = 0
            with cur.copy(sql.SQL('COPY {} ({}) FROM STDIN').format(target, identifiers)) as copy:
                for line_no, row in rows_from_zip(path, member, columns):
                    copy.write_row([cycle, line_no] + row)
                    count += 1
                    if count % 250000 == 0:
                        print(f'  {table}: {count:,} rows streamed (not committed yet)', flush=True)
            if count == 0:
                raise ValueError(f'{table}: empty source; old records retained')
            for column in {'candidates': ['cand_id'], 'committees': ['cmte_id'], 'links': ['cand_id', 'cmte_id'], 'contributions': ['cmte_id', 'state']}[table]:
                cur.execute(sql.SQL('CREATE INDEX IF NOT EXISTS {} ON {} (cycle, {})').format(
                    sql.Identifier(f'{table}_{column}_idx'), target, sql.Identifier(column)))
            cur.execute('''INSERT INTO fec.imports(dataset, cycle, source_url, row_count)
                VALUES (%s, %s, %s, %s) ON CONFLICT(dataset, cycle) DO UPDATE
                SET source_url=excluded.source_url, row_count=excluded.row_count, imported_at=now()''',
                (table, cycle, url, count))
    with conn.cursor() as cur:
        cur.execute(sql.SQL('ANALYZE {}').format(target))
    print(f'Committed {count:,} rows into fec.{table}', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cycle', type=int, default=2024)
    parser.add_argument('--datasets', nargs='+', choices=list(SPECS), default=['candidates', 'committees', 'links'])
    parser.add_argument('--data-dir', type=Path, default=PROJECT_ROOT / 'data')
    parser.add_argument('--config', type=Path, default=PROJECT_ROOT / 'config.json')
    parser.add_argument('--refresh', action='store_true', help='Download a fresh snapshot instead of using cached ZIPs')
    args = parser.parse_args()
    if args.cycle < 1980 or args.cycle > 2098 or args.cycle % 2:
        parser.error('--cycle must be an even year between 1980 and 2098; file availability varies')
    try:
        import psycopg
    except ImportError:
        parser.exit(1, 'Install dependencies first: py -m pip install -r requirements.txt\n')
    config = json.loads(args.config.read_text(encoding='utf-8-sig'))
    allowed = {'host', 'port', 'dbname', 'user', 'sslmode', 'connect_timeout'}
    if set(config) - allowed:
        parser.error('Unexpected config keys. Store no password in config.json.')
    if config.get('dbname') != 'fec_project':
        parser.error('Use dbname fec_project in config.json for this project.')
    password = os.environ.get('PGPASSWORD') or getpass.getpass('PostgreSQL password (hidden): ')
    # Autocommit outside each explicit per-file transaction.
    with psycopg.connect(**config, password=password, autocommit=True) as conn:
        print('Connected to fec_project.', flush=True)
        for name in dict.fromkeys(args.datasets):
            path, url = download(args.cycle, SPECS[name][0], args.data_dir, args.refresh)
            ingest(conn, name, args.cycle, path, url)
    print('Done. Refresh the fec schema in DBeaver.', flush=True)


def run():
    try:
        main()
    except KeyboardInterrupt:
        sys.exit('\nCancelled. The active file import was rolled back; earlier files remain committed.')
    except Exception as error:
        # Do not dump connection strings, credentials, or donor rows into logs.
        print(f'Import failed ({type(error).__name__}).', file=sys.stderr)
        print('Check your connection/configuration, download, disk space, and file format. '
              'The active file transaction is rolled back; previously committed files remain.', file=sys.stderr)
        if isinstance(error, (ValueError, FileNotFoundError, zipfile.BadZipFile, UnicodeError)):
            print(str(error), file=sys.stderr)
        sys.exit(1)
