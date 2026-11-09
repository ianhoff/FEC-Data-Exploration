# Developer and agent guide

## Project purpose

Public entry point: `demo_app.py` is a database-free synthetic demo; never replace
its invented values with real donor extracts. Live operations are documented in
`docs/operations.md`. Before staging, run `scripts/audit_repository.py` and review
the Git candidate list. Personal configs and generated extracts must stay ignored.

Local Windows learning project for Python ingestion, PostgreSQL relational modeling,
SQL analysis, and a Streamlit campaign-finance explorer. The UI defaults to Maryland
House/Senate candidates; ingestion remains nationwide. Read [architecture](docs/architecture.md)
and [data model](docs/data-model.md) before changing ingestion, joins, or analysis.
Column definitions are in [the data dictionary](docs/data-dictionary.json).

## Working commands (PowerShell, project root)

Portable tests: read [testing guide](docs/testing.md). Use
`.\.venv\Scripts\python.exe -m pytest -m "not integration"` for synthetic unit/rendering
tests; the full suite uses `--require-db` and explicit `FEC_TEST_DSN` targeting an
empty disposable local `fec_test_*` database. Never use personal configs for tests.
Do not run root `check_*.py` scripts as part of portable CI. Test cleanup drops
its synthetic `fec`/`fec_model` schemas; useful data must never live in that target.

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-app.txt
.\.venv\Scripts\python.exe -m streamlit run app.py
.\.venv\Scripts\python.exe -m py_compile app.py ingest_fec.py setup_db_access.py export_schema.py
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe check_app.py
.\.venv\Scripts\python.exe export_schema.py
.\.venv\Scripts\python.exe build_model.py
.\.venv\Scripts\python.exe check_model.py
.\.venv\Scripts\python.exe check_origins.py
.\.venv\Scripts\python.exe check_map_render.py
```

Do not recreate a working virtual environment. `check_app.py` uses live PostgreSQL
and expects the original 2024 counts; it is a snapshot-specific smoke check, not
a portable fixture test. It covers Maryland screens, filters, national tables,
search parameter binding, and quality metrics. Inspect its assertions before using
it after a source refresh. Use `verify_import.sql` for database integrity checks.
No browser appearance check is implied by passing simulated Streamlit tests.
For choropleth changes, install `requirements-dev.txt` and run the offline SVG
render check too; schema validation alone cannot detect empty geographic output.

## Credentials and permissions

- `config.json`: importer connection (normally `postgres`); no password keys.
- `config.analysis.json`: application/modeling connection (`fec_project_user`);
  no passwords. Use this account for routine queries and model work.
- Let libpq authenticate using the existing Windows password file. Never open,
  print, copy, or commit its contents, and never ask for passwords in chat.
- App queries request read-only transactions: ordinary queries have a 15-second
  timeout; contribution aggregation has a 180-second timeout. The role itself owns
  `fec_model` and is not globally read-only.
- `setup_db_access.py` is a one-time, interactive provisioning script. Do not rerun
  it as a repair or startup step; it aborts if the role exists and is not atomic
  across database changes and password-file creation.
- Permission/network failures may require the execution environment's normal
  escalation mechanism. Do not bypass it or change authentication protections.

## Data rules

- Join raw tables using both `cycle` and the relevant FEC identifier.
- Archive cycle, candidate election year, transaction date, and download/import
  time are different concepts. Do not substitute one for another.
- Preserve all nonblank raw records, source order, IDs, leading zeros, dates,
  amounts, and memo fields. Empty source fields become NULL; do not silently trim,
  replace decoding errors, deduplicate, or correct unusual source values.
- Raw primary keys are `(cycle, source_line)`; source_line is snapshot-relative.
  Business-key uniqueness must be checked per imported snapshot.
- Missing candidate/committee references are retained. No raw foreign keys exist.
  Do not add enforced relationships without profiling and an explicit unresolved-
  reference strategy. See the data-model document.
- Contributions are reported transaction records, not unique people. There is no
  stable individual-donor ID here; `tran_id` is not globally unique.
- Do not drop memo records, resolve amendments, or attribute linked committee
  funds to candidates without an explicit, documented analysis policy.
- Contribution origins uses the policy in docs/data-model.md: distinct
  principal recipient IDs for the selected campaign state (default Maryland),
  all raw transaction/memo/amendment types retained,
  date inclusion checks and unmapped locations visible. Its aggregate query has a
  180-second timeout and five-minute metadata-keyed cache; ordinary app queries
  retain the 15-second timeout. No persisted contribution model is implied.
- Nationwide contributions require explicit user authorization and a discussion
  of download/storage requirements. Never include them in an incidental test.

## Implementation boundaries

- `ingest_fec.py` owns raw `fec` tables. Reruns replace a selected cycle atomically
  per dataset, not the entire multi-dataset run. Preserve this behavior.
- Put validated typed models in `fec_model`; do not mutate raw values to clean them.
- `build_model.py` now manages versioned model migrations and snapshot refreshes.
  Applied migration SQL is immutable; add a new migration for changes. Run
  `check_model.py` after model changes, then regenerate the schema snapshot.
  The relationship model keeps descriptive source columns as text; it does not
  yet type dates/amounts or model contributions. Unresolved links remain separate.
- Bind all user-supplied SQL values. Dynamic identifiers must come from fixed lists
  or use `psycopg.sql.Identifier`. Do not add an unrestricted SQL runner to the UI.
- App stays local on `127.0.0.1`; publishing or remote database access is separate work.
- Do not log credentials or donor rows. Summarize counts and safe diagnostics.
- Schema changes require a deliberate migration: CREATE TABLE IF NOT EXISTS does
  not upgrade existing tables. Refresh the schema snapshot after approved changes.
- Update architecture/model/dictionary docs when their corresponding behavior changes.
  Capture consequential choices in `docs/decisions/`; distinguish proposals from
  implemented features. Do not introduce checksums or pipeline run history in docs
  as if implemented: neither source-file checksums nor full run history currently
  exists. Applied SQL migration checksums are implemented and are a separate concept.

## Documentation navigation

- [Architecture and operations](docs/architecture.md)
- [Data model and interpretation](docs/data-model.md)
- [Structured field dictionary](docs/data-dictionary.json)
- [Portable tests and CI](docs/testing.md)
- [Raw-layer decision](docs/decisions/0001-raw-ingestion-and-local-explorer.md)
- [Relationship-model decision](docs/decisions/0002-enforced-relationship-snapshots.md)
- `docs/schema.snapshot.json`: generated live catalog, if exported; no table rows.
