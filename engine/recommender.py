"""
Predetermined recommendation engine.
Size-level and SKU-level actions based on return reason patterns + stock levels.
All thresholds read from config (configurable via Settings).
"""

from typing import List

import config


def size_action(
    return_rate: float,
    p75: float,
    pct_small: float,
    pct_large: float,
    pct_quality: float,
    pct_other: float,
    is_flagged: bool,
    stock: int = 0,
    sold: int = 0,
    reason_count: int = 0,
    min_reasons: int = 10,
) -> str:
    if not is_flagged:
        return ""

    if reason_count < min_reasons:
        return "• High return rate. Not enough data to diagnose. Inspect product."

    issues = []
    sizing_total = pct_small + pct_large
    hi = config.HIGH_CONFIDENCE_RATIO
    mid = config.MID_CONFIDENCE_RATIO

    # --- Sizing axis ---
    if sizing_total > 0.1:
        ratio_s = pct_small / max(pct_large, 0.01) if pct_small > 0 else 0
        ratio_l = pct_large / max(pct_small, 0.01) if pct_large > 0 else 0

        can_relabel = (
            stock >= config.RELABEL_MIN_STOCK
            and return_rate >= config.RELABEL_MIN_RETURN_RATE
            and sold >= config.RELABEL_MIN_SALES
        )

        if ratio_s >= hi or (pct_small > 0 and pct_large == 0):
            msg = "Too small (high confidence)"
            if can_relabel:
                msg += ". Relabel existing stock."
            issues.append(msg)
        elif ratio_l >= hi or (pct_large > 0 and pct_small == 0):
            msg = "Too large (high confidence)"
            if can_relabel:
                msg += ". Relabel existing stock."
            issues.append(msg)
        elif ratio_s >= mid:
            issues.append("Too small (mid confidence)")
        elif ratio_l >= mid:
            issues.append("Too large (mid confidence)")
        elif pct_small >= 0.10 or pct_large >= 0.10:
            issues.append(f"Mixed results ({pct_small:.0%} small, {pct_large:.0%} large). Inspect product.")

    # --- Quality axis ---
    if pct_quality >= config.QUALITY_HIGH_THRESHOLD:
        issues.append("Quality issue (high confidence). Inspect product.")
    elif pct_quality >= config.QUALITY_MID_THRESHOLD:
        issues.append("Quality issue (mid confidence). Inspect product.")

    # --- No clear pattern ---
    if not issues:
        issues.append("No clear pattern. Inspect product.")

    return "\n".join(f"• {i}" for i in issues)


def sku_summary(size_actions: List[dict]) -> str:
    flagged = [s for s in size_actions if s.get("is_flagged")]
    all_sizes = size_actions

    if not flagged or not all_sizes:
        return ""

    n = len(all_sizes)
    avg_small = sum(s.get("pct_small", 0) for s in all_sizes) / n
    avg_large = sum(s.get("pct_large", 0) for s in all_sizes) / n
    avg_quality = sum(s.get("pct_quality", 0) for s in all_sizes) / n

    hi = config.HIGH_CONFIDENCE_RATIO
    mid = config.MID_CONFIDENCE_RATIO

    parts = []

    ratio_s = avg_small / max(avg_large, 0.01) if avg_small > 0 else 0
    ratio_l = avg_large / max(avg_small, 0.01) if avg_large > 0 else 0

    sizes_with_sizing = [
        s for s in all_sizes
        if (s.get("pct_small", 0) + s.get("pct_large", 0)) > 0.1
    ]
    n_sizing = len(sizes_with_sizing)

    if n_sizing > 0:
        lean_small_count = sum(
            1 for s in sizes_with_sizing
            if s.get("pct_small", 0) / max(s.get("pct_large", 0), 0.01) >= 1.5
        )
        lean_large_count = sum(
            1 for s in sizes_with_sizing
            if s.get("pct_large", 0) / max(s.get("pct_small", 0), 0.01) >= 1.5
        )
        majority_lean_small = lean_small_count > n_sizing * 0.5
        majority_lean_large = lean_large_count > n_sizing * 0.5
    else:
        majority_lean_small = False
        majority_lean_large = False

    if ratio_s >= hi or (avg_small > 0 and avg_large == 0):
        parts.append("Too small across product (high confidence)")
    elif ratio_l >= hi or (avg_large > 0 and avg_small == 0):
        parts.append("Too large across product (high confidence)")
    elif ratio_s >= mid and majority_lean_small:
        parts.append("Too small across product (mid confidence)")
    elif ratio_l >= mid and majority_lean_large:
        parts.append("Too large across product (mid confidence)")

    if avg_quality >= 0.30:
        parts.append("Quality issue across product. Inspect product.")

    if parts:
        if len(parts) > 1:
            return "\n".join(f"• {p}" for p in parts)
        return parts[0]

    return "Review individual sizes — no consistent pattern across product."
