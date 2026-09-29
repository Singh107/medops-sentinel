"""Independent label and raw-history checks before the model freeze."""
import numpy as np
import pandas as pd
from .loader import DATA, OUT, write_json
from .preprocess import features, vehicle_histories


def verify():
    train = pd.read_csv(OUT / 'train_features.csv')
    endpoints = pd.read_csv(DATA / 'raw' / 'train_tte.csv')
    joined = train[['vehicle_id', 'time_step', 'target']].merge(endpoints, on='vehicle_id', validate='one_to_one')
    remaining = np.round(joined.length_of_study_time_step - joined.time_step, 8)
    expected = ((joined.in_study_repair == 1) & (remaining > 0) & (remaining <= 48)).astype(int)
    assert (expected == joined.target).all()
    assert (remaining > 0).all()
    assert ((joined.in_study_repair == 1) | (remaining >= 48)).all()
    selection = pd.read_csv(OUT / 'train_sample_selection.csv')
    assert len(selection) == 23550 and selection.vehicle_id.nunique() == 23550
    assert selection.eligible.sum() == len(train)
    checked = 0
    for vehicle, history in vehicle_histories(DATA / 'raw' / 'train_operational_readouts.csv'):
        match = train.loc[train.vehicle_id == vehicle]
        if match.empty:
            continue
        cutoff = match.time_step.iloc[0]
        before = features(history, cutoff)
        np.testing.assert_allclose(list(before.values()), match[list(before)].iloc[0].to_numpy(dtype=float),
                                   rtol=1e-10, atol=1e-10, equal_nan=True)
        history.loc[history.time_step > cutoff, history.columns.difference(['vehicle_id', 'time_step'])] = 1e15
        after = features(history, cutoff)
        np.testing.assert_allclose(list(before.values()), list(after.values()), equal_nan=True)
        checked += 1
        if checked == 10:
            break
    ids = {'train': set(train.vehicle_id)}
    expected_features = [c for c in train if c not in ('vehicle_id', 'target')]
    for split in ['validation', 'test']:
        frame = pd.read_csv(OUT / f'{split}_features.csv')
        assert not frame.vehicle_id.duplicated().any()
        assert [c for c in frame if c not in ('vehicle_id', 'target')] == expected_features
        assert 'class_label' not in frame
        if split == 'test':
            assert 'target' not in frame
        ids[split] = set(frame.vehicle_id)
        for previous in ids:
            if previous != split:
                assert not ids[split] & ids[previous]
    write_json(OUT / 'feature_verification.json', {
        'all_training_targets_independently_checked': len(train),
        'unique_random_cutoffs_checked': len(selection),
        'actual_vehicle_future_mutation_checks': checked,
        'feature_schemas_equal': True, 'split_vehicle_ids_disjoint': True, 'status': 'passed'})
    print('Independent feature/label verification passed.', flush=True)


if __name__ == '__main__':
    verify()
