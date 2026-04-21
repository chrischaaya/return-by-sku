"""
Recommendation engine.
Translates analysis results into plain-English actions.
Every flagged item gets a recommendation — never just "investigate".
"""

from typing import Dict, List, Optional

import config


def generate_sku_recommendation(row: dict) -> str:
    """Generate a recommendation for a single SKU row from df_sku."""
    rate = row.get("return_rate", 0)
    baseline = row.get("category_baseline", 0)
    problem = row.get("problem_type", "UNKNOWN")
    top_reason = row.get("top_reason")
    reason_pct = row.get("top_reason_pct", 0)
    supplier = row.get("supplier_name", "Unknown")
    anomaly_sizes = row.get("anomaly_sizes", [])
    has_reasons = row.get("has_reason_data", False)

    rate_pct = f"{rate:.0%}"
    baseline_pct = f"{baseline:.0%}"
    anomaly_size_names = [s["size"] for s in anomaly_sizes] if anomaly_sizes else []

    # --- Sizing: runs small ---
    if problem == "SIZING" and _is_small_size_issue(anomaly_sizes, top_reason):
        sizes_str = ", ".join(anomaly_size_names) if anomaly_size_names else "smaller sizes"
        return (
            f"Sizing issue — product likely runs small. "
            f"Return rate is {rate_pct} vs category avg {baseline_pct}. "
            f"Sizes {sizes_str} have significantly higher returns. "
            f"Action: review the spec sheet and actual measurements for this SKU. "
            f"Consider adding 'runs small — order one size up' to the listing, "
            f"or adjust measurements with supplier {supplier} for next production."
        )

    # --- Sizing: runs large ---
    if problem == "SIZING" and _is_large_size_issue(anomaly_sizes, top_reason):
        sizes_str = ", ".join(anomaly_size_names) if anomaly_size_names else "larger sizes"
        return (
            f"Sizing issue — product likely runs large. "
            f"Return rate is {rate_pct} vs category avg {baseline_pct}. "
            f"Sizes {sizes_str} have significantly higher returns. "
            f"Action: review the spec sheet. Consider adding 'runs large — order one size down' "
            f"to the listing, or tighten measurements with supplier {supplier}."
        )

    # --- Sizing: general ---
    if problem == "SIZING":
        sizes_str = ", ".join(anomaly_size_names) if anomaly_size_names else "multiple sizes"
        return (
            f"Sizing inconsistency detected. Return rate is {rate_pct} vs category avg {baseline_pct}. "
            f"Return rates vary significantly across sizes ({sizes_str} are worst). "
            f"Action: check measurement consistency across the full size range with supplier {supplier}. "
            f"The size grading (increments between sizes) may be off."
        )

    # --- Quality ---
    if problem == "QUALITY":
        return (
            f"Quality issue suspected. Return rate is {rate_pct} vs category avg {baseline_pct}. "
            f"{_reason_detail(top_reason, reason_pct)} "
            f"Action: pull a sample from current stock and inspect for defects. "
            f"If confirmed, raise with supplier {supplier} immediately. "
            f"Consider holding remaining stock until quality is verified."
        )

    # --- Listing mismatch ---
    if problem == "LISTING":
        return (
            f"Listing mismatch suspected. Return rate is {rate_pct} vs category avg {baseline_pct}. "
            f"{_reason_detail(top_reason, reason_pct)} "
            f"Action: compare product listing photos against the actual product. "
            f"Check: does the color look accurate? Do photos show the true fit and fabric? "
            f"Is the description accurate about material, thickness, and stretch? Update where needed."
        )

    # --- No reason data available ---
    if not has_reasons:
        return (
            f"Return rate is {rate_pct} vs category avg {baseline_pct}. "
            f"No return reason data available for this channel. "
            f"Action: review the product page and any customer feedback. "
            f"Check sizing chart accuracy and photo quality."
        )

    # --- Fallback: high returns, no clear cause ---
    return (
        f"Return rate is {rate_pct} vs category avg {baseline_pct}. "
        f"No single dominant cause identified. "
        f"{_reason_detail(top_reason, reason_pct) if has_reasons else ''} "
        f"Action: manual review needed. Check: (1) customer reviews for specific complaints, "
        f"(2) whether product is priced right for its quality, "
        f"(3) whether this product is promoted on channels where fit expectations differ."
    )


