"""
Analysis engine: joins returns + orders data, computes metrics,
detects anomalies. All-time return rates, ranked by recent sales.

Three SKU views:
- Bestsellers: top sellers with problematic return rates
- Rising Stars: recently launched SKUs with high sales + emerging return issues
- Recovering: top SKUs showing significant improvement in return rate
"""

from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

import pandas as pd

import config
from engine import pipelines


def _build_reason_summary(reasons: list) -> Tuple[Optional[str], float, dict]:
    valid = [r for r in reasons if r is not None]
    if not valid:
        return None, 0.0, {}
    counts = Counter(valid)
    top, top_count = counts.most_common(1)[0]
    return top, top_count / len(reasons), dict(counts)


def _classify_problem(
    top_reason: Optional[str],
    reason_pct: float,
    reason_counts: dict,
    size_concentration: float,
    anomaly_sizes: List[dict],
    has_reason_data: bool,
) -> str:
    sizing_total = sum(reason_counts.get(r, 0) for r in config.SIZING_REASONS)
    total = sum(reason_counts.values()) if reason_counts else 0
    sizing_share = sizing_total / total if total > 0 else 0

    if size_concentration > config.SIZE_CONCENTRATION_THRESHOLD:
        return "SIZING"

    if has_reason_data and total > 0:
        if sizing_share > 0.40:
            return "SIZING"
        if reason_counts.get("DEFECTIVE_PRODUCT", 0) / total > 0.30:
            return "QUALITY"
        if reason_counts.get("EXPECTATION_MISMATCH", 0) / total > 0.35:
            return "LISTING"
        if reason_pct >= config.REASON_CONCENTRATION_THRESHOLD and top_reason:
            if top_reason in config.SIZING_REASONS:
                return "SIZING"
            if top_reason in config.QUALITY_REASONS:
                return "QUALITY"
            if top_reason in config.LISTING_REASONS:
                return "LISTING"

    return "UNKNOWN"


def load_data() -> dict:
    """
    Main entry point. Loads all-time data from MongoDB, computes all metrics.
    """
    # --- Fetch raw data ---
    returns_raw = pipelines.get_all_returns_by_sku()
    orders_raw = pipelines.get_all_orders_by_sku()
    recent_sales_raw = pipelines.get_recent_sales_by_sku_size()
    products_raw = pipelines.get_product_metadata()
    first_orders_raw = pipelines.get_sku_first_order_dates()
    returns_recent_raw = pipelines.get_returns_last_30d_by_sku()
    returns_prev_raw = pipelines.get_returns_prev_30d_by_sku()

    # --- Build DataFrames ---
    df_ret = pd.DataFrame(returns_raw) if returns_raw else pd.DataFrame(
        columns=["sku_prefix", "size", "returned", "product_name", "reasons", "channels"]
    )
    df_ord = pd.DataFrame(orders_raw) if orders_raw else pd.DataFrame(
        columns=["sku_prefix", "size", "sold", "product_name", "category"]
    )
    df_recent_size = pd.DataFrame(recent_sales_raw) if recent_sales_raw else pd.DataFrame(
        columns=["sku_prefix", "size", "recent_sold"]
    )
    df_prod = pd.DataFrame(products_raw) if products_raw else pd.DataFrame(
        columns=[
            "sku_prefix", "family_sku", "product_name", "category",
            "category_l1", "category_l2", "category_l3", "category_l4",
            "fit_type", "supplier_name", "supplier_id", "sizes",
        ]
    )
    df_first = pd.DataFrame(first_orders_raw) if first_orders_raw else pd.DataFrame(
        columns=["sku_prefix", "first_order"]
    )
    df_ret_recent = pd.DataFrame(returns_recent_raw) if returns_recent_raw else pd.DataFrame(
        columns=["sku_prefix", "returned_recent"]
    )
    df_ret_prev = pd.DataFrame(returns_prev_raw) if returns_prev_raw else pd.DataFrame(
        columns=["sku_prefix", "returned_prev"]
    )

    # Aggregate recent sales size-level (fast+slow channel results need merging)
    if not df_recent_size.empty:
        df_recent_size = (
            df_recent_size.groupby(["sku_prefix", "size"], as_index=False)["recent_sold"].sum()
        )

    # Determine qualifying SKUs: at least one size with >= MIN_RECENT_SALES_PER_SIZE
    if not df_recent_size.empty:
        qualifying_sizes = df_recent_size[
            df_recent_size["recent_sold"] >= config.MIN_RECENT_SALES_PER_SIZE
        ]
        qualifying_skus = set(qualifying_sizes["sku_prefix"].unique())
        # Also build SKU-level recent_sold totals
        df_recent = df_recent_size.groupby("sku_prefix", as_index=False)["recent_sold"].sum()
    else:
        qualifying_skus = set()
        df_recent = pd.DataFrame(columns=["sku_prefix", "recent_sold"])

    # Same for orders (fast+slow channel results need merging)
    if not df_ord.empty:
        df_ord = (
            df_ord.groupby(["sku_prefix", "size"])
            .agg(sold=("sold", "sum"), product_name=("product_name", "first"), category=("category", "first"))
            .reset_index()
        )

    # --- SKU × Size level (all-time) ---
    df_sku_size = _compute_sku_size(df_ret, df_ord, df_prod)

    # --- SKU level ---
    df_sku = _compute_sku_level(df_sku_size, df_ret, df_prod, df_recent, df_first,
                                 df_ret_recent, df_ret_prev, qualifying_skus)

    # --- Supplier level ---
    df_supplier = _compute_supplier_level(df_sku)

    # --- Category level ---
    df_category = _compute_category_level(df_sku_size)

    return {
        "df_sku": df_sku,
        "df_sku_size": df_sku_size,
        "df_supplier": df_supplier,
        "df_category": df_category,
        "df_recent_size": df_recent_size if not df_recent_size.empty else pd.DataFrame(
            columns=["sku_prefix", "size", "recent_sold"]
        ),
    }


