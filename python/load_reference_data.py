import geopandas as gpd
import pandas as pd
from pathlib import Path
from sqlalchemy import create_engine, text
import os


# ============================================================
# CONFIGURATION
# ============================================================

DB_NAME = os.getenv("ODISHA_DB_NAME", "odisha_exposure")
DB_URL = f"postgresql+psycopg2:///{DB_NAME}"

PROJECT_ROOT = Path.home() / "Projects"
DATA_DIR = PROJECT_ROOT / "odisha-exposure-quality" / "data"

GADM_L2 = DATA_DIR / "gadm41_IND_2.json"

GADM_L0 = (
    DATA_DIR
    / "gadm41_IND_0.json"
)

POSTCODE_FILE = (
    DATA_DIR
    / "postcode_district_reference.csv"
)

GROUND_TRUTH_FILE = (
    DATA_DIR
    / "ground_truth.csv"
)

PROJECT1_GRID = (
    DATA_DIR
    / "odisha_exposure_grid.gpkg"
)

DISTRICT_FALLBACK = (
    DATA_DIR
    / "district_fallback_points.gpkg"
)

engine = create_engine(DB_URL)

# ============================================================
# LOAD PROJECT 1 GRID + DISTRICT FALLBACK REFERENCES
# ============================================================

print("Loading Project 1 exposure grid...")

project1_grid = gpd.read_file(
    PROJECT1_GRID,
    layer="exposure_grid"
)

project1_grid.to_postgis(
    "project1_exposure_grid",
    engine,
    if_exists="replace",
    index=False
)

print(
    f"Project 1 grid loaded: "
    f"{len(project1_grid)} features"
)


print("Loading district fallback points...")

fallback_points = gpd.read_file(
    DISTRICT_FALLBACK,
    layer="district_fallback_points"
)

fallback_points.to_postgis(
    "district_fallback_points",
    engine,
    if_exists="replace",
    index=False
)

print(
    f"District fallback points loaded: "
    f"{len(fallback_points)} features"
)


# ============================================================
# LOAD DISTRICT BOUNDARIES
# ============================================================

print("Loading GADM Level 2 boundaries...")

districts = gpd.read_file(GADM_L2)

# Keep only Odisha districts used by Project 2
GADM_DISTRICT_MAP = {
    "Cuttack": "Cuttack",
    "Jagatsinghapur": "Jagatsinghpur",
    "Khordha": "Khordha",
    "Puri": "Puri",
}

districts = districts[
    districts["NAME_2"].isin(GADM_DISTRICT_MAP.keys())
].copy()

districts["district"] = districts["NAME_2"].map(
    GADM_DISTRICT_MAP
)

districts = districts[
    ["district", "geometry"]
]

districts = districts.to_crs("EPSG:4326")

print(f"Loaded {len(districts)} target district boundaries.")


# ============================================================
# LOAD INDIA BOUNDARY
# ============================================================

print("Loading GADM Level 0 India boundary...")

india = gpd.read_file(GADM_L0)

india = india[
    india["GID_0"] == "IND"
].copy()

india = india[
    ["GID_0", "geometry"]
].rename(
    columns={"GID_0": "gid_0"}
)

india = india.to_crs("EPSG:4326")

print(f"Loaded {len(india)} India boundary feature(s).")


# ============================================================
# LOAD POSTCODE REFERENCE
# ============================================================

print("Loading postcode reference...")

postcode = pd.read_csv(
    POSTCODE_FILE,
    dtype={"postcode": str}
)

print(
    f"Loaded {len(postcode)} postcode reference rows."
)


# ============================================================
# LOAD GROUND-TRUTH ERROR REFERENCE
# ============================================================

print("Loading ground-truth error reference...")

ground_truth = pd.read_csv(
    GROUND_TRUTH_FILE
)

print(
    f"Loaded {len(ground_truth)} ground-truth events."
)


# ============================================================
# WRITE REFERENCE TABLES
# ============================================================

print("Writing reference tables...")

districts.to_postgis(
    "admin_boundaries",
    engine,
    if_exists="replace",
    index=False
)

india.to_postgis(
    "india_boundary",
    engine,
    if_exists="replace",
    index=False
)

postcode.to_sql(
    "postcode_district_reference",
    engine,
    if_exists="replace",
    index=False
)

ground_truth.to_sql(
    "ground_truth",
    engine,
    if_exists="replace",
    index=False
)


# ============================================================
# PRIMARY KEY / INDEXES
# ============================================================

with engine.begin() as conn:

    conn.execute(text("""
        ALTER TABLE admin_boundaries
        ADD PRIMARY KEY (district);
    """))

    conn.execute(text("""
        ALTER TABLE india_boundary
        ADD PRIMARY KEY (gid_0);
    """))

    conn.execute(text("""
        ALTER TABLE postcode_district_reference
        ADD PRIMARY KEY (postcode);
    """))


# ============================================================
# QA
# ============================================================

with engine.connect() as conn:

    district_count = conn.execute(
        text("""
            SELECT COUNT(*)
            FROM admin_boundaries;
        """)
    ).scalar()

    india_count = conn.execute(
        text("""
            SELECT COUNT(*)
            FROM india_boundary;
        """)
    ).scalar()

    postcode_count = conn.execute(
        text("""
            SELECT COUNT(*)
            FROM postcode_district_reference;
        """)
    ).scalar()

    ground_truth_count = conn.execute(
        text("""
            SELECT COUNT(*)
            FROM ground_truth;
        """)
    ).scalar()


print()
print("Reference-data QA:")
print(f"District boundaries : {district_count}")
print(f"India boundary      : {india_count}")
print(f"Postcode references : {postcode_count}")
print(f"Ground-truth events : {ground_truth_count}")
print()
print("Reference data loaded successfully.")
