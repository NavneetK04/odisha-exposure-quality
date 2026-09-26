# Exposure Data Quality & Accumulation Analysis — Coastal Odisha

An end-to-end exposure data-quality workflow for a synthetic coastal Odisha portfolio, covering portfolio validation, controlled error injection, detection, materiality triage, treatment, accumulation analysis, and linkage to catastrophe-risk outputs.

**Stack:** Python 3.11 · PostgreSQL 16 · PostGIS 3.4 · pandas · NumPy · GeoPandas · Shapely · pyproj · SQLAlchemy · Matplotlib · openpyxl

---

# Headline finding

Exposure data quality can materially alter the **portfolio exposure base and spatial accumulation profile** used by catastrophe-risk workflows.

In the validated current implementation:

- The clean synthetic portfolio contains **5,000 records** with total TIV of approximately **₹168.867B**.
- Controlled injection produces a **5,020-record dirty portfolio**.
- The ground-truth catalogue contains **10,001 error events** across 39 error types.
- The detector produces **11,035 quality flags** affecting **4,632 records**.
- Overall detection performance is **90.46% precision** and **99.81% recall** when completeness is included.
- Excluding deterministic completeness rules, injected-error performance is **75.28% precision** and **99.41% recall**.
- Treatment produces **5,020 cleansed records** with 190 fixed, 176 quarantined, 95 assumed, 4,171 referred and 388 requiring no treatment.
- The dirty accumulation contains **₹1.465T** of TIV across 18 occupied grid cells.
- The primary accumulation-eligible portfolio contains **₹155.284B** across 17 occupied grid cells.
- The dirty-to-primary TIV ratio is approximately **9.44×**.

The dirty-to-primary difference is a **scenario comparison under the project's treatment and accumulation-eligibility framework**. It should not be interpreted as a claim that data cleaning has proven that the underlying real portfolio was overstated by that amount.

---

# Results at a glance

| Metric | Current validated result | Notes |
|---|---:|---|
| Clean portfolio | **5,000 records** | Synthetic exposure portfolio |
| Dirty portfolio | **5,020 records** | 5,000 clean records + 20 duplicate rows |
| Ground-truth events | **10,001** | Multiple events can affect one record |
| Unique GT row IDs | **4,611** | 409 portfolio rows have no injected error |
| Detection flags | **11,035** | Across 39 rules |
| Records with ≥1 detected finding | **4,632** | Current detector output |
| Clean total TIV | **₹168.867B** | 5,000-record clean portfolio |
| Dirty accumulation TIV | **₹1.465T** | Contaminated scenario |
| Primary accumulation TIV | **₹155.284B** | Accumulation-eligible scenario |
| Dirty occupied cells | **18** | Project 1 0.25° grid |
| Primary occupied cells | **17** | Project 1 0.25° grid |
| Overall TP | **9,982** | All ground-truth dimensions |
| Overall FP | **1,053** | Includes interaction-driven flags |
| Overall FN | **19** | Ground-truth pairs not detected |
| Overall precision | **90.4576%** | Including completeness |
| Overall recall | **99.8100%** | Including completeness |
| Injected-only TP | **3,207** | Completeness excluded |
| Injected-only FP | **1,053** | Completeness excluded |
| Injected-only FN | **19** | Completeness excluded |
| Injected-only precision | **75.2817%** | Completeness excluded |
| Injected-only recall | **99.4110%** | Completeness excluded |

---

# Why this project

Exposure data quality is often treated as a preprocessing problem.

In catastrophe modelling, it is also a **risk-modelling problem**.

A portfolio can pass basic database validation while still containing errors or ambiguities that materially change:

- exposure totals
- geographical accumulation
- concentration metrics
- portfolio ranking
- modelled loss
- downstream risk decisions

This project therefore follows an exposure-analyst workflow:

1. Receive a portfolio.
2. Interrogate the data.
3. Identify quality issues.
4. Distinguish confirmed errors from uncertainty and assumptions.
5. Assess materiality.
6. Treat or escalate the records.
7. Recalculate accumulation.
8. Quantify the effect on the exposure/risk scenario.
9. Preserve an auditable trail of what changed and why.

The central principle is:

> **Not every data-quality issue is equally important, and not every populated value is necessarily correct.**

---

# Data-quality framework

The portfolio is evaluated across seven operational data-quality dimensions:

| Dimension | Focus |
|---|---|
| Completeness | Missing or incomplete required fields |
| Validity | Values violating explicit field constraints |
| Consistency | Conflicting values across related fields |
| Duplication | Duplicate or near-duplicate exposure records |
| Plausibility | Values that are possible but suspicious |
| Geography | Coordinate, district, postcode and spatial consistency |
| Coding | Invalid or inconsistent categorical codes |

Documentation and auditability are treated as a cross-cutting requirement rather than a detector-only dimension.

Each finding is classified as one of:

## Error

Evidence indicates that the value is wrong.

## Unknown

The available evidence is insufficient to establish whether the value is correct.

## Assumption

A modelling or treatment decision is required because the available data does not uniquely determine the answer.

This distinction prevents the workflow from silently converting uncertainty into false certainty.

---

# Materiality framework

A finding is not automatically considered material simply because it is unusual or missing.

Each issue is assessed against questions such as:

- Could it change the hazard interpretation?
- Could it affect vulnerability or damage modelling?
- Could it involve a high-value exposure?
- Could it create geographical or systematic concentration?
- Could it change a downstream modelling or business decision?

This separates **data-quality detection** from **risk significance**.

The current materiality implementation produces a materiality record for each detected quality flag.

> **Implementation note:** the rule catalogue explicitly maps each of the 39 quality rules to one materiality axis: hazard, vulnerability, or financial. The current materiality output therefore reports axis-level flags rather than leaving these fields uniformly `FALSE`.

---

# Method

## 1. Portfolio construction

The clean portfolio contains **5,000 synthetic exposure records** representing four coastal Odisha districts:

