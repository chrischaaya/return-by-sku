"""
AI-powered recommendation engine.
Single Opus call with all flagged SKUs for speed.
"""

import json
from typing import Optional

import streamlit as st
from anthropic import Anthropic

import config


def _get_client() -> Optional[Anthropic]:
    api_key = st.secrets.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None
    return Anthropic(api_key=api_key)


def generate_all_recommendations(df_sku, df_sku_size) -> dict:
    """
    Single Opus call with all flagged SKUs.
    Returns dict of sku_prefix -> recommendation string.
    """
    client = _get_client()
    if client is None:
        return _generate_all_fallback(df_sku, df_sku_size)

    flagged = df_sku[df_sku.get("problematic_sizes", 0) > 0] if "problematic_sizes" in df_sku.columns else df_sku.head(0)
    if flagged.empty:
        return {}

    # Build compact data for all SKUs
    skus_text = ""
    for _, row in flagged.iterrows():
        sku = row["sku_prefix"]
        sizes = df_sku_size[df_sku_size["sku_prefix"] == sku] if df_sku_size is not None else None
        problematic = sizes[sizes["is_problematic"] == True] if sizes is not None and "is_problematic" in sizes.columns else None

        if problematic is None or problematic.empty:
            continue

        size_lines = []
        for _, s in problematic.iterrows():
            size_lines.append(
                f"  {s['size']}: {s['return_rate']:.0%} return "
                f"(small:{s.get('pct_too_small',0):.0%} large:{s.get('pct_too_large',0):.0%} "
                f"quality:{s.get('pct_quality',0):.0%} other:{s.get('pct_other',0):.0%})"
            )

        skus_text += f"""
{sku} | {row.get('product_name', '')} | {row.get('category_l3', '')} | Supplier: {row.get('supplier_name', 'N/A')} | Overall: {row.get('return_rate', 0):.0%} vs P75: {row.get('category_baseline', 0):.0%}
{chr(10).join(size_lines)}
"""

    if not skus_text.strip():
        return {}

    prompt = f"""You are an operations analyst for a fashion e-commerce company. Below are products with problematic sizes (return rate above category P75).

For each SKU, write 1-2 sentences of direct, actionable recommendation. Rules:
- Analyze sizing (small vs large) SEPARATELY from quality issues
- If too_small is 3x+ too_large → clearly runs small, not "mixed"
- If too_large is 3x+ too_small → clearly runs large, not "mixed"
- A product can have BOTH sizing AND quality problems — report both
- "Quality" = defective/damaged/doesn't match listing
- "Other" = customer changed mind, ordered multiple sizes — not actionable
- Be specific: name the problematic sizes, state the issue, state the action
- No fluff. Direct operational language for a non-technical team.

Return ONLY a JSON object where keys are SKU codes and values are recommendation strings. No markdown, no explanation.

{skus_text}"""

    try:
        response = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=16000,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.content[0].text.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        return json.loads(text)
    except Exception as e:
        # Fallback if Opus fails
        return _generate_all_fallback(df_sku, df_sku_size)


def _generate_all_fallback(df_sku, df_sku_size) -> dict:
    """Rule-based fallback when no API key is available."""
    flagged = df_sku[df_sku.get("problematic_sizes", 0) > 0] if "problematic_sizes" in df_sku.columns else df_sku.head(0)
    results = {}
    for _, row in flagged.iterrows():
        sku = row["sku_prefix"]
        sizes = df_sku_size[df_sku_size["sku_prefix"] == sku].to_dict("records") if df_sku_size is not None else []
        results[sku] = _fallback_recommendation(sizes)
    return results


def _fallback_recommendation(size_data: list) -> str:
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
