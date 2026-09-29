> Historical pre-migration evaluation. Current results: [schema migration report](schema_migration_report.md).

# Correction report

## Data

- machines: 36
- components: 288
- service_events: 3190
- replacement_events: 288
- event_replacement_rate: 0.090282131661442
- weekly_snapshots: 4025
- positive_snapshots: 1167
- snapshot_prevalence: 0.28993788819875776
- positive_snapshots_per_replacement: 4.052083333333333

## Snapshot design

Monday midnight, every 7 days. Strict pre-T history; target T < replacement <= T+30 days. Stop at replacement. Complete 30-day follow-up required.

Cut dates define 30-day purged intervals. Retained train/validation and validation/test dates are separated by 35 days. Thresholds/model choice use validation only; test scored once after freezing choices.

{
  "train": {
    "start": "2021-04-19 00:00:00",
    "end": "2023-02-13 00:00:00",
    "rows": 2705,
    "positive": 790,
    "positive_rate": 0.2920517560073937
  },
  "validation": {
    "start": "2023-03-20 00:00:00",
    "end": "2023-10-02 00:00:00",
    "rows": 910,
    "positive": 257,
    "positive_rate": 0.2824175824175824
  },
  "test": {
    "start": "2023-11-06 00:00:00",
    "end": "2024-06-24 00:00:00",
    "rows": 184,
    "positive": 64,
    "positive_rate": 0.34782608695652173
  }
}

All 4,025 rows passed independent feature/target/lifecycle checks. Boundary unit test passes.

Weekly rows increased from 3,515 to 4,025 because quiet periods and components without history are now represented. Correlation decreased for all seven audited features against the same-generator event comparator. Against the old generator, six decreased but lifetime recurrence increased from 0.979 to 0.987. Weekly scheduling does not ensure independence.

## Temporal model results

| Model | Threshold | Prevalence | Precision | Recall | F1 | ROC-AUC | PR-AUC (AP) | CM [[TN,FP],[FN,TP]] |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| naive_baseline (0.50) | 0.500 | 0.348 | 0.000 | 0.000 | 0.000 | 0.500 | 0.348 | [[120, 0], [64, 0]] |
| naive_baseline (selected) | 0.500 | 0.348 | 0.000 | 0.000 | 0.000 | 0.500 | 0.348 | [[120, 0], [64, 0]] |
| logistic_regression (0.50) | 0.500 | 0.348 | 0.510 | 0.766 | 0.613 | 0.758 | 0.563 | [[73, 47], [15, 49]] |
| logistic_regression (selected) | 0.620 | 0.348 | 0.592 | 0.703 | 0.643 | 0.758 | 0.563 | [[89, 31], [19, 45]] |
| random_forest (0.50) | 0.500 | 0.348 | 0.505 | 0.719 | 0.594 | 0.733 | 0.553 | [[75, 45], [18, 46]] |
| random_forest (selected) | 0.605 | 0.348 | 0.594 | 0.594 | 0.594 | 0.733 | 0.553 | [[94, 26], [26, 38]] |

## Unseen-component results

| Model | Threshold | Prevalence | Precision | Recall | F1 | ROC-AUC | PR-AUC (AP) | CM [[TN,FP],[FN,TP]] |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| naive_baseline (0.50) | 0.500 | 0.269 | 0.000 | 0.000 | 0.000 | 0.500 | 0.269 | [[640, 0], [236, 0]] |
| naive_baseline (selected) | 0.500 | 0.269 | 0.000 | 0.000 | 0.000 | 0.500 | 0.269 | [[640, 0], [236, 0]] |
| logistic_regression (0.50) | 0.500 | 0.269 | 0.474 | 0.784 | 0.591 | 0.788 | 0.580 | [[435, 205], [51, 185]] |
| logistic_regression (selected) | 0.405 | 0.269 | 0.440 | 0.805 | 0.569 | 0.788 | 0.580 | [[398, 242], [46, 190]] |
| random_forest (0.50) | 0.500 | 0.269 | 0.485 | 0.763 | 0.593 | 0.778 | 0.547 | [[449, 191], [56, 180]] |
| random_forest (selected) | 0.470 | 0.269 | 0.475 | 0.767 | 0.587 | 0.778 | 0.547 | [[440, 200], [55, 181]] |

## Ablation

| RF experiment | ROC-AUC | PR-AUC (AP) |
|---|---:|---:|
| full | 0.733 | 0.553 |
| without_age | 0.735 | 0.531 |
| without_recent_errors | 0.729 | 0.566 |
| without_unresolved | 0.737 | 0.556 |
| without_previous_service | 0.751 | 0.565 |
| without_recurring | 0.740 | 0.565 |
| age_metadata_only | 0.513 | 0.377 |
| recent_behavior_only | 0.754 | 0.528 |
| service_history_only | 0.760 | 0.624 |

Age no longer dominates. Recent behavior and service history each carry useful signal; individual drops are small or improve performance, so ablation does not demonstrate independent benefit from every feature. No further adjustment was made based on test results.

## Model selection

Logistic Regression, threshold 0.62. Validation AP 0.581 vs RF 0.537; F1 0.612 vs 0.626. The prespecified interpretability preference selects LR. Temporal/unseen test AP is 0.563/0.580 for LR and 0.553/0.547 for RF. This is limited single-seed evidence, not a formal stability study. Exact train-only pipeline retained.

## Application

Backend 8001 and frontend 5173 respond. All nine GET endpoint routes return HTTP 200. Production build passes. Pipeline predictions match scored CSV, SQLite, component table/detail/risk APIs, and selected-model metrics JSON. Reseed orchestration tested with mocks; generation, training and SQLite reseeding executed separately. Browser rendering/console validation could not be completed: browser-control inventory reports no available browsers. Only verified MedOps backend processes restarted; MealMind untouched. No redesign, UI features, or PHM integration.

## Limitations

- Synthetic, single-seed process; all 288 instances eventually replace. Rates do not describe real equipment.
- Only 184 temporal test rows, 64 positive; weekly overlapping horizons remain dependent.
- Group holdout isolates component IDs, not machines/sites; temporal cohort composition changes.
- Class-weighted scores are uncalibrated. Threshold selection is statistical F1, not operational cost.
- Lifetime history proxies remain correlated; unresolved count represents historical failed service, not current backlog.
- Dashboard presents each instance's last historical score, including replaced instances; 0.40/0.70 display bands differ from the 0.62 binary evaluation threshold.
- Browser render and console/runtime checks remain unverified.
- No proprietary company data, patient data, clinical validation, or autonomous maintenance claim.
