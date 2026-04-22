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


def revert_waiting(sku_prefix: str):
    """Revert a waiting-for-fix SKU back to active."""
    store = _get_store()
    if sku_prefix in store:
        del store[sku_prefix]


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


# =====================================================================
# Test scenarios
# =====================================================================

def seed_test_scenarios():
    """
    Seed session state with test scenarios covering all states.

    Scenarios:
    1. WAITING — action taken 5 days ago, stock still selling, no depletion yet
    2. WAITING — action taken 30 days ago, stock depleted but no new inbound yet
    3. WAITING — action taken 45 days ago, new inbound received but not enough sales yet
    4. FIXED (improved) — old batch had 35% return, new batch has 12%
    5. FIXED (not improved) — old batch had 25% return, new batch has 28%
    6. FIXED (partial) — some sizes evaluated, others pending
    7. NO_ACTION — marked as no action possible
    8. DISMISSED — already resolved

    Uses real SKU prefixes from the data so they display correctly.
    """
    store = _get_store()

    now = datetime.now(timezone.utc)

    # Pick real SKUs from the existing data (top sellers)
    # These will show product names and images correctly
    real_skus = [
        "MBAJ1ZFU01",  # scenario 1 — waiting, just started
        "M6GLCY4Q02",  # scenario 2 — waiting, stock depleted
        "MGTBGRL601",  # scenario 3 — waiting, new inbound but low sales
        "M6RLJVMH02",  # scenario 4 — FIXED, improved
        "MGP6D8RJ01",  # scenario 5 — FIXED, not improved
        "M3HAU69901",  # scenario 6 — FIXED, partial data
        "ML6TCQKI01",  # scenario 7 — no action
        "MH5BERYM02",  # scenario 8 — dismissed
    ]

    # Scenario 1: WAITING — recent action, stock still selling
    store[real_skus[0]] = {
        "status": "waiting_for_fix",
        "actionSummary": "Contacted supplier to review size chart. Adjusted measurements for next production.",
        "createdOn": now - timedelta(days=5),
        "updatedOn": now - timedelta(days=5),
        "stockAtAction": {"S": 515, "M": 1034, "L": 972, "XL": 734},
        "returnRateAtAction": {"S": 0.19, "M": 0.20, "L": 0.22, "XL": 0.20},
        "overallRateAtAction": 0.20,
        "flaggedSizes": ["S", "M", "L", "XL"],
        "oldStockDepletedOn": {},
        "newStockFirstSeenOn": {},
        "newBatchReturnRate": {},
        "newBatchSales": {},
        "fixedOn": None,
    }

    # Scenario 2: WAITING — stock depleted on some sizes, no new inbound
    store[real_skus[1]] = {
        "status": "waiting_for_fix",
        "actionSummary": "Product runs small across all sizes. Sent revised spec sheet to supplier.",
        "createdOn": now - timedelta(days=30),
        "updatedOn": now - timedelta(days=10),
        "stockAtAction": {"M": 200, "L": 150, "XL": 80},
        "returnRateAtAction": {"M": 0.16, "L": 0.19, "XL": 0.19},
        "overallRateAtAction": 0.16,
        "flaggedSizes": ["M", "L", "XL"],
        "oldStockDepletedOn": {"M": now - timedelta(days=10), "XL": now - timedelta(days=15)},
        "newStockFirstSeenOn": {},
        "newBatchReturnRate": {},
        "newBatchSales": {},
        "fixedOn": None,
    }

    # Scenario 3: WAITING — new inbound received but not enough sales yet
    store[real_skus[2]] = {
        "status": "waiting_for_fix",
        "actionSummary": "Quality issue identified. Switched to new fabric supplier.",
        "createdOn": now - timedelta(days=45),
        "updatedOn": now - timedelta(days=5),
        "stockAtAction": {"S": 100, "M": 120, "L": 90},
        "returnRateAtAction": {"S": 0.23, "M": 0.25, "L": 0.21},
        "overallRateAtAction": 0.21,
        "flaggedSizes": ["S", "M", "L"],
        "oldStockDepletedOn": {"S": now - timedelta(days=20), "M": now - timedelta(days=18), "L": now - timedelta(days=22)},
        "newStockFirstSeenOn": {"S": now - timedelta(days=8), "M": now - timedelta(days=8)},
        "newBatchReturnRate": {},
        "newBatchSales": {"S": 5, "M": 7},
        "fixedOn": None,
    }

    # Scenario 4: FIXED — improved (return rate dropped significantly)
    store[real_skus[3]] = {
        "status": "fixed",
        "actionSummary": "Sizing was off — all sizes ran small. Revised measurements with supplier. New batch produced with corrected sizing.",
        "createdOn": now - timedelta(days=60),
        "updatedOn": now - timedelta(days=3),
        "stockAtAction": {"S": 150, "M": 230, "L": 180, "XL": 160, "XS": 80},
        "returnRateAtAction": {"S": 0.33, "M": 0.33, "L": 0.36, "XL": 0.33, "XS": 0.32},
        "overallRateAtAction": 0.33,
        "flaggedSizes": ["S", "M", "L", "XL", "XS"],
        "oldStockDepletedOn": {
            "S": now - timedelta(days=25), "M": now - timedelta(days=20),
            "L": now - timedelta(days=22), "XL": now - timedelta(days=28),
            "XS": now - timedelta(days=30),
        },
        "newStockFirstSeenOn": {
            "S": now - timedelta(days=18), "M": now - timedelta(days=15),
            "L": now - timedelta(days=16), "XL": now - timedelta(days=20),
            "XS": now - timedelta(days=22),
        },
        "newBatchReturnRate": {"S": 0.10, "M": 0.08, "L": 0.11, "XL": 0.09, "XS": 0.12},
        "newBatchSales": {"S": 45, "M": 68, "L": 52, "XL": 38, "XS": 25},
        "fixedOn": now - timedelta(days=3),
    }

    # Scenario 5: FIXED — not improved
    store[real_skus[4]] = {
        "status": "fixed",
        "actionSummary": "Updated product photos and description to better reflect actual fit.",
        "createdOn": now - timedelta(days=50),
        "updatedOn": now - timedelta(days=2),
        "stockAtAction": {"S": 80, "M": 100, "L": 70},
        "returnRateAtAction": {"S": 0.25, "M": 0.28, "L": 0.30},
        "overallRateAtAction": 0.29,
        "flaggedSizes": ["S", "M", "L"],
        "oldStockDepletedOn": {
            "S": now - timedelta(days=20), "M": now - timedelta(days=18),
            "L": now - timedelta(days=22),
        },
        "newStockFirstSeenOn": {
            "S": now - timedelta(days=15), "M": now - timedelta(days=14),
            "L": now - timedelta(days=16),
        },
        "newBatchReturnRate": {"S": 0.27, "M": 0.31, "L": 0.28},
        "newBatchSales": {"S": 30, "M": 42, "L": 28},
        "fixedOn": now - timedelta(days=2),
    }

    # Scenario 6: FIXED — partial (some sizes evaluated, L still pending)
    store[real_skus[5]] = {
        "status": "fixed",
        "actionSummary": "Inconsistent sizing across size range. Sent full measurement audit to supplier.",
        "createdOn": now - timedelta(days=40),
        "updatedOn": now - timedelta(days=1),
        "stockAtAction": {"S": 60, "M": 90, "L": 110, "XL": 50},
        "returnRateAtAction": {"S": 0.23, "M": 0.25, "L": 0.26, "XL": 0.20},
        "overallRateAtAction": 0.25,
        "flaggedSizes": ["S", "M", "L", "XL"],
        "oldStockDepletedOn": {
            "S": now - timedelta(days=18), "M": now - timedelta(days=15),
            "XL": now - timedelta(days=20),
        },
        "newStockFirstSeenOn": {
            "S": now - timedelta(days=12), "M": now - timedelta(days=10),
            "XL": now - timedelta(days=14),
        },
        "newBatchReturnRate": {"S": 0.14, "M": 0.12, "XL": 0.11},
        "newBatchSales": {"S": 22, "M": 35, "XL": 18},
        "fixedOn": now - timedelta(days=1),
    }

    # Scenario 7: NO ACTION
    store[real_skus[6]] = {
        "status": "no_action",
        "createdOn": now - timedelta(days=10),
        "updatedOn": now - timedelta(days=10),
    }

    # Scenario 8: DISMISSED
    store[real_skus[7]] = {
        "status": "dismissed",
        "actionSummary": "Sizing corrected in previous batch. Return rate normalized.",
        "createdOn": now - timedelta(days=90),
        "updatedOn": now - timedelta(days=5),
        "fixedOn": now - timedelta(days=10),
    }
