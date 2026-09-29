# Synthetic operational schema

All records are fictional and informed by general service-workflow concepts from the medical-device industry. No company records, customers, employees, serials, work-order text, locations, proprietary codes, or product names are source material. No external API or LLM generates text.

## Relationships

Machine -> subassembly instance -> work orders. A machine also reaches each work order through its subassembly. The subsystem is the taxonomy parent of the affected subassembly.

- `machines.machine_id` is the primary key and equals the synthetic top-level serial (`SIM-0001`).
- `components.component_id` is a stable instance key (`SUB-SIM-0001`), with a machine foreign key.
- `(machine_id, affected_sub_assembly)` is unique in this single-instance simulation. Names alone are not identities.
- `work_orders.work_order_number` is the primary key (`WO-SIM-000001`); `component_id` is its foreign key.
- Work-order machine ID, subsystem and affected-subassembly name are derived by joins; normalized CSVs avoid repeating this metadata. API histories expose them.
- `component_snapshots` has primary key `(component_id, snapshot_time)` and is derived ML data, not raw operational data.
- A Part Replacement ends the instance at `resolved_on`; no successor installation is simulated.

## Files and columns

### `machines.csv`

`machine_id`, `top_level_serial_number`, `model`, `installation_date`, `status_as_of`, `age`, `system_status`

### `components.csv`

`component_id`, `machine_id`, `affected_sub_assembly`, `product_subsystem`, `installation_date`, `observation_end`

### `work_orders.csv`

`work_order_number`, `component_id`, `created_date`, `investigated_on`, `resolved_on`, `closed_on`, `order_type`, `subject`, `description`, `investigation_description`, `resolution_description`, `system_status`, `order_status`, `record_type`, `problem_category`, `severity`, `resolution_code`, `start_of_downtime`, `end_of_downtime`, `total_downtime_hours`, `time_to_close`, `age`

### `component_snapshots.csv`

`snapshot_time`, `component_id`, `machine_id`, `part_type`, `product_subsystem`, `part_age_days`, `machine_age_years`, `errors_last_7_days`, `errors_last_30_days`, `errors_last_90_days`, `unique_problem_types_30d`, `critical_errors_30d`, `days_since_last_error`, `previous_service_count`, `service_attempts_30d`, `previous_replacement_count`, `recurring_same_problem_count`, `unresolved_problem_count`, `error_rate_change`, `most_common_problem_type`, `previous_work_order_count`, `work_orders_30d`, `non_reliability_orders_30d`, `open_work_order_count`, `downtime_hours_30d`, `historical_downtime_hours`, `system_down_count_30d`, `previous_repair_count`, `previous_restart_count`, `replaced_within_30_days`, `risk_probability`, `risk_label`, `recommendation`

## Field semantics and availability

- Machine `age` is years at `status_as_of`; work-order `age` is machine age in years at creation. API subassembly `age` is years at the displayed historical prediction. None represents work-order duration. A year is 365.25 days.
- `created_date` records initial order type, problem category and triage severity. `investigated_on` makes investigation text available; `resolved_on` makes resolution code/text available. `closed_on` is later administrative closure.
- `order_status` is Created / Investigating / Resolved / Closed at the component observation cutoff. A closed investigation can defer a problem for later work; closed does not imply a permanently corrected fault.
- `time_to_close` is hours from creation to closure, null until closed. It is not an ML feature.
- Work-order `system_status` is the machine state at creation, considering overlapping outages on every linked subassembly. It does not mean that particular work order caused downtime. Machine export status has an explicit as-of timestamp; raw export status is not a feature.
- Downtime belongs to the order that caused it. No outage means null start/end and zero hours. Completed outage duration is exactly end minus start. Ongoing outages have a start, null end and null total; elapsed duration could be derived for a specified time but is not presented as a completed total.
- Successful resolution ends the simulated outage. Another overlapping outage may keep the machine Down. Downtime recovery is simulated separately from whether a problem is permanently corrected.
- `resolution_code` is the single replacement source of truth. `part_replaced` is absent from raw CSVs and derived only in memory/compatibility API/SQLite view.
- Subject, description, investigation and resolution descriptions are short deterministic templates prefixed Synthetic. No employee, customer, complaint, patient or clinical data exists.

## Fictional hierarchy

