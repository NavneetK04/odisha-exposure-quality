# Reproducibility

> Full environment setup, database preparation, pipeline execution, validation checkpoints, and data-source details for reproducing the project.

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