- Cuttack
- Khordha
- Puri
- Jagatsinghpur

The portfolio uses the spatial structure of the Project 1 exposure grid, with LitPop-weighted sampling and spatial jitter.

District assignment is rebuilt using GADM Level 2 administrative boundaries.

### Geographic QA

The final clean portfolio contains:

- 5,000 / 5,000 records inside target districts
- 0 records outside target districts
- 0 district assignment mismatches

Synthetic postcode reference tables are created for the selected districts so that postcode consistency checks can be performed internally.

These postcode relationships are synthetic reference data and should not be interpreted as an externally validated national postcode database.

---

# 2. Controlled error injection

A controlled error-injection framework creates a known ground-truth set against which detection performance can be evaluated.

The injection catalogue contains **39 error types**:

| Dimension | Rules |
|---|---:|
| Completeness | 7 |
| Validity | 7 |
| Consistency | 7 |
| Duplication | 4 |
| Plausibility | 5 |
| Geography | 5 |
| Coding | 4 |
| **Total** | **39** |

The ground-truth table contains:

- `row_id`
- `error_type`
- `dimension`
- `classification`
- `original_value`
- `corrupted_value`

The injector also tracks which fields have already been modified on each record. This prevents one injected transformation from silently overwriting another error's ground truth.

### Achieved injection population

The injection process uses target prevalence by error type, but the achieved number is checked after generation.

The current dirty portfolio contains:

- **5,020 rows**
- **10,001 ground-truth error events**
- **4,611 unique row IDs represented in ground truth**

The difference between 5,020 portfolio rows and 4,611 GT row IDs is expected: some records receive no injected error, while other records receive multiple error events.

---

# 3. Detection

Detection is implemented through SQL rules and Python evaluation.

The final detector catalogue contains **39 rules**, corresponding to the ground-truth injection catalogue.

Detectors include:

- missing-field checks
- numeric validity checks
- cross-field consistency checks
- duplicate detection
- suspicious-value thresholds
- coordinate and administrative-boundary checks
- coding/reference-table checks

Detectors are deliberately a mixture of deterministic and heuristic rules.

This distinction becomes important when interpreting precision.

---

# Detection performance

Completeness rules are reported separately from injected-error performance because missingness is directly observable from portfolio structure.

## Completeness coverage

The current dirty portfolio contains:

| Rule | Detected flags |
|---|---:|
| C-001 | 403 |
| C-002 | 1,507 |
| C-003 | 2,007 |
| C-004 | 1,253 |
| C-005 | 603 |
| C-006 | 752 |
| C-007 | 250 |
| **Total** | **6,775** |

All completeness ground-truth pairs are detected:

> **Completeness coverage = 100.00%**

---

## Detection performance by dimension

| Dimension | TP | FP | FN | Precision | Recall |
|---|---:|---:|---:|---:|---:|
| Validity | 195 | 12 | 0 | 94.20% | 100.00% |
| Consistency | 313 | 54 | 2 | 85.29% | 99.37% |
| Duplication | 161 | 482 | 0 | 25.04% | 100.00% |
| Geography | 416 | 167 | 0 | 71.36% | 100.00% |
| Coding | 1,508 | 252 | 0 | 85.68% | 100.00% |
| Plausibility | 614 | 86 | 17 | 87.71% | 97.31% |
| **Injected-error total** | **3,207** | **1,053** | **19** | **75.28%** | **99.41%** |

The exact rule-level evaluation is stored in:

```text
outputs/detection_performance.csv
```

---

## Full evaluation including completeness

| Metric | Injected-only | Including completeness |
|---|---:|---:|
| TP | 3,207 | 9,982 |
| FP | 1,053 | 1,053 |
| FN | 19 | 19 |
| Precision | **75.28%** | **90.46%** |
| Recall | **99.41%** | **99.81%** |

The primary detector-performance headline uses the injected-error dimensions because completeness is directly observable and deterministic. The full-population metrics are retained for transparency.

---

# Important detector behaviour

The detector output contains interaction-driven false positives.

A detector flag does not necessarily mean the detector is incorrect.

For example:

- D-002 can flag legitimate counterpart records when shared coordinates are deliberately introduced.
- G-001 and G-004 can flag records that also contain another injected error.
- K-001 can flag counterpart records affected by construction-related injections.
- P-001 can interact with other TIV transformations.
- P-005 has false negatives where a later injected transformation overwrites the value needed by the detector.

These behaviours are preserved because the objective is to evaluate the actual multi-error workflow rather than artificially isolate every detector from realistic interactions.

---

# Clean-baseline check

The clean portfolio was generated and loaded before error injection.

The clean baseline produced:

> **0 quality flags**

and:

> **0 affected records**

This is an important validation checkpoint.

The clean portfolio also reproduces the frozen calibration references used by X-005 and P-001.

### X-005 reference

| Metric | Value |
|---|---:|
| Clean median TIV/m² | 42,260.835257 |
| Clean maximum TIV/m² | 288,459.685129 |
| Multiplier | 7 |
| Frozen threshold | 295,825.846800 |

### P-001 reference

| Metric | Value |
|---|---:|
| Clean median building TIV | 16,907,259.331 |
| Clean maximum building TIV | 229,617,246.319 |
| Multiplier | 14 |
| Frozen threshold | 236,701,630.634 |

These references are stored in the database as frozen clean-baseline calibration values.

---

# 4. Treatment and audit trail

Treatment is deliberately separated from detection.

A detector finding does not automatically mean:

> "Change the value."

Instead, each finding receives a treatment decision.

The treatment framework uses four principal actions:

## Fixed

The value can be corrected deterministically from available information.

## Assumed

A value is changed or interpreted using an explicit modelling assumption.

## Quarantined

The record is excluded from the primary modelling population because the unresolved issue makes its use unsafe.

## Referred

The issue requires human review or additional source information.

