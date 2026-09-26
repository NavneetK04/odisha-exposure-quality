"""
Project 2: controlled exposure-data error injection.

Blueprint-faithful version:
- Implements C1-C7, V1-V7, X1-X7, D1-D4, P1-P5, G1-G5, K1-K4.
- Uses field-level exclusivity so one corruption does not silently overwrite another.
- D1 duplicates are created last and inherit the source row's prior injected errors.
- Every ground-truth record carries Error / Unknown / Assumption classification.
- Actual successes and skipped injections are reported separately.

Inputs:
    data/portfolio_clean.csv

Outputs:
    data/portfolio_dirty.csv
    data/ground_truth.csv
    data/injection_log.csv
"""

from __future__ import annotations

import json
import random
import re
from copy import deepcopy
from pathlib import Path

import numpy as np
import pandas as pd


SEED = 42
random.seed(SEED)
np.random.seed(SEED)

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"

CLEAN_FILE = DATA_DIR / "portfolio_clean.csv"
DIRTY_FILE = DATA_DIR / "portfolio_dirty.csv"
GROUND_TRUTH_FILE = DATA_DIR / "ground_truth.csv"
LOG_FILE = DATA_DIR / "injection_log.csv"


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------

def json_value(value):
    """Serialize a value safely for the ground-truth CSV."""
    if isinstance(value, dict):
        return json.dumps(value, default=str, sort_keys=True)
    if pd.isna(value):
        return None
    return str(value)


def snapshot(df, row_id, fields):
    row = df.loc[df["row_id"] == row_id].iloc[0]
    return {field: row[field] for field in fields}


def available_rows(df, claimed, fields, n, exclude=None, extra_condition=None):
    """Return row IDs where none of the requested fields are already claimed."""
    exclude = set(exclude or [])
    candidates = []

    for row_id in df["row_id"].tolist():
        if row_id in exclude:
            continue
        if any(field in claimed.get(row_id, set()) for field in fields):
            continue
        if extra_condition is not None:
            row = df.loc[df["row_id"] == row_id].iloc[0]
            if not extra_condition(row):
                continue
        candidates.append(row_id)

    random.shuffle(candidates)
    return candidates[:n]


def mark_claimed(claimed, row_id, fields):
    claimed.setdefault(row_id, set()).update(fields)


def add_gt(gt_rows, row_id, error_type, dimension, classification,
           original, corrupted):
    gt_rows.append(
        {
            "row_id": int(row_id),
            "error_type": error_type,
            "dimension": dimension,
            "classification": classification,
            "original_value": json_value(original),
            "corrupted_value": json_value(corrupted),
        }
    )


def inject_standard(
    df,
    claimed,
    gt_rows,
    log_rows,
    rule,
    dimension,
    classification,
    fields,
    target,
    transform,
    eligible=None,
):
    """
    Apply a standard field-level injection.

    transform(df, row_id) must mutate the dataframe and return
    (original_value, corrupted_value).
    """
    eligible = eligible or (lambda row: True)

    selected = available_rows(
        df, claimed, fields, target, extra_condition=eligible
    )

    for row_id in selected:
        original, corrupted = transform(df, row_id)
        mark_claimed(claimed, row_id, fields)
        add_gt(
            gt_rows,
            row_id,
            rule,
            dimension,
            classification,
            original,
            corrupted,
        )

    log_rows.append(
        {
            "rule": rule,
            "dimension": dimension,
            "target": target,
            "success": len(selected),
            "skipped": target - len(selected),
        }
    )


# ---------------------------------------------------------------------
# Load clean answer key
# ---------------------------------------------------------------------

df = pd.read_csv(
    CLEAN_FILE,
    dtype={
        "location_id": "string",
        "account_id": "string",
        "postcode": "string",
    },
)

# Explicit stable row ID. This is the evaluation key.
df.insert(0, "row_id", np.arange(1, len(df) + 1))

if "geocode_level" not in df.columns:
    df["geocode_level"] = "ADDRESS"

N_ORIGINAL = len(df)

claimed: dict[int, set[str]] = {}
gt_rows: list[dict] = []
log_rows: list[dict] = []


