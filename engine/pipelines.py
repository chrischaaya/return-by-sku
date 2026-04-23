"""
MongoDB aggregation pipelines for returns and orders data.

KEY DESIGN DECISIONS:
- merchantKey is unreliable on CustomerReturns and Orders (missing on older items).
  We fetch hiccup skuPrefixes from Products and use those as the filter.
- No order status filter — all orders count as sold.
- Delivery lag: exclude orders created < 7 days ago for trendyol/hepsiburada,
  < 14 days for all other channels.
"""

from datetime import datetime, timedelta, timezone

import config
from engine.connection import get_db

_hiccup_sku_prefixes = None


def clear_cache():
    """Reset the module-level SKU prefix cache so next call re-fetches from MongoDB."""
    global _hiccup_sku_prefixes
    _hiccup_sku_prefixes = None


def _cutoff_fast() -> datetime:
    """Cutoff for fast-delivery channels (trendyol, hepsiburada)."""
    return datetime.now(timezone.utc) - timedelta(days=config.FAST_DELIVERY_LAG_DAYS)


def _cutoff_slow() -> datetime:
    """Cutoff for slower channels (everything else)."""
    return datetime.now(timezone.utc) - timedelta(days=config.SLOW_DELIVERY_LAG_DAYS)


def get_hiccup_sku_prefixes() -> list:
    """
    Fetch all skuPrefixes from Products where merchantKey = hiccup,
    excluding variants delisted for known-bad reasons (poor feedback,
    high returns, poor performance, being recreated).
    Cached in module-level variable.
    """
    global _hiccup_sku_prefixes
    if _hiccup_sku_prefixes is not None:
        return _hiccup_sku_prefixes

    db = get_db()

    # Get all hiccup skuPrefixes
    pipeline = [
        {"$match": {"merchantKey": config.MERCHANT_KEY}},
        {"$unwind": "$productVariants"},
        {"$group": {"_id": None, "prefixes": {"$addToSet": "$productVariants.skuPrefix"}}},
    ]
    result = list(db[config.COLL_PRODUCTS].aggregate(pipeline))
    all_prefixes = set(result[0]["prefixes"]) if result else set()

    # Get delisted skuPrefixes to exclude
    delisted_pipeline = [
        {"$match": {"merchantKey": config.MERCHANT_KEY}},
        {"$unwind": "$productVariants"},
        {
            "$match": {
                "productVariants.reorder.delistedUntil": {"$exists": True},
                "productVariants.reorder.delistedReason": {
                    "$regex": "poor customer|poor performance|high return|low performance|low customer|never see you|new sku|new product|new variant|re-created|to be created|will be created|being created",
                    "$options": "i",
                },
            }
        },
        {"$group": {"_id": None, "prefixes": {"$addToSet": "$productVariants.skuPrefix"}}},
    ]
    delisted_result = list(db[config.COLL_PRODUCTS].aggregate(delisted_pipeline))
    delisted_prefixes = set(delisted_result[0]["prefixes"]) if delisted_result else set()

    _hiccup_sku_prefixes = list(all_prefixes - delisted_prefixes)
    return _hiccup_sku_prefixes


def get_all_returns_by_sku() -> list:
    """
    All-time returns at (skuPrefix, size) level.
    Only items with status ACCEPTED, PENDING, or REJECTED.
    Filtered to hiccup products by skuPrefix.
    """
    db = get_db()
    hiccup_skus = get_hiccup_sku_prefixes()
    if not hiccup_skus:
        return []

    pipeline = [
        {"$match": {"salesChannel": {"$nin": config.EXCLUDED_CHANNELS}}},
        {"$unwind": "$items"},
        {
            "$match": {
                "items.status": {"$in": config.VALID_RETURN_ITEM_STATUSES},
                "items.skuPrefix": {"$in": hiccup_skus},
            }
        },
        {
            "$addFields": {
                "reason": {
                    "$ifNull": [
                        "$items.claim.reasonCode",
                        {"$ifNull": ["$items.claim.reasonKey", None]},
                    ]
                }
            }
        },
        {
            "$group": {
                "_id": {
                    "skuPrefix": "$items.skuPrefix",
                    "size": "$items.size",
                },
                "returned": {"$sum": "$items.quantity"},
                "product_name": {"$first": "$items.name"},
                "reasons": {"$push": "$reason"},
                "channels": {"$addToSet": "$salesChannel"},
            }
        },
        {
            "$project": {
                "_id": 0,
                "sku_prefix": "$_id.skuPrefix",
                "size": "$_id.size",
                "returned": 1,
                "product_name": 1,
                "reasons": 1,
                "channels": 1,
            }
        },
    ]

    return list(db[config.COLL_RETURNS].aggregate(pipeline, allowDiskUse=True))