Records with no findings receive:

## None

No treatment was required.

---

# Treatment summary

The current treatment run produces exactly 5,020 cleansed records:

| Treatment | Records |
|---|---:|
| Fixed | **190** |
| Assumed | **95** |
| Quarantined | **176** |
| Referred | **4,171** |
| None | **388** |
| **Total** | **5,020** |

The row-level treatment audit trail retains:

- original value
- cleaned value
- treatment rule
- treatment method
- classification
- priority
- quarantine status
- referral status
- treatment timestamp

---

# Classification summary

The current record-level classifications are:

| Classification | Records |
|---|---:|
| ERROR | 3,295 |
| ERROR;UNKNOWN | 872 |
| NONE | 388 |
| ASSUMPTION;ERROR;UNKNOWN | 262 |
| UNKNOWN | 164 |
| ASSUMPTION;UNKNOWN | 39 |
| **Total** | **5,020** |

Finding-level classification is maintained separately from record-level treatment classification.

---

# 5. Materiality

The current materiality SQL produces:

> **11,035 materiality records**

with:

| Priority | Flags | Distinct exposures |
|---|---:|---:|
| P1 | **206** | **167** |
| P2 | **5,503** | **2,392** |
| P3 | **5,326** | **2,298** |
| **Total** | **11,035** | **4,632** |

The materiality funnel contains **5,020 total exposures**, of which **4,632** have at least one detected finding and **388** have no detected findings.

The P1 exposure set contains **167 exposures** with validated clean-reference TIV of approximately **₹23.009B**, representing approximately **13.63%** of the clean portfolio TIV of **₹168.867B**.

Materiality TIV is based on the current authoritative clean portfolio reference for the original 5,000 records. Rows without a clean reference, such as injected duplicate rows, use the raw TIV fallback defined in `04_materiality.sql`.

The current implementation explicitly maps each of the 39 quality rules to one materiality axis: hazard, vulnerability, or financial.

The current materiality output is:

| Axis | Materiality findings |
|---|---:|
| Hazard | **1,171** |
| Vulnerability | **7,291** |
| Financial | **2,573** |
| **Total** | **11,035** |

The axis mappings are defined in the rule catalogue and are applied during materiality scoring.

**Important implementation limitation:** each quality rule is currently assigned to exactly one axis. This means the axis totals above are **forced single-axis allocations**, not a complete representation of every modelling consequence. Some rules can legitimately affect more than one dimension; for example, **G-002 (swapped coordinates)** can affect both hazard and financial exposure linkage, while **X-003 (TIV inflation)** can affect both vulnerability-related exposure interpretation and financial exposure. Therefore, the 1,171 / 7,291 / 2,573 split should be interpreted as the current rule-catalogue allocation, not as mutually exclusive real-world impact categories.

---

# 6. Accumulation analysis

The purpose of the accumulation stage is to determine whether exposure-quality issues materially change the spatial concentration of the portfolio.

The primary accumulation does not simply use every record that survived a cleaning step.

Instead, records with unresolved material anomalies capable of materially distorting accumulation are excluded from the primary scenario.

These records remain available through sensitivity scenarios.

This distinction is critical:

> **Treatment classification and accumulation eligibility are not the same thing.**

A record can be referred rather than fixed while also being excluded from the primary accumulation because its unresolved value could materially distort the result.

---

# Spatial grid

The accumulation analysis uses the same **0.25° Project 1 exposure grid** used by the catastrophe-risk workflow.

The Project 1 grid contains:

> **525 cells**

and is now stored locally in Project 2 as:

```text
data/odisha_exposure_grid.gpkg
```

This makes Project 2 self-contained with respect to the spatial reference required for accumulation.

---

# Dirty versus primary accumulation

The current validated accumulation results are:

| Portfolio | Grid cells | Locations | TIV |
|---|---:|---:|---:|
| DIRTY | **18** | **4,552** | **₹1,465,404,071,770.565** |
| CLEANSED / PRIMARY | **17** | **4,421** | **₹155,284,374,688.504** |

The dirty-to-primary TIV ratio is approximately:

> **9.44×**

This is a scenario comparison under the project's treatment and accumulation-eligibility framework.

It should **not** be interpreted as saying that cleaning has reduced the true underlying portfolio by 9.44×.

---

# Concentration metrics

## DIRTY

| Metric | Value |
|---|---:|
| Top-1 concentration | 53.115% |
| Top-3 concentration | 81.722% |
| Top-5 concentration | 90.757% |
| HHI | 0.341956 |
| Occupied cells | 18 |

## PRIMARY

| Metric | Value |
|---|---:|
| Top-1 concentration | 38.371% |
| Top-3 concentration | 70.644% |
| Top-5 concentration | 86.645% |
| HHI | 0.219997 |
| Occupied cells | 17 |

These results describe the synthetic portfolio generated for the project. They should not be interpreted as estimates of actual insured exposure concentration for Odisha.

---

# Sensitivity analysis

The primary accumulation excludes unresolved material referred records.

To understand the effect of those exclusions, separate sensitivity scenarios are retained.

| Scenario | TIV | Top-1 | Top-3 | Top-5 | HHI | Cells |
|---|---:|---:|---:|---:|---:|---:|
| **PRIMARY** | ₹155.284B | 38.371% | 70.644% | 86.645% | 0.2200 | 17 |
| **P001_SENSITIVITY** | ₹941.428B | 34.570% | 71.889% | 85.947% | 0.2199 | 17 |
| **P003_SENSITIVITY** | ₹676.118B | 80.265% | 93.258% | 96.933% | 0.6548 | 17 |
| **COMBINED_SENSITIVITY** | ₹1,462.261B | 53.227% | 81.902% | 90.953% | 0.3435 | 17 |
| **DIRTY** | ₹1,465.404B | 53.115% | 81.722% | 90.757% | 0.3420 | 18 |

The sensitivity scenarios demonstrate that unresolved exposure-quality issues can change both:

