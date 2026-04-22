"""
Supplier Performance Analysis — Rigorous, commercially defensible.
Runs against the existing engine to pull data, then performs deep supplier analysis
with strict statistical thresholds.

Usage: python analysis/run_supplier_analysis.py
"""

import sys
import os

# Ensure we run from the project root so engine imports work
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(PROJECT_ROOT)
sys.path.insert(0, PROJECT_ROOT)

import numpy as np
import pandas as pd
from collections import Counter
from datetime import datetime, timezone

# ─── Load data via the existing engine ───
print("Loading data from MongoDB via engine.analyzer.load_data() ...")
from engine.analyzer import load_data

data = load_data()
df_sku = data["df_sku"]
df_sku_size = data["df_sku_size"]
df_supplier = data["df_supplier"]
df_category = data["df_category"]

print(f"  SKUs loaded: {len(df_sku)}")
print(f"  SKU×size rows: {len(df_sku_size)}")
print(f"  Suppliers: {len(df_supplier)}")
print(f"  Categories: {len(df_category)}")

# ─── THRESHOLDS (as specified in framework) ───
MIN_SUPPLIER_SOLD = 1000
MIN_SIZE_SUPPLIER_SOLD = 100
MIN_CAT_SUPPLIER_SOLD = 200
MIN_CAT_SUPPLIER_COMPARE = 500
UNDERPERFORM_ABS_PP = 5.0   # percentage points
UNDERPERFORM_REL_PCT = 25.0  # relative percent
SKU_CONCENTRATION_THRESHOLD = 0.60
SIZE_SPREAD_FLAG_PP = 10.0
# Confidence
HIGH_UNITS = 5000
HIGH_SKU_COUNT = 5
HIGH_SKU_UNITS = 100
MEDIUM_SKU_COUNT = 3

# ─── HELPER: weighted median ───
def weighted_median(values, weights):
    """Compute weighted median of values with given weights."""
    values = np.array(values, dtype=float)
    weights = np.array(weights, dtype=float)
    mask = ~np.isnan(values) & ~np.isnan(weights) & (weights > 0)
    values = values[mask]
    weights = weights[mask]
    if len(values) == 0:
        return np.nan
    sorted_idx = np.argsort(values)
    values = values[sorted_idx]
    weights = weights[sorted_idx]
    cumw = np.cumsum(weights)
    half = cumw[-1] / 2.0
    idx = np.searchsorted(cumw, half)
    return values[min(idx, len(values) - 1)]


# ═══════════════════════════════════════════════════════════════
# 1. QUALIFYING SUPPLIERS (≥1000 units sold)
# ═══════════════════════════════════════════════════════════════
qualifying = df_supplier[df_supplier["total_sold"] >= MIN_SUPPLIER_SOLD].copy()
print(f"\nQualifying suppliers (>={MIN_SUPPLIER_SOLD} sold): {len(qualifying)}")
print(f"  Total volume from qualifying suppliers: {qualifying['total_sold'].sum():,} sold, {qualifying['total_returned'].sum():,} returned")

all_suppliers_vol = df_supplier["total_sold"].sum()
qual_vol = qualifying["total_sold"].sum()
print(f"  Coverage: {qual_vol/all_suppliers_vol*100:.1f}% of all supplier volume")

# ═══════════════════════════════════════════════════════════════
# 2. CATEGORY BENCHMARKS (weighted median across all suppliers per category)
# ═══════════════════════════════════════════════════════════════

# Build supplier × category matrix from SKU-level data
valid_sku = df_sku[df_sku["supplier_name"].notna() & df_sku["category_l3"].notna()].copy()

sup_cat = (
    valid_sku.groupby(["supplier_name", "category_l3"])
    .agg(sold=("total_sold", "sum"), returned=("total_returned", "sum"))
    .reset_index()
)
sup_cat["return_rate"] = sup_cat["returned"] / sup_cat["sold"]

# Category weighted medians
cat_benchmarks = {}
for cat in sup_cat["category_l3"].unique():
    cat_data = sup_cat[sup_cat["category_l3"] == cat]
    wm = weighted_median(cat_data["return_rate"].values, cat_data["sold"].values)
    wavg = cat_data["returned"].sum() / cat_data["sold"].sum()
    cat_benchmarks[cat] = {"weighted_median": wm, "weighted_avg": wavg, "total_sold": cat_data["sold"].sum()}

# Also compute SIZE benchmarks per category
valid_ss = df_sku_size[df_sku_size["supplier_name"].notna() & df_sku_size["category_l3"].notna()].copy()

sup_cat_size = (
    valid_ss.groupby(["supplier_name", "category_l3", "size"])
    .agg(sold=("sold", "sum"), returned=("returned", "sum"))
    .reset_index()
)
sup_cat_size["return_rate"] = sup_cat_size["returned"] / sup_cat_size["sold"].replace(0, 1)

