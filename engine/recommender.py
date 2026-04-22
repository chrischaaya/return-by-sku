"""
Predetermined recommendation engine.
Size-level and SKU-level actions based on return reason patterns + stock levels.
"""

from typing import List

# Relabel conditions: ALL must be met
RELABEL_STOCK_THRESHOLD = 50       # min stock units
RELABEL_RETURN_RATE = 0.60         # min return rate for the size
RELABEL_MIN_SALES = 100            # min sold for confidence
RELABEL_REASON_RATIO = 3.0         # min ratio of dominant reason


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

    # Not enough reason data — flag but don't diagnose
    if reason_count < min_reasons:
        return "• High return rate. Not enough return reason data to diagnose. Inspect product."

    issues = []
    sizing_total = pct_small + pct_large

    # --- Sizing axis (<2x mixed, 2-3x likely, >3x confident) ---
    if sizing_total > 0.1:
        ratio_s = pct_small / max(pct_large, 0.01) if pct_small > 0 else 0
        ratio_l = pct_large / max(pct_small, 0.01) if pct_large > 0 else 0

        # Check relabel conditions: confident + high return rate + high stock + enough sales
        can_relabel = (
            stock >= RELABEL_STOCK_THRESHOLD
            and return_rate >= RELABEL_RETURN_RATE
            and sold >= RELABEL_MIN_SALES
        )

        if ratio_s >= 3 or (pct_small > 0 and pct_large == 0):
            if can_relabel:
                issues.append(f"Runs small for this size. Relabel stock ({stock} units) + size up next batch.")
            else:
                msg = "Runs small for this size. Size up next batch."
                if stock > 50:
                    msg += f" ({stock} units in stock)"
                issues.append(msg)
        elif ratio_l >= 3 or (pct_large > 0 and pct_small == 0):
            if can_relabel:
                issues.append(f"Runs large for this size. Relabel stock ({stock} units) + size down next batch.")
            else:
                msg = "Runs large for this size. Size down next batch."
                if stock > 50:
                    msg += f" ({stock} units in stock)"
                issues.append(msg)
        elif ratio_s >= 2:
            msg = "Likely runs small for this size. Check measurements."
            if stock > 50:
                msg += f" ({stock} units in stock)"
            issues.append(msg)
        elif ratio_l >= 2:
            msg = "Likely runs large for this size. Check measurements."
            if stock > 50:
                msg += f" ({stock} units in stock)"
            issues.append(msg)
        else:
            issues.append("Mixed sizing feedback for this size.")

    # --- Quality axis ---
    if pct_quality >= 0.40:
        issues.append("Quality/fit issue — check photos match actual product.")

    # --- No clear pattern ---
    if not issues:
        issues.append("Mixed feedback. Investigate due to high return rate.")

    return "\n".join(f"• {i}" for i in issues)


def sku_summary(size_actions: List[dict]) -> str:
    """
    SKU-level summary. Generated when the majority of sizes (>50%) with reason
    data lean the same direction. Also flags quality if elevated across sizes.
    Falls back to a review prompt if no consistent pattern exists.
    """
    flagged = [s for s in size_actions if s.get("is_flagged")]
    all_sizes = size_actions  # includes non-flagged sizes too

    if not flagged:
        return ""

    if not all_sizes:
        return ""

    n = len(all_sizes)
    avg_small = sum(s.get("pct_small", 0) for s in all_sizes) / n
    avg_large = sum(s.get("pct_large", 0) for s in all_sizes) / n
    avg_quality = sum(s.get("pct_quality", 0) for s in all_sizes) / n
    total_stock = sum(s.get("stock", 0) for s in flagged)

    parts = []

    # Consistent sizing — check majority (>50%) rather than requiring ALL sizes
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

    if ratio_s >= 3 or (avg_small > 0 and avg_large == 0):
        parts.append("Runs small across all sizes. Revise measurements for next batch.")
    elif ratio_l >= 3 or (avg_large > 0 and avg_small == 0):
        parts.append("Runs large across all sizes. Revise measurements for next batch.")
    elif ratio_s >= 2 and majority_lean_small:
        parts.append("Likely runs small across most sizes. Check measurements with supplier.")
    elif ratio_l >= 2 and majority_lean_large:
        parts.append("Likely runs large across most sizes. Check measurements with supplier.")

    if avg_quality >= 0.30:
        parts.append("Quality/fit issue across sizes — check photos match actual product.")

    if parts:
        if len(parts) > 1:
            return "\n".join(f"• {p}" for p in parts)
        return parts[0]

    # No sizing pattern found — fallback
    return "Review individual sizes — no consistent pattern across product."
