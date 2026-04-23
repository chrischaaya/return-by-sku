"""
Persistent settings stored in MongoDB (hiccup-tools.Settings).
Loaded on app start, saved on user change.
"""

from datetime import datetime, timezone

import streamlit as st
from pymongo import MongoClient

WRITE_URI = (
    "mongodb+srv://claude-hiccup-tools:LU6nLczES8GXzd5W"
    "@hiccup-prod.clqls.mongodb.net/hiccup-tools"
)

_write_client = None

DEFAULTS = {
    # What gets flagged
    "filter_threshold": 0.0,
    "problematic_threshold": 1.3,
    "min_recent_sales_per_size": 10,
    "new_product_min_sales_per_size": 5,
    "new_product_max_age_days": 45,
    # Data filters
    "fast_delivery_lag_days": 7,
    "slow_delivery_lag_days": 14,
    "excluded_channels": ["aboutYou", "vogaCloset"],
}


def _get_db():
    global _write_client
    if _write_client is None:
        uri = st.secrets.get("MONGO_WRITE_URI", WRITE_URI)
        _write_client = MongoClient(uri, serverSelectionTimeoutMS=10000)
    return _write_client["hiccup-tools"]


def load_settings() -> dict:
    """Load settings from MongoDB, falling back to defaults."""
    try:
        doc = _get_db()["Settings"].find_one({"_id": "app_settings"})
        if doc:
            result = {}
            for key, default in DEFAULTS.items():
                result[key] = doc.get(key, default)
            return result
    except Exception:
        pass
    return DEFAULTS.copy()


def save_settings(settings: dict):
    """Save settings to MongoDB."""
    doc = {"_id": "app_settings", "updatedOn": datetime.now(timezone.utc)}
    doc.update(settings)
    _get_db()["Settings"].replace_one({"_id": "app_settings"}, doc, upsert=True)
