import geopandas as gpd
import pandas as pd
import numpy as np
from pathlib import Path


# ============================================================
# CONFIGURATION
# ============================================================

N_LOCATIONS = 5000
RANDOM_SEED = 42
MAX_RETRIES = 100

PROJECT_ROOT = Path.home() / "Projects"

LITPOP_FILE = (
    PROJECT_ROOT
    / "odisha-exposure-quality"
    / "data"
    / "odisha_exposure_grid.gpkg"
)

GADM_FILE = (
    PROJECT_ROOT
    / "odisha-exposure-quality"
    / "data"
    / "gadm41_IND_2.json"
)

OUTPUT_DIR = (
    PROJECT_ROOT
    / "odisha-exposure-quality"
    / "data"
)

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

OUTPUT_FILE = OUTPUT_DIR / "portfolio_clean.csv"

rng = np.random.default_rng(RANDOM_SEED)


# ============================================================
# LOAD PROJECT 1 LITPOP GRID
# ============================================================

print("Loading Project 1 LitPop grid...")

grid = gpd.read_file(
    LITPOP_FILE,
    layer="exposure_grid"
)

print(f"Loaded {len(grid)} grid cells.")

grid = grid[grid["value"] > 0].copy()

grid["grid_lon"] = grid.geometry.x
grid["grid_lat"] = grid.geometry.y


# ============================================================
# LOAD GADM DISTRICT BOUNDARIES
# ============================================================

print("Loading GADM district boundaries...")

india = gpd.read_file(GADM_FILE)

odisha = india[
    india["NAME_1"].astype(str).str.strip().str.lower()
    == "odisha"
].copy()

odisha["district"] = (
    odisha["NAME_2"]
    .astype(str)
    .str.strip()
    .replace({
        "Jagatsinghapur": "Jagatsinghpur"
    })
)

odisha = odisha[
    ["district", "geometry"]
].copy()

print(f"Loaded {len(odisha)} Odisha districts.")


# ============================================================
# TARGET DISTRICTS / CITIES
# ============================================================

# These are the four districts represented in the
# original synthetic portfolio.

district_city = {
    "Khordha": "Bhubaneswar",
    "Cuttack": "Cuttack",
    "Puri": "Puri",
    "Jagatsinghpur": "Paradip"
}

target_districts = list(district_city.keys())

target_polygons = odisha[
    odisha["district"].isin(target_districts)
].copy()

# ============================================================
# SYNTHETIC POSTCODE REFERENCE
# ============================================================

# Internal authoritative mapping for this synthetic portfolio.
# These are realistic Odisha PIN-code ranges used only to
# maintain referential consistency within the generated data.

district_postcodes = {
    "Khordha": [
        "751001", "751002", "751003", "751004", "751005",
        "751006", "751007", "751009", "751010", "751012"
    ],

    "Cuttack": [
        "753001", "753002", "753003", "753004", "753005",
        "753006", "753007", "753008", "753009", "753010"
    ],

    "Puri": [
        "752001", "752002", "752003", "752004", "752005",
        "752006", "752007", "752009", "752011", "752012"
    ],

    "Jagatsinghpur": [
        "754001", "754002", "754003", "754004", "754005",
        "754006", "754007", "754008", "754009", "754010"
    ]
}



# ============================================================
# ASSIGN LITPOP GRID CELLS TO GADM DISTRICTS
# ============================================================

print("Assigning LitPop grid cells to GADM districts...")

grid_points = gpd.GeoDataFrame(
    grid[["grid_lon", "grid_lat", "value"]].copy(),
    geometry=gpd.points_from_xy(
        grid["grid_lon"],
        grid["grid_lat"]
    ),
    crs="EPSG:4326"
)

grid_joined = gpd.sjoin(
    grid_points,
    target_polygons,
    how="inner",
    predicate="within"
)

# Keep only the target districts
grid_joined = grid_joined[
    grid_joined["district"].isin(target_districts)
].copy()

if len(grid_joined) == 0:
    raise RuntimeError(
        "No positive LitPop grid cells found inside target districts."
    )

print(
    f"Positive LitPop cells inside target districts: "
    f"{len(grid_joined)}"
)


# ============================================================
# SAMPLE GRID CELLS USING LITPOP WEIGHTS
# ============================================================

grid_joined["weight"] = (
    grid_joined["value"]
    / grid_joined["value"].sum()
)

print(f"Generating {N_LOCATIONS} synthetic locations...")

selected_indices = rng.choice(
    grid_joined.index.to_numpy(),
    size=N_LOCATIONS,
    replace=True,
    p=grid_joined["weight"].to_numpy()
)