# ---------------------------------------------------------------------
# COMPLETENESS
# Missing / unresolvable data = UNKNOWN.
# ---------------------------------------------------------------------

def c1_transform(d, r):
    original = snapshot(d, r, ["latitude", "longitude"])
    d.loc[d.row_id == r, "latitude"] = np.nan
    d.loc[d.row_id == r, "longitude"] = np.nan
    return original, {"latitude": None, "longitude": None}

inject_standard(
    df, claimed, gt_rows, log_rows,
    "C1_missing_coordinates", "Completeness", "UNKNOWN",
    ["latitude", "longitude"], round(0.08 * N_ORIGINAL),
    c1_transform,
)

def null_field(field):
    def transform(d, r):
        original = snapshot(d, r, [field])
        d.loc[d.row_id == r, field] = np.nan
        return original, {field: None}
    return transform

inject_standard(
    df, claimed, gt_rows, log_rows,
    "C2_missing_construction", "Completeness", "UNKNOWN",
    ["construction_code"], round(0.30 * N_ORIGINAL),
    null_field("construction_code"),
)

inject_standard(
    df, claimed, gt_rows, log_rows,
    "C3_missing_year_built", "Completeness", "UNKNOWN",
    ["year_built"], round(0.40 * N_ORIGINAL),
    null_field("year_built"),
)

inject_standard(
    df, claimed, gt_rows, log_rows,
    "C4_missing_storeys", "Completeness", "UNKNOWN",
    ["num_storeys"], round(0.25 * N_ORIGINAL),
    null_field("num_storeys"),
)

def c5_transform(d, r):
    original = snapshot(d, r, ["tiv_contents"])
    d.loc[d.row_id == r, "tiv_contents"] = np.nan
    return original, {"tiv_contents": None}

inject_standard(
    df, claimed, gt_rows, log_rows,
    "C5_missing_contents", "Completeness", "UNKNOWN",
    ["tiv_contents"], round(0.12 * N_ORIGINAL),
    c5_transform,
    eligible=lambda row: pd.notna(row["tiv_building"]),
)

inject_standard(
    df, claimed, gt_rows, log_rows,
    "C6_missing_deductible", "Completeness", "UNKNOWN",
    ["deductible"], round(0.15 * N_ORIGINAL),
    null_field("deductible"),
)

inject_standard(
    df, claimed, gt_rows, log_rows,
    "C7_missing_occupancy", "Completeness", "UNKNOWN",
    ["occupancy_code"], round(0.05 * N_ORIGINAL),
    null_field("occupancy_code"),
)


# ---------------------------------------------------------------------
# VALIDITY
# ---------------------------------------------------------------------

def v1_transform(d, r):

    original = snapshot(d, r, ["tiv_total"])

    new = -abs(float(d.loc[d.row_id == r, "tiv_total"].iloc[0]))

    d.loc[d.row_id == r, "tiv_total"] = new

    return original, {"tiv_total": new}

inject_standard(
    df, claimed, gt_rows, log_rows,

    "V1_negative_tiv", "Validity", "ERROR",

    ["tiv_total"], round(0.003 * N_ORIGINAL), v1_transform,
)

def v2_transform(d, r):
    original = snapshot(d, r, ["tiv_building"])
    d.loc[d.row_id == r, "tiv_building"] = 0.0
    return original, {"tiv_building": 0.0}

inject_standard(
    df, claimed, gt_rows, log_rows,
    "V2_zero_tiv", "Validity", "UNKNOWN",
    ["tiv_building"], round(0.015 * N_ORIGINAL), v2_transform,
)

def v3_transform(d, r):
    original = snapshot(d, r, ["latitude"])
    d.loc[d.row_id == r, "latitude"] = 190.5
    return original, {"latitude": 190.5}

inject_standard(
    df, claimed, gt_rows, log_rows,
    "V3_invalid_latitude", "Validity", "ERROR",
    ["latitude"], round(0.002 * N_ORIGINAL), v3_transform,
)

def v4_transform(d, r):
    original = snapshot(d, r, ["year_built"])
    d.loc[d.row_id == r, "year_built"] = 2035
    return original, {"year_built": 2035}

inject_standard(
    df, claimed, gt_rows, log_rows,
    "V4_future_year", "Validity", "ERROR",
    ["year_built"], round(0.004 * N_ORIGINAL), v4_transform,
)

