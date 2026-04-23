"""
Predetermined recommendation engine.
Size-level and SKU-level actions based on return reason patterns.
Thresholds: sizing ratio >=2x, quality >=25%.
"""

from typing import List


SIZING_RATIO = 2.0
QUALITY_THRESHOLD = 0.25


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
) -> str:
    if not is_flagged:
        return ""

    issues = []
    sizing_total = pct_small + pct_large

    # --- Sizing axis: one direction >=2x the other ---
    if sizing_total >= 0.25:
        ratio_s = pct_small / max(pct_large, 0.01) if pct_small > 0 else 0
        ratio_l = pct_large / max(pct_small, 0.01) if pct_large > 0 else 0

        if ratio_s >= SIZING_RATIO or (pct_small > 0 and pct_large == 0):
            issues.append("Too small")
        elif ratio_l >= SIZING_RATIO or (pct_large > 0 and pct_small == 0):
            issues.append("Too large")
        else:
            issues.append(f"Mixed results ({pct_small:.0%} small, {pct_large:.0%} large). Inspect product.")

    # --- Quality axis: >=25% ---
    if pct_quality >= QUALITY_THRESHOLD:
        issues.append("Quality issue. Inspect product.")

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

    parts = []

    ratio_s = avg_small / max(avg_large, 0.01) if avg_small > 0 else 0
    ratio_l = avg_large / max(avg_small, 0.01) if avg_large > 0 else 0

    # Majority lean check
    sizes_with_sizing = [
        s for s in all_sizes
        if (s.get("pct_small", 0) + s.get("pct_large", 0)) > 0.1
    ]
    n_sizing = len(sizes_with_sizing)

    if n_sizing > 0:
        lean_small = sum(1 for s in sizes_with_sizing if s.get("pct_small", 0) / max(s.get("pct_large", 0), 0.01) >= 1.5) > n_sizing * 0.5
        lean_large = sum(1 for s in sizes_with_sizing if s.get("pct_large", 0) / max(s.get("pct_small", 0), 0.01) >= 1.5) > n_sizing * 0.5
    else:
        lean_small = lean_large = False

    if ratio_s >= SIZING_RATIO or (avg_small > 0 and avg_large == 0):
        parts.append("Too small across product")
    elif ratio_l >= SIZING_RATIO or (avg_large > 0 and avg_small == 0):
        parts.append("Too large across product")
    elif ratio_s >= 1.5 and lean_small:
        parts.append("Likely too small across product")
    elif ratio_l >= 1.5 and lean_large:
        parts.append("Likely too large across product")

    if avg_quality >= QUALITY_THRESHOLD:
        parts.append("Quality issue across product. Inspect product.")

    if parts:
        if len(parts) > 1:
            return "\n".join(f"• {p}" for p in parts)
        return parts[0]

    return "Review individual sizes — no consistent pattern across product."