sampled = grid_joined.loc[
    selected_indices
].reset_index(drop=True)


# ============================================================
# DISAGGREGATE LOCATIONS WITHIN SELECTED CELLS
# ============================================================

# 0.25 degree grid.
# Initial jitter remains +/- 0.10 degree, as in the
# original generator.

latitude = np.empty(N_LOCATIONS)
longitude = np.empty(N_LOCATIONS)
district = np.empty(N_LOCATIONS, dtype=object)
city = np.empty(N_LOCATIONS, dtype=object)


# Create dictionary for fast polygon lookup
district_polygons = {
    row["district"]: row["geometry"]
    for _, row in target_polygons.iterrows()
}


# ============================================================
# GENERATE GEOGRAPHICALLY VALID LOCATIONS
# ============================================================

for i in range(N_LOCATIONS):

    grid_lat = sampled.loc[i, "grid_lat"]
    grid_lon = sampled.loc[i, "grid_lon"]

    selected_district = sampled.loc[i, "district"]

    polygon = district_polygons[selected_district]

    valid_point = False

    for attempt in range(MAX_RETRIES):

        offset_lat = rng.uniform(-0.10, 0.10)
        offset_lon = rng.uniform(-0.10, 0.10)

        lat = grid_lat + offset_lat
        lon = grid_lon + offset_lon

        point = gpd.GeoSeries(
            [gpd.points_from_xy([lon], [lat])[0]],
            crs="EPSG:4326"
        ).iloc[0]

        if polygon.covers(point):

            latitude[i] = lat
            longitude[i] = lon

            district[i] = selected_district
            city[i] = district_city[selected_district]

            valid_point = True
            break

    if not valid_point:

        # If repeated jitter fails near a boundary,
        # resample a grid cell from the same district.

        district_cells = grid_joined[
            grid_joined["district"] == selected_district
        ]

        success = False

        for retry in range(MAX_RETRIES):

            cell = district_cells.iloc[
                rng.integers(0, len(district_cells))
            ]

            grid_lat = cell["grid_lat"]
            grid_lon = cell["grid_lon"]

            offset_lat = rng.uniform(-0.10, 0.10)
            offset_lon = rng.uniform(-0.10, 0.10)

            lat = grid_lat + offset_lat
            lon = grid_lon + offset_lon

            point = gpd.points_from_xy(
                [lon],
                [lat]
            )[0]

            if polygon.covers(point):

                latitude[i] = lat
                longitude[i] = lon

                district[i] = selected_district
                city[i] = district_city[selected_district]

                success = True
                break

        if not success:
            raise RuntimeError(
                f"Could not generate valid location for row {i} "
                f"in district {selected_district}"
            )


# ============================================================
# OCCUPANCY
# ============================================================

occupancy = rng.choice(
    ["RES", "COM", "IND", "PUB"],
    size=N_LOCATIONS,
    p=[0.60, 0.25, 0.10, 0.05]
)


# ============================================================
# CONSTRUCTION
# ============================================================

construction = rng.choice(
    ["RCC", "MASONRY", "STEEL", "TIMBER"],
    size=N_LOCATIONS,
    p=[0.45, 0.30, 0.15, 0.10]
)


# ============================================================
# YEAR BUILT
# ============================================================

year_built = rng.triangular(
    left=1960,
    mode=2005,
    right=2015,
    size=N_LOCATIONS
).astype(int)


# ============================================================
# NUMBER OF STOREYS
# ============================================================

num_storeys = np.ones(
    N_LOCATIONS,
    dtype=int
)

for construction_type, allowed_storeys, probabilities in [
    (
        "TIMBER",
        [1, 2, 3],
        [0.45, 0.35, 0.20]
    ),
    (
        "MASONRY",
        [1, 2, 3, 4, 5],
        [0.25, 0.30, 0.25, 0.12, 0.08]
    ),
    (
        "STEEL",
        [1, 2, 3, 4, 5, 6, 8],
        [0.10, 0.15, 0.20, 0.20, 0.15, 0.10, 0.10]
    ),
    (
        "RCC",
        [1, 2, 3, 4, 5, 6, 8, 10],
        [0.08, 0.12, 0.18, 0.20, 0.15, 0.10, 0.10, 0.07]
    ),
]:
    mask = construction == construction_type

    num_storeys[mask] = rng.choice(
        allowed_storeys,
        size=mask.sum(),
        p=probabilities
    )

# ============================================================
# FLOOR AREA
# ============================================================

