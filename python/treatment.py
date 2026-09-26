import pandas as pd
import numpy as np
from sqlalchemy import create_engine, text
from datetime import datetime
import os


# ============================================================
# Configuration
# ============================================================

DB_NAME = os.getenv("ODISHA_DB_NAME", "odisha_exposure")
DB_URL = f"postgresql+psycopg2:///{DB_NAME}"

engine = create_engine(DB_URL)


# ============================================================
# Treatment action mapping
# ============================================================

FIX_RULES = {
    "G-002",
    "K-001",
    "K-003",
    "K-004",
    "V-001",
}

QUARANTINE_RULES = {
    "D-001",
    "G-003",
    "G-004",
    "V-003",
    "D-004",
}

ASSUMPTION_RULES = {
    "G-005",
    "P-004",
    "P-005",
}

# Everything else is referred unless explicitly treated above.
# This is deliberate: unknown or non-derivable issues are not guessed.


# ============================================================
# Load portfolio and rule information
# ============================================================

def load_data():
    portfolio = pd.read_sql(
        "SELECT * FROM portfolio_raw ORDER BY row_id",
        engine
    )

    rules = pd.read_sql(
        """
        SELECT
            rule_id,
            classification,
            severity
        FROM rule_catalogue
        """,
        engine
    )

    flags = pd.read_sql(
        """
        SELECT
            q.row_id,
            q.rule_id,
            m.priority
        FROM quality_flags q
        LEFT JOIN materiality_scores m
            ON m.row_id = q.row_id
           AND m.rule_id = q.rule_id
        """,
        engine
    )

    return portfolio, rules, flags


def treatment_action(rule_id):
    if rule_id in FIX_RULES:
        return "FIXED"

    if rule_id in QUARANTINE_RULES:
        return "QUARANTINED"

    if rule_id in ASSUMPTION_RULES:
        return "ASSUMED"

    return "REFERRED"

def apply_fixed(row, rule_id):
    method = None

    if rule_id == "G-002":
        row["latitude_clean"], row["longitude_clean"] = (
            row["longitude_orig"],
            row["latitude_orig"],
        )
        method = "Swapped latitude and longitude back to original coordinate order"

    elif rule_id == "K-001":
        row["construction_clean"] = "RCC"
        method = "Mapped free-text construction variant to canonical RCC code"

    elif rule_id == "K-003":
        value = str(row["construction_orig"]).strip().upper()

        if "RCC" in value or "REINFORCED CEMENT CONCRETE" in value:
            row["construction_clean"] = "RCC"
        elif "MASON" in value:
            row["construction_clean"] = "MASONRY"
        elif "STEEL" in value:
            row["construction_clean"] = "STEEL"
        elif "TIMBER" in value:
            row["construction_clean"] = "TIMBER"
        else:
            row["construction_clean"] = row["construction_orig"]

        method = "Mapped mixed construction coding to canonical construction code"

    elif rule_id == "K-004":
        value = str(row["currency_orig"]).strip().upper()

        currency_map = {
            "INR": "INR",
            "₹": "INR",
            "RS": "INR",
            "RUPEES": "INR",
        }

        row["currency_clean"] = currency_map.get(value, value)

        method = "Normalised currency to canonical code"

    elif rule_id == "V-001":
        row["tiv_total_clean"] = abs(float(row["tiv_total_orig"]))
        row["tiv_total"] = row["tiv_total_clean"]
        method = "Converted negative total TIV to absolute value"

    return row, method


def apply_quarantine(row, rule_id):
    row["quarantined"] = True

    methods = {
        "G-003": "Invalid zero/zero coordinates excluded from modelling",
        "G-004": "Coordinates outside India excluded from modelling",
        "V-003": "Invalid latitude excluded from modelling",
        "D-004": "Conflicting TIV for same location ID excluded pending reconciliation",
    }

    return row, methods.get(
        rule_id,
        "Finding could not be safely resolved"
    )