def get_all_orders_by_sku() -> list:
    """
    All-time orders at (skuPrefix, size) level.
    Filtered to hiccup products by skuPrefix.
    No order status filter — all orders count.
    Excludes recent orders by channel-specific delivery lag.
    Two queries: one for fast channels, one for slow channels.
    """
    db = get_db()
    hiccup_skus = get_hiccup_sku_prefixes()
    if not hiccup_skus:
        return []

    results = []

    # Fast channels (7 day lag)
    fast_pipeline = [
        {
            "$match": {
                "createdOn": {"$lte": _cutoff_fast()},
                "salesChannel": {"$in": config.FAST_DELIVERY_CHANNELS},
                "status": {"$in": config.VALID_ORDER_STATUSES},
            }
        },
        {"$unwind": "$lineItems"},
        {"$match": {"lineItems.skuPrefix": {"$in": hiccup_skus}}},
        {
            "$group": {
                "_id": {
                    "skuPrefix": "$lineItems.skuPrefix",
                    "size": "$lineItems.size",
                },
                "sold": {"$sum": "$lineItems.quantity"},
                "product_name": {"$first": "$lineItems.name"},
                "category": {"$first": "$lineItems.category"},
            }
        },
        {
            "$project": {
                "_id": 0,
                "sku_prefix": "$_id.skuPrefix",
                "size": "$_id.size",
                "sold": 1,
                "product_name": 1,
                "category": 1,
            }
        },
    ]
    results.extend(db[config.COLL_ORDERS].aggregate(fast_pipeline, allowDiskUse=True))

    # Slow channels (14 day lag)
    all_excluded = config.EXCLUDED_CHANNELS + config.FAST_DELIVERY_CHANNELS
    slow_pipeline = [
        {
            "$match": {
                "createdOn": {"$lte": _cutoff_slow()},
                "salesChannel": {"$nin": all_excluded},
                "status": {"$in": config.VALID_ORDER_STATUSES},
            }
        },
        {"$unwind": "$lineItems"},
        {"$match": {"lineItems.skuPrefix": {"$in": hiccup_skus}}},
        {
            "$group": {
                "_id": {
                    "skuPrefix": "$lineItems.skuPrefix",
                    "size": "$lineItems.size",
                },
                "sold": {"$sum": "$lineItems.quantity"},
                "product_name": {"$first": "$lineItems.name"},
                "category": {"$first": "$lineItems.category"},
            }
        },
        {
            "$project": {
                "_id": 0,
                "sku_prefix": "$_id.skuPrefix",
                "size": "$_id.size",
                "sold": 1,
                "product_name": 1,
                "category": 1,
            }
        },
    ]
    results.extend(db[config.COLL_ORDERS].aggregate(slow_pipeline, allowDiskUse=True))

    return list(results)


def get_sku_first_order_dates() -> list:
    """
    Get the earliest order date per skuPrefix.
    Used to identify 'rising stars' (recently launched SKUs).
    """
    db = get_db()
    hiccup_skus = get_hiccup_sku_prefixes()
    if not hiccup_skus:
        return []

    pipeline = [
        {"$match": {"salesChannel": {"$nin": config.EXCLUDED_CHANNELS}, "status": {"$in": config.VALID_ORDER_STATUSES}}},
        {"$unwind": "$lineItems"},
        {"$match": {"lineItems.skuPrefix": {"$in": hiccup_skus}}},
        {
            "$group": {
                "_id": "$lineItems.skuPrefix",
                "first_order": {"$min": "$createdOn"},
            }
        },
        {"$project": {"_id": 0, "sku_prefix": "$_id", "first_order": 1}},
    ]

    return list(db[config.COLL_ORDERS].aggregate(pipeline, allowDiskUse=True))


