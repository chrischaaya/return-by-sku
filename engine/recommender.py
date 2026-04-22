"""
Predetermined recommendation engine.
Size-level and SKU-level actions based on return reason patterns + stock levels.
"""

from typing import List

# Stock threshold: if parkpalet stock > this, suggest relabelling
RELABEL_STOCK_THRESHOLD = 50


def size_action(
    return_rate: float,
    p75: float,
    pct_small: float,
    pct_large: float,
    pct_quality: float,
    pct_other: float,
    is_flagged: bool,
    stock: int = 0,
) -> str:
    if not is_flagged:
        return ""

    issues = []
    sizing_total = pct_small + pct_large

    # --- Sizing axis (<2x mixed, 2-3x likely, >3x confident) ---
    if sizing_total > 0.1:
        ratio_s = pct_small / max(pct_large, 0.01) if pct_small > 0 else 0
        ratio_l = pct_large / max(pct_small, 0.01) if pct_large > 0 else 0

        if ratio_s >= 3 or (pct_small > 0 and pct_large == 0):
            if stock >= RELABEL_STOCK_THRESHOLD:
                issues.append(f"Runs small. Relabel stock ({stock} units) + size up next batch.")
            else:
                issues.append("Runs small. Size up next batch.")
        elif ratio_l >= 3 or (pct_large > 0 and pct_small == 0):
            if stock >= RELABEL_STOCK_THRESHOLD:
                issues.append(f"Runs large. Relabel stock ({stock} units) + size down next batch.")
            else:
                issues.append("Runs large. Size down next batch.")
        elif ratio_s >= 2:
            issues.append("Likely runs small. Check measurements.")
        elif ratio_l >= 2:
            issues.append("Likely runs large. Check measurements.")
        else:
            issues.append("Mixed sizing feedback.")

    # --- Quality axis ---
    if pct_quality >= 0.40:
        issues.append("Quality issue. Review photos/description + inspect stock.")
    elif pct_quality >= 0.25:
        issues.append("Quality concerns. Check listing accuracy.")

    # --- Other axis ---
    if pct_other >= 0.40 and sizing_total < 0.20:
        issues.append("High non-sizing returns. Check customer reviews.")

    if issues:
        return "\n".join(f"• {i}" for i in issues)
    return f"Above P75 ({p75:.0%}). Investigate."


def sku_summary(size_actions: List[dict]) -> str:
    flagged = [s for s in size_actions if s.get("is_flagged")]
    if not flagged:
        return ""

    n = len(flagged)
    avg_small = sum(s.get("pct_small", 0) for s in flagged) / n
    avg_large = sum(s.get("pct_large", 0) for s in flagged) / n
    avg_quality = sum(s.get("pct_quality", 0) for s in flagged) / n
    total_stock = sum(s.get("stock", 0) for s in flagged)

    parts = []

    # Grading issue: small sizes say "too large", large sizes say "too small"
    small_group = [s for s in flagged if s.get("size", "").upper() in {"XXS", "XS", "S"}]
    large_group = [s for s in flagged if s.get("size", "").upper() in {"XL", "XXL", "2XL", "3XL"}]
    if small_group and large_group:
        small_says_large = sum(s.get("pct_large", 0) for s in small_group) / len(small_group)
        large_says_small = sum(s.get("pct_small", 0) for s in large_group) / len(large_group)
        if small_says_large > 0.25 and large_says_small > 0.25:
            parts.append("Grading issue — size increments are off. Audit full size range with supplier.")

    # Consistent sizing (<2x mixed, 2-3x likely, >3x confident)
    if not parts:
        ratio_s = avg_small / max(avg_large, 0.01) if avg_small > 0 else 0
        ratio_l = avg_large / max(avg_small, 0.01) if avg_large > 0 else 0

        if ratio_s >= 3 or (avg_small > 0 and avg_large == 0):
            if total_stock >= RELABEL_STOCK_THRESHOLD:
                parts.append(f"Runs small across all sizes. Relabel parkpalet stock ({total_stock} units) + revise measurements.")
            else:
                parts.append("Runs small across all sizes. Revise measurements for next batch.")
        elif ratio_l >= 3 or (avg_large > 0 and avg_small == 0):
            if total_stock >= RELABEL_STOCK_THRESHOLD:
                parts.append(f"Runs large across all sizes. Relabel parkpalet stock ({total_stock} units) + revise measurements.")
            else:
                parts.append("Runs large across all sizes. Revise measurements for next batch.")
        elif ratio_s >= 2:
            parts.append("Likely runs small across sizes. Check measurements with supplier.")
        elif ratio_l >= 2:
            parts.append("Likely runs large across sizes. Check measurements with supplier.")

    if avg_quality >= 0.30:
        parts.append("Systematic quality issue. Inspect stock + escalate to supplier.")

    if len(parts) > 1:
        return "\n".join(f"• {p}" for p in parts)
    return parts[0] if parts else ""