def v5_transform(d, r):
    original = snapshot(d, r, ["year_built"])
    d.loc[d.row_id == r, "year_built"] = 1750
    return original, {"year_built": 1750}

inject_standard(
    df, claimed, gt_rows, log_rows,
    "V5_implausibly_old_year", "Validity", "UNKNOWN",
    ["year_built"], round(0.002 * N_ORIGINAL), v5_transform,
)

def v6_transform(d, r):
    original = snapshot(d, r, ["num_storeys"])
    new = 0
    d.loc[d.row_id == r, "num_storeys"] = new
    return original, {"num_storeys": new}

inject_standard(
    df, claimed, gt_rows, log_rows,
    "V6_invalid_storeys", "Validity", "ERROR",
    ["num_storeys"], round(0.005 * N_ORIGINAL), v6_transform,
)

def v7_transform(d, r):
    original = snapshot(d, r, ["deductible", "tiv_total"])
    tiv = float(d.loc[d.row_id == r, "tiv_total"].iloc[0])
    if not np.isfinite(tiv) or tiv <= 0:
        tiv = 1_000_000.0
    new = tiv * 5.0
    d.loc[d.row_id == r, "deductible"] = new
    return original, {"deductible": new, "tiv_total": tiv}

inject_standard(
    df, claimed, gt_rows, log_rows,
    "V7_deductible_gt_tiv", "Validity", "ERROR",
    ["deductible"], round(0.008 * N_ORIGINAL), v7_transform,
)


# ---------------------------------------------------------------------
# CONSISTENCY
# ---------------------------------------------------------------------

def x1_transform(d, r):
    original = snapshot(d, r, ["construction_code", "num_storeys"])
    d.loc[d.row_id == r, "construction_code"] = "TIMBER"
    d.loc[d.row_id == r, "num_storeys"] = random.randint(15, 30)
    return original, snapshot(d, r, ["construction_code", "num_storeys"])

inject_standard(
    df, claimed, gt_rows, log_rows,
    "X1_timber_25_storeys", "Consistency", "ERROR",
    ["construction_code", "num_storeys"], round(0.006 * N_ORIGINAL),
    x1_transform,
)

def x2_transform(d, r):
    original = snapshot(d, r, ["construction_code", "year_built"])
    d.loc[d.row_id == r, "construction_code"] = "RCC"
    d.loc[d.row_id == r, "year_built"] = 1880
    return original, snapshot(d, r, ["construction_code", "year_built"])

inject_standard(
    df, claimed, gt_rows, log_rows,
    "X2_rcc_1880", "Consistency", "ERROR",
    ["construction_code", "year_built"], round(0.004 * N_ORIGINAL),
    x2_transform,
)

def x3_transform(d, r):
    fields = ["occupancy_code", "tiv_building", "tiv_contents", "tiv_bi", "tiv_total"]
    original = snapshot(d, r, fields)
    d.loc[d.row_id == r, "occupancy_code"] = "RES"
    d.loc[d.row_id == r, "tiv_building"] = 800_000_000.0
    d.loc[d.row_id == r, "tiv_contents"] = 0.0
    d.loc[d.row_id == r, "tiv_bi"] = 0.0
    d.loc[d.row_id == r, "tiv_total"] = 800_000_000.0
    return original, snapshot(d, r, fields)

inject_standard(
    df, claimed, gt_rows, log_rows,
    "X3_residential_high_tiv", "Consistency", "ERROR",
    ["occupancy_code", "tiv_building", "tiv_contents", "tiv_bi", "tiv_total"],
    round(0.003 * N_ORIGINAL), x3_transform,
)

def x4_transform(d, r):
    original = snapshot(d, r, ["occupancy_code", "num_storeys"])
    d.loc[d.row_id == r, "occupancy_code"] = "IND"
    d.loc[d.row_id == r, "num_storeys"] = 25
    return original, snapshot(d, r, ["occupancy_code", "num_storeys"])

inject_standard(
    df, claimed, gt_rows, log_rows,
    "X4_warehouse_25_storeys", "Consistency", "ERROR",
    ["occupancy_code", "num_storeys"], round(0.003 * N_ORIGINAL),
    x4_transform,
)

