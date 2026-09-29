from __future__ import annotations
from pathlib import Path
import pandas as pd
from ml.generate_service_data import DATE_COLUMNS, RELIABILITY_TYPES
ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
FEATURE_COLUMNS = [
    "part_type", "product_subsystem", "part_age_days", "machine_age_years",
    "errors_last_7_days", "errors_last_30_days", "errors_last_90_days",
    "unique_problem_types_30d", "critical_errors_30d", "days_since_last_error",
    "previous_service_count", "service_attempts_30d", "previous_replacement_count",
    "recurring_same_problem_count", "unresolved_problem_count", "error_rate_change",
    "most_common_problem_type", "previous_work_order_count", "work_orders_30d",
    "non_reliability_orders_30d", "open_work_order_count", "downtime_hours_30d",
    "historical_downtime_hours", "system_down_count_30d", "previous_repair_count", "previous_restart_count",
]


def load_component_data():
    machines = pd.read_csv(DATA_DIR / "machines.csv",parse_dates=["installation_date","status_as_of"])
    components = pd.read_csv(DATA_DIR / "components.csv",parse_dates=["installation_date","observation_end"])
    orders = pd.read_csv(DATA_DIR / "work_orders.csv",parse_dates=DATE_COLUMNS)
    # Compatibility fields are derived in memory; raw work orders have one outcome source.
    orders["part_replaced"] = orders.resolution_code.eq("Part Replacement").astype(int)
    return machines, components, orders


def features_at(component, machine, orders, t):
    """Only creation-known fields and explicitly timestamp-gated outcomes enter features."""
    h = orders[orders.created_date < t]
    reliability = h[h.order_type.isin(RELIABILITY_TYPES)]
    windows = {n: reliability[reliability.created_date >= t-pd.Timedelta(days=n)] for n in [7,30,90]}
    recent = windows[30]
    known = h[h.resolved_on.notna() & (h.resolved_on < t)]
    recent_known = known[known.resolved_on >= t-pd.Timedelta(days=30)]
    # Only completed downtime intervals are used; no eventual total from ongoing outages.
    downtime = h[h.end_of_downtime.notna() & (h.end_of_downtime < t)]
    total_hours = (downtime.end_of_downtime-downtime.start_of_downtime).dt.total_seconds().sum()/3600
    clipped_start = downtime.start_of_downtime.clip(lower=t-pd.Timedelta(days=30))
    recent_hours = ((downtime.end_of_downtime-clipped_start).dt.total_seconds()/3600).clip(lower=0).sum()
    mode = recent.problem_category.mode()
    first_half = reliability[(reliability.created_date>=t-pd.Timedelta(days=30)) & (reliability.created_date<t-pd.Timedelta(days=15))]
    last_half = reliability[reliability.created_date>=t-pd.Timedelta(days=15)]
    open_count = len(h)-len(known)
    return {
        "part_type":component.affected_sub_assembly, "product_subsystem":component.product_subsystem,
        "part_age_days":(t-component.installation_date).days,
        "machine_age_years":(t-machine.installation_date).total_seconds()/(86400*365.25),
        **{f"errors_last_{n}_days":len(w) for n,w in windows.items()},
        "unique_problem_types_30d":recent.problem_category.nunique(),
        "critical_errors_30d":int(recent.severity.ge(4).sum()),
        "days_since_last_error":(t-reliability.created_date.max()).days if len(reliability) else 999,
        "previous_service_count":len(known), "service_attempts_30d":len(recent_known),
        "previous_replacement_count":int(known.resolution_code.eq("Part Replacement").sum()),
        "recurring_same_problem_count":int(reliability.groupby("problem_category").size().max()) if len(reliability) else 0,
        "unresolved_problem_count":open_count+int(known.resolution_code.eq("Issue Logged for Further Investigation").sum()),
        "error_rate_change":(len(last_half)-len(first_half))/15,
        "most_common_problem_type":mode.iloc[0] if len(mode) else "No recent problem",
        "previous_work_order_count":len(h),
        "work_orders_30d":int((h.created_date>=t-pd.Timedelta(days=30)).sum()),
        "non_reliability_orders_30d":int(((h.created_date>=t-pd.Timedelta(days=30)) & ~h.order_type.isin(RELIABILITY_TYPES)).sum()),
        "open_work_order_count":open_count,
        "downtime_hours_30d":float(recent_hours), "historical_downtime_hours":float(total_hours),
        "system_down_count_30d":int(((h.start_of_downtime>=t-pd.Timedelta(days=30)) & (h.start_of_downtime<t)).sum()),
        "previous_repair_count":int(known.resolution_code.eq("Adjustment / Repair").sum()),
        "previous_restart_count":int(known.resolution_code.eq("Reboot / Restart").sum()),
    }


def build_component_snapshot_dataset(cadence="weekly"):
    machines,components,orders = load_component_data()
    machines = machines.set_index("machine_id")
    rows=[]
    for component in components.itertuples(index=False):
        own=orders[orders.component_id.eq(component.component_id)].sort_values("created_date")
        replacements=own.loc[own.resolution_code.eq("Part Replacement"),"resolved_on"].dropna()
        terminal=replacements.min() if len(replacements) else component.observation_end
        dates=pd.date_range(component.installation_date,component.observation_end-pd.Timedelta(days=30),freq="W-MON")
        if cadence=="event": dates=own.created_date
        for t in dates:
            if t>=terminal or t+pd.Timedelta(days=30)>component.observation_end: continue
            features=features_at(component,machines.loc[component.machine_id],own,t)
            rows.append({"snapshot_time":t,"component_id":component.component_id,"machine_id":component.machine_id,
                         **features,"replaced_within_30_days":int(((replacements>t)&(replacements<=t+pd.Timedelta(days=30))).any())})
    return pd.DataFrame(rows)


def prepare_training_frame() -> pd.DataFrame:
    snapshot_df = build_component_snapshot_dataset()
    if snapshot_df.empty:
        return snapshot_df
    return snapshot_df


def add_model_predictions(model: object, model_columns: list[str], dataset: pd.DataFrame | None = None) -> pd.DataFrame:
    frame = dataset if dataset is not None else prepare_training_frame()
    if frame.empty:
        return frame
    feature_frame = frame[model_columns].copy()
    if hasattr(model, "predict_proba"):
        probabilities = model.predict_proba(feature_frame)[:, 1]
    else:
        probabilities = model.decision_function(feature_frame)
    frame = frame.copy()
    frame["risk_probability"] = probabilities
    frame["risk_label"] = frame["risk_probability"].apply(
        lambda value: "HIGH RISK" if value >= 0.7 else "MONITOR" if value >= 0.4 else "LOW RISK"
    )
    frame["recommendation"] = frame["risk_probability"].apply(
        lambda value: "Review recommended." if value >= 0.4 else "Continue monitoring."
    )
    return frame


def save_snapshot_dataset(model: object | None = None) -> pd.DataFrame:
    dataset = prepare_training_frame()
    if model is not None:
        dataset = add_model_predictions(model, FEATURE_COLUMNS, dataset)
    dataset.to_csv(DATA_DIR / "component_snapshots.csv", index=False)
    return dataset


if __name__ == "__main__":
    df = save_snapshot_dataset()
    print(f"Saved {len(df)} component snapshot rows.")