- total portfolio exposure
- the **shape of spatial concentration**

---

# P-001: TIV unit confusion

P-001 represents a TIV unit error in which values are expressed on the wrong scale.

This is an important exposure-quality problem because:

- values can pass basic numeric validity checks
- individual records can look plausible
- the aggregate portfolio can still be severely distorted

The current detector uses a frozen clean-baseline threshold rather than a threshold recalculated from the dirty portfolio.

The final X-005 and P-001 calibration references are generated by:

```text
python/calibrate_references.py
```

---

# P-003: Single-location concentration anomaly

P-003 represents a single-location concentration anomaly.

The current ground-truth P-003 event is **row 3938**. Its stored TIV is approximately **₹520.833B**, and it maps to the Project 1 accumulation grid cell at approximately **85.75°E, 20.50°N**. In the P003 sensitivity scenario, this single unresolved record adds approximately **₹520.833B** of TIV above the primary accumulation.

The purpose of the rule is to identify an exposure whose value creates an unusually large concentration at one location.

This demonstrates why accumulation analysis cannot be separated from exposure data quality.

A value can be:

- syntactically valid
- geographically located
- numerically populated

and still require escalation because of its impact on portfolio concentration.

---

# 7. Linkage to catastrophe-risk modelling

Project 1 established a cyclone catastrophe-risk modelling framework for coastal Odisha using:

- IBTrACS tropical cyclone tracks
- CLIMADA TropCyclone
- LitPop exposure
- an Odisha-derived vulnerability curve
- a 0.25° spatial grid
- simulated loss information

Project 2 uses the same spatial grid to connect exposure-quality analysis to the existing catastrophe-risk framework.

Where Project 1 outputs are available at the same grid-cell level, exposure-quality scenarios can be linked through cell-level proportional exposure scaling:

\[
AAL_{P2,c}
=
AAL_{P1,c}
\times
\frac{TIV_{P2,c}}{TIV_{P1,c}}
\]

where:

- \(AAL_{P1,c}\) = Project 1 cell-level AAL
- \(TIV_{P1,c}\) = Project 1 cell-level exposure
- \(TIV_{P2,c}\) = Project 2 scenario exposure
- \(AAL_{P2,c}\) = corresponding Project 2 scenario AAL

This is a **proportional linkage**, not a new catastrophe model.

A full catastrophe-model rerun would be required if exposure-quality changes also affected:

- construction-specific vulnerability
- occupancy-specific vulnerability
- policy limits
- deductibles
- insured values
- other non-linear model components

---

# 8. What I caught in my own process

A major objective of this project was to test whether problems could be identified in the workflow rather than simply trusting generated output.

## 1. Non-authoritative district assignment

The initial portfolio generator produced district-assignment mismatches because city/district relationships were initially generated without authoritative administrative boundaries.

The issue was identified during QA.

The generator was rebuilt using GADM Level 2 polygons and point-in-polygon validation.

Final result:

- 5,000 / 5,000 records inside target districts
- 0 outside
- 0 district mismatches

---

## 2. Implausible clean-baseline TIV/m² generation

An earlier generator version independently sampled building TIV and floor area. This could create internally inconsistent clean records and produced **60 X-001 clean-baseline flags**.

The generator was rebuilt so that building TIV is derived from floor area and construction-specific value-per-square-metre assumptions, with contents and business-interruption values derived from building TIV rather than independently sampled.

After the generator correction:

- the clean portfolio produces **0 quality flags**
- the clean portfolio produces **0 affected records**
- the clean baseline remains suitable for frozen X-005 and P-001 calibration

This correction is important because detector performance must be evaluated against a clean portfolio that is internally coherent before injected errors are introduced.

---

## 3. Ground-truth corruption from field collisions

The first error-injection implementation allowed multiple transformations to modify overlapping fields.

This created a risk that a later transformation could overwrite an earlier corruption and make the ground-truth table inconsistent with the actual portfolio.

A field-claim mechanism was introduced so that an injection can only modify a field when it has not already been claimed by another error on that record.

This made the ground-truth table traceable to the actual corrupted value.

---

## 4. P-001 contamination of materiality and accumulation

The first materiality and accumulation implementation allowed unresolved P-001 TIV values to flow directly into downstream totals.

The workflow was subsequently changed so that:

- validated clean-baseline references are kept separately
- unresolved material records are excluded from the primary accumulation
- P-001 remains available through a sensitivity scenario
- the dirty scenario remains available for comparison

---

## 5. Fresh-environment reproducibility test

The final workflow was independently reproduced in a fresh PostgreSQL database:

```text
odisha_exposure_repro
```

The reproduction confirmed agreement at the major checkpoints:

| Checkpoint | Result |
|---|---:|
| Clean portfolio | 5,000 rows |
| Clean total TIV | ₹168.8667B |
| X-005 calibration | Exact match |
| P-001 calibration | Exact match |
| Dirty portfolio | 5,020 rows |
| Ground truth | 10,001 events |
| Detection flags | 11,035 |
| Affected rows | 4,632 |
| Overall TP | 9,982 |
| Overall FP | 1,053 |
| Overall FN | 19 |
| Overall precision | 90.4576% |
| Overall recall | 99.8100% |
| Treatment | Exact match |
| Materiality records | 11,035 |
| Accumulation summary | Exact match |
| Accumulation sensitivity | Exact match |
| Impact summary | Exact match |

This confirms that the current analytical pipeline is reproducible in a clean database environment.

---

# 9. What I rejected, and why

## X7 centroid-distance detector

An early geography detector attempted to identify suspicious coordinates using centroid-distance logic.

The detector produced very low precision because legitimate exposures can naturally occur far from simple district or portfolio centroids.

The rule was rejected rather than retained merely to increase the number of available checks.

This reflects an important principle:

> A detector that produces many alerts but very few useful alerts is not automatically a better detector.

---