def x5_transform(d, r):
    original = snapshot(
        d, r,
        ["floor_area_sqm", "num_storeys", "tiv_building"]
    )

    tiv = float(
        d.loc[d.row_id == r, "tiv_building"].iloc[0]
    )

    new_floor_area = tiv / 3_000_000.0

    d.loc[d.row_id == r, "floor_area_sqm"] = new_floor_area

    return original, {
        "floor_area_sqm": new_floor_area,
        "num_storeys": d.loc[d.row_id == r, "num_storeys"].iloc[0],
        "tiv_building": tiv
    }

inject_standard(
    df, claimed, gt_rows, log_rows,
    "X5_floor_area_storey_mismatch", "Consistency", "ERROR",
    ["floor_area_sqm"], round(0.012 * N_ORIGINAL),
    x5_transform,
)

def x6_transform(d, r):
    original = snapshot(d, r, ["postcode", "district"])

    current_district = d.loc[
        d.row_id == r, "district"
    ].iloc[0]

    district_postcodes = {
        "Khordha": [
            "751001","751002","751003","751004","751005",
            "751006","751007","751009","751010","751012"
        ],
        "Cuttack": [
            "753001","753002","753003","753004","753005",
            "753006","753007","753008","753009","753010"
        ],
        "Puri": [
            "752001","752002","752003","752004","752005",
            "752006","752007","752009","752011","752012"
        ],
        "Jagatsinghpur": [
            "754001","754002","754003","754004","754005",
            "754006","754007","754008","754009","754010"
        ]
    }

    other_districts = [
        district
        for district in district_postcodes
        if district != current_district
    ]

    if not other_districts:
        return original, original

    wrong_district = random.choice(other_districts)
    wrong_postcode = random.choice(
        district_postcodes[wrong_district]
    )

    d.loc[d.row_id == r, "postcode"] = wrong_postcode

    return original, snapshot(
        d, r, ["postcode", "district"]
    )

inject_standard(
    df, claimed, gt_rows, log_rows,
    "X6_postcode_district_mismatch", "Consistency", "ERROR",
    ["postcode"], round(0.02 * N_ORIGINAL), x6_transform,
    eligible=lambda row: pd.notna(row["postcode"]) and pd.notna(row["district"]),
)

def x7_transform(d, r):
    original = snapshot(
        d, r, ["city", "latitude", "longitude"]
    )

    current_district = d.loc[
        d.row_id == r, "district"
    ].iloc[0]

    district_city = {
        "Khordha": "Bhubaneswar",
        "Cuttack": "Cuttack",
        "Puri": "Puri",
        "Jagatsinghpur": "Paradip"
    }

    other_cities = [
        city_name
        for district_name, city_name in district_city.items()
        if district_name != current_district
    ]

    if not other_cities:
        return original, original

    new_city = random.choice(other_cities)

    d.loc[d.row_id == r, "city"] = new_city

    return original, snapshot(
        d, r, ["city", "latitude", "longitude"]
    )


inject_standard(
    df, claimed, gt_rows, log_rows,
    "X7_city_coordinate_mismatch", "Consistency", "ERROR",
    ["city"], round(0.015 * N_ORIGINAL), x7_transform,
    eligible=lambda row: (
        pd.notna(row["city"])
        and pd.notna(row["latitude"])
        and pd.notna(row["longitude"])
    ),
)


# ---------------------------------------------------------------------
# PLAUSIBILITY
# These are suspiciousness signals, not impossibility tests.
# ---------------------------------------------------------------------

def scale_tiv_components(d, r, factor):
    cols = ["tiv_building", "tiv_contents", "tiv_bi"]

    for col in cols:
        val = d.loc[d.row_id == r, col].iloc[0]
        if pd.notna(val):
            d.loc[d.row_id == r, col] = float(val) * factor

    d.loc[d.row_id == r, "tiv_total"] = (
        float(d.loc[d.row_id == r, "tiv_building"].iloc[0])
        + float(d.loc[d.row_id == r, "tiv_contents"].iloc[0])
        + float(d.loc[d.row_id == r, "tiv_bi"].iloc[0])
    )

