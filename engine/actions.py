"""
SKU action tracking: state machine, transition detection, before/after comparison.
Uses session state as temporary storage until MongoDB write access is available.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

import pandas as pd
import streamlit as st

import config
from engine.connection import get_db

# Parkpalet warehouse ID
PARKPALET_WH = "65702fd5a7a9890c689df17f"

# Minimum diff to count as real inbound (not returns)
MIN_INBOUND_DIFF = 50


def _get_store() -> dict:
    """Get the action store from session state."""
    if "sku_actions" not in st.session_state:
        st.session_state["sku_actions"] = {}
    return st.session_state["sku_actions"]


# --- Write operations (session state for now, MongoDB later) ---

def save_action(sku_prefix: str, action_summary: str, stock_snapshot: dict,
                return_rates: dict, overall_rate: float, flagged_sizes: list):
    """Record that an action was taken on a SKU."""
    store = _get_store()
    store[sku_prefix] = {
        "status": "waiting_for_fix",
        "actionSummary": action_summary,
        "createdOn": datetime.now(timezone.utc),
        "updatedOn": datetime.now(timezone.utc),
        "stockAtAction": stock_snapshot,
        "returnRateAtAction": return_rates,
        "overallRateAtAction": overall_rate,
        "flaggedSizes": flagged_sizes,
        "oldStockDepletedOn": {},
        "newStockFirstSeenOn": {},
        "newBatchReturnRate": {},
        "newBatchSales": {},
        "fixedOn": None,
    }


def save_no_action(sku_prefix: str):
    """Mark a SKU as no action possible."""
    store = _get_store()
    store[sku_prefix] = {
        "status": "no_action",
        "createdOn": datetime.now(timezone.utc),
        "updatedOn": datetime.now(timezone.utc),
    }


def dismiss_sku(sku_prefix: str):
    """Dismiss a fixed SKU."""
    store = _get_store()
    if sku_prefix in store:
        store[sku_prefix]["status"] = "dismissed"
        store[sku_prefix]["updatedOn"] = datetime.now(timezone.utc)


def revert_no_action(sku_prefix: str):
    """Revert a no-action SKU back to active."""
    store = _get_store()
    if sku_prefix in store:
        del store[sku_prefix]


# --- Read operations ---

def get_action(sku_prefix: str) -> Optional[dict]:
    """Get action data for a SKU."""
    return _get_store().get(sku_prefix)


def get_all_actions() -> dict:
    """Get all actions."""
    return _get_store()


def get_excluded_skus() -> set:
    """SKUs that should not appear in Bestsellers/Rising Stars."""
    store = _get_store()
    return {sku for sku, data in store.items()
            if data["status"] in ("waiting_for_fix", "no_action", "fixed", "dismissed")}


def get_skus_by_status(status: str) -> dict:
    """Get all SKUs with a given status."""
    store = _get_store()
    return {sku: data for sku, data in store.items() if data["status"] == status}


# --- Transition detection ---

def check_transitions(df_sku_size: pd.DataFrame):
    """
    For each 'waiting_for_fix' SKU, check if old stock depleted and new stock arrived.
    Transitions to 'fixed' when conditions are met for at least one size.
    """
    db = get_db()
    store = _get_store()
    waiting = {sku: data for sku, data in store.items() if data["status"] == "waiting_for_fix"}

    if not waiting:
        return

    for sku, action_data in waiting.items():
        action_date = action_data["createdOn"]
        flagged_sizes = action_data.get("flaggedSizes", [])
        stock_at_action = action_data.get("stockAtAction", {})

        any_size_ready = False

        for size in flagged_sizes:
            # Already processed this size
            if size in action_data.get("newBatchReturnRate", {}):
                any_size_ready = True
                continue

            initial_stock = stock_at_action.get(size, 0)
            if initial_stock == 0:
                continue

            # Check if stock hit 0 since action date
            depleted_date = _check_stock_depleted(sku, size, action_date)
            if depleted_date is None:
                continue

            action_data.setdefault("oldStockDepletedOn", {})[size] = depleted_date

            # Check if new inbound (diff >= 50) after depletion
            inbound_date = _check_new_inbound(sku, size, depleted_date)
            if inbound_date is None:
                continue

            action_data.setdefault("newStockFirstSeenOn", {})[size] = inbound_date

            # Check if enough new sales
            new_sales, new_return_rate = _check_new_batch_performance(
                sku, size, inbound_date, df_sku_size
            )
            if new_sales is not None and new_sales >= config.MIN_RECENT_SALES_PER_SIZE:
                action_data.setdefault("newBatchSales", {})[size] = new_sales
                action_data.setdefault("newBatchReturnRate", {})[size] = new_return_rate
                any_size_ready = True

        if any_size_ready and action_data["status"] == "waiting_for_fix":
            action_data["status"] = "fixed"
            action_data["fixedOn"] = datetime.now(timezone.utc)
            action_data["updatedOn"] = datetime.now(timezone.utc)


def _check_stock_depleted(sku_prefix: str, size: str, after_date: datetime) -> Optional[datetime]:
    """Check if stock hit 0 in ProductStockHistory after action date."""
    db = get_db()

    # Find the SKU suffix for this size from ProductStocks
    stock_rec = db["ProductStocks"].find_one(
        {"skuPrefix": sku_prefix, "size": size, "providerKey": "parkpalet"},
        {"sku": 1}
    )
    if not stock_rec:
        return None

    sku_full = stock_rec["sku"]

    # Find first day with available = 0 after action date
    result = db["ProductStockHistory"].find_one(
        {
            "warehouseId": PARKPALET_WH,
            "sku": sku_full,
            "available": 0,
            "createdOn": {"$gt": after_date},
        },
        sort=[("createdOn", 1)],
    )

    return result["createdOn"] if result else None


def _check_new_inbound(sku_prefix: str, size: str, after_date: datetime) -> Optional[datetime]:
    """Check if significant inbound (diff >= 50) after depletion date."""
    db = get_db()

    stock_rec = db["ProductStocks"].find_one(
        {"skuPrefix": sku_prefix, "size": size, "providerKey": "parkpalet"},
        {"sku": 1}
    )
    if not stock_rec:
        return None

    sku_full = stock_rec["sku"]

    result = db["ProductStockHistory"].find_one(
        {
            "warehouseId": PARKPALET_WH,
            "sku": sku_full,
            "diff": {"$gte": MIN_INBOUND_DIFF},
            "createdOn": {"$gt": after_date},
        },
        sort=[("createdOn", 1)],
    )

    return result["createdOn"] if result else None


def _check_new_batch_performance(
    sku_prefix: str, size: str, since_date: datetime, df_sku_size: pd.DataFrame
) -> tuple:
    """
    Count sales and return rate for orders placed after the new stock date.
    Returns (sales_count, return_rate) or (None, None) if not enough data.
    """
    db = get_db()
    hiccup_skus = [sku_prefix]

    # Determine cutoff (channel-specific lag)
    cutoff_fast = datetime.now(timezone.utc) - timedelta(days=config.FAST_DELIVERY_LAG_DAYS)
    cutoff_slow = datetime.now(timezone.utc) - timedelta(days=config.SLOW_DELIVERY_LAG_DAYS)

    # Sales since new stock — simplified: use the earlier cutoff
    cutoff = min(cutoff_fast, cutoff_slow)

    # Count orders
    ord_pipeline = [
        {
            "$match": {
                "createdOn": {"$gte": since_date, "$lte": cutoff},
                "salesChannel": {"$nin": config.EXCLUDED_CHANNELS},
                "status": {"$in": config.VALID_ORDER_STATUSES},
            }
        },
        {"$unwind": "$lineItems"},
        {
            "$match": {
                "lineItems.skuPrefix": sku_prefix,
                "lineItems.size": size,
            }
        },
        {"$group": {"_id": None, "sold": {"$sum": "$lineItems.quantity"}}},
    ]
    ord_result = list(db[config.COLL_ORDERS].aggregate(ord_pipeline))
    new_sold = ord_result[0]["sold"] if ord_result else 0

    if new_sold < config.MIN_RECENT_SALES_PER_SIZE:
        return None, None

    # Count returns
    ret_pipeline = [
        {
            "$match": {
                "createdOn": {"$gte": since_date},
                "salesChannel": {"$nin": config.EXCLUDED_CHANNELS},
            }
        },
        {"$unwind": "$items"},
        {
            "$match": {
                "items.status": {"$in": config.VALID_RETURN_ITEM_STATUSES},
                "items.skuPrefix": sku_prefix,
                "items.size": size,
            }
        },
        {"$group": {"_id": None, "returned": {"$sum": "$items.quantity"}}},
    ]
    ret_result = list(db[config.COLL_RETURNS].aggregate(ret_pipeline))
    new_returned = ret_result[0]["returned"] if ret_result else 0

    new_rate = new_returned / new_sold if new_sold > 0 else 0
    return new_sold, min(new_rate, 1.0)