# Size benchmarks per category
size_cat_benchmarks = {}
for (cat, sz), grp in sup_cat_size.groupby(["category_l3", "size"]):
    wm = weighted_median(grp["return_rate"].values, grp["sold"].values)
    wavg = grp["returned"].sum() / grp["sold"].sum() if grp["sold"].sum() > 0 else 0
    size_cat_benchmarks[(cat, sz)] = {"weighted_median": wm, "weighted_avg": wavg, "total_sold": grp["sold"].sum()}


# ═══════════════════════════════════════════════════════════════
# 3. DETAILED SUPPLIER ANALYSIS
# ═══════════════════════════════════════════════════════════════

results = []

for _, sup_row in qualifying.iterrows():
    sname = sup_row["supplier_name"]
    sup_skus = df_sku[df_sku["supplier_name"] == sname].copy()
    sup_sizes = df_sku_size[df_sku_size["supplier_name"] == sname].copy()

    total_sold = sup_row["total_sold"]
    total_returned = sup_row["total_returned"]
    overall_rate = sup_row["return_rate"]

    # --- SKU concentration ---
    sku_volumes = sup_skus.groupby("sku_prefix")["total_sold"].sum().sort_values(ascending=False)
    top_sku_prefix = sku_volumes.index[0] if len(sku_volumes) > 0 else None
    top_sku_vol = sku_volumes.iloc[0] if len(sku_volumes) > 0 else 0
    top_sku_pct = top_sku_vol / total_sold if total_sold > 0 else 0
    is_concentrated = top_sku_pct > SKU_CONCENTRATION_THRESHOLD

    # Top SKU details
    top_sku_data = sup_skus[sup_skus["sku_prefix"] == top_sku_prefix].iloc[0] if top_sku_prefix else None
    top_sku_name = top_sku_data["product_name"] if top_sku_data is not None else "N/A"
    top_sku_rate = top_sku_data["return_rate"] if top_sku_data is not None else 0

    # --- What happens if we remove the worst SKU? ---
    worst_sku_idx = sup_skus["return_rate"].idxmax() if len(sup_skus) > 0 else None
    if worst_sku_idx is not None:
        worst_sku = sup_skus.loc[worst_sku_idx]
        worst_sku_prefix = worst_sku["sku_prefix"]
        worst_sku_name = worst_sku["product_name"]
        worst_sku_sold = worst_sku["total_sold"]
        worst_sku_returned = worst_sku["total_returned"]
        worst_sku_rate = worst_sku["return_rate"]
        remaining_sold = total_sold - worst_sku_sold
        remaining_returned = total_returned - worst_sku_returned
        rate_without_worst = remaining_returned / remaining_sold if remaining_sold > 0 else 0
    else:
        worst_sku_prefix = worst_sku_name = "N/A"
        worst_sku_sold = worst_sku_returned = 0
        worst_sku_rate = rate_without_worst = overall_rate

    # --- Return rate by category (≥200 sold) ---
    cat_breakdown = []
    sup_cat_data = sup_cat[sup_cat["supplier_name"] == sname]
    for _, crow in sup_cat_data.iterrows():
        cat = crow["category_l3"]
        if crow["sold"] >= MIN_CAT_SUPPLIER_SOLD and cat in cat_benchmarks:
            bench = cat_benchmarks[cat]
            cat_breakdown.append({
                "category": cat,
                "sold": crow["sold"],
                "returned": crow["returned"],
                "rate": crow["return_rate"],
                "benchmark_wmedian": bench["weighted_median"],
                "benchmark_wavg": bench["weighted_avg"],
                "deviation_pp": (crow["return_rate"] - bench["weighted_median"]) * 100,
                "deviation_rel": ((crow["return_rate"] - bench["weighted_median"]) / bench["weighted_median"] * 100) if bench["weighted_median"] > 0 else 0,
            })

    # --- Return rate by size (≥100 sold) ---
    size_breakdown = []
    sup_size_data = sup_sizes.groupby("size").agg(sold=("sold", "sum"), returned=("returned", "sum")).reset_index()
    sup_size_data["rate"] = sup_size_data["returned"] / sup_size_data["sold"].replace(0, 1)
    for _, srow in sup_size_data.iterrows():
        if srow["sold"] >= MIN_SIZE_SUPPLIER_SOLD:
            size_breakdown.append({
                "size": srow["size"],
                "sold": int(srow["sold"]),
                "returned": int(srow["returned"]),
                "rate": srow["rate"],
            })

    # Size spread
    if size_breakdown:
        size_rates = [s["rate"] for s in size_breakdown]
        size_spread = (max(size_rates) - min(size_rates)) * 100
        worst_size = max(size_breakdown, key=lambda s: s["rate"])
        best_size = min(size_breakdown, key=lambda s: s["rate"])
    else:
        size_spread = 0
        worst_size = best_size = None

    # --- Return reason breakdown ---
    sup_reasons_raw = sup_skus[sup_skus["has_reason_data"] == True] if "has_reason_data" in sup_skus.columns else pd.DataFrame()
    # Compute weighted reason percentages
    if not sup_reasons_raw.empty and "pct_too_small" in sup_reasons_raw.columns:
        # Weight by volume
        total_with_reasons = sup_reasons_raw["total_sold"].sum()
        if total_with_reasons > 0:
            pct_too_small = (sup_reasons_raw["pct_too_small"] * sup_reasons_raw["total_sold"]).sum() / total_with_reasons
            pct_too_large = (sup_reasons_raw["pct_too_large"] * sup_reasons_raw["total_sold"]).sum() / total_with_reasons
            pct_quality = (sup_reasons_raw["pct_quality"] * sup_reasons_raw["total_sold"]).sum() / total_with_reasons
            pct_other = (sup_reasons_raw["pct_other_reason"] * sup_reasons_raw["total_sold"]).sum() / total_with_reasons
        else:
            pct_too_small = pct_too_large = pct_quality = pct_other = 0
    else:
        pct_too_small = pct_too_large = pct_quality = pct_other = 0

    # --- Category comparisons (≥500 sold for strong comparison) ---
    strong_cat_deviations = []
    for cb in cat_breakdown:
        if cb["sold"] >= MIN_CAT_SUPPLIER_COMPARE:
            is_under = (cb["deviation_pp"] > UNDERPERFORM_ABS_PP and cb["deviation_rel"] > UNDERPERFORM_REL_PCT)
            strong_cat_deviations.append({
                **cb,
                "underperforming": is_under,
            })

    # --- Sizing consistency check (does supplier consistently run small/large?) ---
    # Check across multiple SKUs
    sizing_skus = sup_skus[sup_skus["has_reason_data"] == True].copy() if "has_reason_data" in sup_skus.columns else pd.DataFrame()
    sizing_pattern = "UNKNOWN"
    if not sizing_skus.empty and len(sizing_skus) >= 3:
        skus_too_small = (sizing_skus["pct_too_small"] > 0.3).sum()
        skus_too_large = (sizing_skus["pct_too_large"] > 0.3).sum()
        total_sizing_skus = len(sizing_skus)
        if skus_too_small / total_sizing_skus > 0.5:
            sizing_pattern = "RUNS_SMALL"
        elif skus_too_large / total_sizing_skus > 0.5:
            sizing_pattern = "RUNS_LARGE"
        elif (skus_too_small + skus_too_large) / total_sizing_skus > 0.5:
            sizing_pattern = "MIXED_SIZING"
        else:
            sizing_pattern = "NO_CLEAR_PATTERN"

    # --- Confidence level ---
    sku_count = len(sup_skus)
    skus_with_100_plus = (sup_skus["total_sold"] >= HIGH_SKU_UNITS).sum()
    if total_sold >= HIGH_UNITS and skus_with_100_plus >= HIGH_SKU_COUNT:
        confidence = "HIGH"
    elif total_sold >= MIN_SUPPLIER_SOLD and sku_count >= MEDIUM_SKU_COUNT:
        confidence = "MEDIUM"
    else:
        confidence = "LOW"

    # --- Overall category benchmark (supplier's primary category) ---
    primary_cat_data = sup_cat_data.sort_values("sold", ascending=False)
    primary_cat = primary_cat_data.iloc[0]["category_l3"] if len(primary_cat_data) > 0 else None
    primary_bench = cat_benchmarks.get(primary_cat, {}).get("weighted_median", 0) if primary_cat else 0
    overall_deviation_pp = (overall_rate - primary_bench) * 100
    overall_deviation_rel = ((overall_rate - primary_bench) / primary_bench * 100) if primary_bench > 0 else 0

    is_underperforming = (overall_deviation_pp > UNDERPERFORM_ABS_PP and overall_deviation_rel > UNDERPERFORM_REL_PCT)
    any_cat_underperforming = any(cd.get("underperforming", False) for cd in strong_cat_deviations)

    # --- Issue type ---
    if pct_too_small > 0.30 or pct_too_large > 0.30:
        issue_type = "SIZING"
    elif pct_quality > 0.20:
        issue_type = "QUALITY"
    elif (pct_too_small + pct_too_large) > 0.30 and pct_quality > 0.10:
        issue_type = "MIXED"
    elif is_underperforming or any_cat_underperforming:
        issue_type = "STRUCTURAL"
    else:
        issue_type = "WITHIN_NORMS"

    # --- Assessment level ---
    excess_returns = max(0, total_returned - primary_bench * total_sold)
    commercial_impact = excess_returns  # units of excess returns

    if is_underperforming and confidence in ("HIGH", "MEDIUM") and commercial_impact > 100:
        assessment = "CRITICAL"
    elif (is_underperforming or any_cat_underperforming) and commercial_impact > 50:
        assessment = "CONCERNING"
    elif overall_rate > primary_bench and commercial_impact > 20:
        assessment = "MONITOR"
    else:
        assessment = "ACCEPTABLE"

    results.append({
        "supplier_name": sname,
        "total_sold": int(total_sold),
        "total_returned": int(total_returned),
        "overall_rate": overall_rate,
        "primary_category": primary_cat,
        "primary_bench": primary_bench,
        "overall_deviation_pp": overall_deviation_pp,
        "overall_deviation_rel": overall_deviation_rel,
        "is_underperforming": is_underperforming,
        "any_cat_underperforming": any_cat_underperforming,
        "assessment": assessment,
        "confidence": confidence,
        "sku_count": sku_count,
        "skus_with_100_plus": skus_with_100_plus,
        "top_sku_prefix": top_sku_prefix,
        "top_sku_name": top_sku_name,
        "top_sku_pct": top_sku_pct,
        "top_sku_rate": top_sku_rate,
        "is_concentrated": is_concentrated,
        "worst_sku_prefix": worst_sku_prefix,
        "worst_sku_name": worst_sku_name,
        "worst_sku_sold": int(worst_sku_sold),
        "worst_sku_returned": int(worst_sku_returned),
        "worst_sku_rate": worst_sku_rate,
        "rate_without_worst": rate_without_worst,
        "cat_breakdown": cat_breakdown,
        "size_breakdown": size_breakdown,
        "strong_cat_deviations": strong_cat_deviations,
        "size_spread": size_spread,
        "worst_size": worst_size,
        "best_size": best_size,
        "pct_too_small": pct_too_small,
        "pct_too_large": pct_too_large,
        "pct_quality": pct_quality,
        "pct_other": pct_other,
        "sizing_pattern": sizing_pattern,
        "issue_type": issue_type,
        "commercial_impact": commercial_impact,
        "excess_returns": excess_returns,
    })

