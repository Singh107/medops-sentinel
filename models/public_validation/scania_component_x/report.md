# First public-data validation: Scania Component X v3

Selected on validation only: **random_forest**, threshold **0.316705**. Test AP 0.0503, ROC-AUC 0.6288, F1 0.0214. This is classification of released repair-proximity labels on unseen vehicles.

**Outcome: weak predictive performance, poor probability calibration, and poor threshold transfer.** The selected threshold detects only 2 of 142 test positives, with 43 false alarms. Its Brier score (0.04126) is worse than the prevalence baseline (0.02739), and its mean predicted probability (13.10%) substantially exceeds observed prevalence (2.81%). The experiment demonstrates execution of a leakage-controlled workflow on independent real-origin data; it does not establish useful operational prediction. No tuning followed these results.

This outcome paragraph is an editorial interpretation of the completed run; the report-generation command reproduces the numerical report from frozen artifacts.

## Data acquisition

[Official release](https://researchdata.se/en/catalogue/dataset/2024-34); [DOI 10.5878/bnh5-ka77](https://doi.org/10.5878/bnh5-ka77), version 3. Scania CV AB / Stockholm University; Swedish National Data Service. CC BY 4.0. Attribution: Tony Lindgren, Olof Steinert, Oskar Andersson Reyna, Zahra Kharazian, Sindri Magnusson. All raw files are unchanged; derived features and modelling are this project's transformations.

Download completed UTC: 2026-09-27T23:07:38.965987+00:00. 11 official files, 1,655,183,186 bytes. All SHA-256 digests were verified again before freezing. Raw data/documentation are ignored by Git; no raw files were committed. This workspace has no Git metadata.

| File | Bytes | SHA-256 |
| --- | --- | --- |
| Scania_Component_X.pdf | 3,283,883 | b8450509bc4b11c6a47a70e56cc37b4aaf1a40e6ebcaeef67477c79691123610 |
| 2024_IDA_challenge_v2.pdf | 231,630 | b4261fe713811c9f3c02fe95d01b56f756c181ebec7b1277df36f7fdaeffb87f |
| train_operational_readouts.csv | 1,219,209,878 | e01cb0bd87dfab4c9dbad215d51d81282fc0d413be96d6f819ea872fb7a3c715 |
| train_tte.csv | 345,412 | d8c2379ed7c95a575dd869730b2b3b96d660317f49e57de300518ff3b08d53a5 |
| train_specifications.csv | 1,081,118 | 47cc9a67aee19d5e2ee8620fe8e467490b2125bacc7787ce781ce9f3c1f0c38f |
| validation_operational_readouts.csv | 215,593,159 | 1e1597eec866588c2ad95eb923555ad719c64b3697d9140f9cec6809349809af |
| validation_labels.csv | 38,742 | ad876c95c3696f4cfca2d76212ad6bb3cac6b2d2950a4aeaf218ee8b1548d08c |
| validation_specifications.csv | 231,765 | a31e832846538dd7a1829108b69420d9377dcd05d6446d8ac1270a974fc58ae2 |
| test_operational_readouts.csv | 214,897,259 | 81f2709cd339e0ff561f5fd3188d7f431680e32400bd788814880d7759615ba1 |
| test_labels.csv | 38,682 | 60f923051d4ba1bef4c81166cf9e8ca01daf3b7a29c73016c6f48a23dcfa0223 |
| test_specifications.csv | 231,658 | 40ac8a111f6d5b416107ec1786f639766ecf1293a1c9c0c0dbf24f14c1c5d0e7 |

## Data audit

| Split | Readouts | Columns | Vehicles | Duplicate rows | Duplicate ID/time | Time range | Missing cells | Max missing/column |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| train | 1,122,452 | 107 | 23,550 | 0 | 0 | [0.0, 507.4] | 354,634 | 0.8578% |
| validation | 196,227 | 107 | 5,046 | 0 | 0 | [0.0, 456.6] | 60,339 | 0.8077% |
| test | 198,140 | 107 | 5,045 | 0 | 0 | [0.0, 447.6] | 66,403 | 0.8953% |

No vehicle IDs overlap across splits. All readouts are ordered within vehicle. Specification and outcome vehicle sets match readouts. All specification files have vehicle_id plus Spec_0 through Spec_7 (nine columns); specifications and outcome files have no missing cells or duplicate vehicle IDs. Full per-column missingness and category inventories are in data_audit.json.

Training endpoints: 23,550 rows, three columns (ID plus two outcomes); 21,278 censored and 2,272 first-repair endpoints. Endpoint range 73.4-510.0 dataset time units. No training readout occurs at or after its endpoint. The paper counts outcome and specification columns separately from the ID; actual schema is consistent.

Validation labels: vehicle_id/class_label; distribution {'0': 4910, '1': 16, '2': 14, '3': 30, '4': 76}. Test labels, audited only after freezing: {'rows': 5045, 'columns': 2, 'unique_vehicles': 5045, 'duplicate_rows': 0, 'missing_values': {'vehicle_id': 0, 'class_label': 0}, 'class_distribution': {'0': 4903, '1': 26, '2': 15, '3': 41, '4': 60}}.

Operational row counts, fleet sizes, dimensions, missingness and training/validation outcomes match the official documentation. No contradictory findings required a stop. The older challenge guide predates the published test labels; the version-3 release and final paper document them.

Median readout gaps are 4.4/4.6/4.4 relative units for train/validation/test; maximum gaps are 387.8/159.8/237.6. Train has seven observed decreases in 171_0; other audited counter decreases are zero. The documented possibility of reset/corruption motivates suppressing any rate spanning a decrease. Missing counter pairs are excluded from the audit counts; feature construction also checks decreases across available values.

## Target and prediction samples

Primary evaluation target: **class_label > 0** at the official final available readout. Classes 1-4 indicate proximity within 48 anonymized dataset time units; class 0 is the released non-imminent class. These are not hours, days, or weeks. Validation/test censor endpoints are unavailable, so negative follow-up cannot be independently verified.

Training: for each vehicle, draw one historical readout uniformly with fixed seed 20260927 and a vehicle-specific hash, without consulting repair/censor status. At T, positive means a recorded first repair with 0 < endpoint-T <= 48. Negative requires observed event-free follow-up through T+48 or a known repair later than T+48. Discard short-follow-up censored/terminal samples without redrawing. Prediction is immediately after the readout, allowing measurements at T.

| Split | Samples = unique vehicles | Positive | Prevalence | Excluded |
| --- | --- | --- | --- | --- |
| train | 18630 | 640 | 3.4353% | 4920 |
| validation | 5046 | 136 | 2.6952% | 0 |
| test | 5045 | 142 | 2.8147% | 0 |

One prefix per vehicle avoids inflated independent sample counts. Random cutoff selection is retrospective, using the available sequence only to sample a cutoff, never as a predictor. Censor eligibility changes the train population. No oversampling, redrawing, or target changes were made to improve performance.

## Features and leakage prevention

219 numeric columns: 105 latest operational values; 97 normalized histogram-bin fractions; 16 rates for eight documented counters (24-unit recent and whole-prefix spans); current time_step. Plus eight categorical specifications. All anonymous variable IDs are retained. Rates use observed elapsed intervals and at least two valid readings, and become missing across resets. Undefined fractions remain missing.

Only measurements at/before the cutoff enter features. IDs, class_label, repair flags, endpoint duration, eventual history length, future rows and future missingness are excluded. Median imputation, scaling and one-hot encoding fit TRAIN only. Unknown categories are ignored. No full-cohort normalization or future interpolation.

Official vehicle-disjoint splits are preserved. They measure unseen-vehicle generalization, not future calendar generalization. No shared calendar axis exists; a global temporal embargo would not be meaningful. No vehicle crosses partitions.

## Validation results

| Model | Threshold rule | Threshold | Precision | Recall | F1 | ROC-AUC | AP | Brier | CM [[TN,FP],[FN,TP]] |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| prevalence_baseline | default_0_5 | 0.500000 | 0.0000 | 0.0000 | 0.0000 | 0.5000 | 0.0270 | 0.02628 | [[4910, 0], [136, 0]] |
| prevalence_baseline | selected_threshold | 0.500000 | 0.0000 | 0.0000 | 0.0000 | 0.5000 | 0.0270 | 0.02628 | [[4910, 0], [136, 0]] |
| logistic_regression | default_0_5 | 0.500000 | 0.0382 | 0.6471 | 0.0721 | 0.6341 | 0.0402 | 0.37565 | [[2693, 2217], [48, 88]] |
| logistic_regression | selected_threshold | 0.924165 | 0.0478 | 0.4632 | 0.0866 | 0.6341 | 0.0402 | 0.37565 | [[3654, 1256], [73, 63]] |
| random_forest | default_0_5 | 0.500000 | 0.0000 | 0.0000 | 0.0000 | 0.6867 | 0.0744 | 0.05395 | [[4910, 0], [136, 0]] |
| random_forest | selected_threshold | 0.316705 | 0.1221 | 0.1176 | 0.1199 | 0.6867 | 0.0744 | 0.05395 | [[4795, 115], [120, 16]] |

## Model selection

Highest validation AP; prefer LR within 0.005 of RF; thresholds maximize validation F1; baseline threshold 0.5. Selected **random_forest** with threshold **0.316705**. No model is refit on train+validation. These thresholds optimize statistical F1, not deployment costs.

Fixed candidates: prior-probability baseline; LR (C=1, lbfgs, max_iter=2000); RF (200 trees, min_samples_leaf=5, sqrt feature sampling, two workers). No class weights, hyperparameter sweeps, neural networks, or calibration fitting. LR converged in [178] iterations.

## Sealed test results

Freeze timestamp: 2026-09-27T23:26:16.707180+00:00. Evaluation completion: 2026-09-27T23:27:25.515123+00:00. Source, protocol, raw data, feature tables, validation results and fitted models were hashed before opening test labels. One evaluator invocation scored all three frozen candidates; the preselected model remains primary. No test-driven tuning or retraining followed.

| Model | Threshold rule | Threshold | Precision | Recall | F1 | ROC-AUC | AP | Brier | CM [[TN,FP],[FN,TP]] |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| prevalence_baseline | default_0_5 | 0.500000 | 0.0000 | 0.0000 | 0.0000 | 0.5000 | 0.0281 | 0.02739 | [[4903, 0], [142, 0]] |
| prevalence_baseline | selected_threshold | 0.500000 | 0.0000 | 0.0000 | 0.0000 | 0.5000 | 0.0281 | 0.02739 | [[4903, 0], [142, 0]] |
| logistic_regression | default_0_5 | 0.500000 | 0.0357 | 0.0634 | 0.0457 | 0.6240 | 0.0393 | 0.06129 | [[4660, 243], [133, 9]] |
| logistic_regression | selected_threshold | 0.924165 | 0.0000 | 0.0000 | 0.0000 | 0.6240 | 0.0393 | 0.06129 | [[4884, 19], [142, 0]] |
| random_forest | default_0_5 | 0.500000 | 0.0000 | 0.0000 | 0.0000 | 0.6288 | 0.0503 | 0.04126 | [[4903, 0], [142, 0]] |
| random_forest | selected_threshold | 0.316705 | 0.0444 | 0.0141 | 0.0214 | 0.6288 | 0.0503 | 0.04126 | [[4860, 43], [140, 2]] |

Sealing disclosure: individual test labels were not opened before the freeze. The official paper publishes aggregate test class counts; those appeared during documentation review and were not used for modelling decisions. The one-use marker prevents accidental repeated evaluation; it is procedural protection, not OS access control.

## Uncertainty and calibration

Selected-model test intervals: 1,000 vehicle bootstrap replicates, fixed fitted model/threshold, seed 20260927, percentile 95%. Each row represents a different vehicle. Intervals do not capture retraining, seed, threshold-selection, or fleet-cluster uncertainty.

| Metric | Point estimate | 95% interval |
| --- | --- | --- |
| precision | 0.0444 | [0.0000, 0.1190] |
| recall | 0.0141 | [0.0000, 0.0388] |
| f1 | 0.0214 | [0.0000, 0.0568] |
| roc_auc | 0.6288 | [0.5838, 0.6703] |
| average_precision | 0.0503 | [0.0356, 0.0753] |
| brier_score | 0.0413 | [0.0378, 0.0444] |

Selected-model mean predicted probability: 13.0994%; observed prevalence: 2.8147%; Brier: 0.04126; quantile-bin absolute calibration error: 0.10285. Brier/ECE are descriptive and do not establish calibrated deployment risk. The baseline Brier score is shown alongside the learned models above.

| Quantile bin | Vehicles | Mean probability | Observed positive fraction |
| --- | --- | --- | --- |
| 1 | 505 | 0.02353 | 0.00396 |
| 2 | 504 | 0.05172 | 0.00992 |
| 3 | 505 | 0.07423 | 0.02772 |
| 4 | 504 | 0.09556 | 0.02579 |
| 5 | 504 | 0.11623 | 0.02183 |
| 6 | 505 | 0.13648 | 0.02772 |
| 7 | 504 | 0.15830 | 0.05159 |
| 8 | 505 | 0.18138 | 0.02772 |
| 9 | 504 | 0.20903 | 0.03373 |
| 10 | 505 | 0.26342 | 0.05149 |

## Interpretability

LR coefficients below follow train-fitted numeric standardization and categorical one-hot encoding. Positive means association with higher predicted repair proximity, conditional on the other model features. No physical meanings or causes are inferred.

Most positive:

| Feature | LR coefficient |
| --- | --- |
| numeric__397_24__latest | 1.21178 |
| categorical__Spec_7_Cat6 | 1.04180 |
| categorical__Spec_2_Cat9 | 0.89845 |
| categorical__Spec_2_Cat14 | 0.83816 |
| categorical__Spec_2_Cat6 | 0.81512 |
| categorical__Spec_7_Cat7 | 0.64137 |
| numeric__427_0__latest | 0.62669 |
| numeric__459_9__fraction | 0.61248 |
| numeric__427_0__history_rate | 0.57323 |
| numeric__459_4__fraction | 0.53121 |

Most negative:

| Feature | LR coefficient |
| --- | --- |
| numeric__167_1__fraction | -1.29326 |
| numeric__167_0__fraction | -1.21337 |
| categorical__Spec_7_Cat2 | -1.17438 |
| numeric__459_4__latest | -1.03304 |
| numeric__158_3__latest | -0.94478 |
| categorical__Spec_5_Cat4 | -0.85122 |
| categorical__Spec_4_Cat0 | -0.84278 |
| categorical__Spec_1_Cat11 | -0.73525 |
| numeric__171_0__history_rate | -0.73371 |
| numeric__459_10__fraction | -0.70656 |

RF impurity importance can favor continuous/high-cardinality variables and split importance between correlated predictors; it is not independent or causal evidence.

| Feature | RF impurity importance |
| --- | --- |
| numeric__459_10__latest | 0.00959 |
| numeric__666_0__latest | 0.00895 |
| numeric__397_33__latest | 0.00735 |
| numeric__158_6__latest | 0.00711 |
| numeric__167_4__fraction | 0.00703 |
| numeric__272_5__latest | 0.00685 |
| numeric__158_5__latest | 0.00682 |
| numeric__158_8__latest | 0.00667 |
| numeric__397_23__fraction | 0.00661 |
| numeric__459_15__fraction | 0.00660 |

## Synthetic MedOps vs Public Scania Validation

| Aspect | Synthetic MedOps | Public Scania |
| --- | --- | --- |
| Origin/domain | Fictional medical-device-style workflow | Real-origin curated truck fleet |
| Equipment | Multiple subassemblies per machine | One anonymous component type |
| History | Service/work-order features | Operational readouts |
| Target | Part Replacement resolution | Recorded repair/proximity label |
| Time | Weekly cutoff; 30 calendar days | One prefix; 48 anonymized relative units |
| Workflow fields | Problems, resolutions, downtime and text | No direct equivalents |

Shared methodology: historical equipment behaviour, time-limited feature construction, future maintenance-risk labels, leakage controls, separate train/validation/test cohorts and interpretable baseline modelling. The public-data experiment demonstrates that this workflow can be applied to an independent real-origin maintenance dataset, subject to its label/censoring and curation limitations. It does not validate MedOps for medical devices, validate its synthetic coefficients, or establish clinical utility.

## Limitations

- Single release and seed; no stability study or cross-dataset validation.
- Curated repair/readout frequencies and anonymous operational units; no incidence claim.
- Validation/test negatives cannot be independently checked for full 48-unit follow-up.
- Train censor exclusions and publisher cutoff selection may cause population shift.
- Operational counters are publisher-processed; original real-time availability of that cleanup cannot be reconstructed. Specifications are assumed static.
- Repair/failure terminology does not prove an exact Part Replacement resolution.
- Observational associations, no causal sensor interpretation or deployment validation.
- Vehicles may share operational contexts; vehicle bootstrap does not model those clusters.
- No work-order, downtime, subsystem-taxonomy or service-text validation.

## Reproduction and verification

See ml/public_validation/scania_component_x/README.md and protocol.md. Runtime versions and exact feature names are in freeze.json. In a fresh output directory:

```powershell
python -m ml.public_validation.scania_component_x.loader --download
python -m ml.public_validation.scania_component_x.inspect_data
# Review audit; stop on contradictions before modelling.
python -m unittest ml.public_validation.scania_component_x.test_integrity
python -m ml.public_validation.scania_component_x.preprocess
python -m ml.public_validation.scania_component_x.model
python -m ml.public_validation.scania_component_x.evaluate
python -m ml.public_validation.scania_component_x.report
```

Seven focused tests cover censor/repair boundaries, future-mutation invariance, irregular-time rates and resets, blacklist enforcement, train-only transformation statistics, freeze-integrity rejection, and refusing a second evaluation before label access. All passed before modelling. Completed artifacts retain the one-use seal.

Independent checks verified all 18,630 training labels, all 23,550 cutoff selections, matching feature schemas and disjoint vehicle sets, and future-mutation invariance on ten actual vehicle histories. After evaluation, all frozen hashes still matched. Replaying only validation predictions from the saved pipelines matched saved predictions within 1.4e-16; test prediction was not repeated. These completion checks are recorded in completion_verification.json. The installed SciPy emitted an ignored `iprint` logging-option warning during LR fitting; LR nevertheless converged in 178 iterations without a convergence warning. Runtime versions are pinned and recorded.

All code/data/results are under isolated public-validation paths, except the requested .gitignore additions. The existing synthetic generator, schema, snapshots, model, SQLite, backend, frontend and API routes were not edited. No application processes or ports were changed; MealMind was untouched. Experiment complete; no additional datasets or UI work.
