import math
from pathlib import Path
import os
import pandas as pd
from sqlalchemy import create_engine, text


# ============================================================
# CONFIGURATION
# ============================================================

DB_NAME = os.getenv("ODISHA_DB_NAME", "odisha_exposure")
DB_URL = f"postgresql+psycopg2:///{DB_NAME}"

PROJECT_ROOT = Path.home() / "Projects"
DATA_DIR = PROJECT_ROOT / "odisha-exposure-quality" / "data"

CLEAN_PORTFOLIO = DATA_DIR / "portfolio_clean.csv"

engine = create_engine(DB_URL)


# ============================================================
# LOAD AUTHORITATIVE CLEAN PORTFOLIO
# ============================================================

print("Loading authoritative clean portfolio...")

df = pd.read_csv(CLEAN_PORTFOLIO)

print(f"Clean portfolio rows: {len(df)}")


# ============================================================
# X-005 CALIBRATION
# ============================================================
#
# X-005 detects unusually high building TIV density:
#
#     tiv_building / floor_area_sqm
#
# Calibration rule:
#
#     threshold = integer_multiplier × clean median TIV/m²
#
# Choose the smallest integer multiplier for which:
#
#     threshold > clean maximum TIV/m²
#
# This ensures the clean baseline produces zero X-005
# detections.
# ============================================================

x005_valid = df[
    (df["floor_area_sqm"] > 0)
    & (df["tiv_building"].notna())
].copy()

x005_valid["tiv_per_sqm"] = (
    x005_valid["tiv_building"]
    / x005_valid["floor_area_sqm"]
)

x005_median = x005_valid["tiv_per_sqm"].median()
x005_max = x005_valid["tiv_per_sqm"].max()

x005_multiplier = math.floor(
    x005_max / x005_median
) + 1

x005_threshold = (
    x005_multiplier * x005_median
)

print()
print("X-005 calibration:")
print(f"  Median TIV/m² : {x005_median}")
print(f"  Clean max     : {x005_max}")
print(f"  Multiplier    : {x005_multiplier}")
print(f"  Threshold     : {x005_threshold}")


# ============================================================
# P-001 CALIBRATION
# ============================================================
#
# P-001 detects extreme building TIV outliers.
#
# Calibration rule:
#
#     threshold = integer_multiplier × clean median building TIV
#
# Choose the smallest integer multiplier for which:
#
#     threshold > clean maximum building TIV
#
# This ensures the clean baseline produces zero P-001
# detections.
# ============================================================

p001_valid = df[
    df["tiv_building"].notna()
    & (df["tiv_building"] > 0)
].copy()

p001_median = p001_valid["tiv_building"].median()
p001_max = p001_valid["tiv_building"].max()

p001_multiplier = math.floor(
    p001_max / p001_median
) + 1

p001_threshold = (
    p001_multiplier * p001_median
)

print()
print("P-001 calibration:")
print(f"  Median TIV     : {p001_median}")
print(f"  Clean max      : {p001_max}")
print(f"  Multiplier     : {p001_multiplier}")
print(f"  Threshold      : {p001_threshold}")


# ============================================================
# WRITE CALIBRATION REFERENCES
# ============================================================

with engine.begin() as conn:

    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS x005_reference (
            reference_name TEXT PRIMARY KEY,
            median_tiv_per_sqm DOUBLE PRECISION NOT NULL,
            multiplier INTEGER NOT NULL,
            threshold_per_sqm DOUBLE PRECISION NOT NULL,
            clean_max_tiv_per_sqm DOUBLE PRECISION NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """))

    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS p001_reference (
    reference_name TEXT PRIMARY KEY,
    median_tiv_building DOUBLE PRECISION NOT NULL,
    multiplier INTEGER NOT NULL,
    threshold_tiv_building DOUBLE PRECISION NOT NULL,
    clean_max_tiv_building DOUBLE PRECISION NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
    """))

    conn.execute(
        text("""
            DELETE FROM x005_reference
            WHERE reference_name = 'clean_baseline';
        """)
    )

    conn.execute(
        text("""
            DELETE FROM p001_reference
            WHERE reference_name = 'clean_baseline';
        """)
    )

    conn.execute(
        text("""
            INSERT INTO x005_reference (
                reference_name,
                median_tiv_per_sqm,
                multiplier,
                threshold_per_sqm,
                clean_max_tiv_per_sqm
            )
            VALUES (
                'clean_baseline',
                :median,
                :multiplier,
                :threshold,
                :clean_max
            );
        """),
        {
            "median": float(x005_median),
            "multiplier": int(x005_multiplier),
            "threshold": float(x005_threshold),
            "clean_max": float(x005_max),
        }
    )

    conn.execute(
        text("""
            INSERT INTO p001_reference (
                reference_name,
                median_tiv_building,
                multiplier,
                threshold_tiv_building,
                clean_max_tiv_building
            )
            VALUES (
                'clean_baseline',
                :median,
                :multiplier,
                :threshold,
                :clean_max
            );
        """),
        {
            "median": float(p001_median),
            "multiplier": int(p001_multiplier),
            "threshold": float(p001_threshold),
            "clean_max": float(p001_max),
        }
    )


# ============================================================
# FINAL QA
# ============================================================

with engine.connect() as conn:

    x005 = conn.execute(
        text("""
            SELECT
                reference_name,
                median_tiv_per_sqm,
                multiplier,
                threshold_per_sqm,
                clean_max_tiv_per_sqm
            FROM x005_reference
            WHERE reference_name = 'clean_baseline';
        """)
    ).mappings().one()

    p001 = conn.execute(
        text("""
            SELECT
                reference_name,
                median_tiv_building,
                multiplier,
                threshold_tiv_building,
                clean_max_tiv_building
            FROM p001_reference
            WHERE reference_name = 'clean_baseline';
        """)
    ).mappings().one()


print()
print("Reference calibration QA:")
print("X-005:", dict(x005))
print("P-001:", dict(p001))
print()
print("Calibration references created successfully.")
