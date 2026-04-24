"""
SKU action tracking: persist actions taken on flagged SKUs.
Persisted in MongoDB (hiccup-tools.returns.SkuActions).
"""

from datetime import datetime, timezone
from typing import Optional

import streamlit as st

_write_client = None


def _get_write_db():
    global _write_client
    if _write_client is None:
        from pymongo import MongoClient
        uri = st.secrets["MONGO_WRITE_URI"]
        _write_client = MongoClient(uri, serverSelectionTimeoutMS=10000)
    return _write_client["hiccup-tools"]


def _coll():
    return _get_write_db()["returns.SkuActions"]


def _add_status_history(update_dict: dict, from_status, to_status: str, actor: str, reason: str = None):
    """Append a statusHistory entry to an update operation."""
    entry = {
        "from": from_status,
        "to": to_status,
        "date": datetime.now(timezone.utc),
        "actor": actor,
    }
    if reason:
        entry["reason"] = reason
    update_dict.setdefault("$push", {})["statusHistory"] = entry


# --- Write operations ---

def save_action(sku_prefix: str, action_summary: str, overall_rate: float, actor: str):
    """Save a new action. Pushes to actions array (keeps full history)."""
    now = datetime.now(timezone.utc)
    action_entry = {
        "summary": action_summary,
        "date": now,
        "overallRate": overall_rate,
        "actor": actor,
    }

    # Check if document exists to determine from_status
    existing = _coll().find_one({"skuPrefix": sku_prefix}, {"status": 1})
    from_status = existing["status"] if existing else None

    update = {
        "$set": {
            "status": "tracking",
            "actionSummary": action_summary,
            "updatedOn": now,
            "overallRateAtAction": overall_rate,
        },
        "$push": {
            "actions": action_entry,
            "statusHistory": {
                "from": from_status,
                "to": "tracking",
                "date": now,
                "actor": actor,
            },
        },
        "$setOnInsert": {"createdOn": now},
    }

    try:
        _coll().update_one(
            {"skuPrefix": sku_prefix},
            update,
            upsert=True,
        )
    except Exception as e:
        st.error(f"Failed to save action for {sku_prefix}: {e}")


def add_new_action(sku_prefix: str, action_summary: str, overall_rate: float, actor: str):
    """Add a follow-up action to an existing tracked SKU."""
    now = datetime.now(timezone.utc)
    action_entry = {
        "summary": action_summary,
        "date": now,
        "overallRate": overall_rate,
        "actor": actor,
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


def save_no_action(sku_prefix: str, actor: str):
    """Park a SKU as 'no action possible'."""
    now = datetime.now(timezone.utc)

    existing = _coll().find_one({"skuPrefix": sku_prefix}, {"status": 1})
    from_status = existing["status"] if existing else None

    update = {
        "$set": {
            "status": "no_action",
            "updatedOn": now,
        },
        "$push": {
            "statusHistory": {
                "from": from_status,
                "to": "no_action",
                "date": now,
                "actor": actor,
            },
        },
        "$setOnInsert": {"createdOn": now},
    }

    try:
        _coll().update_one(
            {"skuPrefix": sku_prefix},
            update,
            upsert=True,
        )
    except Exception as e:
        st.error(f"Failed to save no-action for {sku_prefix}: {e}")


def resolve_sku(sku_prefix: str, actor: str):
    """Resolve — sets status to 'resolved'. Not excluded from Needs Attention."""
    now = datetime.now(timezone.utc)

    existing = _coll().find_one({"skuPrefix": sku_prefix}, {"status": 1})
    from_status = existing["status"] if existing else None

    try:
        _coll().update_one(
            {"skuPrefix": sku_prefix},
            {
                "$set": {"status": "resolved", "updatedOn": now},
                "$push": {
                    "statusHistory": {
                        "from": from_status,
                        "to": "resolved",
                        "date": now,
                        "actor": actor,
                    },
                },
            },
        )
    except Exception as e:
        st.error(f"Failed to resolve {sku_prefix}: {e}")


def revert_action(sku_prefix: str, actor: str):
    """Revert a tracked or parked SKU back to Needs Attention. Soft transition, no deletion."""
    now = datetime.now(timezone.utc)

    existing = _coll().find_one({"skuPrefix": sku_prefix}, {"status": 1})
    from_status = existing["status"] if existing else None

    try:
        _coll().update_one(
            {"skuPrefix": sku_prefix},
            {
                "$set": {"status": "reverted", "updatedOn": now},
                "$push": {
                    "statusHistory": {
                        "from": from_status,
                        "to": "reverted",
                        "date": now,
                        "actor": actor,
                    },
                },
            },
        )
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
            {"status": {"$in": ["tracking", "no_action"]}},
            {"skuPrefix": 1},
        )
    }


def get_skus_by_status(status: str) -> dict:
    results = {}
    for doc in _coll().find({"status": status}):
        results[doc["skuPrefix"]] = doc
    return results
