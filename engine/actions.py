"""
SKU action tracking: persist actions taken on flagged SKUs.
Persisted in MongoDB (hiccup-tools.SkuActions).
"""

from datetime import datetime, timezone
from typing import Optional

import streamlit as st

# Write connection
WRITE_URI = (
    "mongodb+srv://claude-hiccup-tools:LU6nLczES8GXzd5W"
    "@hiccup-prod.clqls.mongodb.net/hiccup-tools"
)

_write_client = None


def _get_write_db():
    global _write_client
    if _write_client is None:
        from pymongo import MongoClient
        # Try secrets first, fallback to hardcoded
        uri = st.secrets.get("MONGO_WRITE_URI", WRITE_URI)
        _write_client = MongoClient(uri, serverSelectionTimeoutMS=10000)
    return _write_client["hiccup-tools"]


def _coll():
    return _get_write_db()["SkuActions"]


# --- Write operations ---

def save_action(sku_prefix: str, action_summary: str, overall_rate: float):
    """Save a new action. Pushes to actions array (keeps full history)."""
    now = datetime.now(timezone.utc)
    action_entry = {
        "summary": action_summary,
        "date": now,
        "overallRate": overall_rate,
    }
    try:
        _coll().update_one(
            {"skuPrefix": sku_prefix},
            {
                "$set": {
                    "status": "tracking",
                    "actionSummary": action_summary,
                    "updatedOn": now,
                    "overallRateAtAction": overall_rate,
                },
                "$push": {"actions": action_entry},
                "$setOnInsert": {"createdOn": now},
            },
            upsert=True,
        )
    except Exception as e:
        st.error(f"Failed to save action for {sku_prefix}: {e}")


def add_new_action(sku_prefix: str, action_summary: str, overall_rate: float):
    """Add a follow-up action to an existing tracked SKU."""
    now = datetime.now(timezone.utc)
    action_entry = {
        "summary": action_summary,
        "date": now,
        "overallRate": overall_rate,
    }
    try:
        _coll().update_one(
            {"skuPrefix": sku_prefix},
            {
                "$set": {
                    "actionSummary": action_summary,
                    "updatedOn": now,
                    "overallRateAtAction": overall_rate,
                },
                "$push": {"actions": action_entry},
            },
        )
    except Exception as e:
        st.error(f"Failed to add action for {sku_prefix}: {e}")


def save_no_action(sku_prefix: str):
    try:
        _coll().update_one(
            {"skuPrefix": sku_prefix},
            {"$set": {
                "status": "no_action",
                "updatedOn": datetime.now(timezone.utc),
            }, "$setOnInsert": {
                "createdOn": datetime.now(timezone.utc),
            }},
            upsert=True,
        )
    except Exception as e:
        st.error(f"Failed to save no-action for {sku_prefix}: {e}")


def resolve_sku(sku_prefix: str):
    """Mark as resolved — removes from Action Tracking."""
    try:
        _coll().update_one(
            {"skuPrefix": sku_prefix},
            {"$set": {"status": "resolved", "updatedOn": datetime.now(timezone.utc)}},
        )
    except Exception as e:
        st.error(f"Failed to resolve {sku_prefix}: {e}")


def dismiss_sku(sku_prefix: str):
    """Alias for resolve_sku (backward compat)."""
    resolve_sku(sku_prefix)


def revert_waiting(sku_prefix: str):
    try:
        _coll().delete_one({"skuPrefix": sku_prefix})
    except Exception as e:
        st.error(f"Failed to revert {sku_prefix}: {e}")


def revert_no_action(sku_prefix: str):
    try:
        _coll().delete_one({"skuPrefix": sku_prefix})
    except Exception as e:
        st.error(f"Failed to revert {sku_prefix}: {e}")


# --- Read operations ---

def get_action(sku_prefix: str) -> Optional[dict]:
    return _coll().find_one({"skuPrefix": sku_prefix})


def get_all_actions() -> dict:
    results = {}
    for doc in _coll().find():
        results[doc["skuPrefix"]] = doc
    return results


def get_excluded_skus() -> set:
    return {
        doc["skuPrefix"] for doc in _coll().find(
            {"status": {"$in": ["tracking", "no_action", "dismissed", "resolved"]}},
            {"skuPrefix": 1},
        )
    }


def get_skus_by_status(status: str) -> dict:
    results = {}
    for doc in _coll().find({"status": status}):
        results[doc["skuPrefix"]] = doc
    return results
