"""Streaming structural audit. Test labels deliberately remain sealed."""
import itertools
import json
import numpy as np
import pandas as pd
from .loader import DATA, OUT, write_json

COUNTERS = ['171_0', '666_0', '427_0', '837_0', '309_0', '835_0', '370_0', '100_0']


def operational(path):
    rows = 0
    missing = None
    hashes, keys = [], []
    counter_decreases = pd.Series(0, index=COUNTERS, dtype='int64')
    counter_pairs = counter_decreases.copy()
    previous = None
    for frame in pd.read_csv(path, chunksize=50000):
        rows += len(frame)
        missing = frame.isna().sum() if missing is None else missing.add(frame.isna().sum())
        hashes.append(pd.util.hash_pandas_object(frame, index=False).to_numpy())
        keys.append(frame[['vehicle_id', 'time_step']])
        current = frame[['vehicle_id', 'time_step'] + COUNTERS]
        extended = current if previous is None else pd.concat([previous, current], ignore_index=True)
        differences = extended.groupby('vehicle_id', sort=False)[COUNTERS].diff().iloc[-len(current):]
        counter_decreases += differences.lt(0).sum()
        counter_pairs += differences.notna().sum()
        previous = extended.groupby('vehicle_id', sort=False).tail(1)
    key = pd.concat(keys, ignore_index=True)
    fingerprints = np.concatenate(hashes)
    duplicated = pd.Series(fingerprints).duplicated(keep=False).to_numpy()
    exact_duplicates = 0
    if duplicated.any():
        candidates, offset = [], 0
        for frame in pd.read_csv(path, chunksize=50000):
            candidates.append(frame.loc[duplicated[offset:offset + len(frame)]])
            offset += len(frame)
        exact_duplicates = int(pd.concat(candidates).duplicated().sum())
    by_vehicle = key.groupby('vehicle_id').time_step.agg(['min', 'max', 'size'])
    deltas = key.groupby('vehicle_id', sort=False).time_step.diff()
    result = {
        'rows': rows, 'columns': len(frame.columns), 'column_names': list(frame.columns),
        'unique_vehicles': len(by_vehicle), 'duplicate_rows': exact_duplicates,
        'duplicate_vehicle_time_keys': int(key.duplicated().sum()),
        'missing_values': {k: int(v) for k, v in missing.items()},
        'total_missing': int(missing.sum()),
        'max_column_missing_fraction': float(missing.max() / rows),
        'time_step_range': [float(key.time_step.min()), float(key.time_step.max())],
        'decreasing_times_in_file_order': int(deltas.lt(0).sum()),
        'readout_gap_quantiles': {str(k): float(v) for k, v in deltas.dropna().quantile([0, .25, .5, .75, 1]).items()},
        'readouts_per_vehicle': {str(k): float(v) for k, v in by_vehicle['size'].quantile([0, .25, .5, .75, 1]).items()},
        'counter_decrease_counts_in_file_order': counter_decreases.to_dict(),
        'counter_observed_consecutive_pairs': counter_pairs.to_dict(),
    }
    return result, by_vehicle


def small_file(path):
    frame = pd.read_csv(path)
    result = {'rows': len(frame), 'columns': len(frame.columns), 'column_names': list(frame.columns),
              'unique_vehicles': int(frame.vehicle_id.nunique()),
              'duplicate_rows': int(frame.duplicated().sum()),
              'duplicate_vehicle_ids': int(frame.vehicle_id.duplicated().sum()),
              'missing_values': frame.isna().sum().to_dict()}
    return result, frame


