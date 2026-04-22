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
    "baseline_percentile": 0.75,
    "min_recent_sales_per_size": 10,
    "new_product_min_sales_per_size": 5,
    "new_product_max_age_days": 45,
    "min_reasons_bestsellers": 20,
    "min_reasons_new_products": 10,
    # Flagging trigger
    "trigger_multiplier": 1.3,
    # Confidence thresholds
    "high_confidence_ratio": 3.0,
    "mid_confidence_ratio": 2.0,
    "quality_high_threshold": 0.40,
    "quality_mid_threshold": 0.25,
    # Relabel conditions
    "relabel_min_stock": 50,
    "relabel_min_return_rate": 0.60,
    "relabel_min_sales": 100,
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