## City-coordinate validation without authoritative boundaries

City-coordinate consistency could not be established reliably without an authoritative city-boundary dataset.

Rather than treating internally generated city-centroid relationships as ground truth, the workflow retained the limitation and used authoritative GADM district boundaries for the geographic validation that could be supported.

---

## Treating every detector flag as an error

Detector output is deliberately not converted directly into corrections.

Heuristic plausibility findings may represent:

- genuine errors
- legitimate unusual exposures
- incomplete information
- modelling assumptions

These therefore flow into materiality and treatment rather than being automatically overwritten.

---

# Known limitations

## Synthetic portfolio

The portfolio is synthetic and is designed for workflow demonstration.

The accumulation patterns therefore demonstrate the behaviour of an exposure-quality workflow and should not be interpreted as real insured exposure concentration for Odisha.

---

## Synthetic postcode reference

Postcode relationships used in the project are internally constructed for the selected districts.

They provide a controlled reference for consistency testing but are not a substitute for an authoritative production postcode database.

---

## Controlled duplication test

The duplication rules include controlled synthetic tests.

They demonstrate detection and workflow behaviour but are not equivalent to full production entity resolution against an external policyholder or location database.

---

## Heuristic detector performance

The injected-error detection precision is **75.28%**, while recall is **99.41%**.

The high recall is partly driven by deterministic rules whose conditions directly correspond to the injected corruption.

Heuristic rules have lower precision because unusual does not necessarily mean wrong.

Production implementation would require calibration against real portfolio review outcomes.

---

## Materiality implementation

The current materiality implementation explicitly maps each of the 39 quality rules to one of three materiality axes:

- Hazard
- Vulnerability
- Financial

The current materiality output contains:

| Axis | Findings |
|---|---:|
| Hazard | **1,171** |
| Vulnerability | **7,291** |
| Financial | **2,573** |
| **Total** | **11,035** |

These mappings are rule-based and are not inferred retrospectively from the observed data.

**Important limitation:** the current catalogue assigns exactly one axis to each rule. This is a deliberate simplification for the present implementation, but it can under-represent cross-dimensional consequences. For example, G-002 can affect hazard and financial linkage, while X-003 can affect vulnerability and financial interpretation. A future enhancement is therefore to support **multi-axis materiality mappings** with explicit weighting or attribution rules where justified.

---

## AAL linkage assumption

Project 2 does not constitute a new catastrophe model.

Where AAL linkage is performed, it uses cell-level proportional scaling against Project 1 outputs:

\[
AAL_{P2,c}
=
AAL_{P1,c}
\times
\frac{TIV_{P2,c}}{TIV_{P1,c}}
\]

This is appropriate only under the assumptions of the Project 1 framework and shared spatial grid.

### AAL arithmetic reconciliation

The sensitivity AAL rows are **scenario totals**, not incremental AAL deltas.

Therefore:

- **P001_SENSITIVITY** = PRIMARY + the incremental P-001 exposure
- **P003_SENSITIVITY** = PRIMARY + the incremental P-003 exposure
- **COMBINED_SENSITIVITY** = PRIMARY + incremental P-001 + incremental P-003

Using the current values:

| Component | TIV | Linked AAL |
|---|---:|---:|
| PRIMARY | ₹155.284B | ₹1.930B |
| Incremental P-001 | ₹786.144B | ₹9.234B |
| Incremental P-003 | ₹520.833B | ₹4.675B |
| **COMBINED_SENSITIVITY** | **₹1,462.261B** | **₹15.839B** |

The reconciliation is therefore:

\[
1.930 + 9.234 + 4.675 \approx 15.839\text{ B}
\]

and:

\[
155.284 + 786.144 + 520.833 \approx 1,462.261\text{ B}
\]

The resulting combined AAL/TIV ratio is approximately **1.083%**. It is not required to lie between the standalone PRIMARY, P001_SENSITIVITY and P003_SENSITIVITY ratios because those sensitivity rows are cumulative scenario totals and the combined scenario is constructed from **incremental deltas** relative to PRIMARY.

A production model with construction-specific vulnerability, occupancy-specific vulnerability, policy terms, deductibles, limits, or other non-linear exposure characteristics would require a full model rerun.

---

## Primary accumulation is a scenario

The primary accumulation excludes unresolved material referred records.

It should therefore not be interpreted as a fully reconciled "true" portfolio.

Instead, it represents the exposure that can currently be supported for primary accumulation under the project's treatment and materiality rules.

Excluded material records remain available through sensitivity scenarios.

---

# Repository structure

```text
odisha-exposure-quality/
│
├── data/
│   ├── district_fallback_points.gpkg
│   ├── gadm41_IND_0.json
│   ├── gadm41_IND_2.json/
│   │   └── gadm41_IND_2.json
│   ├── odisha_exposure_grid.gpkg
│   ├── aal_by_centroid.gpkg
│   ├── portfolio_clean.csv
│   ├── portfolio_clean_for_db.csv
│   ├── portfolio_dirty.csv
│   ├── ground_truth.csv
│   ├── injection_log.csv
│   ├── postcode_district_reference.csv
│   └── materiality_tiv_reference.csv
│
├── python/
│   ├── generate_portfolio.py
│   ├── inject_errors.py
│   ├── load_portfolio.py
│   ├── load_reference_data.py
│   ├── calibrate_references.py
│   ├── build_materiality_reference.py
│   ├── evaluate.py
│   ├── treatment.py
│   ├── calculate_aal_scenarios.py
│   └── generate_figures.py
│
├── sql/
│   ├── 01_schema.sql
│   ├── 02_rules_catalogue.sql
│   ├── 03_detection_rules.sql
│   ├── 04_materiality.sql
│   └── 05_accumulation.sql
│
├── outputs/
│   └── ...
│
├── requirements.txt
├── PROJECT2_BLUEPRINT.md
└── README.md
```

The Project 1 spatial grid required by the accumulation workflow is now stored locally as:

