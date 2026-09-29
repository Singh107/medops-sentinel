# Synthetic operational schema migration report

## Synthetic operational schema

All records were generated locally using general service-workflow concepts. No company records, proprietary text, real identities or external datasets were used. Raw operational records and derived ML snapshots are separate.

**machines.csv**: `machine_id`, `top_level_serial_number`, `model`, `installation_date`, `status_as_of`, `age`, `system_status`.

**components.csv**: `component_id`, `machine_id`, `affected_sub_assembly`, `product_subsystem`, `installation_date`, `observation_end`.

**work_orders.csv**: `work_order_number`, `component_id`, `created_date`, `investigated_on`, `resolved_on`, `closed_on`, `order_type`, `subject`, `description`, `investigation_description`, `resolution_description`, `system_status`, `order_status`, `record_type`, `problem_category`, `severity`, `resolution_code`, `start_of_downtime`, `end_of_downtime`, `total_downtime_hours`, `time_to_close`, `age`.

`component_snapshots.csv`: weekly prediction keys, all 26 audited features, future replacement label and saved model risk outputs. Full column-level semantics: [synthetic schema](../docs/synthetic_schema.md).

## Relationships

`machines.machine_id` (SIM-0001) -> `components.machine_id`; `components.component_id` (SUB-SIM-0001) -> `work_orders.component_id`. Work orders have unique WO-SIM identifiers. Machine + affected_sub_assembly is unique in this single-instance simulation. Subsystem/type labels are joined into work-order API views rather than duplicated in raw exports. SQLite enforces keys and foreign keys.

## Generation logic

Work-order categories have different synthetic frequencies and resolution options. Hardware/maintenance can resolve through repair, reboot, investigation or replacement. Software/configuration sometimes require Part Replacement (39 observed in this run). Feature requests, preventive service and training have no replacement resolutions in this simplified prototype. Machine Down probability depends on severity plus random variation; overlapping subassembly outages determine the machine state at each creation time.

Downtime and time_to_close are derived from timestamp differences. Created -> investigated -> resolved -> closed timestamps are ordered, with unavailable milestones null at the observation cutoff. Four orders remain not closed. Work-order age is machine age in years at creation; component age and machine age are calculated separately for predictions.

Replacement retains modest age, bounded history effects and unobserved component/decision noise. No parameter was tuned against this run's model scores. Replacement is observed only when resolution_code is Part Replacement; backward-compatible part_replaced is derived. A replacement ends that tracked instance.

## ML target

At Monday midnight T, label 1 iff the same instance has `resolution_code == "Part Replacement"` with `T < resolved_on <= T+30 days`; otherwise 0 when full follow-up exists. Work-order creation and closure do not define the replacement event. Strictly pre-T feature history, terminal instances, 30-day follow-up and temporal embargo are retained.

Train is before B1-30d; validation B1 through before B2-30d; test begins B2. Unique weekly dates set the 60%/80% cut positions. Retained periods are separated by 35 days. Test predictions were computed only after validation model/threshold selection. No post-test tuning.

## Feature audit

| Feature | Available at prediction time? | Used? | Reason / gate |
|---|---|---|---|
| `part_type` | Yes, subject to timestamp gate | Yes | Alias of affected_sub_assembly; static installed type, not an ID. |
| `product_subsystem` | Yes, subject to timestamp gate | Yes | Static taxonomy parent of the installed subassembly. |
| `part_age_days` | Yes, subject to timestamp gate | Yes | T minus subassembly installation date, in days. |
| `machine_age_years` | Yes, subject to timestamp gate | Yes | T minus machine installation date divided by 365.25 days. |
| `errors_last_7_days` | Yes, subject to timestamp gate | Yes | Reliability-type work orders created in [T-7d,T); legacy API name. |
| `errors_last_30_days` | Yes, subject to timestamp gate | Yes | Reliability-type work orders created in [T-30d,T). |
| `errors_last_90_days` | Yes, subject to timestamp gate | Yes | Reliability-type work orders created in [T-90d,T). |
| `unique_problem_types_30d` | Yes, subject to timestamp gate | Yes | Distinct creation-time problem categories for reliability orders in [T-30d,T). |
| `critical_errors_30d` | Yes, subject to timestamp gate | Yes | Creation-time triage severity >=4 on reliability orders in [T-30d,T). |
| `days_since_last_error` | Yes, subject to timestamp gate | Yes | Days since latest reliability order created before T; 999 if none. |
| `previous_service_count` | Yes, subject to timestamp gate | Yes | Count of resolutions whose resolved_on < T; does not require later administrative closure. |
| `service_attempts_30d` | Yes, subject to timestamp gate | Yes | Resolution count with resolved_on in [T-30d,T). |
| `previous_replacement_count` | Yes, subject to timestamp gate | Yes | Count of Part Replacement resolutions with resolved_on < T; zero for terminal instances. |
| `recurring_same_problem_count` | Yes, subject to timestamp gate | Yes | Largest lifetime count of a creation-time problem category among prior reliability orders. |
| `unresolved_problem_count` | Yes, subject to timestamp gate | Yes | Orders created before T still awaiting resolution, plus prior resolutions logged for further investigation; not a verified backlog. |
| `error_rate_change` | Yes, subject to timestamp gate | Yes | Reliability creation count in last 15 days minus preceding 15 days, divided by 15 (orders/day). |
| `most_common_problem_type` | Yes, subject to timestamp gate | Yes | Mode of creation-time problem categories in recent 30-day reliability history; lexical tie break. |
| `previous_work_order_count` | Yes, subject to timestamp gate | Yes | All orders created before T, regardless of category. |
| `work_orders_30d` | Yes, subject to timestamp gate | Yes | All orders created in [T-30d,T). |
| `non_reliability_orders_30d` | Yes, subject to timestamp gate | Yes | Feature, preventive, configuration and training orders created in [T-30d,T), separately counted. |
| `open_work_order_count` | Yes, subject to timestamp gate | Yes | Created before T with no resolution known strictly before T; resolved-but-not-closed orders are excluded. |
| `downtime_hours_30d` | Yes, subject to timestamp gate | Yes | Overlap with [T-30d,T) of intervals whose end is already known (end_of_downtime < T); excludes unfinished intervals. |
| `historical_downtime_hours` | Yes, subject to timestamp gate | Yes | Sum of completed subassembly downtime intervals with end_of_downtime < T; never raw eventual total. |
| `system_down_count_30d` | Yes, subject to timestamp gate | Yes | Number of this subassembly's downtime starts in [T-30d,T); other machine outages are not counted. |
| `previous_repair_count` | Yes, subject to timestamp gate | Yes | Adjustment / Repair outcomes gated by resolved_on < T. |
| `previous_restart_count` | Yes, subject to timestamp gate | Yes | Reboot / Restart outcomes gated by resolved_on < T. |


