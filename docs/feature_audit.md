# Feature availability audit

Prediction cutoff is strict: timestamps equal to T are excluded from history. The target uses resolution time, not work-order creation or closure time. All features below are reconstructed from raw tables; no raw final-status columns are copied into snapshots.

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

| Raw field / group | Available at prediction time? | Used? | Reason |
|---|---|---|---|
| IDs, serials, model labels | At installation/creation | No | Join keys and display only; prevent identifier memorization. |
| order_type, problem_category, severity | At creation | Aggregates only | Simulated initial triage fields, never later investigation findings. |
| resolution_code | Only after resolved_on | Historical counts only; future target separately | Unknown outcomes cannot enter predictors. |
| resolved_on | Only when resolution occurs | Gates history / defines target | Future time never becomes a feature. |
| subject, description | At creation | No | Controlled synthetic UI text only. |
| investigation_description, investigated_on | At investigation | No | Excluded even when historical. |
| resolution_description | At resolution | No | Excluded text to prevent direct outcome leakage. |
| closed_on, time_to_close, order_status | Closure / export time | No | Final administrative state can be future information. |
| start_of_downtime | At outage start | Historical count only | Strictly before T. |
| end_of_downtime | At outage end | Completed intervals only | Future ends and totals cannot enter features. |
| total_downtime_hours | At completed outage end | No direct use | Recomputed from already-known interval endpoints. |
| machine age/system_status/status_as_of in export | At export as-of date | No | Age is independently calculated at T; export status is display-only. |
| work-order age | At creation | No | Machine age at order creation, not elapsed order duration. |
| latent condition / random decision noise | Never observed | No | Exists only inside generator, never exported. |

Automated evidence: `python -m unittest ml.test_component_snapshots`; `python -m ml.audit_components`. Independent feature reconstruction covers every snapshot and feature. Mutation checks alter unknown resolution, downtime, closure, status, text and remove future orders without changing earlier feature vectors.