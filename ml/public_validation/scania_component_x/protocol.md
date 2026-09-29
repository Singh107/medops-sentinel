# Protocol fixed before modelling

Date: 2026-09-27. Dataset: Scania Component X v3, DOI 10.5878/bnh5-ka77.
No synthetic MedOps files or application runtime are part of this experiment.

## Documentation and target semantics

Official sources: [release](https://researchdata.se/en/catalogue/dataset/2024-34),
`2024_IDA_challenge_v2.pdf` pp. 1-3 and `Scania_Component_X.pdf` pp. 3-8,
stored in the isolated documentation directory with checksums in the manifest.

The guide defines `length_of_study_time_step` as elapsed operation time to the
first repair when `in_study_repair=1`; otherwise it is the end of observed
repair-free operation. `class_label` categorizes the final released readout:
classes 1-4 represent the 48-to-0 interval before the event, class 0 the
non-imminent category. Time units are anonymized. Do not call them days/hours.
The documentation uses repair/failure/replacement terminology inconsistently;
this experiment refers conservatively to recorded repair proximity.

Primary evaluation: binary classification of the released proximity label,
`class_label > 0`. The underlying validation/test censor endpoints are absent,
so their class-0 follow-up cannot be independently verified. Do not claim
fully ascertained prospective 48-unit incidence or clinical validation.

Training: draw one readout uniformly per vehicle with deterministic seed
20260927 and a vehicle-specific hash, before checking endpoint eligibility.
At cutoff T, y=1 if repaired and 0 < endpoint-T <= 48. Otherwise y=0 only if
endpoint-T >= 48 (or an observed repair lies beyond 48). Discard unknown
short-follow-up and terminal examples without redrawing. Round differences
to 8 decimal places to handle decimal CSV boundary representation.
This eligibility restriction can change the training population and is a
limitation, not a reason to relabel censored vehicles or tune the horizon.

Validation/test use exactly the publisher's final readout per vehicle. One
sample per vehicle in all splits; official partitions remain fixed. A cutoff
occurs immediately after its readout, so measurements at T are available.

## Features

219 numeric features: 105 current-readout values, 97 within-histogram bin
fractions, 16 counter rates (8 counters, recent 24-unit and all-prefix spans),
and observed `time_step`. Eight `Spec_0`-`Spec_7` categorical specifications.
Anonymous variable names are retained. Rates use actual elapsed time between
available values; require at least two valid values and no decrease in that
span. No rate across a detected reset; undefined rates/fractions are missing.
No future filling; a latest missing value stays missing for train-fit imputation.
Means/minima/maxima of cumulative levels are omitted to keep this first model
small. Specifications are documented as categorical vehicle configurations;
availability as static configuration is assumed, not independently timestamped.

All fitting uses train only: numeric median imputation and scaling for LR,
categorical constant imputation and one-hot encoding with unknowns ignored.
RF uses the same train-fitted transformation. No oversampling or class weights;
calibration is assessed without a fitted recalibration stage.

Blacklist: vehicle ID, labels, repair flag, endpoint duration, eventual history
length, future rows or missingness, and any post-cutoff quantity. Training
endpoints are label-only. No cross-fleet calendar split or artificial embargo:
time is vehicle-relative and vehicles are disjoint.

## Models and fixed selection rule

Prevalence/majority baseline; LogisticRegression(C=1, max_iter=2000,
solver=lbfgs); RandomForestClassifier(n_estimators=200, min_samples_leaf=5,
max_features=sqrt, random_state=20260927, n_jobs=2). No hyperparameter sweep.
Primary selection: higher validation average precision; if LR is within 0.005
of RF, prefer LR for simplicity. Baseline also remains eligible if it beats
both. For each learned model select maximum validation F1 threshold using
the precision-recall breakpoints; tied maxima choose the highest threshold.
Baseline stays at 0.5. Report default 0.5 and selected thresholds.

Freeze source hashes, data checksums, feature tables, fitted pipelines, model
choice, and thresholds before test-label parsing. Test evaluator has a one-use
marker; an interrupted evaluation must be investigated rather than silently
repeated. Score all three frozen candidates in that single pass; selected-model
test performance is primary. No changes in response to test results.

Metrics: AP, ROC-AUC, precision, recall, F1, confusion matrix, Brier score,
10 quantile-bin calibration statistics, sample/vehicle count and prevalence.
Selected model: 1,000 vehicle bootstrap replicates, percentile 95% intervals,
seed 20260927. No retraining or re-selection inside test bootstrap; intervals
are conditional on this fitted model and cohort, not full training uncertainty.

## Audit and sealing disclosure

Observed counts match the documentation: train 1,122,452/23,550,
validation 196,227/5,046, test 198,140/5,045 readouts/vehicles; 107 columns.
The endpoint file has two outcome columns plus the ID (three total); specification
files have eight specifications plus ID (nine total). The paper's descriptions
counting outcome/features exclude the ID and are not schema contradictions.
No duplicate rows or vehicle/time keys, no vehicle overlap, no training readout
at/after its endpoint. Missingness is below 1% per operational column.
Seven decreases in train `171_0` are consistent with the documented possibility
of counter resets; rates crossing decreases are suppressed. Other eight-counter
decrease counts are zero. Readout spacing is irregular.

Individual test labels remain unopened before freezing. The official paper
contains aggregate test class counts, which appeared while reviewing its target
definitions; those counts were not used for any modelling decision. Do not claim
that all published aggregate test information was unseen.