base_area_per_storey = rng.uniform(
    40,
    250,
    N_LOCATIONS
)

floor_area_sqm = (
    base_area_per_storey
    * num_storeys
)

# ============================================================
# BUILDING TIV
# ============================================================

construction_rate = {
    "RCC": 50000,
    "MASONRY": 35000,
    "STEEL": 45000,
    "TIMBER": 30000
}

value_per_sqm = np.array([
    construction_rate[c]
    for c in construction
])

value_per_sqm = (
    value_per_sqm
    * rng.lognormal(
        mean=0,
        sigma=0.35,
        size=N_LOCATIONS
    )
)

tiv_building = (
    floor_area_sqm
    * value_per_sqm
)


# ============================================================
# CONTENTS TIV
# ============================================================

contents_ratio = rng.uniform(
    0.20,
    0.40,
    N_LOCATIONS
)

tiv_contents = (
    tiv_building
    * contents_ratio
)


# ============================================================
# BUSINESS INTERRUPTION TIV
# ============================================================

bi_ratio = np.zeros(N_LOCATIONS)

commercial_or_industrial = (
    (occupancy == "COM")
    | (occupancy == "IND")
)

bi_ratio[commercial_or_industrial] = rng.uniform(
    0.10,
    0.30,
    commercial_or_industrial.sum()
)

tiv_bi = (
    tiv_building
    * bi_ratio
)


# ============================================================
# TOTAL TIV
# ============================================================

tiv_total = (
    tiv_building
    + tiv_contents
    + tiv_bi
)




# ============================================================
# POLICY TERMS
# ============================================================

deductible_ratio = rng.uniform(
    0.01,
    0.05,
    N_LOCATIONS
)

deductible = (
    tiv_total
    * deductible_ratio
)

policy_limit = (
    tiv_total
    * rng.uniform(0.80, 1.00, N_LOCATIONS)
)


# ============================================================
# IDENTIFIERS
# ============================================================

location_id = np.array([
    f"LOC{i:05d}"
    for i in range(1, N_LOCATIONS + 1)
])

account_id = np.array([
    f"ACC{i:05d}"
    for i in rng.integers(
        1,
        3501,
        N_LOCATIONS
    )
])


# ============================================================
# GEOCODE LEVEL
# ============================================================

geocode_level = np.full(
    N_LOCATIONS,
    "EXACT"
)


# ============================================================
# BUILD PORTFOLIO
# ============================================================

portfolio = pd.DataFrame({

    "location_id": location_id,
    "account_id": account_id,

    "address_line": "Synthetic location",

    "city": city,
    "district": district,
    "state": "Odisha",

    "postcode": [
    rng.choice(district_postcodes[d])
    for d in district
    ],

    "latitude": latitude,
    "longitude": longitude,

    "geocode_level": geocode_level,

    "occupancy_code": occupancy,
    "construction_code": construction,

    "year_built": year_built,
    "num_storeys": num_storeys,
    "floor_area_sqm": floor_area_sqm,

    "tiv_building": tiv_building,
    "tiv_contents": tiv_contents,
    "tiv_bi": tiv_bi,
    "tiv_total": tiv_total,

    "currency": "INR",

    "deductible": deductible,
    "policy_limit": policy_limit
})

# ============================================================
# SAVE SYNTHETIC POSTCODE REFERENCE
# ============================================================

postcode_reference = pd.DataFrame(
    [
        {
            "postcode": postcode,
            "district": district_name
        }
        for district_name, postcodes
        in district_postcodes.items()
        for postcode in postcodes
    ]
)

postcode_reference.to_csv(
    OUTPUT_DIR / "postcode_district_reference.csv",
    index=False
)

print(
    f"Saved postcode reference: "
    f"{OUTPUT_DIR / 'postcode_district_reference.csv'}"
)

# ============================================================
# SAVE CLEAN PORTFOLIO
# ============================================================

portfolio.to_csv(
    OUTPUT_FILE,
    index=False
)

print()
print("Portfolio generation complete.")
print(f"Rows: {len(portfolio):,}")

print(
    f"Total TIV: "
    f"₹{portfolio['tiv_total'].sum():,.0f}"
)

print(
    f"Median building TIV: "
    f"₹{portfolio['tiv_building'].median():,.0f}"
)

print(
    f"Cities represented: "
    f"{portfolio['city'].nunique()}"
)

print(
    f"Districts represented: "
    f"{portfolio['district'].nunique()}"
)

print(
    f"Saved to: {OUTPUT_FILE}"
)