def inspect():
    result = {'test_labels': 'SEALED: not parsed; counts/distribution deferred until frozen evaluation.',
              'files': {}, 'split_overlap': {}, 'issues_requiring_review': []}
    vehicle_sets = {}
    for split in ('train', 'validation', 'test'):
        name = f'{split}_operational_readouts.csv'
        info, vehicles = operational(DATA / 'raw' / name)
        result['files'][name] = info
        vehicle_sets[split] = set(vehicles.index)
        spec_name = f'{split}_specifications.csv'
        spec_info, specs = small_file(DATA / 'raw' / spec_name)
        spec_info['categorical_values'] = {c: sorted(specs[c].dropna().unique().tolist()) for c in specs if c != 'vehicle_id'}
        result['files'][spec_name] = spec_info
        if set(specs.vehicle_id) != vehicle_sets[split]:
            result['issues_requiring_review'].append(f'{split}: specification/readout vehicle mismatch')
        if split != 'test':
            endpoint_name = 'train_tte.csv' if split == 'train' else 'validation_labels.csv'
            endpoint_info, endpoints = small_file(DATA / 'raw' / endpoint_name)
            label = 'in_study_repair' if split == 'train' else 'class_label'
            endpoint_info['class_distribution'] = endpoints[label].value_counts().sort_index().to_dict()
            if set(endpoints.vehicle_id) != vehicle_sets[split]:
                result['issues_requiring_review'].append(f'{split}: endpoint/readout vehicle mismatch')
            if split == 'train':
                joined = vehicles.join(endpoints.set_index('vehicle_id'))
                endpoint_info['endpoint_range'] = [float(endpoints.length_of_study_time_step.min()), float(endpoints.length_of_study_time_step.max())]
                endpoint_info['vehicles_with_readout_after_endpoint'] = int((joined['max'] > joined.length_of_study_time_step + 1e-8).sum())
                endpoint_info['vehicles_with_readout_at_endpoint'] = int(np.isclose(joined['max'], joined.length_of_study_time_step, atol=1e-8, rtol=0).sum())
                endpoint_info['last_readout_to_endpoint_quantiles'] = {str(k): float(v) for k, v in (joined.length_of_study_time_step - joined['max']).quantile([0, .25, .5, .75, 1]).items()}
            result['files'][endpoint_name] = endpoint_info
        print(f'Audited {split}: {info["rows"]:,} readouts, {len(vehicles):,} vehicles', flush=True)
    for a, b in itertools.combinations(vehicle_sets, 2):
        result['split_overlap'][f'{a}/{b}'] = len(vehicle_sets[a] & vehicle_sets[b])
        if result['split_overlap'][f'{a}/{b}']:
            result['issues_requiring_review'].append(f'{a}/{b}: overlapping vehicles')
    expected = {'train': (1122452, 23550), 'validation': (196227, 5046), 'test': (198140, 5045)}
    for split, (rows, vehicles) in expected.items():
        info = result['files'][f'{split}_operational_readouts.csv']
        if (info['rows'], info['unique_vehicles'], info['columns']) != (rows, vehicles, 107):
            result['issues_requiring_review'].append(f'{split}: published size/schema contradiction')
        if info['max_column_missing_fraction'] >= .01:
            result['issues_requiring_review'].append(f'{split}: published missingness contradiction')
        if info['duplicate_rows'] or info['duplicate_vehicle_time_keys'] or info['decreasing_times_in_file_order']:
            result['issues_requiring_review'].append(f'{split}: unexpected duplicate or unordered readouts')
    train_end = result['files']['train_tte.csv']
    if train_end['class_distribution'] != {0: 21278, 1: 2272} or train_end['vehicles_with_readout_after_endpoint']:
        result['issues_requiring_review'].append('Training repair structure contradicts documentation')
    if result['files']['validation_labels.csv']['class_distribution'] != {0: 4910, 1: 16, 2: 14, 3: 30, 4: 76}:
        result['issues_requiring_review'].append('Validation class distribution contradicts documentation')
    write_json(OUT / 'data_audit.json', result)
    print(json.dumps({k: v for k, v in result.items() if k != 'files'}, indent=2))
    for name, info in result['files'].items():
        print(name, json.dumps({k:v for k,v in info.items() if k not in ('missing_values','column_names','categorical_values')}, default=int))


if __name__ == '__main__':
    inspect()