```text
data/odisha_exposure_grid.gpkg
```

This removes the dependency on the original external Project 1 filesystem path.

---

# Database structure

The workflow is implemented in PostgreSQL with PostGIS.

Core tables include:

- `portfolio_raw`
- `portfolio_cleansed`
- `rule_catalogue`
- `quality_flags`
- `materiality_scores`
- `materiality_tiv_reference`
- `x005_reference`
- `p001_reference`

Reference and accumulation tables are created by the corresponding loading and accumulation scripts.

PostGIS is used for:

- spatial operations
- administrative-boundary validation
- geography checks
- accumulation grid assignment

---

# Reproducing the project

## 1. Environment

The project uses:

- Python 3.11
- PostgreSQL 16
- PostGIS 3.4
- pandas
- NumPy
- GeoPandas
- Shapely
- pyproj
- pyogrio
- SQLAlchemy
- GeoAlchemy2
- psycopg2-binary
- Matplotlib
- openpyxl
- Faker
- python-dotenv

The pinned Python dependencies are stored in:

```text
requirements.txt
```

Create the environment, for example:

```bash
conda create -n exposure_env python=3.11
conda activate exposure_env
pip install -r requirements.txt
```

---

# 2. PostgreSQL and PostGIS

Create a PostgreSQL database:

```bash
sudo -u postgres createdb -O navneet odisha_exposure
```

Enable PostGIS:

```bash
sudo -u postgres psql -d odisha_exposure \
    -c "CREATE EXTENSION IF NOT EXISTS postgis;"
```

The database user must have access to the database.

For a fresh reproduction database, for example:

```bash
sudo -u postgres createdb -O navneet odisha_exposure_repro

sudo -u postgres psql -d odisha_exposure_repro \
    -c "CREATE EXTENSION IF NOT EXISTS postgis;"
```

---

# 3. Select the database

The Python scripts support:

```bash
export ODISHA_DB_NAME=odisha_exposure
```

For the reproduction database:

```bash
export ODISHA_DB_NAME=odisha_exposure_repro
```

If the variable is not set, the scripts default to:

```text
odisha_exposure
```

---

# 4. Create the database schema

Run:

```bash
psql -d "$ODISHA_DB_NAME" -f sql/01_schema.sql
```

Then load the 39-rule catalogue:

```bash
psql -d "$ODISHA_DB_NAME" -f sql/02_rules_catalogue.sql
```

---

# 5. Load reference data

The project now uses self-contained local reference files.

Run:

```bash
python python/load_reference_data.py
```

The local Project 1 exposure grid should contain:

```text
525 features
```

The district fallback reference contains:

```text
4 features
```

---

# 6. Generate the clean portfolio

Run:

```bash
python python/generate_portfolio.py
```

The deterministic generator uses:

```text
N_LOCATIONS = 5000
RANDOM_SEED = 42
```

The resulting clean portfolio should contain:

```text
5,000 rows
```

The current generator derives building TIV from sampled floor area and construction-specific value-per-square-metre assumptions; contents and business-interruption values are then derived from building TIV. This avoids the independent TIV/floor-area sampling that caused the earlier 60 clean-baseline X-001 flags.

The clean portfolio total TIV should be approximately:

```text
₹168,866,720,817.60
```

---

# 7. Load the clean portfolio

The loader defaults to:

```text
data/portfolio_clean.csv
```

Run:

```bash
python python/load_portfolio.py
```

Expected:

```text
5,000 rows
row_id 1–5000
```

---

# 8. Calibrate frozen references

Run:

```bash
python python/calibrate_references.py
```

The current clean-baseline calibration should produce:

### X-005

```text
Median TIV/m²      42,260.835257
Maximum TIV/m²     288,459.685129
Multiplier         7
Threshold          295,825.846800
```

### P-001

```text
Median building TIV     16,907,259.331
Maximum building TIV    229,617,246.319
Multiplier              14
Threshold               236,701,630.634
```

---

# 9. Verify the clean baseline

Before injection, run the detection SQL:

```bash
psql -d "$ODISHA_DB_NAME" -f sql/03_detection_rules.sql
```

The clean portfolio should produce:

```text
0 quality flags
0 affected rows
```

This is an important reproducibility checkpoint.

---

# 10. Inject deterministic errors

Run:

```bash
python python/inject_errors.py
```

The injector uses deterministic seed 42.

It produces:

```text
data/portfolio_dirty.csv
data/ground_truth.csv
data/injection_log.csv
```

The dirty portfolio should contain:

```text
5,020 rows
```

The ground truth should contain:

```text
10,001 events
4,611 unique row IDs
```

---

# 11. Load the dirty portfolio

Because `load_portfolio.py` defaults to the clean portfolio, select the dirty file explicitly:

```bash
PORTFOLIO_FILE=portfolio_dirty.csv \
python python/load_portfolio.py
```

Before doing this on an existing database, replace the previous raw portfolio:

```bash
psql -d "$ODISHA_DB_NAME" \
    -c "TRUNCATE TABLE portfolio_raw RESTART IDENTITY CASCADE;"
```

Then:

```bash
PORTFOLIO_FILE=portfolio_dirty.csv \
python python/load_portfolio.py
```

Expected:

```text
5,020 rows
row_id 1–5020
```

---

# 12. Run detection

Detection SQL populates `quality_flags`.

Run:

```bash
psql -d "$ODISHA_DB_NAME" -f sql/03_detection_rules.sql
```

Expected:

```text
11,035 quality flags
4,632 affected rows
```

---

# 13. Evaluate detection

Only after `03_detection_rules.sql` has populated `quality_flags`, run:

```bash
python python/evaluate.py
```

Expected headline results:

```text
Ground-truth pairs : 10001
Detected pairs     : 11035
True positives     : 9982
False positives    : 1053
False negatives    : 19
Precision           : 90.4576%
Recall              : 99.8100%
```

