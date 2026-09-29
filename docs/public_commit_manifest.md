# Proposed first public commit manifest

Report only; Git is not initialized. Existing root README is included as a candidate
but needs the separately planned final revision before publication. No LICENSE exists
yet. Sizes are uncompressed file bytes, not Git history or dependency installations.

**Proposed contents: 75 files, approximately 6.31 MB (6.02 MiB).**

## SOURCE

- `backend/__init__.py`
- `backend/database/db.py`
- `backend/main.py`
- `backend/services/component_service.py`
- `frontend/index.html`
- `frontend/src/App.tsx`
- `frontend/src/main.tsx`
- `frontend/src/review.ts`
- `frontend/src/styles.css`
- `ml/__init__.py`
- `ml/component_model.py`
- `ml/component_preprocess.py`
- `ml/generate_service_data.py`
- `ml/public_validation/scania_component_x/__init__.py`
- `ml/public_validation/scania_component_x/evaluate.py`
- `ml/public_validation/scania_component_x/inspect_data.py`
- `ml/public_validation/scania_component_x/loader.py`
- `ml/public_validation/scania_component_x/model.py`
- `ml/public_validation/scania_component_x/preprocess.py`
- `ml/public_validation/scania_component_x/report.py`
- `scripts/prepare_scania_reproduction.py`

## DEMO DATA / MODEL

- `data/component_snapshots.csv`
- `data/components.csv`
- `data/machines.csv`
- `data/work_orders.csv`
- `models/component_metrics.json`
- `models/component_model.joblib`

## DOCUMENTATION

- `docs/feature_audit.md`
- `docs/frozen_demo_and_reproduction.md`
- `docs/public_commit_manifest.md`
- `docs/synthetic_schema.md`
- `ml/public_validation/scania_component_x/protocol.md`
- `ml/public_validation/scania_component_x/README.md`
- `models/correction_report.md`
- `models/schema_migration_report.md`
- `README.md`

## TESTS / AUDITS

- `frontend/scripts/qa-review.mjs`
- `ml/audit_components.py`
- `ml/public_validation/scania_component_x/test_integrity.py`
- `ml/public_validation/scania_component_x/verify_features.py`
- `ml/test_component_snapshots.py`
- `ml/verify_application.py`
- `models/application_validation.json`
- `models/artifact_manifest.json`
- `models/leakage_audit.json`
- `models/previous_snapshot_audit.json`
- `models/privacy_check.json`
- `models/reproducibility_check.json`

## SCANIA PUBLIC-VALIDATION EVIDENCE

- `data/public/scania_component_x/v3/manifest.json`
- `models/public_validation/scania_component_x/completion_verification.json`
- `models/public_validation/scania_component_x/data_audit.json`
- `models/public_validation/scania_component_x/feature_verification.json`
- `models/public_validation/scania_component_x/freeze.json`
- `models/public_validation/scania_component_x/interpretability.json`
- `models/public_validation/scania_component_x/metrics.json`
- `models/public_validation/scania_component_x/report.md`
- `models/public_validation/scania_component_x/test_evaluation_started.json`
- `models/public_validation/scania_component_x/test_preaudit.json`
- `models/public_validation/scania_component_x/test_predictions.csv`
- `models/public_validation/scania_component_x/test_sampling.json`
- `models/public_validation/scania_component_x/train_sample_selection.csv`
- `models/public_validation/scania_component_x/train_sampling.json`
- `models/public_validation/scania_component_x/validation_metrics.json`
- `models/public_validation/scania_component_x/validation_preaudit.json`
- `models/public_validation/scania_component_x/validation_predictions.csv`
- `models/public_validation/scania_component_x/validation_sampling.json`

## DEPENDENCY / BUILD FILES

- `.gitignore`
- `frontend/package-lock.json`
- `frontend/package.json`
- `frontend/tsconfig.app.json`
- `frontend/tsconfig.json`
- `frontend/tsconfig.node.json`
- `frontend/vite.config.ts`
- `ml/public_validation/scania_component_x/requirements.txt`
- `requirements.txt`

## Major exclusions

- `.venv/`, `venv/`, Python caches, `.pytest_cache/`: local dependencies/caches.
- `frontend/node_modules/`, `frontend/dist/`, `*.tsbuildinfo`: dependencies/build output.
- `.vscode/settings.json`, `.env`, `.env.*` (except `.env.example`), editor/OS/temp files: local configuration and secrets.
- `data/medops.db` and database journals: runtime SQLite, recreated from frozen CSVs.
- `*.log`: runtime/training/audit logs; existing JSON/Markdown evidence is retained.
- `data/public/scania_component_x/v3/raw/`: approximately 1.652 GB of official CSV downloads.
- `data/public/scania_component_x/v3/documentation/`: downloaded PDFs, extracted text and temporary PDF tooling.
- `models/public_validation/scania_component_x/*_features.csv`: approximately 94.7 MB of generated matrices.
- `models/public_validation/scania_component_x/*.joblib`: approximately 10.4 MB fitted pipeline bundle.
- `reproductions/`: all independent research workspaces and their artifacts.
- Deleted legacy telemetry source/data/models and generated Vite JS/declarations are absent.

## Evidence interpretation

Accepted synthetic CSVs/model/metrics and all retained historical reports are
unchanged. Historical correction/privacy reports describe their original scope;
the schema migration report represents the later accepted synthetic application.
Scania's report honestly records a weak external result, not operational utility.
The original Scania sources/protocol/requirements and all 34 freeze checksums
remain intact. Historical Windows paths inside evidence intentionally remain.
Scania data attribution is separate from the future MedOps source license.

## Cleanup verification

- Production build passed with `vite.config.ts` as the sole Vite config; generated JS/declarations did not return.
- Backend localhost:8001 and frontend localhost:5173 returned HTTP 200.
- All nine application GET routes passed the existing frontend QA script.
- All backend/component/Scania source, audit and test modules imported successfully.
- Four snapshot boundary tests passed using in-memory fixtures.
- Saved model predictions match snapshots; all four SQLite tables match their CSVs; compatibility view remains present.
- Retained synthetic artifacts, metrics, reports, Scania result files and root README match the pre-cleanup byte hashes.
- All 34 accepted Scania freeze checksums passed; data were hashed as opaque bytes, not evaluated or used for decisions.
- Independent workspace preparation copied exact source, resolved an isolated root and refused overwrite; temporary smoke-check workspace was removed.
- No training, generation, public experiment, application redesign, deployment or Git initialization occurred. MealMind was untouched.
- Browser rendering was not part of this cleanup verification.
