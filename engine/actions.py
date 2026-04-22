"""
SKU action tracking: state machine, transition detection, before/after comparison.
Persisted in MongoDB (hiccup-tools.SkuActions).
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

def save_action(sku_prefix: str, action_summary: str, stock_snapshot: dict,
                return_rates: dict, overall_rate: float, flagged_sizes: list):
    _coll().update_one(
        {"skuPrefix": sku_prefix},
        {"$set": {
            "status": "waiting_for_fix",
            "actionSummary": action_summary,
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
        }, "$setOnInsert": {
            "createdOn": datetime.now(timezone.utc),
        }},
        upsert=True,
    )


def save_no_action(sku_prefix: str):
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


def dismiss_sku(sku_prefix: str):
    _coll().update_one(
        {"skuPrefix": sku_prefix},
        {"$set": {"status": "dismissed", "updatedOn": datetime.now(timezone.utc)}},
    )


def revert_waiting(sku_prefix: str):
    _coll().delete_one({"skuPrefix": sku_prefix})


def revert_no_action(sku_prefix: str):
    _coll().delete_one({"skuPrefix": sku_prefix})


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
            {"status": {"$in": ["waiting_for_fix", "no_action", "fixed", "dismissed"]}},
            {"skuPrefix": 1},
        )
    }


def get_skus_by_status(status: str) -> dict:
    results = {}
    for doc in _coll().find({"status": status}):
        results[doc["skuPrefix"]] = doc
    return results


# --- Transition detection ---

def check_transitions(df_sku_size: pd.DataFrame):
    waiting = list(_coll().find({"status": "waiting_for_fix"}))

    for action_data in waiting:
        sku = action_data["skuPrefix"]
        action_date = action_data["createdOn"]
        flagged_sizes = action_data.get("flaggedSizes", [])
        stock_at_action = action_data.get("stockAtAction", {})

        any_size_ready = False
        updates = {}

        for size in flagged_sizes:
            existing_new_rates = action_data.get("newBatchReturnRate", {})
            if size in existing_new_rates:
                any_size_ready = True
                continue

            initial_stock = stock_at_action.get(size, 0)
            if initial_stock == 0:
                continue

            depleted_date = _check_stock_depleted(sku, size, action_date)
            if depleted_date is None:
                continue

            updates[f"oldStockDepletedOn.{size}"] = depleted_date

            inbound_date = _check_new_inbound(sku, size, depleted_date)
            if inbound_date is None:
                continue

            updates[f"newStockFirstSeenOn.{size}"] = inbound_date

            new_sales, new_return_rate = _check_new_batch_performance(
                sku, size, inbound_date, df_sku_size
            )
            if new_sales is not None and new_sales >= config.MIN_RECENT_SALES_PER_SIZE:
                updates[f"newBatchSales.{size}"] = new_sales
                updates[f"newBatchReturnRate.{size}"] = new_return_rate
                any_size_ready = True

        if updates:
            if any_size_ready:
                updates["status"] = "fixed"
                updates["fixedOn"] = datetime.now(timezone.utc)
            updates["updatedOn"] = datetime.now(timezone.utc)
            _coll().update_one({"skuPrefix": sku}, {"$set": updates})


def _check_stock_depleted(sku_prefix: str, size: str, after_date: datetime) -> Optional[datetime]:
    db = get_db()
    stock_rec = db["ProductStocks"].find_one(
        {"skuPrefix": sku_prefix, "size": size, "providerKey": "parkpalet"},
        {"sku": 1}
    )
    if not stock_rec:
        return None

    result = db["ProductStockHistory"].find_one(
        {
            "warehouseId": PARKPALET_WH,
            "sku": stock_rec["sku"],
            "available": 0,
            "createdOn": {"$gt": after_date},
        },
        sort=[("createdOn", 1)],
    )
    return result["createdOn"] if result else None


def _check_new_inbound(sku_prefix: str, size: str, after_date: datetime) -> Optional[datetime]:
    db = get_db()
    stock_rec = db["ProductStocks"].find_one(
        {"skuPrefix": sku_prefix, "size": size, "providerKey": "parkpalet"},
        {"sku": 1}
    )
    if not stock_rec:
        return None

    result = db["ProductStockHistory"].find_one(
        {
            "warehouseId": PARKPALET_WH,
            "sku": stock_rec["sku"],
            "diff": {"$gte": MIN_INBOUND_DIFF},
            "createdOn": {"$gt": after_date},
        },
        sort=[("createdOn", 1)],
    )
    return result["createdOn"] if result else None


def _check_new_batch_performance(
    sku_prefix: str, size: str, since_date: datetime, df_sku_size: pd.DataFrame
) -> tuple:
    db = get_db()
    cutoff = min(
        datetime.now(timezone.utc) - timedelta(days=config.FAST_DELIVERY_LAG_DAYS),
        datetime.now(timezone.utc) - timedelta(days=config.SLOW_DELIVERY_LAG_DAYS),
    )

    ord_pipeline = [
        {
            "$match": {
                "createdOn": {"$gte": since_date, "$lte": cutoff},
                "salesChannel": {"$nin": config.EXCLUDED_CHANNELS},
                "status": {"$in": config.VALID_ORDER_STATUSES},
            }
        },
        {"$unwind": "$lineItems"},
        {"$match": {"lineItems.skuPrefix": sku_prefix, "lineItems.size": size}},
        {"$group": {"_id": None, "sold": {"$sum": "$lineItems.quantity"}}},
    ]
    ord_result = list(db[config.COLL_ORDERS].aggregate(ord_pipeline))
    new_sold = ord_result[0]["sold"] if ord_result else 0

    if new_sold < config.MIN_RECENT_SALES_PER_SIZE:
        return None, None

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
    """Seed MongoDB with test scenarios covering all states."""
    coll = _coll()
    now = datetime.now(timezone.utc)

    scenarios = [
        {
            "skuPrefix": "MBAJ1ZFU01",
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
        },
        {
            "skuPrefix": "M6GLCY4Q02",
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
        },
        {
            "skuPrefix": "MGTBGRL601",
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
        },
        {
            "skuPrefix": "M6RLJVMH02",
            "status": "fixed",
            "actionSummary": "Sizing was off — all sizes ran small. Revised measurements with supplier.",
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
        },
        {
            "skuPrefix": "MGP6D8RJ01",
            "status": "fixed",
            "actionSummary": "Updated product photos and description to better reflect actual fit.",
            "createdOn": now - timedelta(days=50),
            "updatedOn": now - timedelta(days=2),
            "stockAtAction": {"S": 80, "M": 100, "L": 70},
            "returnRateAtAction": {"S": 0.25, "M": 0.28, "L": 0.30},
            "overallRateAtAction": 0.29,
            "flaggedSizes": ["S", "M", "L"],
            "oldStockDepletedOn": {"S": now - timedelta(days=20), "M": now - timedelta(days=18), "L": now - timedelta(days=22)},
            "newStockFirstSeenOn": {"S": now - timedelta(days=15), "M": now - timedelta(days=14), "L": now - timedelta(days=16)},
            "newBatchReturnRate": {"S": 0.27, "M": 0.31, "L": 0.28},
            "newBatchSales": {"S": 30, "M": 42, "L": 28},
            "fixedOn": now - timedelta(days=2),
        },
        {
            "skuPrefix": "M3HAU69901",
            "status": "fixed",
            "actionSummary": "Inconsistent sizing across size range. Sent full measurement audit to supplier.",
            "createdOn": now - timedelta(days=40),
            "updatedOn": now - timedelta(days=1),
            "stockAtAction": {"S": 60, "M": 90, "L": 110, "XL": 50},
            "returnRateAtAction": {"S": 0.23, "M": 0.25, "L": 0.26, "XL": 0.20},
            "overallRateAtAction": 0.25,
            "flaggedSizes": ["S", "M", "L", "XL"],
            "oldStockDepletedOn": {"S": now - timedelta(days=18), "M": now - timedelta(days=15), "XL": now - timedelta(days=20)},
            "newStockFirstSeenOn": {"S": now - timedelta(days=12), "M": now - timedelta(days=10), "XL": now - timedelta(days=14)},
            "newBatchReturnRate": {"S": 0.14, "M": 0.12, "XL": 0.11},
            "newBatchSales": {"S": 22, "M": 35, "XL": 18},
            "fixedOn": now - timedelta(days=1),
        },
        {
            "skuPrefix": "ML6TCQKI01",
            "status": "no_action",
            "createdOn": now - timedelta(days=10),
            "updatedOn": now - timedelta(days=10),
        },
        {
            "skuPrefix": "MH5BERYM02",
            "status": "dismissed",
            "actionSummary": "Sizing corrected in previous batch. Return rate normalized.",
            "createdOn": now - timedelta(days=90),
            "updatedOn": now - timedelta(days=5),
            "fixedOn": now - timedelta(days=10),
        },
    ]

    for s in scenarios:
        coll.replace_one({"skuPrefix": s["skuPrefix"]}, s, upsert=True)