All 7,801 rows and 26 features independently reconstructed; 100 future-field mutations preserve earlier features; four boundary/leakage unit tests pass. All work-order keys, hierarchy, lifecycle, downtime, source-of-truth, machine-state and age checks pass. Raw generation is reproducible within numeric CSV round-trip precision. Excluded field details: [feature audit](../docs/feature_audit.md).

## Dataset

| Measure | Value |
|---|---:|
| machines | 36 |
| subassembly_instances | 288 |
| work_orders | 5,406 |
| part_replacement_work_orders | 276 |
| event_replacement_rate | 5.1054% |
| weekly_snapshots | 7,801 |
| positive_snapshots | 1,155 |
| snapshot_prevalence | 14.8058% |
| positive_snapshots_per_replacement | 4.185 |

## Model results

PR-AUC means average precision. Confusion matrices are [[TN,FP],[FN,TP]]. Threshold selection is validation-only.

| Split | Dates | Rows | Positives | Prevalence |
|---|---|---:|---:|---:|
| train | 2021-04-05 to 2023-06-12 | 6296 | 849 | 13.485% |
| validation | 2023-07-17 to 2024-03-18 | 1131 | 222 | 19.629% |
| test | 2024-04-22 to 2025-01-20 | 71 | 18 | 25.352% |

### Temporal validation

| Model / point | Threshold | Prevalence | Precision | Recall | F1 | ROC-AUC | PR-AUC | Confusion matrix |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| naive_baseline / 0.50 | 0.500 | 0.196 | 0.000 | 0.000 | 0.000 | 0.500 | 0.196 | [[909, 0], [222, 0]] |
| naive_baseline / selected | 0.500 | 0.196 | 0.000 | 0.000 | 0.000 | 0.500 | 0.196 | [[909, 0], [222, 0]] |
| logistic_regression / 0.50 | 0.500 | 0.196 | 0.284 | 0.847 | 0.425 | 0.701 | 0.308 | [[434, 475], [34, 188]] |
| logistic_regression / selected | 0.490 | 0.196 | 0.285 | 0.869 | 0.429 | 0.701 | 0.308 | [[425, 484], [29, 193]] |
| random_forest / 0.50 | 0.500 | 0.196 | 0.284 | 0.757 | 0.413 | 0.680 | 0.295 | [[486, 423], [54, 168]] |
| random_forest / selected | 0.465 | 0.196 | 0.283 | 0.842 | 0.424 | 0.680 | 0.295 | [[436, 473], [35, 187]] |

### Untouched temporal test

| Model / point | Threshold | Prevalence | Precision | Recall | F1 | ROC-AUC | PR-AUC | Confusion matrix |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| naive_baseline / threshold_0_5 | 0.500 | 0.254 | 0.000 | 0.000 | 0.000 | 0.500 | 0.254 | [[53, 0], [18, 0]] |
| naive_baseline / selected_threshold | 0.500 | 0.254 | 0.000 | 0.000 | 0.000 | 0.500 | 0.254 | [[53, 0], [18, 0]] |
| logistic_regression / threshold_0_5 | 0.500 | 0.254 | 0.327 | 1.000 | 0.493 | 0.659 | 0.321 | [[16, 37], [0, 18]] |
| logistic_regression / selected_threshold | 0.490 | 0.254 | 0.321 | 1.000 | 0.486 | 0.659 | 0.321 | [[15, 38], [0, 18]] |
| random_forest / threshold_0_5 | 0.500 | 0.254 | 0.278 | 0.278 | 0.278 | 0.644 | 0.399 | [[40, 13], [13, 5]] |
| random_forest / selected_threshold | 0.465 | 0.254 | 0.367 | 0.611 | 0.458 | 0.644 | 0.399 | [[34, 19], [7, 11]] |

