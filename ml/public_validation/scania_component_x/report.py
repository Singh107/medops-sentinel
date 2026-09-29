"""Render the completed, frozen experiment's artifacts as a Markdown report."""
import json
from .loader import DATA, OUT


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def table(headers, rows):
    return '\n'.join(['| ' + ' | '.join(headers) + ' |',
                      '| ' + ' | '.join(['---'] * len(headers)) + ' |'] +
                     ['| ' + ' | '.join(map(str, row)) + ' |' for row in rows])


def result_table(results):
    rows = []
    for name, variants in results.items():
        for variant, m in variants.items():
            rows.append([name, variant, f'{m["threshold"]:.6f}', f'{m["precision"]:.4f}',
                         f'{m["recall"]:.4f}', f'{m["f1"]:.4f}', f'{m["roc_auc"]:.4f}',
                         f'{m["average_precision"]:.4f}', f'{m["brier_score"]:.5f}', m['confusion_matrix']])
    return table(['Model', 'Threshold rule', 'Threshold', 'Precision', 'Recall', 'F1', 'ROC-AUC',
                  'AP', 'Brier', 'CM [[TN,FP],[FN,TP]]'], rows)


def main():
    manifest = load(DATA / 'manifest.json')
    audit = load(OUT / 'data_audit.json')
    results = load(OUT / 'metrics.json')
    freeze = load(OUT / 'freeze.json')
    sampling = {s: load(OUT / f'{s}_sampling.json') for s in ['train', 'validation', 'test']}
    interpretation = load(OUT / 'interpretability.json')
    selected = freeze['selected_model']
    test = results['test'][selected]['selected_threshold']
    sections = ['# First public-data validation: Scania Component X v3',
        f'Selected on validation only: **{selected}**, threshold **{freeze["thresholds"][selected]:.6f}**. '
        f'Test AP {test["average_precision"]:.4f}, ROC-AUC {test["roc_auc"]:.4f}, F1 {test["f1"]:.4f}. '
        'This is classification of released repair-proximity labels on unseen vehicles.',
        '## Data acquisition',
        '[Official release](https://researchdata.se/en/catalogue/dataset/2024-34); '
        '[DOI 10.5878/bnh5-ka77](https://doi.org/10.5878/bnh5-ka77), version 3. '
        'Scania CV AB / Stockholm University; Swedish National Data Service. '
        'CC BY 4.0. Attribution: Tony Lindgren, Olof Steinert, Oskar Andersson Reyna, '
        'Zahra Kharazian, Sindri Magnusson. All raw files are unchanged; derived features '
        'and modelling are this project\'s transformations.',
        f'Download completed UTC: {manifest["download_date_utc"]}. '
        f'{len(manifest["files"])} official files, {sum(f["bytes"] for f in manifest["files"]):,} bytes. '
        'All SHA-256 digests were verified again before freezing. Raw data/documentation '
        'are ignored by Git; no raw files were committed. This workspace has no Git metadata.',
        table(['File', 'Bytes', 'SHA-256'], [[f['filename'], f'{f["bytes"]:,}', f['sha256']] for f in manifest['files']]),
        '## Data audit']
    rows = []
    for split in ['train', 'validation', 'test']:
        a = audit['files'][f'{split}_operational_readouts.csv']
        rows.append([split, f'{a["rows"]:,}', a['columns'], f'{a["unique_vehicles"]:,}',
                     a['duplicate_rows'], a['duplicate_vehicle_time_keys'], a['time_step_range'],
                     f'{a["total_missing"]:,}', f'{100*a["max_column_missing_fraction"]:.4f}%'])
    sections += [table(['Split', 'Readouts', 'Columns', 'Vehicles', 'Duplicate rows', 'Duplicate ID/time',
                        'Time range', 'Missing cells', 'Max missing/column'], rows),
        'No vehicle IDs overlap across splits. All readouts are ordered within vehicle. '
        'Specification and outcome vehicle sets match readouts. All specification files have '
        'vehicle_id plus Spec_0 through Spec_7 (nine columns); specifications and outcome files '
        'have no missing cells or duplicate vehicle IDs. Full per-column missingness and '
        'category inventories are in data_audit.json.',
        'Training endpoints: 23,550 rows, three columns (ID plus two outcomes); 21,278 censored '
        'and 2,272 first-repair endpoints. Endpoint range 73.4-510.0 dataset time units. '
        'No training readout occurs at or after its endpoint. The paper counts outcome and '
        'specification columns separately from the ID; actual schema is consistent.',
        'Validation labels: vehicle_id/class_label; distribution '
        + str(audit['files']['validation_labels.csv']['class_distribution']) + '. '
        'Test labels, audited only after freezing: ' + str(results['test_label_audit']) + '.',
        'Operational row counts, fleet sizes, dimensions, missingness and training/validation '
        'outcomes match the official documentation. No contradictory findings required a stop. '
        'The older challenge guide predates the published test labels; the version-3 release '
        'and final paper document them.',
        'Median readout gaps are 4.4/4.6/4.4 relative units for train/validation/test; maximum '
        'gaps are 387.8/159.8/237.6. Train has seven observed decreases in 171_0; other '
        'audited counter decreases are zero. The documented possibility of reset/corruption '
        'motivates suppressing any rate spanning a decrease. Missing counter pairs are excluded '
        'from the audit counts; feature construction also checks decreases across available values.',
        '## Target and prediction samples',
        'Primary evaluation target: **class_label > 0** at the official final available readout. '
        'Classes 1-4 indicate proximity within 48 anonymized dataset time units; class 0 is the '
        'released non-imminent class. These are not hours, days, or weeks. Validation/test '
        'censor endpoints are unavailable, so negative follow-up cannot be independently verified.',
        'Training: for each vehicle, draw one historical readout uniformly with fixed seed '
        '20260927 and a vehicle-specific hash, without consulting repair/censor status. At T, '
        'positive means a recorded first repair with 0 < endpoint-T <= 48. Negative requires '
        'observed event-free follow-up through T+48 or a known repair later than T+48. '
        'Discard short-follow-up censored/terminal samples without redrawing. '
        'Prediction is immediately after the readout, allowing measurements at T.',
        table(['Split', 'Samples = unique vehicles', 'Positive', 'Prevalence', 'Excluded'], [
            ['train', sampling['train']['samples'], results['training_positives'],
             f'{results["training_prevalence"]:.4%}', sampling['train']['excluded_unknown_or_terminal']],
            ['validation', 5046, 136, f'{136/5046:.4%}', 0],
            ['test', test['samples'], test['positives'], f'{test["prevalence"]:.4%}', 0]]),
        'One prefix per vehicle avoids inflated independent sample counts. Random cutoff '
        'selection is retrospective, using the available sequence only to sample a cutoff, '
        'never as a predictor. Censor eligibility changes the train population. No oversampling, '
        'redrawing, or target changes were made to improve performance.',
        '## Features and leakage prevention',
        '219 numeric columns: 105 latest operational values; 97 normalized histogram-bin '
        'fractions; 16 rates for eight documented counters (24-unit recent and whole-prefix '
        'spans); current time_step. Plus eight categorical specifications. All anonymous '
        'variable IDs are retained. Rates use observed elapsed intervals and at least two '
        'valid readings, and become missing across resets. Undefined fractions remain missing.',
        'Only measurements at/before the cutoff enter features. IDs, class_label, repair flags, '
        'endpoint duration, eventual history length, future rows and future missingness are '
        'excluded. Median imputation, scaling and one-hot encoding fit TRAIN only. '
        'Unknown categories are ignored. No full-cohort normalization or future interpolation.',
        'Official vehicle-disjoint splits are preserved. They measure unseen-vehicle '
        'generalization, not future calendar generalization. No shared calendar axis exists; '
        'a global temporal embargo would not be meaningful. No vehicle crosses partitions.',
        '## Validation results', result_table(results['validation']),
        '## Model selection',
        results['selection_rule'] + f' Selected **{selected}** with threshold '
        f'**{freeze["thresholds"][selected]:.6f}**. No model is refit on train+validation. '
        'These thresholds optimize statistical F1, not deployment costs.',
        'Fixed candidates: prior-probability baseline; LR (C=1, lbfgs, max_iter=2000); '
        'RF (200 trees, min_samples_leaf=5, sqrt feature sampling, two workers). '
        'No class weights, hyperparameter sweeps, neural networks, or calibration fitting. '
        f'LR converged in {results["lr_iterations"]} iterations.',
        '## Sealed test results',
        f'Freeze timestamp: {freeze["frozen_at_utc"]}. Evaluation completion: '
        f'{results["test_evaluated_at_utc"]}. Source, protocol, raw data, feature tables, '
        'validation results and fitted models were hashed before opening test labels. '
        'One evaluator invocation scored all three frozen candidates; the preselected model '
        'remains primary. No test-driven tuning or retraining followed.',
        result_table(results['test']),
        'Sealing disclosure: individual test labels were not opened before the freeze. '
        'The official paper publishes aggregate test class counts; those appeared during '
        'documentation review and were not used for modelling decisions. The one-use marker '
        'prevents accidental repeated evaluation; it is procedural protection, not OS access control.',
        '## Uncertainty and calibration',
        'Selected-model test intervals: 1,000 vehicle bootstrap replicates, fixed fitted '
        'model/threshold, seed 20260927, percentile 95%. Each row represents a different vehicle. '
        'Intervals do not capture retraining, seed, threshold-selection, or fleet-cluster uncertainty.',
        table(['Metric', 'Point estimate', '95% interval'], [
            [k, f'{test[k]:.4f}', f'[{bounds[0]:.4f}, {bounds[1]:.4f}]']
            for k, bounds in results['test_selected_model_uncertainty']['intervals'].items()]),
        f'Selected-model mean predicted probability: {test["mean_predicted_probability"]:.4%}; '
        f'observed prevalence: {test["prevalence"]:.4%}; Brier: {test["brier_score"]:.5f}; '
        f'quantile-bin absolute calibration error: {test["calibration_ece"]:.5f}. '
        'Brier/ECE are descriptive and do not establish calibrated deployment risk. '
        'The baseline Brier score is shown alongside the learned models above.',
        table(['Quantile bin', 'Vehicles', 'Mean probability', 'Observed positive fraction'], [
            [i+1, b['n'], f'{b["mean_prediction"]:.5f}', f'{b["observed_fraction"]:.5f}']
            for i, b in enumerate(test['calibration_bins'])]),
        '## Interpretability',
        'LR coefficients below follow train-fitted numeric standardization and categorical '
        'one-hot encoding. Positive means association with higher predicted repair proximity, '
        'conditional on the other model features. No physical meanings or causes are inferred.']
    for direction in ['most_positive', 'most_negative']:
        sections += [direction.replace('_', ' ').capitalize() + ':',
            table(['Feature', 'LR coefficient'], [[r['feature'], f'{r["coefficient"]:.5f}']
                   for r in interpretation['logistic_regression'][direction][:10]])]
    sections += ['RF impurity importance can favor continuous/high-cardinality variables and '
        'split importance between correlated predictors; it is not independent or causal evidence.',
        table(['Feature', 'RF impurity importance'], [[r['feature'], f'{r["impurity_importance"]:.5f}']
               for r in interpretation['random_forest'][:10]]),
        '## Synthetic MedOps vs Public Scania Validation',
        table(['Aspect', 'Synthetic MedOps', 'Public Scania'], [
            ['Origin/domain', 'Fictional medical-device-style workflow', 'Real-origin curated truck fleet'],
            ['Equipment', 'Multiple subassemblies per machine', 'One anonymous component type'],
            ['History', 'Service/work-order features', 'Operational readouts'],
            ['Target', 'Part Replacement resolution', 'Recorded repair/proximity label'],
            ['Time', 'Weekly cutoff; 30 calendar days', 'One prefix; 48 anonymized relative units'],
            ['Workflow fields', 'Problems, resolutions, downtime and text', 'No direct equivalents']]),
        'Shared methodology: historical equipment behaviour, time-limited feature construction, '
        'future maintenance-risk labels, leakage controls, separate train/validation/test '
        'cohorts and interpretable baseline modelling. The public-data experiment demonstrates '
        'that this workflow can be applied to an independent real-origin maintenance dataset, '
        'subject to its label/censoring and curation limitations. It does not validate MedOps '
        'for medical devices, validate its synthetic coefficients, or establish clinical utility.',
        '## Limitations',
        '- Single release and seed; no stability study or cross-dataset validation.\n'
        '- Curated repair/readout frequencies and anonymous operational units; no incidence claim.\n'
        '- Validation/test negatives cannot be independently checked for full 48-unit follow-up.\n'
        '- Train censor exclusions and publisher cutoff selection may cause population shift.\n'
        '- Operational counters are publisher-processed; original real-time availability of that '
        'cleanup cannot be reconstructed. Specifications are assumed static.\n'
        '- Repair/failure terminology does not prove an exact Part Replacement resolution.\n'
        '- Observational associations, no causal sensor interpretation or deployment validation.\n'
        '- Vehicles may share operational contexts; vehicle bootstrap does not model those clusters.\n'
        '- No work-order, downtime, subsystem-taxonomy or service-text validation.',
        '## Reproduction and verification',
        'See ml/public_validation/scania_component_x/README.md and protocol.md. '
        'Runtime versions and exact feature names are in freeze.json. In a fresh output directory:',
        '```powershell\n'
        'python -m ml.public_validation.scania_component_x.loader --download\n'
        'python -m ml.public_validation.scania_component_x.inspect_data\n'
        '# Review audit; stop on contradictions before modelling.\n'
        'python -m unittest ml.public_validation.scania_component_x.test_integrity\n'
        'python -m ml.public_validation.scania_component_x.preprocess\n'
        'python -m ml.public_validation.scania_component_x.model\n'
        'python -m ml.public_validation.scania_component_x.evaluate\n'
        'python -m ml.public_validation.scania_component_x.report\n```',
        'Seven focused tests cover censor/repair boundaries, future-mutation invariance, '
        'irregular-time rates and resets, blacklist enforcement, train-only transformation '
        'statistics, freeze-integrity rejection, and refusing a second evaluation before label access. '
        'All passed before modelling. Completed artifacts retain the one-use seal.',
        'All code/data/results are under isolated public-validation paths, except the requested '
        '.gitignore additions. The existing synthetic generator, schema, snapshots, model, SQLite, '
        'backend, frontend and API routes were not edited. No application processes or ports were '
        'changed; MealMind was untouched. Experiment complete; no additional datasets or UI work.']
    (OUT / 'report.md').write_text('\n\n'.join(sections) + '\n', encoding='utf-8')
    print(OUT / 'report.md')


if __name__ == '__main__':
    main()