Injected-only:

```text
Ground-truth pairs : 3226
Detected pairs     : 4260
True positives     : 3207
False positives    : 1053
False negatives    : 19
Precision           : 75.2817%
Recall              : 99.4110%
```

Completeness:

```text
Ground-truth pairs : 6775
Detected pairs     : 6775
Coverage            : 100.0000%
```

---

# 14. Run treatment

Run:

```bash
python python/treatment.py
```

Expected:

```text
Portfolio rows: 5,020
Quality flags:  11,035
Inserted 5,020 records into portfolio_cleansed
```

Treatment:

```text
REFERRED       4171
NONE            388
FIXED           190
QUARANTINED     176
ASSUMED          95
```

---

# 15. Build the materiality TIV reference

The materiality assessment uses validated TIV from the authoritative clean portfolio for the original 5,000 records. Build this reference before running the materiality SQL:


Run:

```bash
python python/build_materiality_reference.py
```

Expected:

```text
Rows               : 5000
Min row_id         : 1
Max row_id         : 5000
Total validated TIV: approximately 168866720817.60
```

---

# 16. Run materiality

Run:

```bash
psql -d "$ODISHA_DB_NAME" -f sql/04_materiality.sql
```

Expected:

```text
Materiality records = 11,035

P1 = 206
P2 = 5,503
P3 = 5,326
```

The materiality output should contain:

```text
Hazard         = 1,171
Vulnerability = 7,291
Financial     = 2,573
```

---

# 17. Run accumulation

Run:

```bash
psql -d "$ODISHA_DB_NAME" -f sql/05_accumulation.sql
```

The main derived tables should contain:

```text
accumulation_summary          2 rows
accumulation_comparison      18 rows
accumulation_sensitivity     68 rows
accumulation_impact_summary   5 rows
```

The main accumulation results should be:

```text
DIRTY
18 cells
4,552 locations
₹1,465,404,071,770.565

PRIMARY
17 cells
4,421 locations
₹155,284,374,688.504
```

---

# 18. Calculate linked AAL scenarios

Project 2 does not rerun the catastrophe model. Instead, where Project 1 cell-level AAL outputs are available, the current workflow applies proportional cell-level scaling:

\[
AAL_{P2,c}
=
AAL_{P1,c}
\times
\frac{TIV_{P2,c}}{TIV_{P1,c}}
\]

Run:

```bash
python python/calculate_aal_scenarios.py
```

The script produces:

```text
outputs/aal_scenario_summary.csv
outputs/aal_scenario_cell_linkage.csv
```

The current linked AAL scenarios include:

| Scenario | TIV | Linked AAL | AAL / TIV |
|---|---:|---:|---:|
| PRIMARY | ₹155.284B | ₹1.930B | 1.243% |
| P001_SENSITIVITY | ₹941.428B | ₹11.164B | 1.186% |
| P003_SENSITIVITY | ₹676.118B | ₹6.604B | 0.977% |
| COMBINED_SENSITIVITY | ₹1.462T | ₹15.839B | 1.083% |
| DIRTY | ₹1.465T | ₹15.841B | 1.081% |

These are **linked/modelled AAL values under proportional cell-level scaling**, not results from a new catastrophe-model rerun.

---

# Reproducibility checkpoints

A successful end-to-end reproduction should satisfy:

| Checkpoint | Expected |
|---|---:|
| Clean portfolio rows | 5,000 |
| Clean total TIV | ₹168.8667B |
| X-005 threshold | ₹295,825.8468/m² |
| P-001 threshold | ₹236,701,630.634 |
| Clean detection flags | 0 |
| Dirty portfolio rows | 5,020 |
| Ground-truth events | 10,001 |
| Unique GT row IDs | 4,611 |
| Detection flags | 11,035 |
| Affected rows | 4,632 |
| Overall TP | 9,982 |
| Overall FP | 1,053 |
| Overall FN | 19 |
| Overall precision | 90.4576% |
| Overall recall | 99.8100% |
| Injected-only precision | 75.2817% |
| Injected-only recall | 99.4110% |
| Completeness coverage | 100% |
| Cleansed records | 5,020 |
| Fixed | 190 |
| Assumed | 95 |
| Quarantined | 176 |
| Referred | 4,171 |
| None | 388 |
| Materiality records | 11,035 |
| Accumulation summary rows | 2 |
| Accumulation comparison rows | 18 |
| Sensitivity rows | 68 |
| Impact summary rows | 5 |

---

# Data sources

| Dataset | Source | Use |
|---|---|---|
| GADM Level 0 | GADM | India national boundary |
| GADM Level 2 | GADM | Odisha district boundaries |
| Project 1 exposure grid | Project 1 | 0.25° accumulation grid |
| Project 1 AAL grid | Project 1 | Cell-level AAL for proportional linkage |
| LitPop-derived exposure | Project 1 / synthetic generation | Spatial weighting |
| District fallback points | Project 2 synthetic reference | Accumulation fallback |
| Postcode reference | Project 2 synthetic reference | Coding consistency |

The Project 1 exposure grid contains:

> **525 cells**

and is stored locally as:

```text
data/odisha_exposure_grid.gpkg
```

Project 2 deliberately aligns accumulation analysis to this existing grid so that exposure-quality findings can be connected to the catastrophe-risk framework developed in Project 1.

---

# Figures

Figures generated from the current pipeline should be stored under:

```text
outputs/figures/
```

The current pipeline generates the following figures:

```text
01_detection_performance_by_dimension.png
02_materiality_funnel.png
03_dirty_vs_primary_accumulation.png
04_concentration_hhi.png
04b_top1_concentration.png
05_aal_scenario_table.png
06_treatment_summary.png
```

These are generated by:

```bash
python python/generate_figures.py
```

Figures **05** and **06** correspond respectively to the AAL scenario table and treatment summary listed above.

