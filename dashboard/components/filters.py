"""
Shared filter controls for the dashboard sidebar.
"""

import streamlit as st

import config


def render_sidebar_filters() -> dict:
    """Render sidebar filters and return selected values."""
    st.sidebar.header("Filters")

    # Channel filter
    all_channels = [
        ch for ch in [
            "trendyol", "trendyolRO", "fashiondays", "fashiondaysBG",
            "emag", "emagBG", "emagHU", "hepsiburada", "hiccup",
            "debenhams", "namshi", "tiktokShop", "amazonUS", "amazonUK",
            "allegro", "ananas", "shein", "noon", "walmart",
        ]
        if ch not in config.EXCLUDED_CHANNELS
    ]

    selected_channels = st.sidebar.multiselect(
        "Channels (leave empty for all)",
        options=all_channels,
        default=[],
    )

    selected_category = st.sidebar.text_input(
        "Category filter (e.g. 'dresses')",
        value="",
        help="Filter by category level 3. Leave empty for all.",
    )

    return {
        "channels": selected_channels if selected_channels else None,
        "category": selected_category.strip() if selected_category.strip() else None,
    }


def render_update_button() -> bool:
    """Render the Update Data button. Returns True if clicked."""
    st.sidebar.markdown("---")
    return st.sidebar.button("Update Data", use_container_width=True)