# Sort by commercial impact
results.sort(key=lambda x: x["commercial_impact"], reverse=True)

# ═══════════════════════════════════════════════════════════════
# 4. SIZE × CATEGORY STRUCTURAL PATTERNS
# ═══════════════════════════════════════════════════════════════

# For each category, identify sizes that are structurally problematic
size_cat_patterns = []
for cat in sorted(cat_benchmarks.keys()):
    cat_bench = cat_benchmarks[cat]
    cat_sizes_data = sup_cat_size[sup_cat_size["category_l3"] == cat].groupby("size").agg(
        sold=("sold", "sum"), returned=("returned", "sum")
    ).reset_index()
    cat_sizes_data["rate"] = cat_sizes_data["returned"] / cat_sizes_data["sold"].replace(0, 1)
    cat_rate = cat_bench["weighted_avg"]

    for _, row in cat_sizes_data.iterrows():
        if row["sold"] >= 200:
            dev = (row["rate"] - cat_rate) * 100
            size_cat_patterns.append({
                "category": cat,
                "size": row["size"],
                "sold": int(row["sold"]),
                "returned": int(row["returned"]),
                "rate": row["rate"],
                "cat_avg": cat_rate,
                "deviation_pp": dev,
            })

# ═══════════════════════════════════════════════════════════════
# 5. TOP PERFORMERS
# ═══════════════════════════════════════════════════════════════

