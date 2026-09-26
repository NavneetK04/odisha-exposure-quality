import pandas as pd
from sqlalchemy import create_engine, text
import os
from pathlib import Path


# ------------------------------------------------------------
# Configuration
# ------------------------------------------------------------

DB_NAME = os.getenv("ODISHA_DB_NAME", "odisha_exposure")
DB_URL = f"postgresql+psycopg2:///{DB_NAME}"

GROUND_TRUTH = "data/ground_truth.csv"
OUTPUT = "outputs/detection_performance.csv"


# ------------------------------------------------------------
# Ground-truth → detection-rule mapping
# ------------------------------------------------------------

RULE_MAP = {
    "C1_missing_coordinates": "C-001",
    "C2_missing_construction": "C-002",
    "C3_missing_year_built": "C-003",
    "C4_missing_storeys": "C-004",
    "C5_missing_contents": "C-005",
    "C6_missing_deductible": "C-006",
    "C7_missing_occupancy": "C-007",

    "V1_negative_tiv": "V-001",
    "V2_zero_tiv": "V-002",
    "V3_invalid_latitude": "V-003",
    "V4_future_year": "V-004",
    "V5_implausibly_old_year": "V-005",
    "V6_invalid_storeys": "V-006",
    "V7_deductible_gt_tiv": "V-007",

    "X1_timber_25_storeys": "X-001",
    "X2_rcc_1880": "X-002",
    "X3_residential_high_tiv": "X-003",
    "X4_warehouse_25_storeys": "X-004",
    "X5_floor_area_storey_mismatch": "X-005",
    "X6_postcode_district_mismatch": "X-006",
    "X7_city_coordinate_mismatch": "X-007",

    "D1_exact_row_duplicate": "D-001",
    "D2_shared_coordinates": "D-002",
    "D3_near_duplicate_address": "D-003",
    "D4_same_location_different_tiv": "D-004",

    "P1_tiv_x1000": "P-001",
    "P2_round_tiv_repeated": "P-002",
    "P3_single_location_35pct_tiv": "P-003",
    "P4_year_built_1900_cluster": "P-004",
    "P5_industrial_one_storey_default": "P-005",

    "G1_sea_coordinate": "G-001",
    "G2_lat_lon_swap": "G-002",
    "G3_zero_zero": "G-003",
    "G4_outside_india": "G-004",
    "G5_postcode_centroid_clustering": "G-005",

    "K1_free_text_construction": "K-001",
    "K2_unknown_occupancy": "K-002",
    "K3_mixed_construction_scheme": "K-003",
    "K4_currency_inconsistency": "K-004",
}


# ------------------------------------------------------------
# Completeness rules
# ------------------------------------------------------------

COMPLETENESS_RULES = {
    "C-001",
    "C-002",
    "C-003",
    "C-004",
    "C-005",
    "C-006",
    "C-007",
}


# ------------------------------------------------------------
# Load ground truth
# ------------------------------------------------------------

gt = pd.read_csv(GROUND_TRUTH)

gt["rule_id"] = gt["error_type"].map(RULE_MAP)

if gt["rule_id"].isna().any():
    unknown = gt.loc[
        gt["rule_id"].isna(),
        "error_type"
    ].unique()

    raise ValueError(
        f"Unmapped ground-truth error types: {unknown}"
    )


# Evaluation unit = row_id + rule_id
gt_pairs = gt[
    ["row_id", "rule_id"]
].drop_duplicates()


# ------------------------------------------------------------
# Load detected flags
# ------------------------------------------------------------

engine = create_engine(DB_URL)

with engine.connect() as conn:
    detected = pd.read_sql(
        text("""
            SELECT row_id, rule_id
            FROM quality_flags
        """),
        conn,
    )

detected_pairs = detected[
    ["row_id", "rule_id"]
].drop_duplicates()


# ------------------------------------------------------------
# Convert to sets
# ------------------------------------------------------------

gt_set = set(
    map(
        tuple,
        gt_pairs.to_records(index=False)
    )
)

detected_set = set(
    map(
        tuple,
        detected_pairs.to_records(index=False)
    )
)