def apply_referred(row, rule_id):
    row["referred"] = True

    methods = {
        "C-001": "Missing coordinates require broker/source confirmation",
        "C-002": "Missing construction requires broker/source confirmation",
        "C-003": "Missing year built requires broker/source confirmation",
        "C-004": "Missing storeys requires broker/source confirmation",
        "C-005": "Missing contents TIV requires broker/source confirmation",
        "C-006": "Missing deductible requires broker/source confirmation",
        "C-007": "Missing occupancy requires broker/source confirmation",
        "D-002": "Shared coordinates require source reconciliation",
        "D-003": "Near-duplicate address requires source reconciliation",
        "P-001": "TIV anomaly requires financial/source confirmation",
        "P-002": "Repeated rounded TIV requires source confirmation",
        "P-003": "Concentrated TIV requires source confirmation",
        "V-002": "Zero TIV requires source confirmation",
        "V-004": "Future year built requires source confirmation",
        "V-005": "Implausibly old year built requires source confirmation",
        "V-006": "Invalid storeys requires source confirmation",
        "V-007": "Deductible exceeding TIV requires policy/source confirmation",
        "X-001": "Timber/high-storey inconsistency requires source confirmation",
        "X-002": "RCC/1880 inconsistency requires source confirmation",
        "X-003": "Residential/high-TIV inconsistency requires source confirmation",
        "X-004": "Warehouse/storey inconsistency requires source confirmation",
        "X-005": "Floor-area/value inconsistency requires source confirmation",
        "X-006": "Postcode/district mismatch requires geographic reconciliation",
        "X-007": "City/coordinate mismatch requires geographic reconciliation",
        "K-002": "Unknown occupancy requires source confirmation",
    }

    return row, methods.get(
        rule_id,
        "Finding referred for source confirmation"
    )


def apply_assumption(row, rule_id):
    methods = {
        "G-005": "Postcode-level geocoding assumption retained and documented",
        "P-004": "Repeated 1900 construction year retained as documented assumption",
        "P-005": "Industrial one-storey pattern retained as documented assumption",
    }

    return row, methods.get(
        rule_id,
        "Assumption applied and documented"
    )


# ============================================================
# Build treated portfolio
# ============================================================

def build_treated_portfolio(portfolio, rules, flags):

    # --------------------------------------------------------
    # Rule lookup
    # --------------------------------------------------------
    rule_lookup = rules.set_index("rule_id").to_dict("index")

    # --------------------------------------------------------
    # Prepare original / clean columns
    # --------------------------------------------------------
    clean_columns = [
        "latitude_clean",
        "longitude_clean",
        "construction_clean",
        "occupancy_clean",
        "currency_clean",
        "tiv_total_clean",
        "geocode_level_clean",
    ]

    original_columns = [
        "latitude_orig",
        "longitude_orig",
        "construction_orig",
        "occupancy_orig",
        "currency_orig",
        "tiv_total_orig",
        "geocode_level_orig",
    ]

    records = []

    # --------------------------------------------------------
    # Process each portfolio row
    # --------------------------------------------------------
    for _, source in portfolio.iterrows():

        row_id = int(source["row_id"])

        # Start with complete copy of source record
        row = source.copy()

        # ----------------------------------------------------
        # Preserve original values
        # ----------------------------------------------------
        row["latitude_orig"] = source["latitude"]
        row["longitude_orig"] = source["longitude"]
        row["construction_orig"] = source["construction_code"]
        row["occupancy_orig"] = source["occupancy_code"]
        row["currency_orig"] = source["currency"]
        row["tiv_total_orig"] = source["tiv_total"]
        row["geocode_level_orig"] = source["geocode_level"]

        # ----------------------------------------------------
        # Initialise clean values = original values
        # ----------------------------------------------------
        row["latitude_clean"] = source["latitude"]
        row["longitude_clean"] = source["longitude"]
        row["construction_clean"] = source["construction_code"]
        row["occupancy_clean"] = source["occupancy_code"]
        row["currency_clean"] = source["currency"]
        row["tiv_total_clean"] = source["tiv_total"]
        row["geocode_level_clean"] = source["geocode_level"]

        # ----------------------------------------------------
        # Initialise treatment audit fields
        # ----------------------------------------------------
        row["treatment_applied"] = "NONE"
        row["treatment_rule"] = None
        row["treatment_method"] = None
        row["classification"] = None
        row["priority"] = None
        row["quarantined"] = False
        row["referred"] = False

        # ----------------------------------------------------
        # Get findings for this row
        # ----------------------------------------------------
        row_flags = flags[flags["row_id"] == row_id]

        if row_flags.empty:
            records.append(row)
            continue

        actions = []
        rules_triggered = []
        methods = []
        classifications = []
        priorities = []

        # ----------------------------------------------------
        # Apply findings
        # ----------------------------------------------------
        for _, flag in row_flags.iterrows():

            rule_id = flag["rule_id"]
            rule = rule_lookup.get(rule_id)

            if rule is None:
                continue

            classification = rule["classification"]
            priority = flag["priority"]

            action = treatment_action(rule_id)

            rules_triggered.append(rule_id)
            classifications.append(classification)

            if pd.notna(priority):
                priorities.append(priority)

            # ------------------------------------------------
            # FIXED
            # ------------------------------------------------
            if action == "FIXED":

                row, method = apply_fixed(row, rule_id)

                actions.append("FIXED")

                if method:
                    methods.append(
                        f"{rule_id}: {method}"
                    )

            # ------------------------------------------------
            # QUARANTINED
            # ------------------------------------------------
            elif action == "QUARANTINED":

                row, method = apply_quarantine(row, rule_id)

                actions.append("QUARANTINED")

                if method:
                    methods.append(
                        f"{rule_id}: {method}"
                    )

            # ------------------------------------------------
            # REFERRED
            # ------------------------------------------------
            elif action == "REFERRED":

                row, method = apply_referred(row, rule_id)

                actions.append("REFERRED")

                if method:
                    methods.append(
                        f"{rule_id}: {method}"
                    )

            # ------------------------------------------------
            # ASSUMED
            # ------------------------------------------------
            elif action == "ASSUMED":

                row, method = apply_assumption(row, rule_id)

                actions.append("ASSUMED")

                if method:
                    methods.append(
                        f"{rule_id}: {method}"
                    )


        # ----------------------------------------------------
        # Aggregate audit trail
        # ----------------------------------------------------

        # Priority hierarchy
        priority_rank = {
            "P1": 1,
            "P2": 2,
            "P3": 3,
        }

        if priorities:
            priorities = sorted(
                set(priorities),
                key=lambda x: priority_rank.get(x, 99)
            )

            row["priority"] = ";".join(priorities)

        if rules_triggered:
            row["treatment_rule"] = ";".join(
                sorted(set(rules_triggered))
            )

        if classifications:
            row["classification"] = ";".join(
                sorted(set(classifications))
            )

        if methods:
            row["treatment_method"] = " | ".join(
                methods
            )

        # ----------------------------------------------------
        # Determine overall treatment state
        # ----------------------------------------------------

        action_set = set(actions)

        if "QUARANTINED" in action_set:
            row["treatment_applied"] = "QUARANTINED"

        elif "REFERRED" in action_set:
            row["treatment_applied"] = "REFERRED"

        elif "ASSUMED" in action_set:
            row["treatment_applied"] = "ASSUMED"

        elif "FIXED" in action_set:
            row["treatment_applied"] = "FIXED"

        records.append(row)

    return pd.DataFrame(records)

