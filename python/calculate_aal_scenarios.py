import os
from pathlib import Path

import geopandas as gpd
import pandas as pd
from sqlalchemy import create_engine, text


# ------------------------------------------------------------
# Configuration
# ------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
OUTPUT_DIR = PROJECT_ROOT / "outputs"
OUTPUT_DIR.mkdir(exist_ok=True)

DB_NAME = os.getenv("ODISHA_DB_NAME", "odisha_exposure")
DB_URL = f"postgresql+psycopg2:///{DB_NAME}"

AAL_FILE = DATA_DIR / "aal_by_centroid.gpkg"
GRID_FILE = DATA_DIR / "odisha_exposure_grid.gpkg"

AAL_LAYER = "aal"
GRID_LAYER = "exposure_grid"

engine = create_engine(DB_URL)


# ------------------------------------------------------------
# Read Project 1 AAL source
# ------------------------------------------------------------

print("Reading Project 1 AAL source...")

aal = gpd.read_file(AAL_FILE, layer=AAL_LAYER)

aal = aal[["geometry", "value", "aal"]].copy()

aal["grid_lon"] = aal.geometry.x.round(8)
aal["grid_lat"] = aal.geometry.y.round(8)

aal = aal.drop(columns="geometry")

aal = aal.rename(
    columns={
        "value": "project1_tiv",
        "aal": "project1_aal",
    }
)

print(f"Project 1 cells: {len(aal):,}")
print(f"Project 1 TIV: ₹{aal['project1_tiv'].sum():,.2f}")
print(f"Project 1 AAL: ₹{aal['project1_aal'].sum():,.2f}")


# ------------------------------------------------------------
# Read Project 1 exposure grid independently
# ------------------------------------------------------------

grid = gpd.read_file(GRID_FILE, layer=GRID_LAYER)

grid = grid[["geometry", "value"]].copy()

grid["grid_lon"] = grid.geometry.x.round(8)
grid["grid_lat"] = grid.geometry.y.round(8)

grid = grid.drop(columns="geometry")

grid = grid.rename(columns={"value": "grid_tiv"})

grid_check = grid.merge(
    aal[["grid_lon", "grid_lat", "project1_tiv"]],
    on=["grid_lon", "grid_lat"],
    how="outer",
    indicator=True,
)

if not (grid_check["_merge"] == "both").all():
    raise ValueError("Project 1 AAL grid and exposure grid do not match.")

grid_check["tiv_difference"] = (
    grid_check["grid_tiv"] - grid_check["project1_tiv"]
).abs()

max_difference = grid_check["tiv_difference"].max()

print(f"Maximum Project 1 grid TIV difference: {max_difference:.12f}")

if max_difference > 1e-6:
    raise ValueError(
        "Project 1 AAL source and exposure grid have different TIV values."
    )


# ------------------------------------------------------------
# Load current Project 2 scenario TIVs
# ------------------------------------------------------------

print("\nLoading current Project 2 accumulation scenarios...")

dirty = pd.read_sql(
    text(
        """
        SELECT
            grid_lon,
            grid_lat,
            total_tiv
        FROM accumulation_dirty
        """
    ),
    engine,
)

dirty["scenario"] = "DIRTY"


sensitivity = pd.read_sql(
    text(
        """
        SELECT
            scenario,
            grid_lon,
            grid_lat,
            total_tiv
        FROM accumulation_sensitivity
        WHERE scenario IN (
            'PRIMARY',
            'P001_SENSITIVITY',
            'P003_SENSITIVITY',
            'COMBINED_SENSITIVITY'
        )
        """
    ),
    engine,
)

scenarios = pd.concat(
    [
        dirty[["scenario", "grid_lon", "grid_lat", "total_tiv"]],
        sensitivity[["scenario", "grid_lon", "grid_lat", "total_tiv"]],
    ],
    ignore_index=True,
)

scenarios["grid_lon"] = scenarios["grid_lon"].round(8)
scenarios["grid_lat"] = scenarios["grid_lat"].round(8)


# ------------------------------------------------------------
# Check for duplicate scenario/cell combinations
# ------------------------------------------------------------

duplicates = scenarios.duplicated(
    subset=["scenario", "grid_lon", "grid_lat"]
).sum()

if duplicates:
    raise ValueError(
        f"Found {duplicates} duplicate scenario/cell combinations."
    )


# ------------------------------------------------------------
# Link Project 2 TIV to Project 1 AAL
# ------------------------------------------------------------

linked = scenarios.merge(
    aal,
    on=["grid_lon", "grid_lat"],
    how="left",
    validate="many_to_one",
)

if linked["project1_aal"].isna().any():
    missing = linked.loc[
        linked["project1_aal"].isna(),
        ["scenario", "grid_lon", "grid_lat"],
    ]

    raise ValueError(
        f"Some Project 2 cells do not match the Project 1 AAL grid:\n{missing}"
    )


# ------------------------------------------------------------
# Proportional AAL linkage
# ------------------------------------------------------------

# For cells with positive Project 1 TIV:
#
# AAL_P2,c =
#     AAL_P1,c × (TIV_P2,c / TIV_P1,c)
#
# If Project 1 TIV is zero, proportional scaling is undefined.
# Such cells receive zero linked AAL here.
#
# This is consistent with the Project 1 grid structure where
# zero-value cells have zero AAL.

linked["linked_aal"] = 0.0

positive = linked["project1_tiv"] > 0

linked.loc[positive, "linked_aal"] = (
    linked.loc[positive, "project1_aal"]
    * linked.loc[positive, "total_tiv"]
    / linked.loc[positive, "project1_tiv"]
)


# ------------------------------------------------------------
# Scenario summary
# ------------------------------------------------------------

summary = (
    linked.groupby("scenario", as_index=False)
    .agg(
        grid_cells=("grid_lon", "size"),
        portfolio_tiv=("total_tiv", "sum"),
        linked_aal=("linked_aal", "sum"),
    )
)

project1_tiv = aal["project1_tiv"].sum()
project1_aal = aal["project1_aal"].sum()

summary["aal_to_tiv"] = (
    summary["linked_aal"] / summary["portfolio_tiv"]
)

summary["aal_multiple_vs_project1"] = (
    summary["linked_aal"] / project1_aal
)

summary["aal_change_vs_project1_pct"] = (
    (summary["linked_aal"] / project1_aal - 1.0) * 100
)

summary = summary.sort_values("scenario")


# ------------------------------------------------------------
# Print results
# ------------------------------------------------------------

print("\n" + "=" * 80)
print("CURRENT AAL SCENARIO RESULTS")
print("=" * 80)

print(
    summary.to_string(
        index=False,
        formatters={
            "portfolio_tiv": lambda x: f"₹{x:,.2f}",
            "linked_aal": lambda x: f"₹{x:,.2f}",
            "aal_to_tiv": lambda x: f"{x:.6%}",
            "aal_multiple_vs_project1": lambda x: f"{x:.4f}x",
            "aal_change_vs_project1_pct": lambda x: f"{x:+.2f}%",
        },
    )
)

print("\nProject 1 baseline:")
print(f"  TIV: ₹{project1_tiv:,.2f}")
print(f"  AAL: ₹{project1_aal:,.2f}")


# ------------------------------------------------------------
# Save outputs
# ------------------------------------------------------------

summary_file = OUTPUT_DIR / "aal_scenario_summary.csv"
cell_file = OUTPUT_DIR / "aal_scenario_cell_linkage.csv"

summary.to_csv(summary_file, index=False)
linked.to_csv(cell_file, index=False)

print("\nSaved:")
print(f"  {summary_file}")
print(f"  {cell_file}")