def p1_transform(d, r):
    fields = ["tiv_building", "tiv_contents", "tiv_bi", "tiv_total"]
    original = snapshot(d, r, fields)
    scale_tiv_components(d, r, 1000.0)
    return original, snapshot(d, r, fields)

inject_standard(
    df, claimed, gt_rows, log_rows,
    "P1_tiv_x1000", "Plausibility", "UNKNOWN",
    ["tiv_building", "tiv_contents", "tiv_bi", "tiv_total"],
    round(0.005 * N_ORIGINAL), p1_transform,
)

def p2_transform(d, r):
    fields = ["tiv_building", "tiv_contents", "tiv_bi", "tiv_total"]
    original = snapshot(d, r, fields)
    current_total = float(d.loc[d.row_id == r, "tiv_total"].iloc[0])
    if current_total <= 0 or not np.isfinite(current_total):
        new_total = 10_000_000.0
    else:
        ratio = 10_000_000.0 / current_total
        scale_tiv_components(d, r, ratio)
    return original, snapshot(d, r, fields)

inject_standard(
    df, claimed, gt_rows, log_rows,
    "P2_round_tiv_repeated", "Plausibility", "UNKNOWN",
    ["tiv_building", "tiv_contents", "tiv_bi", "tiv_total"],
    round(0.03 * N_ORIGINAL), p2_transform,
)

def p3_transform(d, r):
    fields = ["tiv_building", "tiv_contents", "tiv_bi", "tiv_total"]
    original = snapshot(d, r, fields)

    total_before = pd.to_numeric(d["tiv_total"], errors="coerce").fillna(0).sum()
    other_total = total_before - float(d.loc[d.row_id == r, "tiv_total"].iloc[0])
    desired = (0.35 / 0.65) * other_total

    current_total = float(d.loc[d.row_id == r, "tiv_total"].iloc[0])
    ratio = desired / current_total if current_total > 0 else 1.0
    scale_tiv_components(d, r, ratio)

    return original, snapshot(d, r, fields)

inject_standard(
    df, claimed, gt_rows, log_rows,
    "P3_single_location_35pct_tiv", "Plausibility", "UNKNOWN",
    ["tiv_building", "tiv_contents", "tiv_bi", "tiv_total"],
    1, p3_transform,
)

def p4_transform(d, r):
    original = snapshot(d, r, ["year_built"])
    d.loc[d.row_id == r, "year_built"] = 1900
    return original, {"year_built": 1900}

inject_standard(
    df, claimed, gt_rows, log_rows,
    "P4_year_built_1900_cluster", "Plausibility", "UNKNOWN",
    ["year_built"], round(0.05 * N_ORIGINAL), p4_transform,
)

def p5_transform(d, r):
    original = snapshot(d, r, ["num_storeys", "occupancy_code"])
    d.loc[d.row_id == r, "num_storeys"] = 1
    return original, {"num_storeys": 1, "occupancy_code": d.loc[d.row_id == r, "occupancy_code"].iloc[0]}

inject_standard(
    df, claimed, gt_rows, log_rows,
    "P5_industrial_one_storey_default", "Plausibility", "UNKNOWN",
    ["num_storeys"], round(0.04 * N_ORIGINAL),
    p5_transform,
    eligible=lambda row: str(row["occupancy_code"]).upper() == "IND"
    and pd.notna(row["num_storeys"])
    and int(row["num_storeys"]) != 1,
)


# ---------------------------------------------------------------------
# GEOGRAPHY
# ---------------------------------------------------------------------

def g1_transform(d, r):
    original = snapshot(d, r, ["latitude", "longitude"])
    d.loc[d.row_id == r, "latitude"] = 19.0
    d.loc[d.row_id == r, "longitude"] = 86.8
    return original, {"latitude": 19.0, "longitude": 86.8}

inject_standard(
    df, claimed, gt_rows, log_rows,
    "G1_sea_coordinate", "Geography", "ERROR",
    ["latitude", "longitude"], round(0.012 * N_ORIGINAL), g1_transform,
)