def _compute_sku_size(
    df_ret: pd.DataFrame, df_ord: pd.DataFrame, df_prod: pd.DataFrame
) -> pd.DataFrame:
    if df_ord.empty:
        return pd.DataFrame()

    ord_agg = df_ord.copy()

    if df_ret.empty:
        ord_agg["returned"] = 0
        ord_agg["size_reasons"] = [[] for _ in range(len(ord_agg))]
    else:
        ret_agg = (
            df_ret.groupby(["sku_prefix", "size"])
            .agg(
                returned=("returned", "sum"),
                size_reasons=("reasons", lambda x: [r for rl in x for r in rl]),
            )
            .reset_index()
        )
        ord_agg = ord_agg.merge(ret_agg, on=["sku_prefix", "size"], how="left")
        ord_agg["returned"] = ord_agg["returned"].fillna(0).astype(int)
        ord_agg["size_reasons"] = ord_agg["size_reasons"].apply(
            lambda x: x if isinstance(x, list) else []
        )

    ord_agg["return_rate"] = (ord_agg["returned"] / ord_agg["sold"]).clip(upper=1.0)

    # Size-level reason percentages
    def _size_reason_pcts(reasons):
        total = len([r for r in reasons if r is not None])
        if total == 0:
            return 0.0, 0.0, 0.0, 0.0
        ts = sum(1 for r in reasons if r == "TOO_SMALL")
        tl = sum(1 for r in reasons if r == "TOO_LARGE")
        qual = sum(1 for r in reasons if r in config.QUALITY_REASONS)
        ot = total - ts - tl - qual
        return ts / total, tl / total, qual / total, max(ot / total, 0)

    pcts = ord_agg["size_reasons"].apply(_size_reason_pcts)
    ord_agg["pct_too_small"] = pcts.apply(lambda x: x[0])
    ord_agg["pct_too_large"] = pcts.apply(lambda x: x[1])
    ord_agg["pct_quality"] = pcts.apply(lambda x: x[2])
    ord_agg["pct_other"] = pcts.apply(lambda x: x[3])

    # Add product metadata
    prod_dedup = df_prod.drop_duplicates(subset="sku_prefix")
    ord_agg = ord_agg.merge(
        prod_dedup[["sku_prefix", "category_l3", "category_l4", "supplier_name", "fit_type", "image_url"]],
        on="sku_prefix",
        how="left",
    )

    mask = ord_agg["category_l3"].isna() & ord_agg["category"].notna()
    if mask.any():
        parts = ord_agg.loc[mask, "category"].str.split("/")
        ord_agg.loc[mask, "category_l3"] = parts.str[2]
        ord_agg.loc[mask, "category_l4"] = parts.str[3]

    return ord_agg


