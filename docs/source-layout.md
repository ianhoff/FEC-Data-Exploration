# Source layout

```text
src/fec_explorer/
  ingestion.py          ZIP parsing, download/cache, COPY, importer CLI
  modeling.py           Versioned model migration and refresh
  database.py           Live read-only query helper
  origins.py            Contribution SQL and map rendering
  application.py        Streamlit navigation and safe error handling
  pages/                Overview, exploration, quality, Maryland, contributions
  access.py             Interactive one-time database-role setup
  schema_export.py      Read-only schema export
  paths.py              Checkout-local paths
  resources/            Bundled TopoJSON and upstream license
```

`pyproject.toml` configures the package, dependency extras, and console commands.
Install from the checkout using `python -m pip install -e .`; `requirements*.txt`
also installs it in editable mode. App/test dependencies can be installed with
`python -m pip install -e ".[app,dev]"`. Changes to Python source take effect
without reinstalling, though Streamlit may need restarting after module edits.

Use `from fec_explorer.ingestion import rows_from_zip` and other package imports.
Root `ingest_fec.py`, `build_model.py`, `setup_db_access.py`, and `export_schema.py`
retain CLI compatibility; `app.py` and `demo_app.py` remain Streamlit entrypoints.
There is no longer a root `origins.py`. Installed console commands include
`fec-ingest`, `fec-build-model`, and `fec-export-schema`.

Tests live outside `src/`, use installed package imports, and have no pytest
`pythonpath` override. Existing root `check_*.py` files are still optional local
checks. Migrations, SQL exploration scripts, documentation, and synthetic demo
aggregates remain checkout files. Applied migrations were not rewritten or moved.

`paths.PROJECT_ROOT` resolves to the checkout for an editable install. Override it
with `FEC_PROJECT_DIR` when operating against another project directory. With a
wheel install it falls back to the current working directory. Configs, cached
downloads, migrations, and generated exports belong to that project directory;
they are not silently embedded in an installed package. Full app/demo entrypoints
and migration operations still use the repository checkout.

The map uses importlib.resources and is included with its ISC attribution in a
built wheel, so rendering does not depend on the working directory or a public
map-data URL. CI verifies both editable-package tests and wheel resource loading.