def g2_transform(d, r):
    original = snapshot(d, r, ["latitude", "longitude"])
    lat = d.loc[d.row_id == r, "latitude"].iloc[0]
    lon = d.loc[d.row_id == r, "longitude"].iloc[0]
    d.loc[d.row_id == r, "latitude"] = lon
    d.loc[d.row_id == r, "longitude"] = lat
    return original, snapshot(d, r, ["latitude", "longitude"])

inject_standard(
    df, claimed, gt_rows, log_rows,
    "G2_lat_lon_swap", "Geography", "ERROR",
    ["latitude", "longitude"], round(0.006 * N_ORIGINAL), g2_transform,
    eligible=lambda row: pd.notna(row["latitude"]) and pd.notna(row["longitude"]),
)

def g3_transform(d, r):
    original = snapshot(d, r, ["latitude", "longitude"])
    d.loc[d.row_id == r, "latitude"] = 0.0
    d.loc[d.row_id == r, "longitude"] = 0.0
    return original, {"latitude": 0.0, "longitude": 0.0}

inject_standard(
    df, claimed, gt_rows, log_rows,
    "G3_zero_zero", "Geography", "ERROR",
    ["latitude", "longitude"], round(0.002 * N_ORIGINAL), g3_transform,
)

def g4_transform(d, r):
    original = snapshot(d, r, ["latitude", "longitude"])
    d.loc[d.row_id == r, "latitude"] = 51.5
    d.loc[d.row_id == r, "longitude"] = -0.1
    return original, {"latitude": 51.5, "longitude": -0.1}

inject_standard(
    df, claimed, gt_rows, log_rows,
    "G4_outside_india", "Geography", "ERROR",
    ["latitude", "longitude"], round(0.003 * N_ORIGINAL), g4_transform,
)

def g5_transform(d, r):
    original = snapshot(d, r, ["latitude", "longitude", "geocode_level"])
    # Anchor is supplied through a temporary column on the dataframe.
    anchor_lat = d.loc[d.row_id == r, "_g5_anchor_lat"].iloc[0]
    anchor_lon = d.loc[d.row_id == r, "_g5_anchor_lon"].iloc[0]
    d.loc[d.row_id == r, "latitude"] = anchor_lat
    d.loc[d.row_id == r, "longitude"] = anchor_lon
    d.loc[d.row_id == r, "geocode_level"] = "POSTCODE"
    return original, snapshot(d, r, ["latitude", "longitude", "geocode_level"])

# Create postcode-centroid-like clusters around 10 existing clean anchors.
# This is an explicit synthetic representation of postcode-level snapping.
g5_fields = ["latitude", "longitude", "geocode_level"]
g5_target = round(0.06 * N_ORIGINAL)
g5_candidates = available_rows(
    df, claimed, g5_fields, g5_target,
    extra_condition=lambda row: pd.notna(row["latitude"]) and pd.notna(row["longitude"])
)

anchors = df[
    df["latitude"].notna() & df["longitude"].notna()
].sample(min(10, len(df)), random_state=SEED)[["latitude", "longitude"]].to_numpy()

for i, row_id in enumerate(g5_candidates):
    anchor = anchors[i % len(anchors)]
    df.loc[df.row_id == row_id, "_g5_anchor_lat"] = float(anchor[0])
    df.loc[df.row_id == row_id, "_g5_anchor_lon"] = float(anchor[1])

    original, corrupted = g5_transform(df, row_id)
    mark_claimed(claimed, row_id, g5_fields)
    add_gt(
        gt_rows,
        row_id,
        "G5_postcode_centroid_clustering",
        "Geography",
        "ASSUMPTION",
        original,
        corrupted,
    )

log_rows.append(
    {
        "rule": "G5_postcode_centroid_clustering",
        "dimension": "Geography",
        "target": g5_target,
        "success": len(g5_candidates),
        "skipped": g5_target - len(g5_candidates),
    }
)

df.drop(columns=["_g5_anchor_lat", "_g5_anchor_lon"], inplace=True)


# ---------------------------------------------------------------------
# CODING
# ---------------------------------------------------------------------

construction_variants = [
    "R.C.C.",
    "Reinforced Cement Concrete",
]

def k1_transform(d, r):
    original = snapshot(d, r, ["construction_code"])
    d.loc[d.row_id == r, "construction_code"] = random.choice(construction_variants)
    return original, snapshot(d, r, ["construction_code"])

