"""One historical prediction prefix per vehicle, with censor-aware train labels."""
import hashlib
import json
import numpy as np
import pandas as pd
from .loader import DATA, OUT, write_json
from .inspect_data import COUNTERS

SEED = 20260927
HORIZON = 48.0
RECENT_WINDOW = 24.0
HISTOGRAMS = {'167': 10, '272': 10, '291': 11, '158': 10, '459': 20, '397': 36}
BLACKLIST = {'vehicle_id', 'class_label', 'in_study_repair', 'length_of_study_time_step',
             'repair_endpoint', 'censor_endpoint', 'eventual_history_length', 'target'}


def train_target(t, endpoint, repaired):
    """None means terminal or insufficient follow-up; never an assumed negative."""
    remaining = round(float(endpoint) - float(t), 8)
    if remaining <= 0:
        return None
    if int(repaired) == 1:
        return int(remaining <= HORIZON)
    return 0 if remaining >= HORIZON else None


def prefix_index(vehicle_id, n):
    """Uniform deterministic readout draw, without repair/censor information."""
    seed = int.from_bytes(hashlib.sha256(f'{SEED}:{vehicle_id}'.encode()).digest()[:8], 'big')
    return int(np.random.default_rng(seed).integers(n))


def features(history, cutoff):
    history = history.loc[history.time_step <= cutoff].sort_values('time_step')
    if history.empty:
        raise ValueError('Empty prediction history')
    columns = [c for c in history if c not in ('vehicle_id', 'time_step')]
    if set(columns) & BLACKLIST:
        raise ValueError('Forbidden field supplied to feature construction')
    latest = history.iloc[-1]
    result = {f'{c}__latest': float(latest[c]) for c in columns}
    result['time_step'] = float(cutoff)
    for counter in COUNTERS:
        for name, lower in [('recent_rate', cutoff - RECENT_WINDOW), ('history_rate', -np.inf)]:
            known = history.loc[history.time_step > lower, ['time_step', counter]].dropna()
            value = np.nan
            if len(known) >= 2:
                x = known[counter].to_numpy()
                elapsed = float(known.time_step.iloc[-1] - known.time_step.iloc[0])
                if elapsed > 0 and np.all(np.diff(x) >= 0):
                    value = float((x[-1] - x[0]) / elapsed)
            result[f'{counter}__{name}'] = value
    for variable, bins in HISTOGRAMS.items():
        names = [f'{variable}_{i}' for i in range(bins)]
        values = latest[names].to_numpy(dtype=float)
        total = values.sum()
        fractions = values / total if np.isfinite(total) and total > 0 else np.full(bins, np.nan)
        result.update({f'{c}__fraction': float(v) for c, v in zip(names, fractions)})
    return result


def vehicle_histories(path):
    """Bounded-memory iteration; require contiguous ascending vehicle blocks."""
    carry = None
    last_id = -1
    for chunk in pd.read_csv(path, chunksize=50000):
        frame = chunk if carry is None else pd.concat([carry, chunk], ignore_index=True)
        final_id = frame.vehicle_id.iloc[-1]
        carry = frame.loc[frame.vehicle_id == final_id]
        complete = frame.loc[frame.vehicle_id != final_id]
        for vehicle_id, history in complete.groupby('vehicle_id', sort=False):
            if vehicle_id <= last_id:
                raise ValueError('Non-contiguous vehicle blocks')
            last_id = vehicle_id
            yield int(vehicle_id), history.sort_values('time_step')
    if carry is not None:
        yield int(carry.vehicle_id.iloc[0]), carry.sort_values('time_step')


def prepare_split(split):
    if split not in ('train', 'validation', 'test'):
        raise ValueError(split)
    specs = pd.read_csv(DATA / 'raw' / f'{split}_specifications.csv').set_index('vehicle_id')
    endpoints = pd.read_csv(DATA / 'raw' / 'train_tte.csv').set_index('vehicle_id') if split == 'train' else None
    records = []
    excluded = []
    sampled = []
    for vehicle_id, history in vehicle_histories(DATA / 'raw' / f'{split}_operational_readouts.csv'):
        index = prefix_index(vehicle_id, len(history)) if split == 'train' else len(history) - 1
        t = float(history.time_step.iloc[index])
        y = None
        if split == 'train':
            endpoint = endpoints.loc[vehicle_id]
            y = train_target(t, endpoint.length_of_study_time_step, endpoint.in_study_repair)
            sampled.append({'vehicle_id': vehicle_id, 'prediction_time': t, 'eligible': y is not None})
            if y is None:
                excluded.append(vehicle_id)
                continue
        row = {'vehicle_id': vehicle_id, **features(history.iloc[:index + 1], t), **specs.loc[vehicle_id].to_dict()}
        if split == 'train':
            row['target'] = y
        records.append(row)
    frame = pd.DataFrame(records)
    if frame.vehicle_id.duplicated().any():
        raise ValueError('More than one prediction per vehicle')
    if split == 'validation':
        labels = pd.read_csv(DATA / 'raw' / 'validation_labels.csv')
        frame = frame.merge(labels, on='vehicle_id', validate='one_to_one')
        frame['target'] = (frame.pop('class_label') > 0).astype(int)
    OUT.mkdir(parents=True, exist_ok=True)
    frame.to_csv(OUT / f'{split}_features.csv', index=False)
    report = {'split': split, 'samples': len(frame), 'unique_vehicles': int(frame.vehicle_id.nunique()),
              'excluded_unknown_or_terminal': len(excluded), 'excluded_vehicle_ids': excluded,
              'numeric_features': 219, 'categorical_features': 8,
              'positive_samples': int(frame.target.sum()) if 'target' in frame else None,
              'prevalence': float(frame.target.mean()) if 'target' in frame else None}
    write_json(OUT / f'{split}_sampling.json', report)
    if sampled:
        pd.DataFrame(sampled).to_csv(OUT / 'train_sample_selection.csv', index=False)
    print(json.dumps({k:v for k,v in report.items() if k != 'excluded_vehicle_ids'}), flush=True)


def main():
    if (OUT / 'freeze.json').exists():
        raise RuntimeError('Frozen experiment: do not overwrite features')
    audit = json.loads((OUT / 'data_audit.json').read_text())
    if audit['issues_requiring_review']:
        raise RuntimeError('Resolve audit findings before preprocessing')
    for split in ('train', 'validation', 'test'):
        prepare_split(split)


if __name__ == '__main__':
    main()
