# Local operations and setup

A local Python/PostgreSQL project for FEC ingestion, relational modeling, SQL
analysis, and a Streamlit interface. Ingestion is nationwide; app queries focus
on Maryland congressional campaigns.

## Start or refresh an existing installation

From the project folder in PowerShell:

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Open [the local app](http://127.0.0.1:8501). Existing installations do not need
account setup, virtual-environment creation, or reimporting on each startup.

- **Ctrl+R in the browser:** reload the page. Streamlit's **Rerun** reruns the app.
- **Refresh data in the sidebar:** rerun queries and clear the contribution
  aggregate cache. It does not download, reimport, or rebuild models.
- **After imported-module changes** (for example `origins.py`), if old behavior or
  an unexpected-keyword error persists, press **Ctrl+C** in the Streamlit terminal,
  rerun the startup command, then refresh the browser. A browser refresh alone
  cannot guarantee a Python module reload.

## Developer documentation

### Portable automated tests

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -m "not integration"
```

This runs synthetic unit and offline map-rendering tests without your database or
FEC downloads. PostgreSQL integration tests require an explicit empty disposable
`fec_test_*` database via `FEC_TEST_DSN`; run the full suite with `pytest --require-db`.
See [testing setup and safeguards](testing.md) before configuring that target.
The GitHub Actions workflow runs the complete suite with ephemeral PostgreSQL
services and saves test/coverage reports. Existing `check_*.py` scripts remain
separate local snapshot checks; pytest does not collect them.

Build the validated relationship model after importing the three small datasets:

```powershell
.\.venv\Scripts\python.exe build_model.py
.\.venv\Scripts\python.exe check_model.py
.\.venv\Scripts\python.exe export_schema.py
```

The model uses cycle-aware master keys and six enforced foreign keys in
`fec_model`, while preserving unmatched links separately. It keeps raw tables
intact. Refresh `fec_model` in DBeaver and open its ER diagram to see the enforced
relationships. `verify_model.sql` contains inspection queries. The model retains
source field types; date/amount conversions and contributions modeling remain
future work. Rebuild after raw refreshes; optionally select `--cycle 2024`.

- [AGENTS.md](../AGENTS.md): working rules, commands, credentials, and data safeguards.
- [Architecture](architecture.md): components, ingestion lifecycle, application behavior, and limitations.
- [Data model](data-model.md): table grain, keys, relationships, and analysis semantics.
- [Field dictionary](data-dictionary.json): structured descriptions for every importer-defined column.
- [Raw-layer decision](decisions/0001-raw-ingestion-and-local-explorer.md) and
  [relationship-model decision](decisions/0002-enforced-relationship-snapshots.md): rationale and consequences.

Generate a live catalog snapshot with `.\.venv\Scripts\python.exe export_schema.py`.
It writes `docs/schema.snapshot.json` with columns, constraints, and indexes;
it does not export table records or password-file contents.

## Local data explorer

**Contribution origins** maps reported contribution records to House/Senate
principal campaign committee IDs in any selected campaign state (50 states plus
DC, default Maryland). This selects the state of the race, not contributor state.
Select archive and candidate election year,
campaign, date range, and either reported amount or record count. The map shows
50 states plus DC, with Alaska/Hawaii insets, hover details, state totals, and CSV
exports. Other locations and excluded/invalid dates are reported separately.
The selected campaign state is gray and excluded from the color scale and
tooltip-share denominator by default. A toggle restores it. Overall totals, state
tables, and CSV exports still include that state; its total is shown separately.
All transaction types, memos, and amendments remain included; sums are exploratory,
not official fundraising totals. See [analysis policy](data-model.md#contribution-origins-analysis-policy).
The selected cycle must already have contributions imported. No downloads run from
the app. Initial queries may take a few minutes; aggregates cache for five minutes.
The feature requires PostgreSQL 16+ (the current local server is PostgreSQL 18).
Map boundaries are bundled locally with attribution in `assets/README.md`.

Run `.\.venv\Scripts\python.exe check_origins.py` for map SQL edge cases and live
UI checks. The live missing-data check currently expects no 2022 contributions.

The default Maryland overview shows congressional candidates running in Maryland,
with separate archive-cycle and candidate-election-year controls. The election year
defaults to the archive year when available. Races & candidates filters House
districts and statewide Senate candidates and includes candidate profiles,
principal committees, and reported committee links. Links retain missing committee
references and show all relationship election years within the selected archive.
Party and race counts describe candidate records, not election results or ballot
qualification. National Overview, Explore tables, and Data quality remain available.

Install the optional app dependencies and start the local interface:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-app.txt
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Open http://127.0.0.1:8501 in your browser. Stop the server with Ctrl+C.
The app uses config.analysis.json and your Windows PostgreSQL password file.
Ordinary queries use read-only transactions with a 15-second timeout. Contribution
aggregation uses read-only transactions with a 180-second timeout and a five-minute
cache keyed by selection and source import metadata. Refresh data clears that cache.
The existing project account still has modeling privileges outside the app.
The server binds only to your computer's loopback address; it is a local dev tool.

Overview shows live row counts, import metadata, and candidate office counts.
Explore tables supports literal name/ID searches, candidate state/office filters,
100-row pages, CSV downloads of the current page, and parameterized SQL previews.
Data quality shows identifier checks, all unmatched links with CSV export, and
the election-year profile. No raw rows are dropped or corrected.
The archive cycle filter does not restrict candidate election year.
Contribution origins queries already imported contributions; it never downloads them.

For the initial 2024 snapshot, run the live screen smoke check with:
`.\.venv\Scripts\python.exe check_app.py`
Expected-count assertions in that check are specific to the initial imported snapshot.

The contribution check assumes 2024 contributions and a 2022 archive without
contributions; review these assumptions if source data changes. For actual chart
rendering (beyond simulated Streamlit checks), install developer dependencies:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe check_map_render.py
```

The offline SVG check verifies 51 state/DC shapes, valid colors/legends, and the
selected-state exclusion. It does not replace a browser layout review. `check_model.py`
reconciles masters/links and tests invalid references in rollback-only transactions.

This runs on YOUR computer, where PostgreSQL is installed. It does not connect to DBeaver: both Python and DBeaver connect to fec_project.
Requires Python 3.10+ and an existing PostgreSQL database named fec_project.

## Windows: first run

1. Open the project folder in File Explorer, type powershell in the address bar, and press Enter.
2. Check Python: `py --version`. If unavailable, install Python from https://www.python.org/downloads/windows/ and reopen PowerShell. If your installation uses `python` instead of `py`, substitute that command below.
3. Create an isolated environment only if `.venv` does not already exist:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe ingest_fec.py
```

No environment activation or PowerShell execution-policy change is needed.
The script asks for your PostgreSQL password; typing will be invisible. Press Enter when done. config.json contains only non-secret connection settings. Edit those settings if your working DBeaver connection differs.

The default command downloads and loads the smaller candidates, committees, and links files for 2024. Each file commits separately. It creates schema fec with tables candidates, committees, links, plus an imports tracking table.

4. After the small import, provision analysis access once before running the app
   or building models:

```powershell
.\.venv\Scripts\python.exe setup_db_access.py
```

This prompts locally for the admin password and a different new project password.
It creates `fec_project_user`, the owned `fec_model` schema, and
`config.analysis.json`. The password is stored outside the repository at
`%APPDATA%\postgresql\pgpass.conf` with restricted Windows permissions. The file
contains plain-text credentials: let libpq use it; never print or commit it.
Do not send passwords in chat. Setup aborts if the role exists and must not be
rerun automatically. Database and password-file changes are not one transaction;
inspect any partial failure before trying again.

5. Install `requirements-app.txt` and start the app using the commands above.
The contribution-map feature requires PostgreSQL 16+; the local project has run
with Python 3.14 and PostgreSQL 18, without implying all other combinations were tested.

### Add another archive cycle

```powershell
.\.venv\Scripts\python.exe ingest_fec.py --cycle 2022
```

Other cycles are retained. The app discovers imported cycles from `fec.imports`
after a rerun. A cycle can appear before all its datasets are imported. Historical
availability and layouts must be validated; an accepted year argument alone does
not establish compatibility. After refreshing raw datasets, rerun `build_model.py`
for those cycles to refresh the separate model snapshots.

## View in DBeaver

Refresh the fec_project connection. Expand Schemas → fec → Tables. If fec is hidden, enable it in the connection's schema filter. Open explore.sql in the SQL editor attached to fec_project and run the first queries individually. Queries referencing contributions work only after the next step.

## Add contributions when ready

```powershell
.\.venv\Scripts\python.exe ingest_fec.py --datasets contributions
```

IMPORTANT: this downloads the full national 2024 individual-contributions archive, not just Maryland. It can require a large download, substantial database/WAL disk space, and a long import. It streams rows to bound Python memory, but PostgreSQL still needs disk space. The script reports archive size when the server supplies it and prints progress every 250,000 rows. There is no sample or Maryland-only mode in this starter. Complete the small import first.

## Repeat runs and failure handling

The importer owns these fec tables. For each selected file it replaces that cycle's records atomically; it does not append duplicates. Do not manually edit imported rows you want preserved. Other cycles are retained. It serializes imports from this script to avoid concurrent replacements.

ZIP downloads are cached in data. To fetch a fresh snapshot:

```powershell
.\.venv\Scripts\python.exe ingest_fec.py --datasets candidates committees links --refresh
```

To replace contributions with a fresh snapshot, explicitly select contributions
and use `--refresh`. A corrupt cached ZIP can also be replaced with `--refresh`.
Cancelled imports restart from the beginning; they do not resume mid-file.
Parsing/COPY failures roll back the active dataset transaction; earlier datasets
remain committed. Rerun after addressing the failure.
ANALYZE runs after commit, so its failure can be reported after data was saved.
Check tracking/counts rather than assuming every failure implies rollback.
Partial-download cleanup runs on normal exception handling; abrupt process
termination can leave `.part` files behind. Downloads display no ongoing progress;
a growing `.part` file indicates transfer progress. The cache retains only one
archive per dataset/cycle, not historical versions or source checksums.

## Data design: intentionally a raw ingestion layer

Every FEC column is retained as text in its published order, with lowercase column names. Empty fields become NULL; other whitespace is retained. cycle and source_line are added; together they are the primary key. source_line identifies an input-file row, not a stable transaction across refreshed downloads.

Dates (MMDDYYYY) and amounts remain raw text. The SQL examples show guarded conversion of amounts to exact numeric values. Create validated typed tables/views as your next modeling step. No foreign keys are enforced at this raw layer: missing references and duplicate business identifiers should be profiled before imposing clean-model constraints. Indexes support cycle + candidate/committee joins and contribution state filtering.

The source SUB_ID is retained; TRAN_ID is not assumed globally unique. The script preserves all source records: it does not resolve amendments, deduplicate donations, identify unique people, remove memo rows, attribute joint fundraising, or calculate official fundraising totals. A sum of raw records is not automatically a campaign's funds raised. The individual bulk file is a subset of disclosed itemized contributions, not every donation.

Sources and field dictionaries:
- https://www.fec.gov/data/browse-data/?tab=bulk-data
- https://www.fec.gov/campaign-finance-data/candidate-master-file-description/
- https://www.fec.gov/campaign-finance-data/committee-master-file-description/
- https://www.fec.gov/campaign-finance-data/candidate-committee-linkage-file-description/
- https://www.fec.gov/campaign-finance-data/contributions-individuals-file-description/
- https://www.psycopg.org/psycopg3/docs/basic/copy.html

Archive URL pattern: https://www.fec.gov/files/bulk-downloads/2024/cn24.zip
Other prefixes: cm24.zip, ccl24.zip, indiv24.zip. Expected members: cn.txt, cm.txt, ccl.txt, itcont.txt.

## Troubleshooting

- Connection refused: check the PostgreSQL service and host/port.
- Authentication failed: use the credentials that worked in DBeaver.
- No module named psycopg: run the dependency install with the same .venv Python.
- Permission denied for schema/database: the configured user needs CREATE on fec_project.
- On a strict UTF-8 decoding failure or field-count error, the import stops rather than silently altering source data. Share only the diagnostic/file name, never donor rows or passwords.

End-to-end local imports, relationship-model builds, live app/query checks, and
offline map rendering checks have been run during development. These are historical
results, not guarantees for refreshed snapshots. The November 2026 contribution
load contained 58,210,165 reported records, not unique donors. Inspect current
tracking cheaply with `SELECT cycle, row_count, imported_at FROM fec.imports WHERE dataset='contributions';`.
