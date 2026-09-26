# Methodology

> Detailed methodology, validation logic, treatment decisions, accumulation analysis, catastrophe-risk linkage, and known limitations for the Odisha exposure data-quality project.

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

![Detection performance by dimension](../outputs/figures/01_detection_performance_by_dimension.png)


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

The treatment framework uses five record-level outcomes:

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

![Treatment summary](../outputs/figures/06_treatment_summary.png)


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

![Materiality funnel](../outputs/figures/02_materiality_funnel.png)


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

Instead, the production accumulation excludes the unique records flagged by the accumulation-critical **P-001/P-003 quality rules**. These exclusions are driven by the production `quality_flags` table rather than by ground truth.

This keeps detector evaluation and production accumulation logically separate: ground truth is used to evaluate detection performance, while the production detector output determines accumulation eligibility.

The excluded records remain available through the sensitivity scenarios.

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

![Dirty versus primary accumulation](../outputs/figures/03_dirty_vs_primary_accumulation.png)


The current validated accumulation results are:

| Portfolio | Grid cells | Locations | TIV |
|---|---:|---:|---:|
| DIRTY | **18** | **4,552** | **₹1,465,404,071,770.565** |
| CLEANSED / PRIMARY | **17** | **4,409** | **₹145,684,374,688.504** |

The dirty-to-primary TIV ratio is approximately:

> **10.06×**

The primary accumulation excludes **41 unique records** flagged by the accumulation-critical P-001/P-003 rules. In the seed-42 evaluation, **26** of these correspond to injected ground-truth events and **15** are detector false positives. The cleansed TIV associated with those 15 false-positive exclusions is **₹12.0B**.

The two detected P-003 records overlap with the P-001 detection set, so the production exclusion set contains **41 unique records rather than 43**.

This is a scenario comparison under the project's treatment and accumulation-eligibility framework.

It should **not** be interpreted as saying that cleaning has reduced the true underlying portfolio by 10.06×.

---

# Concentration metrics

![Concentration HHI](../outputs/figures/04_concentration_hhi.png)

![Top-1 concentration](../outputs/figures/04b_top1_concentration.png)


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
| Top-1 concentration | 39.252% |
| Top-3 concentration | 71.455% |
| Top-5 concentration | 86.314% |
| HHI | 0.224192 |
| Occupied cells | 17 |

These results describe the synthetic portfolio generated for the project. They should not be interpreted as estimates of actual insured exposure concentration for Odisha.

---

# Sensitivity analysis

The primary accumulation excludes the unique records flagged by the accumulation-critical P-001/P-003 detection rules.

Separate sensitivity scenarios are retained to examine the resulting accumulation under the production detection framework.

In the seed-42 run, both detected P-003 records are contained within the P-001 exclusion set. Consequently, P001_SENSITIVITY and COMBINED_SENSITIVITY produce the same accumulation result, while P003_SENSITIVITY produces a distinct result from PRIMARY.

The COMBINED_SENSITIVITY scenario is a separate cumulative scenario that retains the relevant unresolved exposure and is therefore not an additive combination of independent P001 and P003 increments.

| Scenario | TIV | Top-1 | Top-3 | Top-5 | HHI | Cells |
|---|---:|---:|---:|---:|---:|---:|
| **PRIMARY** | ₹145.684B | 39.252% | 71.455% | 86.314% | 0.2242 | 17 |
| **P003_SENSITIVITY** | ₹829.722B | 84.979% | 94.988% | 97.597% | 0.7284 | 17 |
| **P001_SENSITIVITY** | ₹1,462.261B | 53.227% | 81.902% | 90.953% | 0.3435 | 17 |
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

P-003 ground truth remains available for detector evaluation, but it is not used to determine production accumulation eligibility. The primary accumulation is driven by the production `quality_flags` output for P-001/P-003.

In the seed-42 evaluation, the production detection set contains **41 unique records** flagged by P-001/P-003. Ground truth contains **26** corresponding injected records, leaving **15 detector false positives**. The cleansed TIV associated with those false-positive exclusions is **₹12.0B**. The two detected P-003 records overlap with the P-001 detection set, so the production exclusion set contains 41 unique records rather than 43.

The purpose of the rule is to identify an exposure whose value creates an unusually large concentration at one location.

This demonstrates why accumulation analysis cannot be separated from exposure data quality.

A value can be:

- syntactically valid
- geographically located
- numerically populated

and still require escalation because of its impact on portfolio concentration.

---

# 7. Linkage to catastrophe-risk modelling

![AAL scenario analysis](../outputs/figures/05_aal_scenario_table.png)


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
- unresolved P-001/P-003 records detected by the production quality-control pipeline are excluded from the primary accumulation
- production detector output, rather than ground truth, determines accumulation eligibility
- sensitivity scenarios are retained to document the effect of the detected exclusion framework
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

The sensitivity AAL rows are **scenario totals**, not independent incremental AAL contributions.

Under the corrected production-driven accumulation logic, both detected P-003 records are contained within the P-001 exclusion set. Therefore, P001_SENSITIVITY and COMBINED_SENSITIVITY coincide in this seed-42 run, while P003_SENSITIVITY produces a distinct accumulation and AAL result from PRIMARY.

Using the current values:

| Scenario | TIV | Linked AAL |
|---|---:|---:|
| PRIMARY | ₹145.684B | ₹1.811B |
| P003_SENSITIVITY | ₹829.722B | ₹7.950B |
| P001_SENSITIVITY | ₹1,462.261B | ₹15.839B |
| COMBINED_SENSITIVITY | ₹1,462.261B | ₹15.839B |

The P001 and P003 scenarios are **not additive incremental components** of the combined scenario. In this seed-42 run, P001_SENSITIVITY and COMBINED_SENSITIVITY coincide because both detected P-003 records are contained within the P-001 exclusion set, while P003_SENSITIVITY produces a distinct scenario total.

The combined scenario is a separate cumulative sensitivity scenario that retains the relevant unresolved exposure rather than excluding it from the primary accumulation. Consequently, it should **not** be reconciled as:

\[
PRIMARY + \text{incremental P-001} + \text{incremental P-003}
\]

The combined scenario has:

\[
TIV = ₹1,462.261B
\]

and:

\[
AAL = ₹15.839B
\]

giving an AAL/TIV ratio of approximately:

\[
\mathbf{1.083\%}
\]

The primary scenario has:

\[
TIV = ₹145.684B
\]

and:

\[
AAL = ₹1.811B
\]

giving an AAL/TIV ratio of approximately:

\[
\mathbf{1.243\%}
\]

These ratios are scenario-specific and need not be interpreted as additive quantities.

A production model with construction-specific vulnerability, occupancy-specific vulnerability, policy terms, deductibles, limits, or other non-linear exposure characteristics would require a full catastrophe-model rerun.

---

## Primary accumulation is a scenario

The primary accumulation excludes the unique records flagged by the accumulation-critical P-001/P-003 detection rules.

It should therefore not be interpreted as a fully reconciled "true" portfolio.

Instead, it represents the exposure that can currently be supported for primary accumulation under the project's production detection and treatment framework.

Ground truth is used for detector evaluation only; production `quality_flags` determine accumulation eligibility.

Excluded records remain available through sensitivity scenarios.

---
