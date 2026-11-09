# Publication preparation

## Public entry points

- `README.md` introduces scope, engineering choices, demo, tests, and limitations.
- `demo_app.py` uses invented aggregate data in `demo/origins.json`, without
  PostgreSQL, personal configs, or source downloads. Demo values are clearly labeled.
- `docs/images/demo-map.png` is a rendered synthetic map preview, not a live-app
  screenshot or a presentation of actual FEC findings.
- `docs/images/relationship-model.svg` shows the six enforced model relationships.
- `LICENSE` applies MIT terms to original project code and synthetic values.
  `THIRD_PARTY_NOTICES.md` documents separate FEC and map-asset provenance.

The live app retains its Maryland landing pages; contribution origins supports
any campaign state. The portfolio name is Campaign Finance Explorer, with the
Maryland focus explained rather than implying all screens were generalized.

## Files and Git history

This folder had no `.git` directory when publication preparation began. A new
local repository was initialized, so there was no existing local commit history
to inspect or purge. The supplied GitHub destination initially advertised no refs.

`.gitignore` excludes local connection configs, virtual environments, downloaded
archives, temporary test databases, reports, and common credential files. It
does not remove files already tracked in future commits. Example configs contain
non-secret defaults only. Do not overwrite existing working local configs.

Run the candidate-file audit before staging/pushing:

```powershell
.\.venv\Scripts\python.exe scripts/audit_repository.py
git status --short
git diff --cached --stat
git diff --cached
```

The audit examines Git's tracked/nonignored candidate paths, refuses selected
local-only artifacts, and scans text for selected credential patterns without
printing matches. It never opens ignored password files. This is a targeted check,
not proof that every possible secret is absent. Synthetic CI service credentials
are intentionally public and valid only for disposable test containers.

## GitHub workflow

Destination: https://github.com/ianhoff/FEC-Data-Exploration

Pushing `.github/workflows/tests.yml` triggers four Python/PostgreSQL combinations.
The README badge reports actual workflow state. Inspect failing logs and fix
compatibility issues before describing the hosted matrix as verified. A local
pass or a workflow file alone is not evidence of a successful GitHub run.

For later changes, review the staged diff and let tests pass before merging.
The project remains local-only; publishing source does not expose PostgreSQL,
personal configuration, or a running application server.
