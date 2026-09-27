from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "outputs"
FIG_DIR = OUTPUT_DIR / "figures"
FIG_DIR.mkdir(exist_ok=True)


# ============================================================
# 1. Detection performance by dimension
# ============================================================

df = pd.read_csv(
    OUTPUT_DIR / "detection_performance_by_dimension.csv"
)

fig, ax = plt.subplots(figsize=(10, 6))

x = np.arange(len(df))
width = 0.36

ax.bar(x - width / 2, df["precision"] * 100, width, label="Precision")
ax.bar(x + width / 2, df["recall"] * 100, width, label="Recall")

ax.set_xticks(x)
ax.set_xticklabels(df["dimension"], rotation=30, ha="right")
ax.set_ylabel("Percentage (%)")
ax.set_ylim(0, 105)
ax.set_title("Detection Performance by Data-Quality Dimension")
ax.legend()
ax.grid(axis="y", alpha=0.25)

fig.tight_layout()
fig.savefig(
    FIG_DIR / "01_detection_performance_by_dimension.png",
    dpi=200,
    bbox_inches="tight"
)
plt.close(fig)


# ============================================================
# 2. Materiality funnel
# ============================================================

df = pd.read_csv(
    OUTPUT_DIR / "materiality_funnel.csv"
)

fig, ax = plt.subplots(figsize=(10, 6))

labels = df["stage"].tolist()
values = df["count"].tolist()

y = np.arange(len(labels))

ax.barh(y, values)
ax.set_yticks(y)
ax.set_yticklabels(labels)
ax.invert_yaxis()
ax.set_xlabel("Number of exposures")
ax.set_title("Exposure Materiality Funnel")

for i, row in df.iterrows():
    ax.text(
        row["count"] + max(values) * 0.01,
        i,
        f'{int(row["count"]):,} ({row["percentage"]:.2f}%)',
        va="center"
    )

fig.tight_layout()
fig.savefig(
    FIG_DIR / "02_materiality_funnel.png",
    dpi=200,
    bbox_inches="tight"
)
plt.close(fig)


# ============================================================
# 3. Dirty vs primary accumulation
# ============================================================

df = pd.read_csv(
    OUTPUT_DIR / "accumulation_dirty_vs_primary.csv"
)

fig, ax = plt.subplots(figsize=(8, 6))

labels = df["scenario"].tolist()
values = df["total_tiv"] / 1e9

bars = ax.bar(labels, values)

ax.set_ylabel("Portfolio TIV (₹ billion)")
ax.set_title("Dirty vs Primary Accumulation")
ax.grid(axis="y", alpha=0.25)

for bar, value in zip(bars, values):
    ax.text(
        bar.get_x() + bar.get_width() / 2,
        bar.get_height(),
        f"₹{value:,.1f}B",
        ha="center",
        va="bottom"
    )

fig.tight_layout()
fig.savefig(
    FIG_DIR / "03_dirty_vs_primary_accumulation.png",
    dpi=200,
    bbox_inches="tight"
)
plt.close(fig)


# ============================================================
# 4. HHI concentration
# ============================================================

df = pd.read_csv(
    OUTPUT_DIR / "concentration_comparison.csv"
)

fig, ax = plt.subplots(figsize=(10, 6))

bars = ax.bar(df["scenario"], df["hhi"])

ax.set_ylabel("HHI")
ax.set_title("Accumulation Concentration - HHI")
ax.tick_params(axis="x", rotation=25)
ax.grid(axis="y", alpha=0.25)

for bar, value in zip(bars, df["hhi"]):
    ax.text(
        bar.get_x() + bar.get_width() / 2,
        bar.get_height(),
        f"{value:.4f}",
        ha="center",
        va="bottom"
    )

fig.tight_layout()
fig.savefig(
    FIG_DIR / "04_concentration_hhi.png",
    dpi=200,
    bbox_inches="tight"
)
plt.close(fig)


# ============================================================
# 4b. Top-1 concentration
# ============================================================

top1_df = pd.read_csv(
    OUTPUT_DIR / "concentration_comparison.csv"
)