# ============================================================
# Write cleansed portfolio
# ============================================================

def write_cleansed(df):

    output_columns = [
        "row_id",

        "latitude_clean",
        "longitude_clean",
        "construction_clean",
        "occupancy_clean",
        "currency_clean",
        "tiv_total_clean",
        "geocode_level_clean",

        "latitude_orig",
        "longitude_orig",
        "construction_orig",
        "occupancy_orig",
        "currency_orig",
        "tiv_total_orig",
        "geocode_level_orig",

        "treatment_applied",
        "treatment_rule",
        "treatment_method",
        "classification",
        "priority",
        "quarantined",
        "referred",

        "location_id",
        "account_id",
        "address_line",
        "city",
        "district",
        "state",
        "postcode",
        "occupancy_code",
        "construction_code",
        "year_built",
        "num_storeys",
        "floor_area_sqm",
        "tiv_building",
        "tiv_contents",
        "tiv_bi",
        "tiv_total",
        "deductible",
        "policy_limit",
    ]

    output = df[output_columns].copy()

    output.to_sql(
    "portfolio_cleansed",
    engine,
    if_exists="append",
    index=False,
)

    print(
        f"Inserted {len(output):,} records into portfolio_cleansed"
    )


# ============================================================
# Main
# ============================================================

if __name__ == "__main__":

    portfolio, rules, flags = load_data()

    print(f"Portfolio rows: {len(portfolio):,}")
    print(f"Quality flags:  {len(flags):,}")

    treated = build_treated_portfolio(
        portfolio,
        rules,
        flags,
    )
    write_cleansed(treated)

    print("\nTreatment summary:")
    print(
        treated["treatment_applied"]
        .value_counts(dropna=False)
    )

    print("\nClassification summary:")
    print(
        treated["classification"]
        .fillna("NONE")
        .value_counts()
    )