# ------------------------------------------------------------
# Per-rule evaluation
# ------------------------------------------------------------

rows = []

for error_type, rule_id in RULE_MAP.items():

    gt_rule = {
        pair
        for pair in gt_set
        if pair[1] == rule_id
    }

    detected_rule = {
        pair
        for pair in detected_set
        if pair[1] == rule_id
    }

    tp = len(gt_rule & detected_rule)
    fp = len(detected_rule - gt_rule)
    fn = len(gt_rule - detected_rule)

    precision = (
        tp / (tp + fp)
        if (tp + fp) > 0
        else 0.0
    )

    recall = (
        tp / (tp + fn)
        if (tp + fn) > 0
        else 0.0
    )

    rows.append({
        "rule_id": rule_id,
        "error_type": error_type,
        "TP": tp,
        "FP": fp,
        "FN": fn,
        "precision": precision,
        "recall": recall,
    })


results = pd.DataFrame(rows)

results = results.sort_values("rule_id")


# ------------------------------------------------------------
# Save per-rule results
# ------------------------------------------------------------

results.to_csv(
    OUTPUT,
    index=False
)


# ------------------------------------------------------------
# Aggregate evaluation helper
# ------------------------------------------------------------

def aggregate_metrics(gt_set, detected_set):

    tp = len(gt_set & detected_set)
    fp = len(detected_set - gt_set)
    fn = len(gt_set - detected_set)

    precision = (
        tp / (tp + fp)
        if (tp + fp) > 0
        else 0.0
    )

    recall = (
        tp / (tp + fn)
        if (tp + fn) > 0
        else 0.0
    )

    return tp, fp, fn, precision, recall


# ------------------------------------------------------------
# Completeness-separated evaluation
# ------------------------------------------------------------

non_completeness_gt = {
    pair
    for pair in gt_set
    if pair[1] not in COMPLETENESS_RULES
}

non_completeness_detected = {
    pair
    for pair in detected_set
    if pair[1] not in COMPLETENESS_RULES
}


# ------------------------------------------------------------
# Overall metrics
# ------------------------------------------------------------

all_tp, all_fp, all_fn, all_precision, all_recall = (
    aggregate_metrics(
        gt_set,
        detected_set
    )
)

nc_tp, nc_fp, nc_fn, nc_precision, nc_recall = (
    aggregate_metrics(
        non_completeness_gt,
        non_completeness_detected
    )
)


# ------------------------------------------------------------
# Completeness coverage
# ------------------------------------------------------------

completeness_gt = {
    pair
    for pair in gt_set
    if pair[1] in COMPLETENESS_RULES
}

completeness_detected = {
    pair
    for pair in detected_set
    if pair[1] in COMPLETENESS_RULES
}

completeness_tp = len(
    completeness_gt & completeness_detected
)

completeness_fp = len(
    completeness_detected - completeness_gt
)

completeness_fn = len(
    completeness_gt - completeness_detected
)

completeness_coverage = (
    completeness_tp / len(completeness_gt)
    if len(completeness_gt) > 0
    else 0.0
)


# ------------------------------------------------------------
# Reproducible reporting outputs
# ------------------------------------------------------------

rule_dimension = (
    gt[["rule_id", "dimension"]]
    .drop_duplicates("rule_id")
)

dimension_results = results.merge(
    rule_dimension,
    on="rule_id",
    how="left",
)

if dimension_results["dimension"].isna().any():
    missing = dimension_results.loc[
        dimension_results["dimension"].isna(),
        "rule_id"
    ].tolist()
    raise ValueError(
        f"Missing dimensions for rules: {missing}"
    )

dimension_summary = (
    dimension_results
    .groupby("dimension", as_index=False)
    [["TP", "FP", "FN"]]
    .sum()
)

dimension_summary["precision"] = (
    dimension_summary["TP"]
    / (dimension_summary["TP"] + dimension_summary["FP"])
).fillna(0.0)

dimension_summary["recall"] = (
    dimension_summary["TP"]
    / (dimension_summary["TP"] + dimension_summary["FN"])
).fillna(0.0)

