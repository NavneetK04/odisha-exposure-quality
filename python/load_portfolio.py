import pandas as pd
from pathlib import Path
from sqlalchemy import create_engine, text
import os


# ============================================================
# CONFIGURATION
# ============================================================

DB_NAME = os.getenv("ODISHA_DB_NAME", "odisha_exposure")
DB_URL = f"postgresql+psycopg2:///{DB_NAME}"

PROJECT_ROOT = Path.home()
DATA_FILE = (
    PROJECT_ROOT
    / "Projects"
    / "odisha-exposure-quality"
    / "data"
    / os.getenv("PORTFOLIO_FILE", "portfolio_clean.csv")
)

engine = create_engine(DB_URL)


# ============================================================
# LOAD CLEAN PORTFOLIO
# ============================================================

print(f"Loading portfolio: {DATA_FILE.name}")

df = pd.read_csv(DATA_FILE)

print(f"Rows loaded: {len(df):,}")


# ============================================================
# BASIC QA
# ============================================================

expected_rows = 5020 if os.getenv("PORTFOLIO_FILE") == "portfolio_dirty.csv" else 5000

if len(df) != expected_rows:
    raise ValueError(
        f"Expected {expected_rows:,} rows, found {len(df):,}"
    )

if df["tiv_total"].isna().any():
    raise ValueError(
        "Missing tiv_total values found in portfolio."
    )

if os.getenv("PORTFOLIO_FILE") != "portfolio_dirty.csv":
    if (df["tiv_total"] <= 0).any():
        raise ValueError(
            "Non-positive TIV found in clean portfolio."
        )

# ============================================================
# LOAD TO POSTGRESQL
# ============================================================

print("Writing portfolio_raw...")

df.to_sql(
    "portfolio_raw",
    engine,
    if_exists="append",
    index=False
)


# ============================================================
# QA AFTER LOAD
# ============================================================

with engine.connect() as conn:

    result = pd.read_sql(
        text("""
            SELECT
                COUNT(*) AS rows,
                MIN(row_id) AS min_row_id,
                MAX(row_id) AS max_row_id,
                SUM(tiv_total) AS total_tiv
            FROM portfolio_raw;
        """),
        conn
    )

print()
print("portfolio_raw QA:")
print(result.to_string(index=False))

print()
print(f"{DATA_FILE.name} loaded successfully.")