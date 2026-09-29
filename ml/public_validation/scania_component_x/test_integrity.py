"""Focused tests of censoring boundaries, future isolation, and freeze integrity."""
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path
import numpy as np
import pandas as pd
from .preprocess import COUNTERS, HISTOGRAMS, features, prefix_index, train_target
from .evaluate import run_test, verify_freeze
from .model import make_pipeline
from sklearn.linear_model import LogisticRegression


def history():
    cols = COUNTERS + [f'{v}_{i}' for v, bins in HISTOGRAMS.items() for i in range(bins)]
    return pd.DataFrame({'vehicle_id': [8] * 4, 'time_step': [0., 12., 24., 36.],
                         **{c: [1., 2., 3., 4.] for c in cols}})


class IntegrityTests(unittest.TestCase):
    def test_censor_and_repair_boundaries(self):
        self.assertEqual(train_target(10, 58, 1), 1)
        self.assertEqual(train_target(10, 58.2, 1), 0)
        self.assertEqual(train_target(10, 58, 0), 0)
        self.assertIsNone(train_target(10, 57.8, 0))
        self.assertIsNone(train_target(10, 10, 1))
        self.assertIsNone(train_target(10, 9.8, 1))
        self.assertEqual(train_target(10.2, 58.2, 1), 1)

    def test_future_rows_and_missingness_do_not_change_features(self):
        frame = history()
        expected = features(frame.iloc[:3], 24)
        frame.loc[3, COUNTERS] = np.nan
        frame.loc[3, '167_0'] = 1e12
        actual = features(frame, 24)
        np.testing.assert_allclose(list(expected.values()), list(actual.values()), equal_nan=True)
        self.assertEqual(actual['171_0__latest'], 3.)

    def test_counter_reset_and_irregular_intervals(self):
        frame = history()
        self.assertAlmostEqual(features(frame, 36)['171_0__history_rate'], 3 / 36)
        frame.loc[2, '171_0'] = 0
        self.assertTrue(np.isnan(features(frame, 36)['171_0__history_rate']))
        self.assertTrue(np.isnan(features(frame.iloc[:1], 0)['171_0__recent_rate']))

    def test_forbidden_fields_and_outcome_independent_sampling(self):
        frame = history()
        frame['length_of_study_time_step'] = 100
        with self.assertRaises(ValueError):
            features(frame, 24)
        self.assertEqual(prefix_index(8, 40), prefix_index(8, 40))
        self.assertTrue(0 <= prefix_index(8, 40) < 40)

    def test_changed_frozen_artifact_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / 'file').write_text('changed')
            with patch('ml.public_validation.scania_component_x.evaluate.ROOT', root):
                with self.assertRaises(RuntimeError):
                    verify_freeze({'sha256': {'file': 'not-matching'}})

    def test_imputation_and_encoding_are_train_only(self):
        X = pd.DataFrame({'number': [1., np.nan, 3., 5.], 'category': ['A', 'A', 'B', 'B']})
        pipe = make_pipeline(LogisticRegression(), ['number'], ['category'])
        pipe.fit(X, [0, 0, 1, 1])
        transform = pipe.named_steps['preprocess']
        imputer = transform.named_transformers_['numeric'].named_steps['impute']
        before = imputer.statistics_.copy()
        transform.transform(pd.DataFrame({'number': [1e20, np.nan], 'category': ['UNSEEN', 'A']}))
        np.testing.assert_array_equal(before, imputer.statistics_)
        self.assertEqual(before[0], 3.)

    def test_second_evaluation_refused_before_label_read(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / 'freeze.json').write_text('{"sha256": {}}')
            (root / 'test_evaluation_started.json').write_text('{}')
            with patch('ml.public_validation.scania_component_x.evaluate.OUT', root):
                with patch('ml.public_validation.scania_component_x.evaluate.pd.read_csv') as reader:
                    with self.assertRaises(FileExistsError):
                        run_test()
                    reader.assert_not_called()


if __name__ == '__main__':
    unittest.main()
