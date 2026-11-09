# Automated testing

## Portable suite versus local smoke checks

`tests/` contains synthetic pytest tests. They do not depend on FEC downloads,
personal configuration files, imported cycles, or the `fec_project` database.
The existing root `check_*.py` scripts remain optional local checks with their
documented snapshot assumptions. `pytest.ini` limits discovery to `tests/`, so
those scripts do not run in CI.

Install test dependencies once into the existing environment:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

Run unit and actual SVG rendering tests without PostgreSQL:

```powershell
.\.venv\Scripts\python.exe -m pytest -m "not integration"
```

Run unit tests without rendering with `-m "not integration and not rendering"`.
Rendering needs `vl-convert-python`, included in the developer requirements.
All map boundaries come from local assets.

## Integration database contract

Integration tests require PostgreSQL 16+ and an explicitly configured, **empty,
disposable** database named `fec_test_*`. The test role must own the database or
be able to create schemas/tables. The suite creates and drops only `fec` and
`fec_model` within that test target, once per test. It refuses targets with either
schema already present. It does not create/drop databases, provision user accounts,
or modify your project's connection files.

Set `FEC_TEST_DSN` to the test server's connection settings. For a separately
provisioned passwordless local test instance on port 55439, for example:

```powershell
$env:FEC_TEST_DSN = 'host=127.0.0.1 port=55439 dbname=fec_test_local user=fec_test_runner'
.\.venv\Scripts\python.exe -m pytest --require-db
Remove-Item Env:FEC_TEST_DSN
```

Use the actual port and authentication of your disposable instance. This example
does not start PostgreSQL or relax authentication on an existing server. Keep
local test credentials outside source control. Libpq's personal password file
and inherited `PG*` environment settings are not used by test fixtures.

Without `FEC_TEST_DSN`, normal pytest runs skip integration tests. `--require-db`
makes missing configuration a failure, as required in CI. Invalid database names,
nonlocal hosts, and PostgreSQL service-file references are rejected before opening
a connection. Never point integration tests at a database containing useful data,
even if its name starts with `fec_test_`. Do not run the suite concurrently against
the same test database; use separate targets for parallel jobs.

For a temporary-folder ACL conflict between sandboxed/elevated Windows processes,
use a fresh directory inside the ignored test area:

```powershell
.\.venv\Scripts\python.exe -m pytest --require-db --basetemp=.test-postgres/pytest-temp -p no:cacheprovider
```

Pytest owns and may clear its `--basetemp` directory. Reserve it strictly for
temporary test files. `.test-postgres/` is ignored and is not application storage.

## Test coverage by behavior

| Suite | What it verifies |
| --- | --- |
| Unit parser | All four source layouts, ordering, nulls, leading zeros, whitespace, BOM, physical line numbers, strict decoding, missing/ambiguous members, corrupt ZIPs |
| Unit download/cache | Cache reuse, successful replacement, failed-refresh preservation and `.part` cleanup, using mocked byte streams |
| Unit map data | Recipient ID deduplication, separate unknown locations, zero states, invalid exclusion codes |
| Offline rendering | All 51 state/DC shapes, color variation, finite legends, negative/zero sums, selected-state exclusion and tooltip status |
| Ingestion integration | COPY, repeat replacement, other-cycle preservation, failed replacement rollback, tracking consistency, earlier dataset commits surviving later failure |
| Model integration | Actual migrations, repeat builds, all six foreign keys, cross-cycle rejection, unresolved-link accounting, duplicate/missing masters, multi-cycle rollback, migration checksum checks |
| Origins integration | Production SQL against tiny synthetic tables: date boundaries/leap/invalid dates, exact signed amounts, invalid amounts, memo/amendment retention, recipient/cycle isolation, and shared principal IDs without multiplied transactions |

Fixtures deny normal production `psycopg.connect` calls, personal config reads,
and Python download access. Only the guarded integration fixture opens its explicit
test connection. The production model builder and contribution aggregator accept
caller-supplied connections so tests exercise real SQL without calling CLI setup.

## Reports and CI

```powershell
.\.venv\Scripts\python.exe -m pytest --require-db --cov=ingest_fec --cov=build_model --cov=origins --cov-branch --cov-report=term-missing --cov-report=xml --junitxml=test-results/pytest.xml
```

Coverage measures those three modules, including currently unexercised CLI paths;
it is not application-wide UI coverage and has no arbitrary percentage gate.
Reports and temporary files are ignored by Git.

`.github/workflows/tests.yml` runs on pushes, pull requests, and manual dispatch.
It combines Python 3.11/3.14 with PostgreSQL 16/18 service containers. Each job
gets an empty `fec_test_ci` database and synthetic service-only credentials; no
personal secrets are needed. Jobs require integration tests instead of accepting
silent skips. JUnit and coverage XML are uploaded even when tests fail, when
reports are available.

The workflow must run on GitHub to verify the complete Linux/version matrix.
A local Windows pass does not establish that all CI combinations passed.