top1_values = top1_df["top1_share"].astype(float) * 100

fig, ax = plt.subplots(figsize=(10, 6))

bars = ax.bar(
    top1_df["scenario"],
    top1_values
)

ax.set_ylabel("Top-1 cell share (%)")
ax.set_title("Accumulation Concentration - Top-1 Cell")
ax.set_ylim(0, 100)
ax.tick_params(axis="x", rotation=25)
ax.grid(axis="y", alpha=0.25)

for bar, value in zip(bars, top1_values):
    ax.text(
        bar.get_x() + bar.get_width() / 2,
        value,
        f"{value:.2f}%",
        ha="center",
        va="bottom"
    )

fig.tight_layout()

fig.savefig(
    FIG_DIR / "04b_top1_concentration.png",
    dpi=150,
    bbox_inches="tight"
)

plt.close(fig)


# ============================================================
# 5. AAL scenario table
# ============================================================

df = pd.read_csv(
    OUTPUT_DIR / "aal_scenario_summary.csv"
)

display_df = df.copy()

display_df["TIV (₹B)"] = display_df["portfolio_tiv"] / 1e9
display_df["Linked AAL (₹B)"] = display_df["linked_aal"] / 1e9
display_df["AAL/TIV (%)"] = display_df["aal_to_tiv"] * 100
display_df["AAL vs P1 (×)"] = display_df["aal_multiple_vs_project1"]
display_df["Change vs P1 (%)"] = display_df["aal_change_vs_project1_pct"]

display_df = display_df[
    [
        "scenario",
        "TIV (₹B)",
        "Linked AAL (₹B)",
        "AAL/TIV (%)",
        "AAL vs P1 (×)",
        "Change vs P1 (%)",
    ]
]

display_df.columns = [
    "Scenario",
    "TIV (₹B)",
    "Linked AAL (₹B)",
    "AAL/TIV (%)",
    "AAL vs P1 (×)",
    "Change vs P1 (%)",
]

fig, ax = plt.subplots(figsize=(13, 4.8))
ax.axis("off")

table = ax.table(
    cellText=[
        [
            row["Scenario"],
            f'{row["TIV (₹B)"]:,.1f}',
            f'{row["Linked AAL (₹B)"]:,.2f}',
            f'{row["AAL/TIV (%)"]:.3f}',
            f'{row["AAL vs P1 (×)"]:.2f}',
            f'{row["Change vs P1 (%)"]:.1f}',
        ]
        for _, row in display_df.iterrows()
    ],
    colLabels=display_df.columns,
    loc="center",
    cellLoc="center"
)

table.auto_set_font_size(False)
table.set_fontsize(9)
table.scale(1, 1.8)

ax.set_title(
    "Linked AAL Under Accumulation Scenarios",
    pad=20
)

fig.tight_layout()
fig.savefig(
    FIG_DIR / "05_aal_scenario_table.png",
    dpi=200,
    bbox_inches="tight"
)
plt.close(fig)


# ============================================================
# 6. Treatment summary
# ============================================================

df = pd.read_csv(
    OUTPUT_DIR / "treatment_summary.csv"
)

fig, ax = plt.subplots(figsize=(9, 6))

bars = ax.bar(
    df["treatment"],
    df["count"]
)

ax.set_ylabel("Number of exposures")
ax.set_title("Treatment Outcome Summary")
ax.tick_params(axis="x", rotation=25)
ax.grid(axis="y", alpha=0.25)

for bar, value in zip(bars, df["count"]):
    ax.text(
        bar.get_x() + bar.get_width() / 2,
        bar.get_height(),
        f"{int(value):,}",
        ha="center",
        va="bottom"
    )

fig.tight_layout()
fig.savefig(
    FIG_DIR / "06_treatment_summary.png",
    dpi=200,
    bbox_inches="tight"
)
plt.close(fig)


print()
print("All figures regenerated successfully.")
print(f"Output directory: {FIG_DIR}")
for path in sorted(FIG_DIR.glob("*.png")):
    print(f"  {path.name}")
