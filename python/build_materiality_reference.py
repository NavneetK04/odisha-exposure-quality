import os
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text


# ============================================================
# CONFIGURATION
# ============================================================

DB_NAME = os.getenv("ODISHA_DB_NAME", "odisha_exposure")
DB_URL = f"postgresql+psycopg2:///{DB_NAME}"

PROJECT_ROOT = Path.home() / "Projects"
DATA_DIR = PROJECT_ROOT / "odisha-exposure-quality" / "data"

CLEAN_FILE = DATA_DIR / "portfolio_clean.csv"

engine = create_engine(DB_URL)


# ============================================================
# LOAD AUTHORITATIVE CLEAN PORTFOLIO
# ============================================================

print("Loading authoritative clean portfolio...")

df = pd.read_csv(CLEAN_FILE)

if len(df) != 5000:
    raise ValueError(
        f"Expected 5,000 clean rows, found {len(df):,}"
    )

if df["tiv_total"].isna().any():
    raise ValueError("Clean portfolio contains NULL tiv_total values.")

if (df["tiv_total"] <= 0).any():
    raise ValueError("Clean portfolio contains non-positive tiv_total values.")


# inject_errors.py defines the stable evaluation key:
# clean portfolio rows -> row_id 1..5000

df.insert(
    0,
    "row_id",
    range(1, len(df) + 1)
)

reference = df[
    ["row_id", "tiv_total"]
].rename(
    columns={"tiv_total": "validated_tiv"}
)

reference["validation_basis"] = (
    "authoritative_clean_portfolio"
)


# ============================================================
# WRITE DATABASE REFERENCE
# ============================================================

with engine.begin() as conn:

    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS materiality_tiv_reference (
            row_id INTEGER PRIMARY KEY,
            validated_tiv NUMERIC NOT NULL,
            validation_basis VARCHAR(50) NOT NULL
        );
    """))

    conn.execute(
        text("TRUNCATE TABLE materiality_tiv_reference;")
    )


reference.to_sql(
    "materiality_tiv_reference",
    engine,
    if_exists="append",
    index=False,
)


# ============================================================
# QA
# ============================================================

with engine.connect() as conn:

    result = conn.execute(text("""
        SELECT
            COUNT(*) AS rows,
            MIN(row_id) AS min_row_id,
            MAX(row_id) AS max_row_id,
            SUM(validated_tiv) AS total_validated_tiv
        FROM materiality_tiv_reference;
    """)).mappings().one()


print()
print("Materiality TIV reference QA:")
print(f"Rows              : {result['rows']}")
print(f"Min row_id        : {result['min_row_id']}")
print(f"Max row_id        : {result['max_row_id']}")
print(f"Total validated TIV: {result['total_validated_tiv']}")
print()
print("Materiality TIV reference created successfully.")
