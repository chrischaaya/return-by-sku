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


def get_recent_sales_by_sku_size() -> list:
    """
    Last 30 days of sales at (skuPrefix, size) level.
    Used to determine which SKUs qualify (>=MIN_RECENT_SALES_PER_SIZE per size).
    Uses same channel-specific lag logic.
    """
    db = get_db()
    hiccup_skus = get_hiccup_sku_prefixes()
    if not hiccup_skus:
        return []

    results = []
    now = datetime.now(timezone.utc)

    # Fast channels
    fast_start = now - timedelta(days=30 + config.FAST_DELIVERY_LAG_DAYS)
    fast_end = _cutoff_fast()
    fast_pipeline = [
        {
            "$match": {
                "createdOn": {"$gte": fast_start, "$lte": fast_end},
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
                "recent_sold": {"$sum": "$lineItems.quantity"},
            }
        },
        {
            "$project": {
                "_id": 0,
                "sku_prefix": "$_id.skuPrefix",
                "size": "$_id.size",
                "recent_sold": 1,
            }
        },
    ]
    results.extend(db[config.COLL_ORDERS].aggregate(fast_pipeline, allowDiskUse=True))

    # Slow channels
    all_excluded = config.EXCLUDED_CHANNELS + config.FAST_DELIVERY_CHANNELS
    slow_start = now - timedelta(days=30 + config.SLOW_DELIVERY_LAG_DAYS)
    slow_end = _cutoff_slow()
    slow_pipeline = [
        {
            "$match": {
                "createdOn": {"$gte": slow_start, "$lte": slow_end},
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
                "recent_sold": {"$sum": "$lineItems.quantity"},
            }
        },
        {
            "$project": {
                "_id": 0,
                "sku_prefix": "$_id.skuPrefix",
                "size": "$_id.size",
                "recent_sold": 1,
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
            }
        },
    ]

    return list(db[config.COLL_PRODUCTS].aggregate(pipeline, allowDiskUse=True))


def get_all_sku_sizes() -> list:
    """
    Get all defined sizes per skuPrefix from the Products.skus array.
    Used to show all sizes even if they have 0 sales.
    """
    db = get_db()
    hiccup_skus = get_hiccup_sku_prefixes()
    if not hiccup_skus:
        return []

    pipeline = [
        {"$match": {"merchantKey": config.MERCHANT_KEY}},
        {"$unwind": "$skus"},
        {"$match": {"skus.skuPrefix": {"$in": hiccup_skus}}},
        {
            "$group": {
                "_id": {"skuPrefix": "$skus.skuPrefix", "size": "$skus.size"},
            }
        },
        {
            "$project": {
                "_id": 0,
                "sku_prefix": "$_id.skuPrefix",
                "size": "$_id.size",
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
