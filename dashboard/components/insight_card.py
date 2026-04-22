"""
Reusable insight card component.
Displays: problem statement, diagnosis, recommended action.
"""

from typing import Optional

import streamlit as st


def render_insight_card(
    title: str,
    return_rate: float,
    baseline: float,
    problem_type: str,
    recommendation: str,
    trend_direction: Optional[str] = None,
    extra_info: Optional[dict] = None,
):
    """Render a single SKU insight card."""
    # Color based on severity
    if return_rate > baseline * 1.5:
        border_color = "#e74c3c"  # red
        severity_label = "HIGH"
    elif return_rate > baseline * 1.2:
        border_color = "#f39c12"  # orange
        severity_label = "MODERATE"
    else:
        border_color = "#3498db"  # blue
        severity_label = "LOW"

    # Trend indicator
    trend_icon = ""
    if trend_direction == "IMPROVING":
        trend_icon = " ↓ improving"
    elif trend_direction == "WORSENING":
        trend_icon = " ↑ worsening"

    # Problem type badge
    type_labels = {
        "SIZING": "Sizing Issue",
        "QUALITY": "Quality Issue",
        "LISTING": "Listing Mismatch",
        "MIXED": "Multiple Causes",
        "UNKNOWN": "Needs Investigation",
    }
    type_label = type_labels.get(problem_type, problem_type)

    with st.container(border=True):
        cols = st.columns([3, 1, 1])
        with cols[0]:
            st.markdown(f"**{title}**")
        with cols[1]:
            st.markdown(f"`{type_label}`")
        with cols[2]:
            st.markdown(f"**{severity_label}**{trend_icon}")

        metric_cols = st.columns(3)
        with metric_cols[0]:
            st.metric("Return Rate", f"{return_rate:.1%}", f"{return_rate - baseline:+.1%} vs avg")
        with metric_cols[1]:
            st.metric("Category Avg", f"{baseline:.1%}")
        with metric_cols[2]:
            if extra_info and "total_sold" in extra_info:
                st.metric("Units Sold", f"{extra_info['total_sold']:,}")

        if extra_info and extra_info.get("supplier_name"):
            st.caption(f"Supplier: {extra_info['supplier_name']}")

        st.info(recommendation)


def render_winner_card(
    title: str,
    current_rate: float,
    prev_rate: float,
    baseline: float,
    recommendation: str,
):
    """Render a card for an improving SKU."""
    improvement = prev_rate - current_rate

    with st.container(border=True):
        cols = st.columns([3, 1])
        with cols[0]:
            st.markdown(f"**{title}**")
        with cols[1]:
            st.markdown("**IMPROVING** ↓")

        metric_cols = st.columns(3)
        with metric_cols[0]:
            st.metric("Current Rate", f"{current_rate:.1%}", f"-{improvement:.1%}", delta_color="inverse")
        with metric_cols[1]:
            st.metric("Previous Rate", f"{prev_rate:.1%}")
        with metric_cols[2]:
            st.metric("Category Avg", f"{baseline:.1%}")

        st.success(recommendation)