def get_product_metadata() -> list:
    """
    Fetch product metadata: category hierarchy, supplier info, fit type.
    Only hiccup products.
    """
    db = get_db()

    pipeline = [
        {"$match": {"merchantKey": config.MERCHANT_KEY}},
        {"$unwind": "$productVariants"},
        {
            "$project": {
                "_id": 0,
                "sku_prefix": "$productVariants.skuPrefix",
                "family_sku": "$familySku",
                "product_name": "$name.en",
                "category": "$category",
                "category_l1": "$cat.level1",
                "category_l2": "$cat.level2",
                "category_l3": "$cat.level3",
                "category_l4": "$cat.level4",
                "fit_type": "$fitType",
                "supplier_name": {
                    "$arrayElemAt": ["$productVariants.suppliers.name", 0]
                },
                "supplier_id": {
                    "$arrayElemAt": ["$productVariants.suppliers.id", 0]
                },
                "image_url": {
                    "$arrayElemAt": ["$productVariants.images.image", 0]
                },
                "sizes": "$sizes",
                "product_manager": "$productManager.name",
            }
        },
    ]

    return list(db[config.COLL_PRODUCTS].aggregate(pipeline, allowDiskUse=True))


def get_all_sku_sizes() -> list:
    """
    Get all defined sizes per skuPrefix from Products.sizes (product-level)
    crossed with each productVariant's skuPrefix.
    """
    db = get_db()
    hiccup_skus = get_hiccup_sku_prefixes()
    if not hiccup_skus:
        return []

    pipeline = [
        {"$match": {"merchantKey": config.MERCHANT_KEY}},
        {"$unwind": "$productVariants"},
        {"$match": {"productVariants.skuPrefix": {"$in": hiccup_skus}}},
        {"$unwind": "$sizes"},
        {
            "$project": {
                "_id": 0,
                "sku_prefix": "$productVariants.skuPrefix",
                "size": "$sizes",
            }
        },
    ]

    return list(db[config.COLL_PRODUCTS].aggregate(pipeline, allowDiskUse=True))


def get_parkpalet_stock() -> list:
    """
    Parkpalet warehouse stock at (skuPrefix, size) level.
    Only hiccup products with available > 0.
    """
    db = get_db()
    hiccup_skus = get_hiccup_sku_prefixes()
    if not hiccup_skus:
        return []

    pipeline = [
        {
            "$match": {
                "providerKey": "parkpalet",
                "available": {"$gt": 0},
                "skuPrefix": {"$in": hiccup_skus},
            }
        },
        {
            "$group": {
                "_id": {"skuPrefix": "$skuPrefix", "size": "$size"},
                "stock": {"$sum": "$available"},
            }
        },
        {
            "$project": {
                "_id": 0,
                "sku_prefix": "$_id.skuPrefix",
                "size": "$_id.size",
                "parkpalet_stock": "$stock",
            }
        },
    ]

    return list(db["ProductStocks"].aggregate(pipeline, allowDiskUse=True))


def get_product_reviews() -> list:
    """
    Average rating, review count, and fit breakdown per (skuPrefix, size).
    Fit values: TRUE_TO_SIZE, SMALL, LARGE.
    """
    db = get_db()
    hiccup_skus = get_hiccup_sku_prefixes()
    if not hiccup_skus:
        return []

    pipeline = [
        {
            "$match": {
                "status": "PUBLISHED",
                "isDeleted": False,
                "skuPrefix": {"$in": hiccup_skus},
            }
        },
        {
            "$group": {
                "_id": {"skuPrefix": "$skuPrefix", "size": "$size"},
                "avg_rating": {"$avg": "$rating"},
                "review_count": {"$sum": 1},
                "fit_true": {
                    "$sum": {"$cond": [{"$eq": ["$fit", "TRUE_TO_SIZE"]}, 1, 0]}
                },
                "fit_small": {
                    "$sum": {"$cond": [{"$eq": ["$fit", "SMALL"]}, 1, 0]}
                },
                "fit_large": {
                    "$sum": {"$cond": [{"$eq": ["$fit", "LARGE"]}, 1, 0]}
                },
            }
        },
        {
            "$project": {
                "_id": 0,
                "sku_prefix": "$_id.skuPrefix",
                "size": "$_id.size",
                "avg_rating": {"$round": ["$avg_rating", 1]},
                "review_count": 1,
                "fit_true": 1,
                "fit_small": 1,
                "fit_large": 1,
            }
        },
    ]
    return list(db["ProductReviews"].aggregate(pipeline, allowDiskUse=True))


