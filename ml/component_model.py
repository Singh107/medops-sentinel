from __future__ import annotations

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.model_selection import GroupShuffleSplit

from ml.component_preprocess import FEATURE_COLUMNS, prepare_training_frame

ROOT = Path(__file__).resolve().parents[1]
MODELS_DIR = ROOT / "models"
MODELS_DIR.mkdir(parents=True, exist_ok=True)

CATEGORICAL_FEATURES = ["part_type", "product_subsystem", "most_common_problem_type"]
NUMERIC_FEATURES = [c for c in FEATURE_COLUMNS if c not in CATEGORICAL_FEATURES]


def _prepare_model_input(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    model_df = df.copy()
    for col in CATEGORICAL_FEATURES:
        model_df[col] = model_df[col].fillna("Unknown")
    for col in NUMERIC_FEATURES:
        model_df[col] = pd.to_numeric(model_df[col], errors="coerce").fillna(0)
    X = model_df[FEATURE_COLUMNS].copy()
    y = model_df["replaced_within_30_days"].astype(int)
    return X, y


def _build_pipeline(model_name: str, columns: list[str] = FEATURE_COLUMNS) -> Pipeline:
    preprocessor = ColumnTransformer(
        transformers=[
            ("categorical", OneHotEncoder(handle_unknown="ignore"), [c for c in CATEGORICAL_FEATURES if c in columns]),
            ("numeric", StandardScaler(), [c for c in NUMERIC_FEATURES if c in columns]),
        ],
        remainder="drop",
    )
    if model_name == "naive_baseline":
        model = DummyClassifier(strategy="most_frequent")
    elif model_name == "logistic_regression":
        model = LogisticRegression(max_iter=5000, class_weight="balanced", solver="liblinear")
    elif model_name == "random_forest":
        model = RandomForestClassifier(
            n_estimators=300,
            max_depth=8,
            min_samples_leaf=2,
            class_weight="balanced",
            random_state=42,
            n_jobs=-1,
        )
    else:
        raise ValueError(f"Unknown model name: {model_name}")
    return Pipeline(steps=[("preprocessor", preprocessor), ("model", model)])


def _compute_metrics(y_true: pd.Series, y_prob: np.ndarray, threshold: float) -> dict:
    y_pred = (y_prob >= threshold).astype(int)
    cm = confusion_matrix(y_true, y_pred, labels=[0, 1])
    return {
        "prevalence": float(np.mean(y_true)),
        "threshold": float(threshold),
        "precision": float(precision_score(y_true, y_pred, zero_division=0)),
        "recall": float(recall_score(y_true, y_pred, zero_division=0)),
        "f1": float(f1_score(y_true, y_pred, zero_division=0)),
        "roc_auc": float(roc_auc_score(y_true, y_prob) if len(np.unique(y_true)) > 1 else 0.0),
        "pr_auc": float(average_precision_score(y_true, y_prob) if len(np.unique(y_true)) > 1 else 0.0),
        "confusion_matrix": cm.tolist(),
    }


def _choose_threshold(y_val: pd.Series, y_prob_val: np.ndarray) -> float:
    if len(np.unique(y_val)) < 2:
        return 0.5
    best_threshold = 0.5
    best_score = -1.0
    for threshold in np.linspace(0.05, 0.95, 181):
        pred = (y_prob_val >= threshold).astype(int)
        score = f1_score(y_val, pred, zero_division=0)
        if score > best_score:
            best_score = float(score)
            best_threshold = float(threshold)
    return best_threshold


def _feature_importance_for_pipeline(model_name: str, pipeline: Pipeline, feature_names: list[str]) -> list[dict]:
    if model_name == "naive_baseline":
        return []
    transformed = pipeline.named_steps["preprocessor"].get_feature_names_out()
    if model_name == "logistic_regression":
        coefs = np.asarray(pipeline.named_steps["model"].coef_).ravel()
        importances = [
            {"feature": feature, "importance": float(abs(value))}
            for feature, value in zip(transformed, coefs)
        ]
    elif model_name == "random_forest":
        importances = [
            {"feature": feature, "importance": float(value)}
            for feature, value in zip(transformed, pipeline.named_steps["model"].feature_importances_)
        ]
    else:
        return []
    importances.sort(key=lambda item: item["importance"], reverse=True)
    return importances[:10]


def _split_chronological(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    dates = np.sort(df.snapshot_time.unique())
    b1, b2 = pd.Timestamp(dates[int(len(dates)*.6)]), pd.Timestamp(dates[int(len(dates)*.8)])
    gap = pd.Timedelta(days=30)
    parts = (df[df.snapshot_time < b1-gap],
             df[(df.snapshot_time >= b1) & (df.snapshot_time < b2-gap)],
             df[df.snapshot_time >= b2])
    for part in parts:
        if part.empty or part.replaced_within_30_days.nunique() != 2:
            raise ValueError("Empty or single-class temporal partition")
    assert parts[0].snapshot_time.max()+gap < parts[1].snapshot_time.min()
    assert parts[1].snapshot_time.max()+gap < parts[2].snapshot_time.min()
    return parts


def split_summary(parts):
    return {name: {"start": str(p.snapshot_time.min()), "end": str(p.snapshot_time.max()),
                   "rows": len(p), "positive": int(p.replaced_within_30_days.sum()),
                   "positive_rate": float(p.replaced_within_30_days.mean())}
            for name, p in zip(["train", "validation", "test"], parts)}


def fit_validation(parts):
    train, val, _ = parts
    fitted, results = {}, {}
    for name in ["naive_baseline", "logistic_regression", "random_forest"]:
        pipeline = _build_pipeline(name)
        pipeline.fit(train[FEATURE_COLUMNS], train.replaced_within_30_days)
        prob = pipeline.predict_proba(val[FEATURE_COLUMNS])[:, 1]
        threshold = .5 if name == "naive_baseline" else _choose_threshold(val.replaced_within_30_days, prob)
        fitted[name] = pipeline
        results[name] = _compute_metrics(val.replaced_within_30_days, prob, threshold)
        results[name]["threshold_0_5"] = _compute_metrics(val.replaced_within_30_days, prob, .5)
    return fitted, results


def final_evaluation(fitted, validation, test):
    results = {}
    for name, pipeline in fitted.items():
        prob = pipeline.predict_proba(test[FEATURE_COLUMNS])[:, 1]
        results[name] = {
            "threshold_0_5": _compute_metrics(test.replaced_within_30_days, prob, .5),
            "selected_threshold": _compute_metrics(test.replaced_within_30_days, prob, validation[name]["threshold"])}
    return results


def evaluate_models() -> dict:
    from ml.component_preprocess import load_component_data, add_model_predictions, DATA_DIR
    dataset = prepare_training_frame()
    parts = _split_chronological(dataset)
    fitted, validation = fit_validation(parts)
    # Predeclared preference for interpretability if LR is within 0.02 AP and 0.03 F1.
    lr, rf = validation["logistic_regression"], validation["random_forest"]
    selected = "logistic_regression" if lr["pr_auc"] >= rf["pr_auc"]-.02 and lr["f1"] >= rf["f1"]-.03 else "random_forest"
    threshold = validation[selected]["threshold"]
    # Group holdout isolates all three partitions by component, independent of calendar time.
    split = GroupShuffleSplit(n_splits=1, test_size=.2, random_state=42)
    dev_idx, test_idx = next(split.split(dataset, groups=dataset.component_id))
    dev = dataset.iloc[dev_idx]
    tr, va = next(GroupShuffleSplit(n_splits=1, test_size=.25, random_state=43).split(dev, groups=dev.component_id))
    grouped = (dev.iloc[tr], dev.iloc[va], dataset.iloc[test_idx])
    assert not (set(grouped[0].component_id) & set(grouped[1].component_id))
    assert not (set(grouped[0].component_id) & set(grouped[2].component_id))
    assert not (set(grouped[1].component_id) & set(grouped[2].component_id))
    group_fitted, group_validation = fit_validation(grouped)
    recent_counts = ["errors_last_7_days", "errors_last_30_days", "errors_last_90_days", "service_attempts_30d"]
    recent = recent_counts + ["unique_problem_types_30d", "critical_errors_30d", "days_since_last_error", "error_rate_change", "most_common_problem_type"]
    history = ["previous_service_count", "previous_replacement_count", "recurring_same_problem_count", "unresolved_problem_count", "service_attempts_30d"]
    experiments = {"full": FEATURE_COLUMNS,
        "without_age": [c for c in FEATURE_COLUMNS if c not in ["part_age_days", "machine_age_years"]],
        "without_recent_errors": [c for c in FEATURE_COLUMNS if c not in recent_counts],
        "without_unresolved": [c for c in FEATURE_COLUMNS if c != "unresolved_problem_count"],
        "without_previous_service": [c for c in FEATURE_COLUMNS if c != "previous_service_count"],
        "without_recurring": [c for c in FEATURE_COLUMNS if c != "recurring_same_problem_count"],
        "age_metadata_only": ["part_type", "product_subsystem", "part_age_days", "machine_age_years"],
        "recent_behavior_only": recent, "service_history_only": history}
    ablation_pipelines, ablation_validation = {}, {}
    for name, cols in experiments.items():
        pipe = fitted["random_forest"] if name == "full" else _build_pipeline("random_forest", cols)
        if name != "full":
            pipe.fit(parts[0][cols], parts[0].replaced_within_30_days)
        prob = pipe.predict_proba(parts[1][cols])[:, 1]
        ablation_validation[name] = _compute_metrics(parts[1].replaced_within_30_days, prob, .5)
        ablation_pipelines[name] = pipe
    # Check age dominance on validation before opening the test partition.
    age_drop = ablation_validation["full"]["roc_auc"]-ablation_validation["without_age"]["roc_auc"]
    if age_drop > .15:
        raise ValueError(f"Age remains dominant on validation: AUC drop {age_drop:.3f}; investigate before test")
    # Frozen models/thresholds; one final test pass for each preregistered experiment.
    metrics = final_evaluation(fitted, validation, parts[2])
    group_metrics = final_evaluation(group_fitted, group_validation, grouped[2])
    ablation = {}
    for name, pipe in ablation_pipelines.items():
        if name == "full":
            ablation[name] = metrics["random_forest"]["threshold_0_5"]
        else:
            prob = pipe.predict_proba(parts[2][experiments[name]])[:, 1]
            ablation[name] = _compute_metrics(parts[2].replaced_within_30_days, prob, .5)
    machines, components, events = load_component_data()
    replacements = int(events.part_replaced.sum())
    payload = {"selected_model": selected, "selected_threshold": threshold,
        "selection_reason": "Validation-only: prefer LR if within 0.02 PR-AUC and 0.03 F1 of RF; otherwise RF. No test-based selection.",
        "dataset_rows": len(dataset), "actual_replacement_events": replacements,
        "target_positive_rate": float(dataset.replaced_within_30_days.mean()),
        "data": {"machines": len(machines), "subassembly_instances": len(components), "work_orders": len(events),
                 "part_replacement_work_orders": replacements, "event_replacement_rate": replacements/len(events),
                 "weekly_snapshots": len(dataset), "positive_snapshots": int(dataset.replaced_within_30_days.sum()),
                 "snapshot_prevalence": float(dataset.replaced_within_30_days.mean()),
                 "positive_snapshots_per_replacement": float(dataset.replaced_within_30_days.sum()/replacements)},
        "cadence": "Monday 00:00 every 7 days; strict pre-T history; terminal replacement; 30-day complete follow-up",
        "embargo_days": 30, "splits": split_summary(parts), "metrics": metrics,
        "model_selection_validation": validation,
        "unseen_components": {"splits": split_summary(grouped), "metrics": group_metrics, "validation": group_validation},
        "ablation": ablation, "ablation_validation": ablation_validation,
        "ablation_columns": experiments,
        "feature_columns": FEATURE_COLUMNS,
        "schema_version": "synthetic-work-orders-v1",
        "top_predictive_features": _feature_importance_for_pipeline(selected, fitted[selected], FEATURE_COLUMNS)}
    joblib.dump(fitted[selected], MODELS_DIR / "component_model.joblib")
    add_model_predictions(fitted[selected], FEATURE_COLUMNS, dataset).to_csv(DATA_DIR / "component_snapshots.csv", index=False)
    (MODELS_DIR / "component_metrics.json").write_text(json.dumps(payload, indent=2))
    return payload


if __name__ == "__main__":
    print(json.dumps(evaluate_models(), indent=2))