def _compute_sku_level(
    df_sku_size: pd.DataFrame,
    df_ret: pd.DataFrame,
    df_prod: pd.DataFrame,
    df_recent: pd.DataFrame,
    df_first: pd.DataFrame,
    df_ret_recent: pd.DataFrame,
    df_ret_prev: pd.DataFrame,
    qualifying_skus: set,
) -> pd.DataFrame:
    if df_sku_size.empty:
        return pd.DataFrame()

    # --- Aggregate across sizes ---
    sku_agg = (
        df_sku_size.groupby("sku_prefix")
        .agg(
            total_sold=("sold", "sum"),
            total_returned=("returned", "sum"),
            product_name=("product_name", "first"),
            category_l3=("category_l3", "first"),
            category_l4=("category_l4", "first"),
            supplier_name=("supplier_name", "first"),
            image_url=("image_url", "first"),
        )
        .reset_index()
    )

    sku_agg["return_rate"] = (sku_agg["total_returned"] / sku_agg["total_sold"]).clip(upper=1.0)

    # --- Add recent sales ---
    sku_agg = sku_agg.merge(df_recent, on="sku_prefix", how="left")
    sku_agg["recent_sold"] = sku_agg["recent_sold"].fillna(0).astype(int)

    # --- Add first order date ---
    sku_agg = sku_agg.merge(df_first, on="sku_prefix", how="left")

    # --- Category baselines (P75) ---
    # Only use SKUs with >= 20 units for baseline calculation (avoids noise)
    baseline_pool = sku_agg[sku_agg["total_sold"] >= 20]
    baselines = (
        baseline_pool.groupby("category_l3")["return_rate"]
        .quantile(config.BASELINE_PERCENTILE)
        .rename("category_baseline")
    )
    sku_agg = sku_agg.merge(baselines, on="category_l3", how="left")
    global_p75 = baseline_pool["return_rate"].quantile(config.BASELINE_PERCENTILE) if not baseline_pool.empty else 0
    sku_agg["category_baseline"] = sku_agg["category_baseline"].fillna(global_p75)

    # --- Deviation ---
    sku_agg["deviation"] = sku_agg["return_rate"] - sku_agg["category_baseline"]
    sku_agg["deviation_pct"] = sku_agg["deviation"] / sku_agg["category_baseline"].replace(0, 1)

    # --- Qualifying flag: at least one size with >= MIN_RECENT_SALES_PER_SIZE in last 30d ---
    sku_agg["qualifies"] = sku_agg["sku_prefix"].isin(qualifying_skus)

    # --- Channels per SKU ---
    if not df_ret.empty:
        channels_per_sku = (
            df_ret.groupby("sku_prefix")["channels"]
            .apply(lambda x: sorted(set(ch for ch_list in x for ch in ch_list)))
            .rename("channels")
        )
        sku_agg = sku_agg.merge(channels_per_sku, on="sku_prefix", how="left")
    else:
        sku_agg["channels"] = [[] for _ in range(len(sku_agg))]

    sku_agg["channels"] = sku_agg["channels"].apply(
        lambda x: x if isinstance(x, list) else []
    )

    # --- Reason analysis ---
    if not df_ret.empty:
        reason_data = (
            df_ret.groupby("sku_prefix")["reasons"]
            .apply(lambda groups: [r for reasons_list in groups for r in reasons_list])
            .rename("all_reasons")
        )
        sku_agg = sku_agg.merge(reason_data, on="sku_prefix", how="left")
    else:
        sku_agg["all_reasons"] = [[] for _ in range(len(sku_agg))]

    sku_agg["all_reasons"] = sku_agg["all_reasons"].apply(
        lambda x: x if isinstance(x, list) else []
    )

    reason_results = sku_agg["all_reasons"].apply(
        lambda reasons: _build_reason_summary(reasons)
    )
    sku_agg["top_reason"] = reason_results.apply(lambda x: x[0])
    sku_agg["top_reason_pct"] = reason_results.apply(lambda x: x[1])
    sku_agg["reason_counts"] = reason_results.apply(lambda x: x[2])
    sku_agg["has_reason_data"] = sku_agg["all_reasons"].apply(
        lambda x: any(r is not None for r in x)
    )

    # --- Reason percentages ---
    def _reason_pcts(reasons):
        total = len([r for r in reasons if r is not None])
        if total == 0:
            return 0.0, 0.0, 0.0, 0.0
        too_small = sum(1 for r in reasons if r == "TOO_SMALL")
        too_large = sum(1 for r in reasons if r == "TOO_LARGE")
        qual = sum(1 for r in reasons if r in config.QUALITY_REASONS)
        other = total - too_small - too_large - qual
        return too_small / total, too_large / total, qual / total, max(other / total, 0)

    pcts = sku_agg["all_reasons"].apply(_reason_pcts)
    sku_agg["pct_too_small"] = pcts.apply(lambda x: x[0])
    sku_agg["pct_too_large"] = pcts.apply(lambda x: x[1])
    sku_agg["pct_quality"] = pcts.apply(lambda x: x[2])
    sku_agg["pct_other_reason"] = pcts.apply(lambda x: x[3])

    # --- Size anomaly analysis ---
    size_stats = _compute_size_anomalies(df_sku_size)
    sku_agg = sku_agg.merge(size_stats, on="sku_prefix", how="left")
    sku_agg["size_concentration"] = sku_agg["size_concentration"].fillna(1.0)
    sku_agg["has_sizing_issue"] = (
        sku_agg["size_concentration"] > config.SIZE_CONCENTRATION_THRESHOLD
    )
    sku_agg["anomaly_sizes"] = sku_agg["anomaly_sizes"].apply(
        lambda x: x if isinstance(x, list) else []
    )

    # --- Problem classification ---
    sku_agg["problem_type"] = sku_agg.apply(
        lambda row: _classify_problem(
            row["top_reason"],
            row["top_reason_pct"],
            row["reason_counts"] if isinstance(row["reason_counts"], dict) else {},
            row["size_concentration"],
            row["anomaly_sizes"],
            row["has_reason_data"],
        ),
        axis=1,
    )

    # --- Trend analysis (recovering) ---
    # Only for top N SKUs by recent sales
    sku_agg = _add_trend_data(sku_agg, df_recent, df_ret_recent, df_ret_prev)

    # --- Rising star flag ---
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=config.RISING_STAR_MAX_AGE_DAYS)
    if not sku_agg["first_order"].empty and sku_agg["first_order"].notna().any():
        # Make timezone-aware if needed
        first_order_col = pd.to_datetime(sku_agg["first_order"], utc=True)
        sku_agg["is_rising_star"] = (
            first_order_col.notna()
            & (first_order_col >= cutoff_date)
            & (sku_agg["recent_sold"] > 0)
        )
    else:
        sku_agg["is_rising_star"] = False

    # Sort by return rate deviation (highest above baseline first)
    sku_agg = sku_agg.sort_values("deviation", ascending=False).reset_index(drop=True)

    # Clean up
    sku_agg = sku_agg.drop(columns=["all_reasons", "reason_counts"], errors="ignore")

    return sku_agg