def get_sku_review_comments(sku_prefix: str, limit: int = 200) -> list:
    """
    Fetch individual review comments for a specific SKU, most recent first.
    """
    db = get_db()
    pipeline = [
        {
            "$match": {
                "skuPrefix": sku_prefix,
                "status": "PUBLISHED",
                "isDeleted": False,
            }
        },
        {"$sort": {"createdOn": -1}},
        {"$limit": limit},
        {
            "$project": {
                "_id": 0,
                "size": 1,
                "rating": 1,
                "fit": 1,
                "comments": 1,
                "originalComment": 1,
                "createdOn": 1,
                "name": 1,
                "reviewTitle": 1,
            }
        },
    ]
    return list(db["ProductReviews"].aggregate(pipeline))


def get_trendyol_review_stats() -> list:
    """
    Fetch Trendyol review stats (rating + count) per skuPrefix from scripts.TrendyolReviewStats.
    Uses hiccupStats for Hiccup's own listings. Falls back to merchantStats.
    """
    from pymongo import MongoClient
    import streamlit as st

    uri = st.secrets.get("MONGO_URI")
    client = MongoClient(uri, serverSelectionTimeoutMS=10000)
    try:
        db = client["scripts"]
        pipeline = [
            {"$project": {
                "_id": 0,
                "sku_prefix": "$skuPrefix",
                "review_count": {
                    "$cond": {
                        "if": {"$gt": [{"$ifNull": ["$hiccupStats.reviewCount", 0]}, 0]},
                        "then": "$hiccupStats.reviewCount",
                        "else": {"$ifNull": ["$merchantStats.reviewCount", 0]},
                    }
                },
                "avg_rating": {
                    "$cond": {
                        "if": {"$gt": [{"$ifNull": ["$hiccupStats.reviewCount", 0]}, 0]},
                        "then": "$hiccupStats.avgRating",
                        "else": "$merchantStats.avgRating",
                    }
                },
            }},
            {"$match": {"review_count": {"$gt": 0}}},
        ]
        return list(db["TrendyolReviewStats"].aggregate(pipeline))
    except Exception:
        return []
    finally:
        client.close()


def get_orders_count_for_skus(sku_prefixes: list, start_date: datetime, end_date: datetime) -> dict:
    """Fast: total sold per SKU in a date range. Returns {sku_prefix: sold}."""
    db = get_db()
    if not sku_prefixes:
        return {}
    pipeline = [
        {"$match": {"createdOn": {"$gte": start_date, "$lte": end_date}, "salesChannel": {"$nin": config.EXCLUDED_CHANNELS}, "status": {"$in": config.VALID_ORDER_STATUSES}}},
        {"$unwind": "$lineItems"},
        {"$match": {"lineItems.skuPrefix": {"$in": sku_prefixes}}},
        {"$group": {"_id": "$lineItems.skuPrefix", "sold": {"$sum": "$lineItems.quantity"}}},
    ]
    return {r["_id"]: r["sold"] for r in db[config.COLL_ORDERS].aggregate(pipeline, allowDiskUse=True)}


def get_returns_count_for_skus(sku_prefixes: list, start_date: datetime, end_date: datetime) -> dict:
    """Fast: total returned per SKU in a date range. Returns {sku_prefix: returned}."""
    db = get_db()
    if not sku_prefixes:
        return {}
    pipeline = [
        {"$match": {"date": {"$gte": start_date, "$lte": end_date}, "salesChannel": {"$nin": config.EXCLUDED_CHANNELS}}},
        {"$unwind": "$items"},
        {"$match": {"items.status": {"$in": config.VALID_RETURN_ITEM_STATUSES}, "items.skuPrefix": {"$in": sku_prefixes}}},
        {"$group": {"_id": "$items.skuPrefix", "returned": {"$sum": "$items.quantity"}}},
    ]
    return {r["_id"]: r["returned"] for r in db[config.COLL_RETURNS].aggregate(pipeline, allowDiskUse=True)}


