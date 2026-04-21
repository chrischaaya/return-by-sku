"""
AI-powered recommendation engine.
Two-stage: Haiku drafts recommendations, Opus reviews and refines them in batch.
"""

import concurrent.futures
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


def _haiku_recommend(client: Anthropic, row: dict, size_data: list) -> str:
    """Stage 1: Haiku drafts a recommendation."""
    prompt = _build_sku_prompt(row, size_data)
    try:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=250,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text.strip()
    except Exception:
        return ""


def _opus_review(client: Anthropic, batch: list) -> dict:
    """
    Stage 2: Opus reviews a batch of Haiku recommendations.
    Takes a list of {sku, product_name, haiku_rec, data_summary} dicts.
    Returns dict of sku -> refined recommendation.
    """
    if not batch:
        return {}

    items_text = ""
    for item in batch:
        items_text += f"""
---
SKU: {item['sku']}
Product: {item['product_name']}
Data: {item['data_summary']}
Haiku draft: {item['haiku_rec']}
"""

    prompt = f"""You are a senior operations director reviewing AI-generated product return recommendations for a fashion e-commerce team. The team is non-technical — recommendations must be clear, specific, and actionable.

Review each recommendation below. For each SKU:
1. Check if the recommendation is accurate given the data
2. Fix any logical errors (e.g. calling something "mixed" when one direction clearly dominates)
3. Ensure the language is direct and tells the team exactly what to do
4. Keep each recommendation to 2-3 sentences max
5. If the draft is good, keep it as-is — don't change for the sake of changing

Return your response as a JSON object where keys are SKU codes and values are the final recommendation strings. Only output the JSON, nothing else.

{items_text}"""

    try:
        response = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.content[0].text.strip()
        # Extract JSON from response
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        return json.loads(text)
    except Exception:
        # If Opus fails, return Haiku drafts as-is
        return {item["sku"]: item["haiku_rec"] for item in batch}


def generate_all_recommendations(df_sku, df_sku_size) -> dict:
    """
    Two-stage recommendation generation:
    1. Haiku drafts recommendations for each SKU (parallel, fast)
    2. Opus reviews and refines them in batches (quality check)
    """
    client = _get_client()
    if client is None:
        # No API key — use fallback
        return _generate_all_fallback(df_sku, df_sku_size)

    flagged = df_sku[df_sku.get("problematic_sizes", 0) > 0] if "problematic_sizes" in df_sku.columns else df_sku.head(0)
    if flagged.empty:
        return {}

    # Prepare tasks
    tasks = []
    for _, row in flagged.iterrows():
        sku = row["sku_prefix"]
        sizes = df_sku_size[df_sku_size["sku_prefix"] == sku].to_dict("records") if df_sku_size is not None else []
        tasks.append((sku, row.to_dict(), sizes))

    # Stage 1: Haiku drafts (parallel)
    haiku_results = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        future_map = {
            executor.submit(_haiku_recommend, client, row_dict, sizes): sku
            for sku, row_dict, sizes in tasks
        }
        for future in concurrent.futures.as_completed(future_map):
            sku = future_map[future]
            try:
                haiku_results[sku] = future.result()
            except Exception:
                haiku_results[sku] = ""

    # Stage 2: Opus review (in batches of 15)
    batch_items = []
    for sku, row_dict, sizes in tasks:
        haiku_rec = haiku_results.get(sku, "")
        if not haiku_rec:
            continue

        # Compact data summary for Opus
        flagged_sizes = [s for s in sizes if s.get("is_problematic")]
        summary_parts = []
        for s in flagged_sizes:
            summary_parts.append(
                f"{s['size']}: {s['return_rate']:.0%} return "
                f"(small:{s.get('pct_too_small',0):.0%} large:{s.get('pct_too_large',0):.0%} "
                f"quality:{s.get('pct_quality',0):.0%} other:{s.get('pct_other',0):.0%})"
            )

        batch_items.append({
            "sku": sku,
            "product_name": row_dict.get("product_name", ""),
            "haiku_rec": haiku_rec,
            "data_summary": f"Return rate {row_dict.get('return_rate',0):.0%} vs P75 {row_dict.get('category_baseline',0):.0%}. "
                           f"Flagged sizes: {'; '.join(summary_parts) if summary_parts else 'none'}",
        })

    # Process Opus in batches
    BATCH_SIZE = 15
    final_results = {}
    for i in range(0, len(batch_items), BATCH_SIZE):
        batch = batch_items[i:i + BATCH_SIZE]
        reviewed = _opus_review(client, batch)
        final_results.update(reviewed)

    # Fill in any SKUs that Opus didn't return (keep Haiku draft)
    for sku in haiku_results:
        if sku not in final_results:
            final_results[sku] = haiku_results[sku]

    return final_results


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
    """Simple rule-based fallback."""
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
