"""Fit three fixed models, select on validation, and freeze before test access."""
from datetime import datetime, timezone
import json
from pathlib import Path
import platform
import warnings
import joblib
import numpy as np
import pandas as pd
import sklearn
import scipy
import threadpoolctl
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.exceptions import ConvergenceWarning
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import precision_recall_curve
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from .evaluate import metrics
from .loader import DATA, OUT, ROOT, sha256, write_json
from .preprocess import BLACKLIST, SEED
from .verify_features import verify


def select_threshold(y, p):
    precision, recall, thresholds = precision_recall_curve(y, p)
    f1 = 2 * precision[:-1] * recall[:-1] / np.maximum(precision[:-1] + recall[:-1], 1e-15)
    best = np.flatnonzero(np.isclose(f1, f1.max(), rtol=0, atol=1e-12))[-1]
    return float(thresholds[best])


def make_pipeline(estimator, numeric, categorical):
    numeric_steps = Pipeline([('impute', SimpleImputer(strategy='median', keep_empty_features=True)),
                              ('scale', StandardScaler())])
    categorical_steps = Pipeline([('impute', SimpleImputer(strategy='constant', fill_value='MISSING')),
                                  ('encode', OneHotEncoder(handle_unknown='ignore', sparse_output=False))])
    transform = ColumnTransformer([('numeric', numeric_steps, numeric),
                                   ('categorical', categorical_steps, categorical)])
    return Pipeline([('preprocess', transform), ('model', estimator)])


def fit():
    if (OUT / 'freeze.json').exists() or (OUT / 'test_evaluation_started.json').exists():
        raise RuntimeError('Experiment frozen: refusing refit')
    verify()
    train = pd.read_csv(OUT / 'train_features.csv')
    validation = pd.read_csv(OUT / 'validation_features.csv')
    categorical = [f'Spec_{i}' for i in range(8)]
    feature_columns = [c for c in train if c not in BLACKLIST]
    numeric = [c for c in feature_columns if c not in categorical]
    if len(numeric) != 219 or len(categorical) != 8:
        raise ValueError('Unexpected feature schema')
    if set(train.vehicle_id) & set(validation.vehicle_id):
        raise ValueError('Vehicle overlap')
    estimators = {
        'prevalence_baseline': DummyClassifier(strategy='prior'),
        'logistic_regression': LogisticRegression(C=1, max_iter=2000, solver='lbfgs', random_state=SEED),
        'random_forest': RandomForestClassifier(n_estimators=200, min_samples_leaf=5,
             max_features='sqrt', random_state=SEED, n_jobs=2),
    }
    bundle, thresholds = {}, {}
    result = {'validation': {}, 'training_samples': len(train), 'training_vehicles': int(train.vehicle_id.nunique()),
              'training_positives': int(train.target.sum()), 'training_prevalence': float(train.target.mean())}
    predictions = validation[['vehicle_id', 'target']].copy()
    interpretation = {}
    for name, estimator in estimators.items():
        pipeline = make_pipeline(estimator, numeric, categorical)
        with warnings.catch_warnings():
            warnings.simplefilter('error', ConvergenceWarning)
            pipeline.fit(train[feature_columns], train.target)
        p = pipeline.predict_proba(validation[feature_columns])[:, 1]
        threshold = .5 if name == 'prevalence_baseline' else select_threshold(validation.target, p)
        thresholds[name] = threshold
        result['validation'][name] = {'default_0_5': metrics(validation.target, p, .5),
                                     'selected_threshold': metrics(validation.target, p, threshold)}
        bundle[name] = pipeline
        predictions[f'{name}_probability'] = p
        names = pipeline.named_steps['preprocess'].get_feature_names_out()
        if name == 'logistic_regression':
            coefficients = pipeline.named_steps['model'].coef_[0]
            interpretation[name] = {
                direction: [{'feature': names[i], 'coefficient': float(coefficients[i])} for i in indices]
                for direction, indices in [('most_positive', np.argsort(coefficients)[-15:][::-1]),
                                            ('most_negative', np.argsort(coefficients)[:15])]}
            result['lr_iterations'] = pipeline.named_steps['model'].n_iter_.tolist()
        elif name == 'random_forest':
            importances = pipeline.named_steps['model'].feature_importances_
            interpretation[name] = [{'feature': names[i], 'impurity_importance': float(importances[i])}
                                    for i in np.argsort(importances)[-20:][::-1]]
        print(name, 'validation AP', result['validation'][name]['selected_threshold']['average_precision'],
              'threshold', threshold, flush=True)
    aps = {name: r['selected_threshold']['average_precision'] for name, r in result['validation'].items()}
    selected = max(aps, key=aps.get)
    if selected == 'random_forest' and aps['logistic_regression'] >= aps['random_forest'] - .005:
        selected = 'logistic_regression'
    result['selected_model'] = selected
    result['selection_rule'] = 'Highest validation AP; prefer LR within 0.005 of RF; thresholds maximize validation F1; baseline threshold 0.5.'
    predictions.to_csv(OUT / 'validation_predictions.csv', index=False)
    write_json(OUT / 'validation_metrics.json', result)
    write_json(OUT / 'interpretability.json', interpretation)
    joblib.dump(bundle, OUT / 'pipelines.joblib')
    files = list(Path(__file__).parent.glob('*.py')) + [Path(__file__).parent / 'protocol.md',
             Path(__file__).parent / 'requirements.txt']
    files += [OUT / name for name in ['pipelines.joblib', 'train_features.csv', 'validation_features.csv',
              'test_features.csv', 'validation_metrics.json', 'data_audit.json', 'feature_verification.json',
              'train_sample_selection.csv', 'train_sampling.json', 'validation_sampling.json', 'test_sampling.json']]
    files += [DATA / 'manifest.json']
    manifest = json.loads((DATA / 'manifest.json').read_text())
    checksums = {str(p.relative_to(ROOT)): sha256(p) for p in files}
    for entry in manifest['files']:
        path = DATA / entry['relative_path']
        if sha256(path) != entry['sha256']:
            raise ValueError(f'Download changed: {path.name}')
        checksums[str(path.relative_to(ROOT))] = entry['sha256']
    write_json(OUT / 'freeze.json', {
        'frozen_at_utc': datetime.now(timezone.utc).isoformat(), 'selected_model': selected,
        'thresholds': thresholds, 'selection_rule': result['selection_rule'],
        'feature_columns': feature_columns, 'sha256': checksums,
        'python': platform.python_version(), 'pandas': pd.__version__, 'numpy': np.__version__,
        'scikit_learn': sklearn.__version__, 'joblib': joblib.__version__,
        'scipy': scipy.__version__, 'threadpoolctl': threadpoolctl.__version__,
        'test_labels_parsed': False, 'published_test_aggregates_seen_in_documentation': True})
    print(f'FROZEN: {selected}; no test labels parsed.', flush=True)


if __name__ == '__main__':
    fit()