The AAL figure is based on the current Project 1 / Project 2 cell-level proportional linkage outputs. It should be interpreted as linked/modelled AAL under the stated proportional-scaling assumption, not as a new catastrophe-model rerun.

---

# Key lessons from the workflow

## 1. Data quality is not binary

A value is not simply "good" or "bad".

Some values are:

- demonstrably wrong
- suspicious but plausible
- impossible to verify
- dependent on a modelling assumption

The workflow therefore preserves uncertainty instead of hiding it.

---

## 2. Detection and materiality are different problems

A detector asks:

> "Does this record deserve attention?"

Materiality asks:

> "Could this issue materially change the decision?"

A portfolio can contain thousands of findings while only a smaller subset requires escalation.

---

## 3. Plausible values can still be dangerous

P-001 demonstrates that a TIV value can look numerically reasonable at the individual-record level while being materially wrong at portfolio level.

Exposure quality therefore has to be assessed both:

- record by record
- in aggregate

---

## 4. Spatial accumulation exposes problems that row-level QA can miss

P-003 demonstrates why accumulation analysis is important.

A single large exposure can materially change the concentration profile of a portfolio even when its individual fields are syntactically valid.

---

## 5. Auditability matters as much as correction

The workflow does not simply overwrite suspicious values.

For each treated issue, the process retains:

- original value
- cleaned value
- treatment decision
- treatment rule
- treatment method
- classification
- priority
- quarantine/referral status

This makes the final portfolio traceable back to the original data.

---

## 6. Reproducibility requires explicit workflow state

The fresh-database reproduction revealed several important operational requirements:

- reference data must be loaded before spatial SQL is run
- PostGIS must be enabled in a fresh database
- clean and dirty portfolio loading must be explicit
- the PostgreSQL identity sequence must be reset when replacing raw data
- detection SQL must run before the Python evaluation script
- calibration references must be frozen before dirty data is introduced

These are now part of the documented reproduction workflow.

---

# Future work

- Replace synthetic exposure generation with a real commercial or public exposure portfolio.
- Add authoritative India-wide postcode and city reference datasets.
- Introduce real entity-resolution testing using policyholder/location identifiers.
- Calibrate heuristic detector thresholds against reviewed portfolio outcomes.
- Add construction-specific and occupancy-specific vulnerability functions.
- Incorporate policy limits, deductibles and insured values.
- Extend accumulation analysis to multiple geographic resolutions.
- Add account-level and policy-level accumulation.
- Connect exposure-quality changes to full catastrophe-model reruns rather than proportional AAL scaling.
- Add automated data-quality reporting for repeated portfolio submissions.
- Introduce analyst review queues for P1 and high-impact P2 findings.
- Track changes between successive portfolio versions.
- Extend the current single-axis materiality catalogue to support justified multi-axis mappings and explicit attribution across hazard, vulnerability and financial impacts.
- Add automated end-to-end reproduction checks.

---

# Relationship to Project 1

Project 1 established the catastrophe-risk modelling framework for coastal Odisha:

```text
Hazard × Exposure × Vulnerability
            ↓
           Loss
            ↓
       AAL / OEP / AEP / TVaR
```

Project 2 focuses on a different part of the same modelling chain:

```text
Raw Portfolio
     ↓
Data Quality
     ↓
Materiality
     ↓
Treatment
     ↓
Accumulation
     ↓
Exposure Input
     ↓
Catastrophe Risk Model
     ↓
Loss / Risk Metrics
```

The projects therefore address complementary problems.

**Project 1 asks:**

> How can cyclone hazard, exposure and vulnerability be combined to estimate risk?

**Project 2 asks:**

> Can the exposure input be trusted, and how sensitive is the accumulation/risk workflow to unresolved exposure-quality issues?

The shared 0.25° grid provides the spatial bridge between the two projects.

---

# Conclusion

This project demonstrates an exposure-quality workflow rather than a simple data-cleaning script.

The portfolio is:

1. interrogated across multiple dimensions,
2. deliberately corrupted using controlled error injection,
3. evaluated against explicit ground truth,
4. classified into errors, unknowns and assumptions,
5. assessed for materiality,
6. treated or escalated,
7. separated into primary and sensitivity accumulation scenarios,
8. and quantified for downstream exposure impact.

The current validated implementation produces:

> **5,020 dirty records → 10,001 ground-truth events → 11,035 detected flags → 5,020 treated records → 17–18 occupied accumulation cells**

with:

> **99.81% overall recall**

and:

> **75.28% injected-error precision**

The accumulation comparison shows:

> **₹1.465T dirty TIV**

versus:

> **₹155.284B primary accumulation-eligible TIV**

with concentration also changing materially between scenarios.

The important result is not simply the magnitude of the exposure difference.

It is the workflow used to arrive at it:

> **detect → classify → assess materiality → treat → accumulate → quantify impact**

That process is designed to make exposure analysis **traceable, reproducible and decision-relevant**.

---

# References

1. GADM. *Database of Global Administrative Areas.* GADM Level 0 and Level 2 administrative boundaries.
2. Aznar-Siguan, G. & Bresch, D. N. (2019). *CLIMADA v1: a global weather and climate risk assessment platform.* Geoscientific Model Development, 12, 3085–3097.
3. Eberenz, S., Stocker, D., Röösli, T., & Bresch, D. N. (2020). *Asset exposure data for global physical risk assessment.* Earth System Science Data, 12, 817–833.
4. Project 1: *Climate-Conditioned Tropical Cyclone Risk — Coastal Odisha.* Existing catastrophe-risk model and 0.25° exposure grid used for spatial alignment and risk linkage.
5. PostgreSQL Documentation.
6. PostGIS Documentation.

---

# Author

**Navneet Krishnan**

M.Sc. Atmospheric Sciences · National Institute of Technology Rourkela

LinkedIn:  
https://www.linkedin.com/in/navneet-krishnan2004

Email:  
krishnan.navneet2004@gmail.com