### Secondary unseen-component test

| Model / point | Threshold | Prevalence | Precision | Recall | F1 | ROC-AUC | PR-AUC | Confusion matrix |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| naive_baseline / threshold_0_5 | 0.500 | 0.146 | 0.000 | 0.000 | 0.000 | 0.500 | 0.146 | [[1315, 0], [224, 0]] |
| naive_baseline / selected_threshold | 0.500 | 0.146 | 0.000 | 0.000 | 0.000 | 0.500 | 0.146 | [[1315, 0], [224, 0]] |
| logistic_regression / threshold_0_5 | 0.500 | 0.146 | 0.282 | 0.826 | 0.421 | 0.761 | 0.278 | [[845, 470], [39, 185]] |
| logistic_regression / selected_threshold | 0.475 | 0.146 | 0.274 | 0.844 | 0.414 | 0.761 | 0.278 | [[814, 501], [35, 189]] |
| random_forest / threshold_0_5 | 0.500 | 0.146 | 0.311 | 0.790 | 0.446 | 0.790 | 0.329 | [[922, 393], [47, 177]] |
| random_forest / selected_threshold | 0.415 | 0.146 | 0.281 | 0.879 | 0.426 | 0.790 | 0.329 | [[811, 504], [27, 197]] |

### Selection

**Logistic Regression, threshold 0.49.** Validation AP 0.308 vs RF 0.295, F1 0.429 vs 0.424, ROC-AUC 0.701 vs 0.680. LR remains selected under the accepted validation/interpretability rule. RF has higher test AP, but test performance did not influence selection. The exact training-only pipeline is retained.

### Retained RF ablation diagnostics

| Experiment | ROC-AUC | PR-AUC |
|---|---:|---:|
| full | 0.644 | 0.399 |
| without_age | 0.431 | 0.219 |
| without_recent_errors | 0.679 | 0.391 |
| without_unresolved | 0.672 | 0.356 |
| without_previous_service | 0.637 | 0.412 |
| without_recurring | 0.673 | 0.373 |
| age_metadata_only | 0.764 | 0.611 |
| recent_behavior_only | 0.654 | 0.321 |
| service_history_only | 0.392 | 0.208 |

## Application

Backend 8001 and frontend 5173 return HTTP 200. All nine existing GET routes pass. Reseed route orchestration is tested with subprocess mocks; real generation, training and SQLite migration executed separately. The fixed synthetic seed parameter is now explicit (303). Saved pipeline, CSV scores, SQLite rows, component table/detail/risk APIs and selected-model metrics agree. Production build passes.

Frontend changes are limited to terminology and existing detail/history bindings: subsystem, subassembly age in years, machine status/age with as-of date, historical prediction date, downtime, work-order ID/type and resolution code. Decision-support wording and synthetic disclosure remain. Browser rendering/console validation is blocked by an empty browser-control inventory, so no runtime-render claim is made. Only the verified MedOps backend was restarted; MealMind ports/processes were not modified.

## Privacy / proprietary check

Owned MedOps source, documents, generated CSV/JSON and SQLite were inspected; third-party dependency packages were excluded from record review. No real company records or identifiers were added or found in the reviewed operational data. All generated subjects/descriptions/investigation/resolution text have Synthetic prefixes and are produced from visible local templates.

Preexisting product-like model labels were replaced by SIM-MODEL identifiers. Retained legacy telemetry IDs now use SIM-LEGACY prefixes. The obsolete service_events CSV was removed; a derived SQLite compatibility view replaces it. No unrelated user files were deleted. Pattern/provenance review is evidence of synthetic construction, not proof that generic vocabulary never occurs elsewhere. Public software/dependency references are retained.

## Limitations

- One synthetic seed; 276 of 288 instances eventually replace, with no successor installation or replacement inventory workflow.
- Temporal test has only 71 rows and 18 positives; estimates are unstable and correlated weekly rows do not represent independent trials.
- Validation/test prevalence and cohort composition differ; calendar-date fractions are not row fractions.
- Group holdout isolates component instances, not machines or sites.
- Simplified categories, no simultaneous work orders on one instance, limited open orders and no ongoing outage in this generated export.
- Unresolved/deferred counts are proxies, not a verified issue backlog; history features are correlated.
- Class-weighted scores are uncalibrated and F1-selected thresholds do not represent operational costs.
- Dashboard scores are dated historical scores; machine export state is a separate as-of view, not live monitoring.
- Browser render and console checks remain unverified.
- No proprietary/patient data, real-equipment rate claim, clinical validity, complaint MVP, PHM integration or major UI redesign.