def get_pos_for_skus(sku_action_pairs: list) -> dict:
    """
    Batch: get POs for multiple SKUs in one query to hiccup-ff.
    sku_action_pairs: [(sku_prefix, action_date), ...]
    Returns {sku_prefix: [{created_on, received_on, items}, ...]}.
    """
    from pymongo import MongoClient
    import streamlit as st

    if not sku_action_pairs:
        return {}

    uri = st.secrets.get("MONGO_FF_URI", st.secrets.get("MONGO_URI"))
    client = MongoClient(uri, serverSelectionTimeoutMS=10000)
    try:
        db = client["hiccup-ff"]
        sku_prefixes = [p[0] for p in sku_action_pairs]
        earliest = min(p[1] for p in sku_action_pairs)
        pipeline = [
            {"$match": {"skuPrefix": {"$in": sku_prefixes}, "createdOn": {"$gt": earliest}, "warehouseTransactionDate": {"$exists": True, "$ne": None}, "status": {"$nin": ["ORDER_CANCELLED"]}}},
            {"$sort": {"warehouseTransactionDate": 1}},
            {"$project": {"_id": 0, "skuPrefix": 1, "created_on": "$createdOn", "received_on": "$warehouseTransactionDate",
                "items": {"$map": {"input": "$items", "as": "item", "in": {"size": "$$item.size", "ordered": "$$item.ordered", "received": "$$item.received"}}}}},
        ]
        results = {}
        for doc in db["SupplierProductOrders"].aggregate(pipeline):
            sku = doc.pop("skuPrefix")
            # Only keep POs created after this SKU's action date
            action_date = next((p[1] for p in sku_action_pairs if p[0] == sku), earliest)
            if doc["created_on"] > action_date:
                results.setdefault(sku, []).append(doc)
        return results
    except Exception:
        return {}
    finally:
        client.close()


def get_daily_orders_for_skus(sku_prefixes: list, start_date: datetime, end_date: datetime) -> list:
    """
    Daily order counts per (skuPrefix, size) for multiple SKUs in one query.
    Returns [{sku_prefix, date, size, sold}, ...].
    """
    db = get_db()
    if not sku_prefixes:
        return []
    pipeline = [
        {
            "$match": {
                "createdOn": {"$gte": start_date, "$lte": end_date},
                "salesChannel": {"$nin": config.EXCLUDED_CHANNELS},
                "status": {"$in": config.VALID_ORDER_STATUSES},
            }
        },
        {"$unwind": "$lineItems"},
        {"$match": {"lineItems.skuPrefix": {"$in": sku_prefixes}}},
        {
            "$group": {
                "_id": {
                    "skuPrefix": "$lineItems.skuPrefix",
                    "date": {"$dateToString": {"format": "%Y-%m-%d", "date": "$createdOn"}},
                    "size": "$lineItems.size",
                },
                "sold": {"$sum": "$lineItems.quantity"},
            }
        },
        {
            "$project": {
                "_id": 0,
                "sku_prefix": "$_id.skuPrefix",
                "date": "$_id.date",
                "size": "$_id.size",
                "sold": 1,
            }
        },
    ]
    return list(db[config.COLL_ORDERS].aggregate(pipeline, allowDiskUse=True))


def get_daily_returns_for_skus(sku_prefixes: list, start_date: datetime, end_date: datetime) -> list:
    """
    Daily return counts per (skuPrefix, size) for multiple SKUs in one query.
    Returns [{sku_prefix, date, size, returned}, ...].
    """
    db = get_db()
    if not sku_prefixes:
        return []
    pipeline = [
        {
            "$match": {
                "date": {"$gte": start_date, "$lte": end_date},
                "salesChannel": {"$nin": config.EXCLUDED_CHANNELS},
            }
        },
        {"$unwind": "$items"},
        {
            "$match": {
                "items.status": {"$in": config.VALID_RETURN_ITEM_STATUSES},
                "items.skuPrefix": {"$in": sku_prefixes},
            }
        },
        {
            "$group": {
                "_id": {
                    "skuPrefix": "$items.skuPrefix",
                    "date": {"$dateToString": {"format": "%Y-%m-%d", "date": "$date"}},
                    "size": "$items.size",
                },
                "returned": {"$sum": "$items.quantity"},
            }
        },
        {
            "$project": {
                "_id": 0,
                "sku_prefix": "$_id.skuPrefix",
                "date": "$_id.date",
                "size": "$_id.size",
                "returned": 1,
            }
        },
    ]
    return list(db[config.COLL_RETURNS].aggregate(pipeline, allowDiskUse=True))


