"""Metrics and a one-use, hash-verified sealed-test evaluation."""
from datetime import datetime, timezone
import json
import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import (average_precision_score, brier_score_loss, confusion_matrix,
                             f1_score, precision_score, recall_score, roc_auc_score)
from .loader import DATA, OUT, ROOT, sha256, write_json
from .preprocess import SEED


def metrics(y, probabilities, threshold):
    y = np.asarray(y, dtype=int)
    p = np.asarray(probabilities, dtype=float)
    predicted = p >= threshold
    edges = np.unique(np.quantile(p, np.linspace(0, 1, 11)))
    groups = np.searchsorted(edges[1:-1], p, side='right')
    calibration = []
    for group in np.unique(groups):
        mask = groups == group
        calibration.append({'n': int(mask.sum()), 'mean_prediction': float(p[mask].mean()),
                            'observed_fraction': float(y[mask].mean())})
    return {'samples': len(y), 'unique_vehicles': len(y), 'positives': int(y.sum()),
            'prevalence': float(y.mean()), 'threshold': float(threshold),
            'precision': float(precision_score(y, predicted, zero_division=0)),
            'recall': float(recall_score(y, predicted, zero_division=0)),
            'f1': float(f1_score(y, predicted, zero_division=0)),
            'roc_auc': float(roc_auc_score(y, p)) if len(np.unique(y)) == 2 else None,
            'average_precision': float(average_precision_score(y, p)) if y.sum() else None,
            'brier_score': float(brier_score_loss(y, p)),
            'confusion_matrix': confusion_matrix(y, predicted, labels=[0, 1]).tolist(),
            'mean_predicted_probability': float(p.mean()),
            'calibration_bins': calibration,
            'calibration_ece': float(sum(b['n'] * abs(b['mean_prediction'] - b['observed_fraction']) for b in calibration) / len(y))}


def bootstrap(y, p, threshold, repeats=1000):
    rng = np.random.default_rng(SEED)
    keys = ['precision', 'recall', 'f1', 'roc_auc', 'average_precision', 'brier_score']
    values = {k: [] for k in keys}
    for _ in range(repeats):
        i = rng.integers(0, len(y), len(y))
        result = metrics(np.asarray(y)[i], np.asarray(p)[i], threshold)
        for k in keys:
            if result[k] is not None:
                values[k].append(result[k])
    return {'method': 'Vehicle bootstrap; one sample per vehicle; percentile 95%; fixed fitted model and threshold',
            'replicates': repeats, 'seed': SEED,
            'intervals': {k: np.quantile(v, [.025, .975]).tolist() for k, v in values.items()}}


def verify_freeze(freeze):
    for rel, expected in freeze['sha256'].items():
        path = ROOT / rel
        if sha256(path) != expected:
            raise RuntimeError(f'Frozen artifact changed: {rel}')


def run_test():
    freeze = json.loads((OUT / 'freeze.json').read_text())
    verify_freeze(freeze)
    marker = OUT / 'test_evaluation_started.json'
    with marker.open('x', encoding='utf-8') as f:
        json.dump({'started_at_utc': datetime.now(timezone.utc).isoformat(),
                   'freeze_sha256': sha256(OUT / 'freeze.json'),
                   'notice': 'One-use seal. Do not remove to tune or silently repeat.'}, f, indent=2)
    # The only code path that parses individual test labels is below this seal.
    labels = pd.read_csv(DATA / 'raw' / 'test_labels.csv')
    table = pd.read_csv(OUT / 'test_features.csv')
    if list(labels.columns) != ['vehicle_id', 'class_label'] or labels.isna().any().any():
        raise ValueError('Unexpected test-label schema/missingness; stop and investigate')
    if labels.vehicle_id.duplicated().any() or set(labels.vehicle_id) != set(table.vehicle_id):
        raise ValueError('Test vehicles mismatch; stop and investigate')
    if not labels.class_label.isin(range(5)).all():
        raise ValueError('Unknown test class')
    table = table.merge(labels, on='vehicle_id', validate='one_to_one')
    y = (table.class_label > 0).astype(int).to_numpy()
    X = table[freeze['feature_columns']]
    bundle = joblib.load(OUT / 'pipelines.joblib')
    results = json.loads((OUT / 'validation_metrics.json').read_text())
    results['test'] = {}
    predictions = table[['vehicle_id', 'class_label']].copy()
    for name, pipeline in bundle.items():
        p = pipeline.predict_proba(X)[:, 1]
        t = freeze['thresholds'][name]
        results['test'][name] = {'default_0_5': metrics(y, p, .5), 'selected_threshold': metrics(y, p, t)}
        predictions[f'{name}_probability'] = p
        predictions[f'{name}_prediction'] = (p >= t).astype(int)
        if name == freeze['selected_model']:
            results['test_selected_model_uncertainty'] = bootstrap(y, p, t)
    results['selected_model'] = freeze['selected_model']
    results['test_label_audit'] = {'rows': len(labels), 'columns': len(labels.columns),
        'unique_vehicles': int(labels.vehicle_id.nunique()), 'duplicate_rows': int(labels.duplicated().sum()),
        'missing_values': labels.isna().sum().to_dict(),
        'class_distribution': labels.class_label.value_counts().sort_index().to_dict()}
    results['test_evaluated_at_utc'] = datetime.now(timezone.utc).isoformat()
    predictions.to_csv(OUT / 'test_predictions.csv', index=False)
    write_json(OUT / 'metrics.json', results)
    print(json.dumps({name: result['selected_threshold'] for name, result in results['test'].items()}, indent=2))


if __name__ == '__main__':
    run_test()