def generate_supplier_recommendation(row: dict) -> str:
    """Generate a recommendation for a supplier row from df_supplier."""
    rate = row.get("return_rate", 0)
    total_skus = row.get("total_skus", 0)
    flagged = row.get("flagged_skus", 0)
    worst_cat = row.get("worst_category", "unknown")
    name = row.get("supplier_name", "Unknown")
    top_reason = row.get("top_reason")

    rate_pct = f"{rate:.0%}"

    if flagged == 0:
        return f"No flagged SKUs. Overall return rate {rate_pct}. No action needed."

    if flagged >= 3 and top_reason in config.SIZING_REASONS:
        return (
            f"{flagged} of {total_skus} SKUs flagged. Overall return rate {rate_pct}. "
            f"Worst category: {worst_cat}. Primary issue: sizing. "
            f"Action: schedule a supplier review — sizing standards need audit across "
            f"multiple products. Request a measurement check for all active SKUs."
        )

    if flagged >= 3 and top_reason in config.QUALITY_REASONS:
        return (
            f"{flagged} of {total_skus} SKUs flagged. Overall return rate {rate_pct}. "
            f"Worst category: {worst_cat}. Primary issue: product defects. "
            f"Action: raise quality concern with {name}. Request factory inspection "
            f"or tighter QC process. Consider holding new orders until resolved."
        )

    if flagged >= 3:
        return (
            f"{flagged} of {total_skus} SKUs flagged. Overall return rate {rate_pct}. "
            f"Worst category: {worst_cat}. "
            f"Action: schedule a supplier review meeting with {name}. "
            f"Bring the SKU-level breakdown and request a corrective action plan."
        )

    return (
        f"{flagged} of {total_skus} SKUs above threshold. Return rate {rate_pct}. "
        f"Worst category: {worst_cat}. Monitor — not yet a systemic pattern."
    )


def _is_small_size_issue(anomaly_sizes: List[dict], top_reason: Optional[str]) -> bool:
    small_sizes = {"XXS", "XS", "S", "S/M"}
    if top_reason == "TOO_SMALL":
        return True
    if anomaly_sizes:
        anomaly_names = {s["size"] for s in anomaly_sizes}
        return bool(anomaly_names & small_sizes)
    return False


def _is_large_size_issue(anomaly_sizes: List[dict], top_reason: Optional[str]) -> bool:
    large_sizes = {"XL", "XXL", "2XL", "3XL", "4XL", "5XL"}
    if top_reason == "TOO_LARGE":
        return True
    if anomaly_sizes:
        anomaly_names = {s["size"] for s in anomaly_sizes}
        return bool(anomaly_names & large_sizes)
    return False


def _reason_detail(top_reason: Optional[str], reason_pct: float) -> str:
    if not top_reason:
        return ""
    reason_labels = {
        "TOO_SMALL": "Too small",
        "TOO_LARGE": "Too large",
        "EXPECTATION_MISMATCH": "Doesn't match expectations",
        "DEFECTIVE_PRODUCT": "Product defective/damaged",
        "NO_LONGER_WANTED": "No longer wanted",
        "WRONG_PRODUCT": "Wrong product received",
        "NOT_DELIVERED": "Not delivered",
        "DELIVERY_ISSUE": "Delivery issue",
        "SURPLUS_PRODUCT": "Ordered multiple sizes",
        "OTHER": "Other",
    }
    label = reason_labels.get(top_reason, top_reason)
    return f"Top return reason: \"{label}\" ({reason_pct:.0%} of returns). "