# Suppliers below their category benchmark
good_performers = [r for r in results if r["overall_rate"] < r["primary_bench"] and r["confidence"] in ("HIGH", "MEDIUM")]
good_performers.sort(key=lambda x: x["overall_deviation_pp"])  # Most below benchmark first


# ═══════════════════════════════════════════════════════════════
# 6. GENERATE REPORT
# ═══════════════════════════════════════════════════════════════

def fmt_pct(val):
    return f"{val*100:.1f}%"

def fmt_pp(val):
    sign = "+" if val > 0 else ""
    return f"{sign}{val:.1f}pp"

# Build the markdown report
lines = []

lines.append("# Supplier Performance Analysis")
lines.append(f"**Generated:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
lines.append("")
lines.append("**Methodology:** All-time return rates from CustomerReturns (ACCEPTED/PENDING/REJECTED) vs Orders (DISPATCHED/DELIVERED/PROCESSING). Delivery lag excluded (7d fast channels, 14d slow). merchantKey=hiccup only. Channels excluded: aboutYou, vogaCloset.")
lines.append("")

# ─── EXECUTIVE SUMMARY ───
lines.append("## Executive Summary")
lines.append("")

# Data overview
total_qualifying = len(qualifying)
total_sold_all = qualifying["total_sold"].sum()
total_returned_all = qualifying["total_returned"].sum()
overall_rate_all = total_returned_all / total_sold_all if total_sold_all > 0 else 0
lines.append(f"**Data scope:** {total_qualifying} suppliers with ≥{MIN_SUPPLIER_SOLD} units sold, covering {total_sold_all:,} units sold and {total_returned_all:,} returned ({fmt_pct(overall_rate_all)} overall).")
lines.append("")

# Count by assessment
critical = [r for r in results if r["assessment"] == "CRITICAL"]
concerning = [r for r in results if r["assessment"] == "CONCERNING"]
monitor = [r for r in results if r["assessment"] == "MONITOR"]
acceptable = [r for r in results if r["assessment"] == "ACCEPTABLE"]

lines.append(f"- **CRITICAL:** {len(critical)} suppliers")
lines.append(f"- **CONCERNING:** {len(concerning)} suppliers")
lines.append(f"- **MONITOR:** {len(monitor)} suppliers")
lines.append(f"- **ACCEPTABLE:** {len(acceptable)} suppliers")
lines.append("")

# Top 5 requiring attention
lines.append("### Top 5 Suppliers Requiring Immediate Attention")
lines.append("")
lines.append("| # | Supplier | Assessment | Return Rate | Benchmark | Excess Returns | Confidence |")
lines.append("|---|----------|------------|-------------|-----------|----------------|------------|")
attention_list = [r for r in results if r["assessment"] in ("CRITICAL", "CONCERNING", "MONITOR")]
attention_list.sort(key=lambda x: x["commercial_impact"], reverse=True)
for i, r in enumerate(attention_list[:5], 1):
    lines.append(f"| {i} | {r['supplier_name']} | {r['assessment']} | {fmt_pct(r['overall_rate'])} | {fmt_pct(r['primary_bench'])} (cat median) | ~{int(r['excess_returns'])} units | {r['confidence']} |")
lines.append("")

# Top 5 performing well
lines.append("### Top 5 Suppliers Performing Well")
lines.append("")
lines.append("| # | Supplier | Return Rate | Benchmark | Below by | Volume | Confidence |")
lines.append("|---|----------|-------------|-----------|----------|--------|------------|")
for i, r in enumerate(good_performers[:5], 1):
    lines.append(f"| {i} | {r['supplier_name']} | {fmt_pct(r['overall_rate'])} | {fmt_pct(r['primary_bench'])} | {fmt_pp(r['overall_deviation_pp'])} | {r['total_sold']:,} sold | {r['confidence']} |")
lines.append("")

# ─── CATEGORY BENCHMARKS TABLE ───
lines.append("## Category Benchmarks")
lines.append("")
lines.append("These are the reference rates used for all supplier comparisons.")
lines.append("")
lines.append("| Category | Total Sold | Weighted Avg Return Rate | Weighted Median Return Rate |")
lines.append("|----------|-----------|-------------------------|----------------------------|")
sorted_cats = sorted(cat_benchmarks.items(), key=lambda x: x[1]["total_sold"], reverse=True)
for cat, bench in sorted_cats:
    if bench["total_sold"] >= 500:
        lines.append(f"| {cat} | {bench['total_sold']:,} | {fmt_pct(bench['weighted_avg'])} | {fmt_pct(bench['weighted_median'])} |")
lines.append("")


# ─── DETAILED SUPPLIER ASSESSMENTS ───
lines.append("## Detailed Supplier Assessments")
lines.append("")
lines.append("Sorted by commercial impact (volume x excess return rate). Only suppliers with assessment of CRITICAL, CONCERNING, or MONITOR are detailed below.")
lines.append("")

for r in results:
    if r["assessment"] == "ACCEPTABLE":
        continue

    lines.append(f"### {r['supplier_name']} — {r['assessment']}")
    lines.append("")

    # Summary metrics
    lines.append(f"- **Volume:** {r['total_sold']:,} units sold, {r['total_returned']:,} returned, **{fmt_pct(r['overall_rate'])} return rate**")
    lines.append(f"- **Primary category:** {r['primary_category']} (benchmark: {fmt_pct(r['primary_bench'])} weighted median)")
    lines.append(f"- **Deviation:** {fmt_pp(r['overall_deviation_pp'])} absolute, {r['overall_deviation_rel']:.1f}% relative")
    lines.append(f"- **Confidence:** {r['confidence']} ({r['sku_count']} SKUs total, {r['skus_with_100_plus']} with ≥100 units)")
    lines.append(f"- **Excess returns:** ~{int(r['excess_returns'])} units above what the category median would predict")
    lines.append("")

    # SKU concentration
    lines.append(f"**SKU Concentration:** {r['top_sku_pct']*100:.1f}% of volume from top SKU")
    if r["is_concentrated"]:
        lines.append(f"  - WARNING: Concentrated. Top SKU: `{r['top_sku_prefix']}` ({r['top_sku_name'][:60]}), return rate {fmt_pct(r['top_sku_rate'])}")
        lines.append(f"  - Evaluate this SKU separately from the supplier")
    lines.append("")

    # Issue type
    lines.append(f"**Issue Type:** {r['issue_type']}")
    if r["pct_too_small"] > 0 or r["pct_too_large"] > 0 or r["pct_quality"] > 0:
        lines.append(f"  - Too Small: {r['pct_too_small']*100:.1f}% | Too Large: {r['pct_too_large']*100:.1f}% | Quality: {r['pct_quality']*100:.1f}% | Other: {r['pct_other']*100:.1f}%")
        if r["sizing_pattern"] != "UNKNOWN" and r["sizing_pattern"] != "NO_CLEAR_PATTERN":
            lines.append(f"  - Sizing pattern across SKUs: **{r['sizing_pattern']}** (consistent across multiple products)")
    else:
        lines.append(f"  - No return reason data available for this supplier's channels")
    lines.append("")

    # Category breakdown
    if r["cat_breakdown"]:
        lines.append("**Return Rate by Category:**")
        lines.append("")
        lines.append("| Category | Sold | Return Rate | Benchmark (wt. median) | Deviation | Underperforming? |")
        lines.append("|----------|------|-------------|------------------------|-----------|------------------|")
        for cb in sorted(r["cat_breakdown"], key=lambda x: x["sold"], reverse=True):
            is_under = "YES" if (cb["deviation_pp"] > UNDERPERFORM_ABS_PP and cb["deviation_rel"] > UNDERPERFORM_REL_PCT) else "no"
            lines.append(f"| {cb['category']} | {cb['sold']:,} | {fmt_pct(cb['rate'])} | {fmt_pct(cb['benchmark_wmedian'])} | {fmt_pp(cb['deviation_pp'])} | {is_under} |")
        lines.append("")

    # Size breakdown
    if r["size_breakdown"]:
        lines.append("**Return Rate by Size:**")
        lines.append("")
        lines.append("| Size | Sold | Returned | Return Rate |")
        lines.append("|------|------|----------|-------------|")
        for sb in sorted(r["size_breakdown"], key=lambda x: x["rate"], reverse=True):
            lines.append(f"| {sb['size']} | {sb['sold']:,} | {sb['returned']:,} | {fmt_pct(sb['rate'])} |")
        lines.append("")
        lines.append(f"Size spread: {r['size_spread']:.1f}pp (worst: {r['worst_size']['size']} at {fmt_pct(r['worst_size']['rate'])}, best: {r['best_size']['size']} at {fmt_pct(r['best_size']['rate'])})")
        if r["size_spread"] > SIZE_SPREAD_FLAG_PP:
            lines.append(f"  - FLAG: Size spread >{SIZE_SPREAD_FLAG_PP:.0f}pp — potential grading issue")
        lines.append("")

    # Worst SKU removal
    lines.append(f"**Robustness Check — Remove worst SKU:**")
    lines.append(f"  - Worst SKU: `{r['worst_sku_prefix']}` ({r['worst_sku_name'][:60] if isinstance(r['worst_sku_name'], str) else 'N/A'}) — {r['worst_sku_sold']:,} sold, {fmt_pct(r['worst_sku_rate'])} return rate")
    lines.append(f"  - Supplier rate drops from {fmt_pct(r['overall_rate'])} to {fmt_pct(r['rate_without_worst'])} without this SKU")
    drop = (r["overall_rate"] - r["rate_without_worst"]) * 100
    if drop > 3:
        lines.append(f"  - This single SKU accounts for ~{drop:.1f}pp of the supplier's rate — the problem may be SKU-specific, not supplier-wide")
    else:
        lines.append(f"  - Removing it only changes the rate by {drop:.1f}pp — the issue is spread across the supplier's range")
    lines.append("")

    # Recommended action
    lines.append("**Recommended Action:**")
    if r["assessment"] == "CRITICAL":
        if r["issue_type"] == "SIZING":
            lines.append(f"  - Request updated size charts and grading specs from {r['supplier_name']}")
            lines.append(f"  - Consider mandatory fit samples before next order")
            if r["sizing_pattern"] == "RUNS_SMALL":
                lines.append(f"  - Specific: Products consistently run small — request upsizing across the range")
            elif r["sizing_pattern"] == "RUNS_LARGE":
                lines.append(f"  - Specific: Products consistently run large — request downsizing across the range")
        elif r["issue_type"] == "QUALITY":
            lines.append(f"  - Arrange quality audit with {r['supplier_name']}. {r['pct_quality']*100:.0f}% of returns cite quality issues")
            lines.append(f"  - Consider reducing order depth until quality improves")
        else:
            lines.append(f"  - Schedule supplier review meeting. Return rate of {fmt_pct(r['overall_rate'])} is significantly above category benchmark of {fmt_pct(r['primary_bench'])}")
            lines.append(f"  - Review their top-returning products individually for root cause")
    elif r["assessment"] == "CONCERNING":
        lines.append(f"  - Raise in next regular supplier meeting. Document the {fmt_pp(r['overall_deviation_pp'])} deviation from category benchmark")
        if r["is_concentrated"]:
            lines.append(f"  - Focus conversation on top SKU `{r['top_sku_prefix']}` which drives most of the volume")
    else:  # MONITOR
        lines.append(f"  - No immediate action required. Re-evaluate in 30 days")
        lines.append(f"  - If trend continues, escalate to CONCERNING")
    lines.append("")

    # Suggested conversation
    lines.append("**Suggested Supplier Conversation:**")
    if r["assessment"] == "CRITICAL":
        lines.append(f'  > "We need to discuss the return performance on your products. Your return rate is {fmt_pct(r["overall_rate"])}, which is {fmt_pp(r["overall_deviation_pp"])} above the category average of {fmt_pct(r["primary_bench"])}. This represents approximately {int(r["excess_returns"])} excess returned units. We need a concrete improvement plan."')
    elif r["assessment"] == "CONCERNING":
        lines.append(f'  > "We\'re seeing your return rate at {fmt_pct(r["overall_rate"])} against a category benchmark of {fmt_pct(r["primary_bench"])}. Can we review the sizing/quality feedback together and identify improvements?"')
    else:
        lines.append(f'  > "FYI — we\'re monitoring return rates and your products are slightly above the category benchmark. No action needed now, but wanted to flag it."')
    lines.append("")
    lines.append("---")
    lines.append("")


# ─── ALL QUALIFYING SUPPLIERS (FULL TABLE) ───
lines.append("## All Qualifying Suppliers — Full Table")
lines.append("")
lines.append("| Supplier | Sold | Returned | Return Rate | Primary Cat | Cat Benchmark | Deviation | SKUs | Confidence | Assessment |")
lines.append("|----------|------|----------|-------------|-------------|---------------|-----------|------|------------|------------|")
for r in results:
    lines.append(f"| {r['supplier_name']} | {r['total_sold']:,} | {r['total_returned']:,} | {fmt_pct(r['overall_rate'])} | {r['primary_category']} | {fmt_pct(r['primary_bench'])} | {fmt_pp(r['overall_deviation_pp'])} | {r['sku_count']} | {r['confidence']} | {r['assessment']} |")
lines.append("")


# ─── SIZE × CATEGORY PATTERNS ───
lines.append("## Size x Category Structural Patterns")
lines.append("")
lines.append("Sizes that are structurally problematic across all suppliers in a category (not supplier-specific). Only sizes with ≥200 units sold shown.")
lines.append("")

# Find sizes that consistently over-index
structural_issues = [p for p in size_cat_patterns if p["deviation_pp"] > 3.0]
structural_issues.sort(key=lambda x: x["deviation_pp"], reverse=True)

if structural_issues:
    lines.append("### Sizes with Above-Average Return Rates (>3pp above category avg)")
    lines.append("")
    lines.append("| Category | Size | Sold | Return Rate | Category Avg | Deviation |")
    lines.append("|----------|------|------|-------------|--------------|-----------|")
    for p in structural_issues[:20]:
        lines.append(f"| {p['category']} | {p['size']} | {p['sold']:,} | {fmt_pct(p['rate'])} | {fmt_pct(p['cat_avg'])} | {fmt_pp(p['deviation_pp'])} |")
    lines.append("")

# Sizes that are structurally low
structural_good = [p for p in size_cat_patterns if p["deviation_pp"] < -3.0]
structural_good.sort(key=lambda x: x["deviation_pp"])

if structural_good:
    lines.append("### Sizes with Below-Average Return Rates (<-3pp below category avg)")
    lines.append("")
    lines.append("| Category | Size | Sold | Return Rate | Category Avg | Deviation |")
    lines.append("|----------|------|------|-------------|--------------|-----------|")
    for p in structural_good[:20]:
        lines.append(f"| {p['category']} | {p['size']} | {p['sold']:,} | {fmt_pct(p['rate'])} | {fmt_pct(p['cat_avg'])} | {fmt_pp(p['deviation_pp'])} |")
    lines.append("")

# Cross-category size analysis: which sizes are bad everywhere?
size_across_cats = {}
for p in size_cat_patterns:
    sz = p["size"]
    if sz not in size_across_cats:
        size_across_cats[sz] = {"above": 0, "below": 0, "total": 0, "total_sold": 0}
    size_across_cats[sz]["total"] += 1
    size_across_cats[sz]["total_sold"] += p["sold"]
    if p["deviation_pp"] > 3:
        size_across_cats[sz]["above"] += 1
    elif p["deviation_pp"] < -3:
        size_across_cats[sz]["below"] += 1

lines.append("### Cross-Category Size Summary")
lines.append("")
lines.append("Does a size consistently over-index on returns regardless of category?")
lines.append("")
lines.append("| Size | Categories Measured | Above Avg (>3pp) | Below Avg (<-3pp) | Interpretation |")
lines.append("|------|--------------------|------------------|-------------------|----------------|")
for sz, stats in sorted(size_across_cats.items(), key=lambda x: x[1]["above"], reverse=True):
    if stats["total"] >= 2:
        pct_above = stats["above"] / stats["total"] * 100
        if pct_above > 60:
            interp = "Structurally problematic"
        elif pct_above > 30:
            interp = "Mixed — some categories only"
        else:
            interp = "Not consistently problematic"
        lines.append(f"| {sz} | {stats['total']} | {stats['above']} ({pct_above:.0f}%) | {stats['below']} | {interp} |")
lines.append("")


# ─── METHODOLOGY NOTES ───
lines.append("## Methodology & Caveats")
lines.append("")
lines.append("### Thresholds Applied")
lines.append(f"- Supplier minimum: {MIN_SUPPLIER_SOLD} units sold")
lines.append(f"- Size×supplier minimum: {MIN_SIZE_SUPPLIER_SOLD} units sold for size-level conclusions")
lines.append(f"- Category×supplier minimum: {MIN_CAT_SUPPLIER_SOLD} units sold for category-level breakdown, {MIN_CAT_SUPPLIER_COMPARE} for underperformance flagging")
lines.append(f"- Underperforming threshold: >{UNDERPERFORM_ABS_PP}pp absolute AND >{UNDERPERFORM_REL_PCT}% relative above benchmark")
lines.append(f"- SKU concentration flag: >{SKU_CONCENTRATION_THRESHOLD*100:.0f}% of volume from 1 SKU")
lines.append(f"- Size spread flag: >{SIZE_SPREAD_FLAG_PP:.0f}pp between best and worst size")
lines.append("")
lines.append("### Confidence Levels")
lines.append(f"- HIGH: ≥{HIGH_UNITS} units, ≥{HIGH_SKU_COUNT} SKUs with ≥{HIGH_SKU_UNITS} units each")
lines.append(f"- MEDIUM: ≥{MIN_SUPPLIER_SOLD} units, ≥{MEDIUM_SKU_COUNT} SKUs")
lines.append("- LOW: anything below these thresholds")
lines.append("")
lines.append("### Return Reason Coverage")
lines.append("Return reason data (too small / too large / quality / other) is only available for channels: trendyol, fashiondays, fashiondaysBG, hepsiburada, emag, trendyolRO. Suppliers selling primarily through other channels will show 0% for all reason categories — this does not mean there are no sizing issues, just that we cannot measure them.")
lines.append("")
lines.append("### Benchmarking Approach")
lines.append("- Category benchmarks use **weighted median** return rate across all suppliers in that category, weighted by volume. This is more robust than a simple average (resistant to outliers).")
lines.append("- A supplier is flagged as underperforming only when they exceed the benchmark by BOTH >5pp absolute AND >25% relative. This dual threshold prevents flagging low-rate categories (where 5pp is huge) and high-rate categories (where 5pp is noise).")
lines.append("")
lines.append("### What This Analysis Does NOT Cover")
lines.append("- Financial impact (cost of returns, logistics, lost margin)")
lines.append("- Temporal trends (is the supplier improving or getting worse?)")
lines.append("- Channel-specific performance (a supplier may perform differently on Trendyol vs. other channels)")
lines.append("- New products launched in the last 45 days (insufficient return data)")
lines.append("")


# ═══════════════════════════════════════════════════════════════
# WRITE TO FILE
# ═══════════════════════════════════════════════════════════════

report = "\n".join(lines)
output_path = os.path.join(PROJECT_ROOT, "analysis", "supplier_analysis_2026-04-22.md")
with open(output_path, "w") as f:
    f.write(report)

print(f"\nReport written to: {output_path}")
print(f"  Length: {len(lines)} lines, {len(report)} characters")

# ═══════════════════════════════════════════════════════════════
# STDOUT SUMMARY
# ═══════════════════════════════════════════════════════════════

print("\n" + "=" * 70)
print("SUPPLIER PERFORMANCE ANALYSIS — SUMMARY")
print("=" * 70)
print(f"\nData: {total_qualifying} suppliers, {total_sold_all:,} sold, {total_returned_all:,} returned ({fmt_pct(overall_rate_all)})")
print(f"\nCRITICAL ({len(critical)}):")
for r in critical:
    print(f"  - {r['supplier_name']}: {fmt_pct(r['overall_rate'])} vs {fmt_pct(r['primary_bench'])} benchmark ({r['confidence']} confidence, {r['issue_type']})")

print(f"\nCONCERNING ({len(concerning)}):")
for r in concerning:
    print(f"  - {r['supplier_name']}: {fmt_pct(r['overall_rate'])} vs {fmt_pct(r['primary_bench'])} benchmark ({r['confidence']} confidence, {r['issue_type']})")

print(f"\nMONITOR ({len(monitor)}):")
for r in monitor:
    print(f"  - {r['supplier_name']}: {fmt_pct(r['overall_rate'])} vs {fmt_pct(r['primary_bench'])} benchmark ({r['confidence']} confidence)")

print(f"\nACCEPTABLE ({len(acceptable)}):")
for r in acceptable[:10]:
    print(f"  - {r['supplier_name']}: {fmt_pct(r['overall_rate'])} vs {fmt_pct(r['primary_bench'])} benchmark")
if len(acceptable) > 10:
    print(f"  ... and {len(acceptable)-10} more")

print(f"\nTOP PERFORMERS:")
for r in good_performers[:5]:
    print(f"  - {r['supplier_name']}: {fmt_pct(r['overall_rate'])} ({fmt_pp(r['overall_deviation_pp'])} below benchmark, {r['total_sold']:,} sold)")

print(f"\nFull report: {output_path}")