inject_standard(
    df, claimed, gt_rows, log_rows,
    "K1_free_text_construction", "Coding", "ERROR",
    ["construction_code"], round(0.15 * N_ORIGINAL), k1_transform,
)

def k2_transform(d, r):
    original = snapshot(d, r, ["occupancy_code"])
    d.loc[d.row_id == r, "occupancy_code"] = random.choice(["MIXED-USE?", "SEE NOTES"])
    return original, snapshot(d, r, ["occupancy_code"])

inject_standard(
    df, claimed, gt_rows, log_rows,
    "K2_unknown_occupancy", "Coding", "UNKNOWN",
    ["occupancy_code"], round(0.08 * N_ORIGINAL), k2_transform,
)

def k3_transform(d, r):
    original = snapshot(d, r, ["construction_code"])
    d.loc[d.row_id == r, "construction_code"] = random.choice(["01", "02", "03", "04"])
    return original, snapshot(d, r, ["construction_code"])

inject_standard(
    df, claimed, gt_rows, log_rows,
    "K3_mixed_construction_scheme", "Coding", "ERROR",
    ["construction_code"], round(0.05 * N_ORIGINAL), k3_transform,
)

def k4_transform(d, r):
    original = snapshot(d, r, ["currency"])
    d.loc[d.row_id == r, "currency"] = random.choice(["Rs", "USD", "EUR", "GBP"])
    return original, snapshot(d, r, ["currency"])

inject_standard(
    df, claimed, gt_rows, log_rows,
    "K4_currency_inconsistency", "Coding", "ERROR",
    ["currency"], round(0.02 * N_ORIGINAL), k4_transform,
)


# ---------------------------------------------------------------------
# DUPLICATION
# Duplication is deliberately last.
# ---------------------------------------------------------------------



# D2: same coordinates, different location_id.
def d2_transform(d, r):
    original = snapshot(d, r, ["latitude", "longitude", "location_id"])

    source_pool = d[
        (d["latitude"].notna())
        & (d["longitude"].notna())
        & (d["location_id"].notna())
        & (d["row_id"] != r)
    ]
    source = source_pool.sample(1, random_state=random.randint(1, 1_000_000)).iloc[0]

    d.loc[d.row_id == r, "latitude"] = source["latitude"]
    d.loc[d.row_id == r, "longitude"] = source["longitude"]

    return original, snapshot(d, r, ["latitude", "longitude", "location_id"])

inject_standard(
    df, claimed, gt_rows, log_rows,
    "D2_shared_coordinates", "Duplication", "UNKNOWN",
    ["latitude", "longitude"], round(0.015 * N_ORIGINAL), d2_transform,
    eligible=lambda row: pd.notna(row["latitude"])
    and pd.notna(row["longitude"])
    and pd.notna(row["location_id"]),
)

# D3: near-duplicate address.
def make_near_duplicate(address):
    if pd.isna(address):
        return address
    s = str(address)
    s2 = s.replace(",", "").replace("-", " ")
    s2 = re.sub(r"\bRoad\b", "Rd", s2, flags=re.I)
    s2 = re.sub(r"\bStreet\b", "St", s2, flags=re.I)
    s2 = re.sub(r"\s+", " ", s2).strip()
    if s2 == s:
        s2 = s + " Ltd."
    return s2

def d3_transform(d, r):
    original = snapshot(d, r, ["address_line"])

    address = d.loc[d.row_id == r, "address_line"].iloc[0]

    d.loc[d.row_id == r, "address_line"] = make_near_duplicate(address)

    return original, snapshot(d, r, ["address_line"])

inject_standard(
    df, claimed, gt_rows, log_rows,
    "D3_near_duplicate_address", "Duplication", "UNKNOWN",
    ["address_line"], round(0.01 * N_ORIGINAL), d3_transform,
    eligible=lambda row: pd.notna(row["address_line"]),
)