def _add_trend_data(
    df_sku: pd.DataFrame,
    df_recent: pd.DataFrame,
    df_ret_recent: pd.DataFrame,
    df_ret_prev: pd.DataFrame,
) -> pd.DataFrame:
    """Add trend data for top SKUs: compare last 30d returns vs previous 30d returns."""
    if df_sku.empty:
        df_sku["returned_recent"] = 0
        df_sku["returned_prev"] = 0
        df_sku["rate_recent"] = None
        df_sku["rate_prev"] = None
        df_sku["trend"] = 0.0
        df_sku["is_recovering"] = False
        return df_sku

    # Merge recent/prev return counts
    df_sku = df_sku.merge(df_ret_recent, on="sku_prefix", how="left")
    df_sku["returned_recent"] = df_sku["returned_recent"].fillna(0).astype(int)

    df_sku = df_sku.merge(df_ret_prev, on="sku_prefix", how="left")
    df_sku["returned_prev"] = df_sku["returned_prev"].fillna(0).astype(int)

    # For trend, we need sales in each period too — approximate using recent_sold
    # for both periods (not perfect but avoids 2 more queries)
    # rate_recent = returned_recent / recent_sold
    # rate_prev = returned_prev / recent_sold (same denominator as proxy)
    df_sku["rate_recent"] = float("nan")
    df_sku["rate_prev"] = float("nan")
    df_sku["trend"] = 0.0
    df_sku["is_recovering"] = False

    # Only compute trends for top N by recent sales
    top_mask = df_sku["recent_sold"] > 0
    top_skus = df_sku.loc[top_mask].nlargest(config.TOP_SKU_FOR_TRENDS, "recent_sold").index

    mask = df_sku.index.isin(top_skus)
    if mask.any():
        recent_sold = df_sku.loc[mask, "recent_sold"].replace(0, 1).astype(float)
        rate_recent = (df_sku.loc[mask, "returned_recent"].astype(float) / recent_sold).clip(upper=1.0)
        rate_prev = (df_sku.loc[mask, "returned_prev"].astype(float) / recent_sold).clip(upper=1.0)
        df_sku.loc[mask, "rate_recent"] = rate_recent.values
        df_sku.loc[mask, "rate_prev"] = rate_prev.values
        df_sku.loc[mask, "trend"] = (rate_recent.fillna(0) - rate_prev.fillna(0)).values
        df_sku.loc[mask, "is_recovering"] = (
            (df_sku.loc[mask, "trend"] < -0.05)
            & (df_sku.loc[mask, "returned_prev"] >= 3)
        )

    return df_sku


