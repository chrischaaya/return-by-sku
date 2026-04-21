"""
AI-powered recommendation engine.
Sends each SKU's size-level data to Claude Haiku for analysis.
"""

import concurrent.futures
from typing import Optional

import streamlit as st
from anthropic import Anthropic

import config


def _get_client() -> Optional[Anthropic]:
    api_key = st.secrets.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None
    return Anthropic(api_key=api_key)


def _build_sku_prompt(row: dict, size_data: list) -> str:
    """Build a compact prompt with all the SKU's data."""
    size_table = "Size | Sold | Return Rate | % Too Small | % Too Large | % Quality | % Other | Flagged\n"
    size_table += "---|---|---|---|---|---|---|---\n"
    for s in size_data:
        size_table += (
            f"{s['size']} | {s['sold']} | {s['return_rate']:.1%} | "
            f"{s.get('pct_too_small', 0):.0%} | {s.get('pct_too_large', 0):.0%} | "
            f"{s.get('pct_quality', 0):.0%} | {s.get('pct_other', 0):.0%} | "
            f"{'YES' if s.get('is_problematic') else ''}\n"
        )

    return f"""You are an operations analyst for a fashion e-commerce company. Analyze this SKU's return data and give a specific, actionable recommendation.

**Product:** {row.get('product_name', 'Unknown')}
**SKU:** {row.get('sku_prefix', '')}
**Category:** {row.get('category_l3', 'N/A')} / {row.get('category_l4', 'N/A')}
**Supplier:** {row.get('supplier_name', 'N/A')}
**Category P75 return rate:** {row.get('category_baseline', 0):.1%}
**Overall return rate:** {row.get('return_rate', 0):.1%}
**All-time sold:** {row.get('total_sold', 0):,}

**Size breakdown:**
{size_table}

Return reason definitions:
- Too Small / Too Large = customer says the product doesn't fit (sizing issue)
- Quality = product is defective, damaged, or doesn't match listing photos/description
- Other = no longer wanted, ordered multiple sizes, delivery issues, etc.

Rules:
- Only flag sizes marked "YES" in the Flagged column
- Analyze sizing (small vs large) separately from quality issues
- If too_small dominates too_large (3x+ ratio), it clearly runs small — don't call it mixed
- Same logic for too_large dominating too_small
- A product can have BOTH a sizing issue AND a quality issue — report both
- Be specific about which sizes are problematic and why
- Keep it to 2-3 sentences max. No fluff, no hedging. Direct operational language.
- If there's not enough return reason data, say so"""


def generate_ai_recommendation(row: dict, size_data: list) -> str:
    """Generate a recommendation for one SKU using Claude Haiku."""
    client = _get_client()
    if client is None:
        return _fallback_recommendation(row, size_data)

    prompt = _build_sku_prompt(row, size_data)

    try:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text.strip()
    except Exception as e:
        return _fallback_recommendation(row, size_data)


def generate_all_recommendations(df_sku, df_sku_size) -> dict:
    """
    Generate AI recommendations for all flagged SKUs in parallel.
    Returns dict of sku_prefix -> recommendation string.
    """
    client = _get_client()
    if client is None:
        return {}

    flagged = df_sku[df_sku.get("problematic_sizes", 0) > 0] if "problematic_sizes" in df_sku.columns else df_sku.head(0)
    if flagged.empty:
        return {}

    tasks = []
    for _, row in flagged.iterrows():
        sku = row["sku_prefix"]
        sizes = df_sku_size[df_sku_size["sku_prefix"] == sku].to_dict("records") if df_sku_size is not None else []
        tasks.append((sku, row.to_dict(), sizes))

    results = {}

    # Process in parallel, max 10 at a time
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        future_map = {
            executor.submit(generate_ai_recommendation, row_dict, sizes): sku
            for sku, row_dict, sizes in tasks
        }
        for future in concurrent.futures.as_completed(future_map):
            sku = future_map[future]
            try:
                results[sku] = future.result()
            except Exception:
                results[sku] = ""

    return results


def _fallback_recommendation(row: dict, size_data: list) -> str:
    """Simple rule-based fallback when API key is not available."""
    flagged_sizes = [s for s in size_data if s.get("is_problematic")]
    if not flagged_sizes:
        return ""

    issues = []
    for s in flagged_sizes:
        ps = s.get("pct_too_small", 0)
        pl = s.get("pct_too_large", 0)
        pq = s.get("pct_quality", 0)

        if ps > 0 and (pl == 0 or ps / max(pl, 0.01) >= 3):
            issues.append(f"{s['size']}: runs small ({ps:.0%})")
        elif pl > 0 and (ps == 0 or pl / max(ps, 0.01) >= 3):
            issues.append(f"{s['size']}: runs large ({pl:.0%})")
        elif ps >= 0.15 and pl >= 0.15:
            issues.append(f"{s['size']}: inconsistent sizing")
        if pq >= 0.25:
            issues.append(f"{s['size']}: quality issue ({pq:.0%})")

    return "; ".join(issues) if issues else "Above P75. Investigate."