- SIM Thermal Subsystem: SIM Circulation Unit, SIM Flow Monitor
- SIM Image Subsystem: SIM Image Controller, SIM Processing Unit
- SIM Energy Subsystem: SIM Power Unit, SIM Regulation Unit
- SIM Motion Subsystem: SIM Position Drive, SIM Alignment Monitor
- SIM Software Subsystem: SIM Control Application, SIM Configuration Service
- SIM Network Subsystem: SIM Network Interface, SIM Message Gateway

## Simulation

Seeds are 101 for machines, 202 for subassemblies and 303 for work orders. Thirty-six staggered machines each receive eight distinct types sampled from the fictional taxonomy. Each instance is followed for at most 540 days. No simultaneous work orders are created on the same instance, but machine-wide orders may overlap.

Daily order opportunities retain stochastic recent-history feedback with a modest age term. Category weights differ for software/network versus other fictional subsystems. Reliability histories include Maintenance Issue, Hardware Issue and Software Issue; feature requests, preventive, configuration and training are separately counted. Severity, outage probability, investigation delay, resolution delay and closure delay have stochastic variation.

Replacement uses the accepted bounded-history sigmoid: intercept -4.2, smooth age contribution up to 0.60, bounded contributions for errors (0.30), critical events (0.35), failed/deferred history (0.45 and 0.35), recurrence (0.40), prior orders (0.30), type-independent base 0.15, and latent condition plus decision noise (each standard deviation 1). Software/configuration replacement probability is multiplied by 0.20. Feature requests, preventive and training are non-replacement categories in this prototype; hardware/maintenance resolutions overlap across repairs, reboots, investigation and replacement. Parameters were fixed before inspecting model results.

Investigation starts 1?24 hours after creation. Resolution takes an additional bounded lognormal duration, and closure follows 1?36 hours later. Milestones beyond the observation cutoff remain unknown/null. Closed work orders have exactly derived time_to_close. Downtime ends at the observed resolution time when an outage occurred.

One generator simplification remains: resolved orders free the instance after administrative closure and eventual replacement ends follow-up. A deferred-investigation resolution may restore operation without proving the underlying problem gone. Different component observation endpoints mean an export is a synthetic historical record, not synchronized live fleet monitoring.

## ML and evaluation

Monday midnight predictions retain the accepted 30-day horizon. Features use timestamps strictly before T; the target is 1 iff a work order linked to that instance has resolution_code = Part Replacement and T < resolved_on <= T+30 days. Creation can precede T; the replacement is still future if resolution occurs later. No label is derived from creation or closure dates. Complete 30-day follow-up is required.

The 60% and 80% positions in sorted unique weekly dates define boundaries B1/B2. Train keeps T < B1-30d, validation B1 <= T < B2-30d, test T >= B2. Both gaps are purged, yielding 35-day separation between retained Monday dates. The final test is scored once per prespecified model/ablation after choices are frozen. All preprocessing fits train only.

Thresholds maximize validation F1 on 0.05?0.95 in 0.005 increments. LR is preferred if its validation average precision is within 0.02 of RF and F1 within 0.03; otherwise RF. Majority baseline retains 0.50. The serialized model is the exact training-only pipeline, not a later refit. PR-AUC means average precision. Secondary group holdout isolates component IDs across 60/20/20 splits, not machines or sites. RF ablations are retained as diagnostics; no test-driven generator changes.

Every feature and excluded raw field is documented in [feature_audit.md](feature_audit.md). Old API feature names such as errors_last_30_days remain compatibility labels for reliability work-order counts. No raw resolution/closure/text/export-status fields enter the model.

## Application and future scope

Existing endpoint paths remain. SQLite contains the three normalized raw tables, derived snapshots and a read-only service_events compatibility view. The obsolete service_events CSV is removed. Legacy telemetry experiments remain separate and unused by the operational application; their generated identifiers now use SIM-LEGACY prefixes.

Table/detail risk scores are the latest eligible historical weekly score. Prediction date and replaced-instance status are displayed. Machine state and age have their own explicit export date. Risk bands 0.40/0.70 are presentation bands, separate from the validation classification threshold. Scores are uncalibrated decision-support estimates; the UI recommends review, never commands replacement.

Complaint references, treatment interruption, verification methods/results, and order origin remain future schema extensions; no complaint or patient records were generated. PHM integration and major visual/workflow changes remain out of scope.