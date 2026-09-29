# Scania Component X v3: isolated public validation

This experiment has no imports from the synthetic MedOps pipeline and does not
read/write the application's database, frontend, backend, or existing models.

Completed first run: validation selected Random Forest at 0.316705. Test AP
0.0503 (prevalence baseline 0.0281), ROC-AUC 0.6288, F1 0.0214, and only
2/142 positives detected. Test Brier 0.04126 is worse than baseline 0.02739.
This is a weak result with poor calibration/threshold transfer, not a useful
operational predictor. No post-test tuning was performed. Full report:
`models/public_validation/scania_component_x/report.md`.

## Dataset and attribution

SCANIA Component X Dataset, version 3 (2025-04-09), Scania CV AB and Stockholm
University; Swedish National Data Service / Researchdata.se.
[Release DOI: 10.5878/bnh5-ka77](https://doi.org/10.5878/bnh5-ka77).
[Official catalogue](https://researchdata.se/en/catalogue/dataset/2024-34).
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
Creators: Tony Lindgren, Olof Steinert, Oskar Andersson Reyna, Zahra Kharazian,
and Sindri Magnusson. Article: Kharazian et al. (2025), Scientific Data 12:493,
[doi:10.1038/s41597-025-04802-6](https://doi.org/10.1038/s41597-025-04802-6).

The official files remain unchanged. This project derives prefix features and
binary targets; those transformations are this project's work. Real-origin
truck histories are anonymized and curated; repair/readout frequencies may have
been modified by the publisher and are not fleet incidence estimates.

`loader.py --download` obtains only the version-3 API files: nine CSVs (train,
validation, test operational readouts and specifications; train_tte; validation
and test labels) plus Scania_Component_X.pdf and 2024_IDA_challenge_v2.pdf.
The manifest records URLs, byte sizes, SHA-256, release attribution and UTC date.
Raw data and downloaded documentation are Git-ignored. No account is required.
Allow approximately 2 GB for raw data plus derived features and model artifacts.

## Protocol

Read [protocol.md](protocol.md) for the pre-model target and decision rules.
Training constructs a first-repair-within-48-dataset-time-units label only when
ascertained; unknown short-follow-up censoring is excluded. Evaluation classifies
released proximity labels (1-4 vs 0). Their underlying censor endpoints are not
released, preventing independent confirmation of all class-0 follow-up.

Each vehicle contributes at most one example: a fixed-seed random train readout,
or the official final validation/test readout. All features use data at or before
that cutoff. The official vehicle-disjoint splits measure unseen-vehicle
generalization, not future calendar generalization. No global calendar exists.

Features: latest 105 anonymous values; 97 histogram fractions; 16 reset-aware
counter rates; current relative time; eight one-hot-encoded specifications.
Numeric imputation/scaling and categorical encoding are fit on train only.
IDs, labels, endpoint duration/repair flags, eventual history length, and future
rows/missingness are excluded. Historical counter rates use actual elapsed
readout intervals and become missing if a reset or insufficient data occurs.

Three fixed candidates: prevalence baseline, Logistic Regression, Random Forest.
No neural networks, boosted models, sweeps, or post-test tuning. Validation AP
selects the model (LR preference within 0.005 of RF); validation F1 selects each
learned-model threshold. Class weighting and post-hoc recalibration are not used.

Metrics include prevalence, precision, recall, F1, ROC-AUC, average precision,
confusion matrix, Brier score and quantile-bin calibration. The selected model
receives 1,000 vehicle-bootstrap percentile intervals. Coefficients and RF
impurity importance are associations, not causal explanations of anonymized
sensors. Correlated features can distribute importance arbitrarily.

## Reproduction

The accepted evidence in a fresh checkout includes a freeze seal and must not
be overwritten. First follow [the independent workspace preparation guide](../../../docs/frozen_demo_and_reproduction.md#independent-scania-reproduction).
Run the following commands from that **new workspace root**, using its separate
Python environment and the versions in this directory's `requirements.txt`:

```powershell
python -m pip install -r ml/public_validation/scania_component_x/requirements.txt
python -m ml.public_validation.scania_component_x.loader --download
python -m ml.public_validation.scania_component_x.inspect_data
```

Read `models/public_validation/scania_component_x/data_audit.json`. Stop for
any documentation contradiction or nonempty `issues_requiring_review` before
continuing. Test labels remain unparsed during inspection.

```powershell
python -m unittest ml.public_validation.scania_component_x.test_integrity
python -m ml.public_validation.scania_component_x.preprocess
python -m ml.public_validation.scania_component_x.model
python -m ml.public_validation.scania_component_x.evaluate
python -m ml.public_validation.scania_component_x.report
```

`model` writes fitted pipelines, validation metrics, interpretation and a hash
freeze. `evaluate` verifies that freeze before opening the test labels and uses
an exclusive one-use marker. It scores all frozen models in a single evaluation;
the preselected model is primary. It does not train or select anything.

Do not overwrite an existing frozen run. Reproduction means a newly staged independent workspace, not removing the seal to tune after
seeing test results. A genuine interrupted-run/software bug requires a recorded
explanation and transparent rerun. Hashes detect accidental changes; this is
procedural separation, not access-control protection against a determined user.

## Outputs and limitations

`data/public/scania_component_x/v3/manifest.json`: source/file integrity.
`models/public_validation/scania_component_x/`: audit, feature tables, sample
selection, validation/test predictions, pipelines.joblib, freeze.json,
interpretability.json, metrics.json, and report.md.

There is one observation per included vehicle, so bootstrap units are vehicles.
Intervals condition on this fitted model and do not include seed/model-selection
uncertainty or dependencies between vehicles. Eligibility exclusions can create
train/evaluation population shift. Static specification timing and publisher
preprocessing cannot be independently audited. Relative time is not a day/hour.
Repair proximity is not a medical work-order Part Replacement resolution.
No fleet deployment, causal, clinical, or medical-device performance claim follows.

The individual test-label file remains sealed until evaluation. The published
paper's aggregate test counts appeared during documentation review and were not
used in modelling decisions. This disclosure is retained in the freeze/report.