def _compute_size_anomalies(df_sku_size: pd.DataFrame) -> pd.DataFrame:
    qualified = df_sku_size[df_sku_size["sold"] >= config.MIN_SIZE_VOLUME].copy()
    if qualified.empty:
        return pd.DataFrame(
            {"sku_prefix": pd.Series(dtype=str), "size_concentration": pd.Series(dtype=float), "anomaly_sizes": pd.Series(dtype=object)}
        )

    results = []
    for sku, group in qualified.groupby("sku_prefix"):
        rates = group["return_rate"]
        if len(rates) < 2 or rates.mean() == 0:
            results.append({"sku_prefix": sku, "size_concentration": 1.0, "anomaly_sizes": []})
            continue

        concentration = rates.max() / rates.mean()
        threshold = rates.mean() * config.SIZE_CONCENTRATION_THRESHOLD
        anomalies = group[group["return_rate"] > threshold][
            ["size", "return_rate", "sold", "returned"]
        ].to_dict("records")

        results.append({
            "sku_prefix": sku,
            "size_concentration": concentration,
            "anomaly_sizes": anomalies,
        })

    return pd.DataFrame(results)


def _compute_supplier_level(df_sku: pd.DataFrame) -> pd.DataFrame:
    if df_sku.empty or "supplier_name" not in df_sku.columns:
        return pd.DataFrame()

    valid = df_sku[df_sku["supplier_name"].notna()].copy()
    if valid.empty:
        return pd.DataFrame()

    supplier_agg = (
        valid.groupby("supplier_name")
        .agg(
            total_skus=("sku_prefix", "nunique"),
            total_sold=("total_sold", "sum"),
            total_returned=("total_returned", "sum"),
            recent_sold=("recent_sold", "sum"),
        )
        .reset_index()
    )

    supplier_agg["return_rate"] = (
        supplier_agg["total_returned"] / supplier_agg["total_sold"]
    ).clip(upper=1.0)

    # Worst category per supplier
    worst_cats = (
        valid.groupby(["supplier_name", "category_l3"])
        .agg(cat_sold=("total_sold", "sum"), cat_returned=("total_returned", "sum"))
        .reset_index()
    )
    worst_cats["cat_rate"] = (worst_cats["cat_returned"] / worst_cats["cat_sold"]).clip(upper=1.0)
    worst_cats = worst_cats.sort_values("cat_rate", ascending=False).drop_duplicates("supplier_name")
    supplier_agg = supplier_agg.merge(
        worst_cats[["supplier_name", "category_l3"]].rename(columns={"category_l3": "worst_category"}),
        on="supplier_name",
        how="left",
    )

    # Top reason per supplier
    top_reasons = (
        valid[valid["top_reason"].notna()]
        .groupby("supplier_name")["top_reason"]
        .apply(lambda x: Counter(x).most_common(1)[0][0] if len(x) > 0 else None)
        .rename("top_reason")
    )
    supplier_agg = supplier_agg.merge(top_reasons, on="supplier_name", how="left")

    # Flagged SKU count
    flagged = valid[valid["deviation"] > 0]
    flagged_counts = flagged.groupby("supplier_name")["sku_prefix"].nunique().rename("flagged_skus")
    supplier_agg = supplier_agg.merge(flagged_counts, on="supplier_name", how="left")
    supplier_agg["flagged_skus"] = supplier_agg["flagged_skus"].fillna(0).astype(int)

    supplier_agg = supplier_agg.sort_values("return_rate", ascending=False).reset_index(drop=True)

    return supplier_agg


def _compute_category_level(df_sku_size: pd.DataFrame) -> pd.DataFrame:
    if df_sku_size.empty:
        return pd.DataFrame()

    cat_data = df_sku_size[df_sku_size["category_l3"].notna()].copy()
    if cat_data.empty:
        return pd.DataFrame()

    cat_agg = (
        cat_data.groupby("category_l3")
        .agg(sold=("sold", "sum"), returned=("returned", "sum"))
        .reset_index()
    )
    cat_agg["return_rate"] = (cat_agg["returned"] / cat_agg["sold"]).clip(upper=1.0)

    global_baseline = cat_agg["return_rate"].median()
    cat_agg["baseline"] = global_baseline

    cat_agg["status"] = "AT_BASELINE"
    cat_agg.loc[cat_agg["return_rate"] < global_baseline * 0.85, "status"] = "BELOW_BASELINE"
    cat_agg.loc[cat_agg["return_rate"] > global_baseline * 1.15, "status"] = "ABOVE_BASELINE"

    cat_agg = cat_agg.sort_values("return_rate", ascending=False).reset_index(drop=True)

    return cat_agg
