# Frozen demo and independent research

## Default application startup

From the repository root on Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
npm.cmd --prefix frontend ci
.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8001
```

In a second terminal at the repository root:

```powershell
npm.cmd --prefix frontend run dev -- --host 127.0.0.1 --port 5173
```

On POSIX use `.venv/bin/python` and `npm` instead. Backend startup creates/seeds
the ignored SQLite database from the committed frozen CSVs. It does not train
or generate data. Preserve the four synthetic CSVs, component model, metrics
and artifact manifest together. Do not invoke POST `/api/seed` for frozen-demo
startup: that research endpoint regenerates data and retrains.

Production build: `npm.cmd --prefix frontend run build`.

## Optional synthetic research commands (not startup)

These are documentation for a future separately authorized research copy.
Generation/training overwrite accepted artifacts; do not run them in the frozen
checkout. Nothing in this cleanup executes them.

```text
python -m ml.generate_service_data
python -m ml.component_model
```

Snapshot boundary tests: `python -m unittest ml.test_component_snapshots`.
Full audit: `python -m ml.audit_components` (writes audit outputs).
Application verification: `python -m ml.verify_application` (writes its report;
requires running servers). Keep those output-writing audits in a research copy
when preserving accepted evidence byte for byte.

## Independent Scania reproduction

Accepted evidence remains at `models/public_validation/scania_component_x/`;
the original acquisition manifest remains under `data/public/scania_component_x/v3/`.
The original Python sources, protocol, requirements and all accepted evidence
are unchanged. The accepted result is weak and is not operationally useful.

A fresh clone also contains the accepted freeze seal. Therefore **do not run
download, preprocessing or modelling in the application checkout**, and do not
delete its seal. Instead prepare an empty, Git-ignored research workspace:

```text
python scripts/prepare_scania_reproduction.py independent-run-01
cd reproductions/independent-run-01
python -m venv .venv
```

Activate this new environment (Windows: `.venv\Scripts\Activate.ps1`; POSIX:
`source .venv/bin/activate`), then follow the Scania README's dependency install,
official download, inspection, review gate, tests, preprocessing, model, single
evaluation and report commands **from this new workspace root**. If PowerShell
activation is restricted, invoke its `.venv\Scripts\python.exe` explicitly.

The helper only copies source/documentation. It refuses existing destinations;
it does not download data, read labels, fit models or copy accepted outputs.
The unchanged loader resolves its root from the staged module location, so all
new downloads, manifests and results stay inside the independent workspace.
Do not replace accepted evidence with independent-run outputs. Reproducing a
procedure does not guarantee identical numerical results across platforms.

Historical backslashes in the accepted acquisition/freeze JSON are preserved
because they identify the original Windows run. For read-only verification on
another OS, interpret them as project-relative components (for example,
`root.joinpath(*PureWindowsPath(recorded_path).parts)`). Do not edit the evidence
or reuse those old manifests in a new run. New manifests use the local platform's
paths; executable roots and the staging helper use pathlib.

Raw data, downloaded PDFs/tools, feature matrices and fitted Scania pipelines
are excluded from publication. Small reports, prediction/sample-selection CSVs,
metrics and integrity evidence remain publishable. MedOps source code is licensed under [MIT](../LICENSE). Scania's CC BY 4.0
attribution remains separate and is retained in the Scania README.