dimension_order = [
    "Completeness",
    "Validity",
    "Consistency",
    "Duplication",
    "Geography",
    "Coding",
    "Plausibility",
]

dimension_summary["dimension"] = pd.Categorical(
    dimension_summary["dimension"],
    categories=dimension_order,
    ordered=True,
)

dimension_summary = dimension_summary.sort_values("dimension")

dimension_output = "outputs/detection_performance_by_dimension.csv"

dimension_summary.to_csv(
    dimension_output,
    index=False,
)


# Completeness-only coverage output.
completeness_results = dimension_results[
    dimension_results["dimension"] == "Completeness"
].copy()

completeness_tp = completeness_results["TP"].sum()
completeness_fp = completeness_results["FP"].sum()
completeness_fn = completeness_results["FN"].sum()

completeness_total_gt = (
    completeness_tp + completeness_fn
)

completeness_coverage = (
    completeness_tp / completeness_total_gt
    if completeness_total_gt > 0
    else 0.0
)

pd.DataFrame([{
    "TP": completeness_tp,
    "FP": completeness_fp,
    "FN": completeness_fn,
    "coverage": completeness_coverage,
}]).to_csv(
    "outputs/completeness_coverage.csv",
    index=False,
)


# Text summary.
summary_lines = [
    "Detection evaluation summary",
    "============================",
    "",
    f"Database: {DB_NAME}",
    f"Ground-truth pairs: {len(gt_set)}",
    f"Detected pairs: {len(detected_set)}",
    "",
    "Overall detection",
    f"TP: {all_tp}",
    f"FP: {all_fp}",
    f"FN: {all_fn}",
    f"Precision: {all_precision:.6%}",
    f"Recall: {all_recall:.6%}",
    "",
    "Injected-error evaluation (completeness excluded)",
    f"TP: {nc_tp}",
    f"FP: {nc_fp}",
    f"FN: {nc_fn}",
    f"Precision: {nc_precision:.6%}",
    f"Recall: {nc_recall:.6%}",
    "",
    "Completeness",
    f"TP: {completeness_tp}",
    f"FP: {completeness_fp}",
    f"FN: {completeness_fn}",
    f"Coverage: {completeness_coverage:.6%}",
]

Path("outputs/detection_evaluation_summary.txt").write_text(
    "\n".join(summary_lines) + "\n"
)




# ------------------------------------------------------------
# Display
# ------------------------------------------------------------

pd.set_option("display.max_rows", 100)
pd.set_option("display.width", 200)

print("\nDetection performance:")
print(results.to_string(index=False))

print(f"\nSaved to: {OUTPUT}")


print("\n============================================================")
print("OVERALL DETECTION")
print("============================================================")

print(f"Ground-truth pairs : {len(gt_set)}")
print(f"Detected pairs     : {len(detected_set)}")
print(f"True positives     : {all_tp}")
print(f"False positives    : {all_fp}")
print(f"False negatives    : {all_fn}")

print(f"Precision           : {all_precision:.4%}")
print(f"Recall              : {all_recall:.4%}")


print("\n============================================================")
print("INJECTED-ERROR EVALUATION")
print("(Completeness excluded)")
print("============================================================")

print(f"Ground-truth pairs : {len(non_completeness_gt)}")
print(f"Detected pairs     : {len(non_completeness_detected)}")
print(f"True positives     : {nc_tp}")
print(f"False positives    : {nc_fp}")
print(f"False negatives    : {nc_fn}")

print(f"Precision           : {nc_precision:.4%}")
print(f"Recall              : {nc_recall:.4%}")


print("\n============================================================")
print("COMPLETENESS COVERAGE")
print("============================================================")

print(f"Ground-truth pairs : {len(completeness_gt)}")
print(f"Detected pairs     : {len(completeness_detected)}")
print(f"True positives     : {completeness_tp}")
print(f"False positives    : {completeness_fp}")
print(f"False negatives    : {completeness_fn}")

print(f"Coverage            : {completeness_coverage:.4%}")