def get_daily_orders_for_sku(sku_prefix: str, start_date: datetime, end_date: datetime) -> list:
    """
    Daily order counts per size for a single SKU.
    Returns [{date, size, sold}, ...] — one row per (date, size).
    """
    db = get_db()
    pipeline = [
        {
            "$match": {
                "createdOn": {"$gte": start_date, "$lte": end_date},
                "salesChannel": {"$nin": config.EXCLUDED_CHANNELS},
                "status": {"$in": config.VALID_ORDER_STATUSES},
            }
        },
        {"$unwind": "$lineItems"},
        {"$match": {"lineItems.skuPrefix": sku_prefix}},
        {
            "$group": {
                "_id": {
                    "date": {"$dateToString": {"format": "%Y-%m-%d", "date": "$createdOn"}},
                    "size": "$lineItems.size",
                },
                "sold": {"$sum": "$lineItems.quantity"},
            }
        },
        {
            "$project": {
                "_id": 0,
                "date": "$_id.date",
                "size": "$_id.size",
                "sold": 1,
            }
        },
        {"$sort": {"date": 1}},
    ]
    return list(db[config.COLL_ORDERS].aggregate(pipeline, allowDiskUse=True))


def get_daily_returns_for_sku(sku_prefix: str, start_date: datetime, end_date: datetime) -> list:
    """
    Daily return counts per size for a single SKU.
    Returns [{date, size, returned}, ...] — one row per (date, size).
    """
    db = get_db()
    pipeline = [
        {
            "$match": {
                "date": {"$gte": start_date, "$lte": end_date},
                "salesChannel": {"$nin": config.EXCLUDED_CHANNELS},
            }
        },
        {"$unwind": "$items"},
        {
            "$match": {
                "items.status": {"$in": config.VALID_RETURN_ITEM_STATUSES},
                "items.skuPrefix": sku_prefix,
            }
        },
        {
            "$group": {
                "_id": {
                    "date": {"$dateToString": {"format": "%Y-%m-%d", "date": "$date"}},
                    "size": "$items.size",
                },
                "returned": {"$sum": "$items.quantity"},
            }
        },
        {
            "$project": {
                "_id": 0,
                "date": "$_id.date",
                "size": "$_id.size",
                "returned": 1,
            }
        },
        {"$sort": {"date": 1}},
    ]
    return list(db[config.COLL_RETURNS].aggregate(pipeline, allowDiskUse=True))


def get_sku_pos(sku_prefix: str, after_date: datetime) -> list:
    """
    Fetch POs from hiccup-ff.SupplierProductOrders created after after_date
    that have been received at the warehouse.
    Returns [{created_on, received_on, items: [{size, ordered, received}]}, ...]
    """
    from pymongo import MongoClient
    import streamlit as st

    uri = st.secrets.get("MONGO_FF_URI", st.secrets.get("MONGO_URI"))
    client = MongoClient(uri, serverSelectionTimeoutMS=10000)
    try:
        db = client["hiccup-ff"]
        pipeline = [
            {
                "$match": {
                    "skuPrefix": sku_prefix,
                    "createdOn": {"$gt": after_date},
                    "warehouseTransactionDate": {"$exists": True, "$ne": None},
                    "status": {"$nin": ["ORDER_CANCELLED"]},
                }
            },
            {"$sort": {"warehouseTransactionDate": 1}},
            {
                "$project": {
                    "_id": 0,
                    "created_on": "$createdOn",
                    "received_on": "$warehouseTransactionDate",
                    "items": {
                        "$map": {
                            "input": "$items",
                            "as": "item",
                            "in": {
                                "size": "$$item.size",
                                "ordered": "$$item.ordered",
                                "received": "$$item.received",
                            },
                        }
                    },
                }
            },
        ]
        return list(db["SupplierProductOrders"].aggregate(pipeline))
    except Exception:
        return []
    finally:
        client.close()