# D4: same location_id twice, different TIV.
def d4_transform(d, r):
    fields = ["location_id", "tiv_building", "tiv_contents", "tiv_bi", "tiv_total"]
    original = snapshot(d, r, fields)

    source_pool = d[
        (d["location_id"].notna())
        & (d["row_id"] != r)
    ]
    source = source_pool.sample(1, random_state=random.randint(1, 1_000_000)).iloc[0]

    d.loc[d.row_id == r, "location_id"] = source["location_id"]

    # Preserve internal TIV consistency while making the version different.
    scale_tiv_components(d, r, 1.15)

    return original, snapshot(d, r, fields)

inject_standard(
    df, claimed, gt_rows, log_rows,
    "D4_same_location_different_tiv", "Duplication", "ERROR",
    ["location_id", "tiv_building", "tiv_contents", "tiv_bi", "tiv_total"],
    round(0.003 * N_ORIGINAL), d4_transform,
    eligible=lambda row: pd.notna(row["location_id"])
    and pd.notna(row["tiv_total"]),
)

# D1: exact row duplicate with new row_id.
# Source rows are selected from rows that already have at least one
# injected error, so duplicates inherit those errors.
source_ids = [
    row_id for row_id in df["row_id"].tolist()
    if any(gt["row_id"] == row_id for gt in gt_rows)
]
random.shuffle(source_ids)

d1_target = round(0.004 * N_ORIGINAL)
d1_success = 0

for source_id in source_ids[:d1_target]:
    source_row = df.loc[df.row_id == source_id].iloc[0].copy()
    new_id = int(df["row_id"].max()) + 1

    source_gt = [g for g in gt_rows if g["row_id"] == source_id]

    source_row["row_id"] = new_id
    df = pd.concat([df, pd.DataFrame([source_row])], ignore_index=True)

    # Inherit the source's injected errors in the duplicated record.
    for g in source_gt:
        inherited = deepcopy(g)
        inherited["row_id"] = new_id
        gt_rows.append(inherited)

    add_gt(
        gt_rows,
        new_id,
        "D1_exact_row_duplicate",
        "Duplication",
        "ERROR",
        {"source_row_id": source_id},
        {"duplicated_row_id": new_id},
    )

    claimed[new_id] = set(claimed.get(source_id, set()))
    d1_success += 1

log_rows.append(
    {
        "rule": "D1_exact_row_duplicate",
        "dimension": "Duplication",
        "target": d1_target,
        "success": d1_success,
        "skipped": d1_target - d1_success,
    }
)

ORIGINAL_ROW_IDS = set(range(1, N_ORIGINAL + 1))


# ---------------------------------------------------------------------
# Finalise
# ---------------------------------------------------------------------

# Ensure IDs and identifiers have stable types in the CSV.
df["row_id"] = df["row_id"].astype(int)

if "postcode" in df.columns:
    df["postcode"] = df["postcode"].astype("string")

if "location_id" in df.columns:
    df["location_id"] = df["location_id"].astype("string")

if "account_id" in df.columns:
    df["account_id"] = df["account_id"].astype("string")

# Ground truth is sorted for auditability.
gt = pd.DataFrame(gt_rows)
gt = gt.sort_values(["row_id", "dimension", "error_type"]).reset_index(drop=True)

log = pd.DataFrame(log_rows)

df.to_csv(DIRTY_FILE, index=False)
gt.to_csv(GROUND_TRUTH_FILE, index=False)
log.to_csv(LOG_FILE, index=False)

print("\nError injection complete.")
print(f"Clean source rows:        {N_ORIGINAL:,}")
print(f"Dirty portfolio rows:     {len(df):,}")
print(f"Ground-truth records:     {len(gt):,}")
print(f"Unique ground-truth rows: {gt['row_id'].nunique():,}")

print("\nInjection summary:")
print(
    log.to_string(
        index=False,
        formatters={
            "target": "{:,.0f}".format,
            "success": "{:,.0f}".format,
            "skipped": "{:,.0f}".format,
        },
    )
)

print("\nErrors by dimension:")
print(gt["dimension"].value_counts().sort_index())

print("\nClassifications:")
print(gt["classification"].value_counts().sort_index())

print("\nMultiple findings per row:")
print(int((gt.groupby("row_id").size() > 1).sum()))

print(f"\nSaved:")
print(f"  {DIRTY_FILE}")
print(f"  {GROUND_TRUTH_FILE}")
print(f"  {LOG_FILE}")
