# Action Tracking Redesign — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the FIFO-based "In Progress / Results" tabs with a single "Action Tracking" tab that shows trend-based return rate graphs per SKU.

**Architecture:** New pipeline functions query daily orders/returns and POs on-demand per SKU. A new `engine/tracking.py` module computes rolling 7-day return rates and pre-PO baselines. The UI replaces two tabs with one, rendering collapsed metric cards and expandable Plotly graphs.

**Tech Stack:** Python, Streamlit, Plotly, pandas, pymongo (MongoDB: hiccup-app + hiccup-ff)

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `engine/pipelines.py` | Modify | Add 3 new pipeline functions (daily orders, daily returns, SKU POs) |
| `engine/tracking.py` | Create | Rolling return rate computation, pre-PO baseline, status badge logic |
| `engine/actions.py` | Modify | Simplify save_action, remove FIFO functions, update get_excluded_skus |
| `dashboard/app.py` | Modify | Replace In Progress + Results tabs with Action Tracking tab |
| `config.py` | Modify | Add hiccup-ff connection URI |

---

### Task 1: Add pipeline functions for daily order/return counts and PO lookup

**Files:**
- Modify: `engine/pipelines.py`

- [ ] **Step 1: Add `get_daily_orders_for_sku` function**

Add at the end of `engine/pipelines.py`:

```python
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
```

- [ ] **Step 2: Add `get_daily_returns_for_sku` function**

Add below the previous function:

```python
def get_daily_returns_for_sku(sku_prefix: str, start_date: datetime, end_date: datetime) -> list:
    """
    Daily return counts per size for a single SKU.
    Returns [{date, size, returned}, ...] — one row per (date, size).
    """
    db = get_db()
    pipeline = [
        {
            "$match": {
                "createdOn": {"$gte": start_date, "$lte": end_date},
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
                    "date": {"$dateToString": {"format": "%Y-%m-%d", "date": "$createdOn"}},
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
```

- [ ] **Step 3: Add `get_sku_pos` function for PO data from hiccup-ff**

Add below the previous function:

```python
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
```

- [ ] **Step 4: Verify the pipelines connect and return data**

Run in terminal:

```bash
cd "/Users/Chris/Claude/sessions/projects/return by sku"
python3 -c "
import sys; sys.path.insert(0, '.')
from datetime import datetime, timedelta, timezone
from engine import pipelines

# Test daily orders
start = datetime.now(timezone.utc) - timedelta(days=30)
end = datetime.now(timezone.utc)
orders = pipelines.get_daily_orders_for_sku('MBAJ1ZFU01', start, end)
print(f'Daily orders: {len(orders)} rows')
if orders: print(f'  Sample: {orders[0]}')

# Test daily returns
returns = pipelines.get_daily_returns_for_sku('MBAJ1ZFU01', start, end)
print(f'Daily returns: {len(returns)} rows')
if returns: print(f'  Sample: {returns[0]}')

# Test PO lookup
pos = pipelines.get_sku_pos('MBAJ1ZFU01', start - timedelta(days=180))
print(f'POs found: {len(pos)}')
if pos: print(f'  First PO received: {pos[0].get(\"received_on\")}')
"
```

Expected: Non-zero rows for orders/returns. POs may be 0 for this SKU — that's fine.

- [ ] **Step 5: Commit**

```bash
git add engine/pipelines.py
git commit -m "feat: add daily order/return and PO pipeline functions for action tracking"
```

---

### Task 2: Create tracking computation module

**Files:**
- Create: `engine/tracking.py`

- [ ] **Step 1: Create `engine/tracking.py` with rolling return rate computation**

```python
"""
Action tracking: rolling return rate computation, pre-PO baseline, status badges.
No FIFO assumptions — purely trend-based.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

import pandas as pd
import streamlit as st

import config
from engine import pipelines


@st.cache_data(ttl=300)
def get_tracking_data(sku_prefix: str, action_date_str: str) -> dict:
    """
    Compute all tracking data for a single SKU.
    action_date_str is ISO format string (cache-friendly).
    Returns dict with: rolling_df, pos, last_14d_rate, pre_po_rate, lifetime_rate, badge.
    """
    action_date = datetime.fromisoformat(action_date_str).replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)

    # Fetch data: go back 180 days or to action_date - 30d, whichever is earlier
    graph_start = min(action_date - timedelta(days=30), now - timedelta(days=180))

    daily_orders = pipelines.get_daily_orders_for_sku(sku_prefix, graph_start, now)
    daily_returns = pipelines.get_daily_returns_for_sku(sku_prefix, graph_start, now)
    pos = pipelines.get_sku_pos(sku_prefix, action_date)

    # Build daily DataFrames
    df_ord = pd.DataFrame(daily_orders) if daily_orders else pd.DataFrame(columns=["date", "size", "sold"])
    df_ret = pd.DataFrame(daily_returns) if daily_returns else pd.DataFrame(columns=["date", "size", "returned"])

    if df_ord.empty:
        return _empty_result(pos)

    # Get all sizes
    all_sizes = sorted(set(df_ord["size"].unique()) | set(df_ret["size"].unique()) if not df_ret.empty else set(df_ord["size"].unique()))

    # Build complete date range
    date_range = pd.date_range(graph_start.date(), now.date(), freq="D")

    # Compute rolling 7-day return rate per size + overall
    rolling_rows = []
    for d in date_range:
        d_str = d.strftime("%Y-%m-%d")
        w_start = (d - timedelta(days=7)).strftime("%Y-%m-%d")

        # Window sold/returned
        sold_window = df_ord[(df_ord["date"] > w_start) & (df_ord["date"] <= d_str)]
        ret_window = df_ret[(df_ret["date"] > w_start) & (df_ret["date"] <= d_str)] if not df_ret.empty else pd.DataFrame(columns=["date", "size", "returned"])

        total_sold = sold_window["sold"].sum()
        total_returned = ret_window["returned"].sum() if not ret_window.empty else 0

        row = {
            "date": d_str,
            "overall_rate": min(total_returned / total_sold, 1.0) if total_sold > 0 else None,
            "overall_sold": int(total_sold),
        }

        for size in all_sizes:
            s_sold = sold_window[sold_window["size"] == size]["sold"].sum()
            s_ret = ret_window[ret_window["size"] == size]["returned"].sum() if not ret_window.empty else 0
            row[f"rate_{size}"] = min(s_ret / s_sold, 1.0) if s_sold > 0 else None

        rolling_rows.append(row)

    rolling_df = pd.DataFrame(rolling_rows)
    rolling_df["date"] = pd.to_datetime(rolling_df["date"])

    # Last 14 days rate (simple, not rolling)
    lag_days = config.SLOW_DELIVERY_LAG_DAYS
    end_14d = now - timedelta(days=lag_days)
    start_14d = end_14d - timedelta(days=14)
    s14 = start_14d.strftime("%Y-%m-%d")
    e14 = end_14d.strftime("%Y-%m-%d")
    sold_14d = df_ord[(df_ord["date"] >= s14) & (df_ord["date"] <= e14)]["sold"].sum()
    ret_14d = df_ret[(df_ret["date"] >= s14) & (df_ret["date"] <= e14)]["returned"].sum() if not df_ret.empty else 0
    last_14d_rate = min(ret_14d / sold_14d, 1.0) if sold_14d > 0 else None

    # Pre-PO baseline (30 days before first PO received)
    pre_po_rate = _compute_pre_po_rate(df_ord, df_ret, pos)

    # Lifetime rate
    total_sold = df_ord["sold"].sum()
    total_ret = df_ret["returned"].sum() if not df_ret.empty else 0
    lifetime_rate = min(total_ret / total_sold, 1.0) if total_sold > 0 else 0

    # Badge
    badge = _compute_badge(last_14d_rate, pre_po_rate, pos)

    return {
        "rolling_df": rolling_df,
        "sizes": all_sizes,
        "pos": pos,
        "last_14d_rate": last_14d_rate,
        "pre_po_rate": pre_po_rate,
        "lifetime_rate": lifetime_rate,
        "badge": badge,
    }


def _compute_pre_po_rate(df_ord, df_ret, pos) -> Optional[float]:
    """Return rate for the 30 days before the first PO was received at warehouse."""
    if not pos:
        return None

    received_on = pos[0].get("received_on")
    if received_on is None:
        return None

    if isinstance(received_on, str):
        received_on = datetime.fromisoformat(received_on)

    orders_end = received_on - timedelta(days=14)
    orders_start = orders_end - timedelta(days=30)
    s = orders_start.strftime("%Y-%m-%d")
    e = orders_end.strftime("%Y-%m-%d")
    r_end = received_on.strftime("%Y-%m-%d")

    sold = df_ord[(df_ord["date"] >= s) & (df_ord["date"] <= e)]["sold"].sum()
    returned = df_ret[(df_ret["date"] >= s) & (df_ret["date"] <= r_end)]["returned"].sum() if not df_ret.empty else 0

    if sold == 0:
        return None
    return min(returned / sold, 1.0)


def _compute_badge(last_14d_rate, pre_po_rate, pos) -> str:
    """Compute status badge from metrics."""
    if not pos or pre_po_rate is None or last_14d_rate is None:
        return "WAITING"

    diff = last_14d_rate - pre_po_rate
    if diff <= -0.03:
        return "IMPROVING"
    elif diff >= 0.03:
        return "WORSENING"
    else:
        return "NO CHANGE"


def _empty_result(pos):
    return {
        "rolling_df": pd.DataFrame(),
        "sizes": [],
        "pos": pos,
        "last_14d_rate": None,
        "pre_po_rate": None,
        "lifetime_rate": 0,
        "badge": "WAITING",
    }
```

- [ ] **Step 2: Verify the module loads and computes**

```bash
cd "/Users/Chris/Claude/sessions/projects/return by sku"
python3 -c "
import sys; sys.path.insert(0, '.')
from engine.tracking import get_tracking_data
from datetime import datetime, timezone, timedelta

# Use a recent date as action_date
action = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
result = get_tracking_data('MBAJ1ZFU01', action)
print(f'Rolling DF rows: {len(result[\"rolling_df\"])}')
print(f'Sizes: {result[\"sizes\"]}')
print(f'POs: {len(result[\"pos\"])}')
print(f'Last 14d: {result[\"last_14d_rate\"]}')
print(f'Pre-PO: {result[\"pre_po_rate\"]}')
print(f'Lifetime: {result[\"lifetime_rate\"]}')
print(f'Badge: {result[\"badge\"]}')
"
```

Expected: Non-empty rolling DF, some sizes, numeric rates.

- [ ] **Step 3: Commit**

```bash
git add engine/tracking.py
git commit -m "feat: add tracking module with rolling return rate and pre-PO baseline"
```

---

### Task 3: Simplify `engine/actions.py`

**Files:**
- Modify: `engine/actions.py`

- [ ] **Step 1: Simplify `save_action` — remove FIFO fields, use `tracking` status**

Replace the `save_action` function:

```python
def save_action(sku_prefix: str, action_summary: str, overall_rate: float):
    try:
        _coll().update_one(
            {"skuPrefix": sku_prefix},
            {"$set": {
                "status": "tracking",
                "actionSummary": action_summary,
                "updatedOn": datetime.now(timezone.utc),
                "overallRateAtAction": overall_rate,
            }, "$setOnInsert": {
                "createdOn": datetime.now(timezone.utc),
            }},
            upsert=True,
        )
    except Exception as e:
        st.error(f"Failed to save action for {sku_prefix}: {e}")
```

- [ ] **Step 2: Update `get_excluded_skus` to use new status values**

Replace:

```python
def get_excluded_skus() -> set:
    return {
        doc["skuPrefix"] for doc in _coll().find(
            {"status": {"$in": ["tracking", "no_action", "dismissed"]}},
            {"skuPrefix": 1},
        )
    }
```

- [ ] **Step 3: Remove FIFO functions**

Delete these functions entirely from `engine/actions.py`:
- `check_transitions` (lines 144-191)
- `_check_stock_depleted` (lines 194-212)
- `_check_new_inbound` (lines 215-233)
- `_check_new_batch_performance` (lines 236-284)
- `seed_test_scenarios` (lines 303-433)
- `clear_test_scenarios` (lines 291-300)

Also remove the constants they used:
- `PARKPALET_WH`
- `MIN_INBOUND_DIFF`

Remove imports no longer needed:
- `import pandas as pd` (if no longer used)
- `import config` (if no longer used)
- `from engine.connection import get_db` (if no longer used)

Keep: `save_action`, `save_no_action`, `dismiss_sku`, `revert_no_action`, `revert_waiting`, `get_action`, `get_all_actions`, `get_excluded_skus`, `get_skus_by_status`. And keep the write connection (`_get_write_db`, `_coll`).

- [ ] **Step 4: Verify actions module compiles**

```bash
cd "/Users/Chris/Claude/sessions/projects/return by sku"
python3 -c "import py_compile; py_compile.compile('engine/actions.py', doraise=True); print('OK')"
```

- [ ] **Step 5: Commit**

```bash
git add engine/actions.py
git commit -m "refactor: simplify actions module, remove FIFO tracking logic"
```

---

### Task 4: Rewrite tab structure and Action Tracking UI in `dashboard/app.py`

**Files:**
- Modify: `dashboard/app.py`

This is the largest task. It replaces the In Progress and Results tabs with a single Action Tracking tab.

- [ ] **Step 1: Update imports**

At the top of `dashboard/app.py`, add the tracking import alongside existing ones:

```python
from engine.tracking import get_tracking_data
```

Remove `check_transitions` from the actions import line:

```python
from engine.actions import (
    save_action, save_no_action, dismiss_sku, revert_no_action,
    revert_waiting, get_excluded_skus, get_skus_by_status, get_action,
)
```

Also add plotly import at the top alongside existing imports:

```python
import plotly.graph_objects as go
```

- [ ] **Step 2: Remove `check_transitions` call from computation block**

In the computation block (around line 270), find and delete:

```python
    check_transitions(df_sku_size)
```

- [ ] **Step 3: Update data loading — replace `waiting_data` and `fixed_data` with `tracking_data`**

Replace these lines:

```python
waiting_data = get_skus_by_status("waiting_for_fix")
fixed_data = get_skus_by_status("fixed")
parked_data = get_skus_by_status("no_action")
```

With:

```python
tracking_data = get_skus_by_status("tracking")
parked_data = get_skus_by_status("no_action")
```

- [ ] **Step 4: Replace tab structure**

Replace:

```python
tab_att, tab_prog, tab_res, tab_park = st.tabs([
    f"Needs Attention ({len(needs_attention)})",
    f"In Progress ({len(waiting_data)})",
    f"Results ({len(fixed_data)})",
    f"Parked ({len(parked_data)})",
])
```

With:

```python
tab_att, tab_track, tab_park = st.tabs([
    f"Needs Attention ({len(needs_attention)})",
    f"Action Tracking ({len(tracking_data)})",
    f"Parked ({len(parked_data)})",
])
```

- [ ] **Step 5: Update "Action taken" handler in `render_product_card`**

In the CTA section of `render_product_card`, find the `save_action` call and simplify it. Replace the block inside `if txt.strip():` (around line 620-640):

```python
                if st.button("Submit", key=f"sub_{sku}"):
                    if txt.strip():
                        save_action(sku, txt.strip(), float(rate))
                        st.session_state.pop(f"modal_{sku}", None)
                        st.session_state.pop("computed", None)
                        st.rerun()
```

- [ ] **Step 6: Add the `render_tracking_card` function**

Add before the tab sections (after `render_reviews`), a new function:

```python
BADGE_STYLES = {
    "IMPROVING": ("background:#dcfce7; color:#166534;", "IMPROVING"),
    "NO CHANGE": ("background:#f1f5f9; color:#475569;", "NO CHANGE"),
    "WORSENING": ("background:#fef2f2; color:#991b1b;", "WORSENING"),
    "WAITING": ("background:#fef3c7; color:#92400e;", "WAITING"),
}


def render_tracking_card(sku_prefix, action_doc):
    """Render a single action-tracked SKU as a collapsible card with graph."""
    row = df_sku[df_sku["sku_prefix"] == sku_prefix]
    name = row.iloc[0]["product_name"] if not row.empty else sku_prefix
    img_url = row.iloc[0].get("image_url") if not row.empty else None
    has_img = img_url and isinstance(img_url, str) and img_url.startswith("http")
    supplier = row.iloc[0].get("supplier_name", "N/A") if not row.empty else "N/A"
    pm = row.iloc[0].get("product_manager", "N/A") if not row.empty else "N/A"

    action_summary = action_doc.get("actionSummary", "N/A")
    created_on = action_doc.get("createdOn")
    days_ago = (pd.Timestamp.now(tz="UTC") - pd.Timestamp(created_on, tz="UTC")).days if created_on else 0
    date_str = created_on.strftime("%d %b %Y") if created_on else "?"

    # Fetch tracking metrics
    action_iso = created_on.isoformat() if created_on else datetime.now(timezone.utc).isoformat()
    td = get_tracking_data(sku_prefix, action_iso)

    badge_key = td["badge"]
    badge_style, badge_label = BADGE_STYLES.get(badge_key, BADGE_STYLES["WAITING"])

    last_14d = f"{td['last_14d_rate']:.1%}" if td["last_14d_rate"] is not None else "—"
    pre_po = f"{td['pre_po_rate']:.1%}" if td["pre_po_rate"] is not None else "—"
    lifetime = f"{td['lifetime_rate']:.1%}"

    # PO info
    if td["pos"]:
        first_po = td["pos"][0]
        po_date = first_po["received_on"]
        po_date_str = po_date.strftime("%d %b") if hasattr(po_date, "strftime") else str(po_date)[:10]
        po_units = sum(item.get("received", 0) for item in first_po.get("items", []))
        po_text = f"Received {po_date_str}"
        po_detail = f"{po_units} units"
    else:
        po_text = "No PO yet"
        po_detail = "—"

    with st.container(border=True):
        # Header: image + info + badge
        if has_img:
            ic, mc = st.columns([1, 8])
        else:
            ic, mc = None, st.container()
        if ic:
            with ic:
                st.image(img_url, width=60)
        with mc:
            hc1, hc2 = st.columns([6, 1])
            with hc1:
                st.markdown(f"**{name}**")
                st.caption(f"{sku_prefix} · {supplier} · PM: {pm or 'N/A'}")
            with hc2:
                st.markdown(f'<div style="text-align:right;"><span style="{badge_style} font-size:11px; font-weight:600; padding:3px 10px; border-radius:12px;">{badge_label}</span></div>', unsafe_allow_html=True)

            # Action box
            st.markdown(
                f'<div style="padding:8px 12px; border-left:4px solid #f59e0b; background:#fffbeb; border-radius:4px; font-size:12px; margin:4px 0;">'
                f'<b>Action:</b> {action_summary}<br>'
                f'<span style="color:#888;">Taken {date_str} ({days_ago} days ago)</span>'
                f'</div>',
                unsafe_allow_html=True,
            )

            # Metric boxes
            mc1, mc2, mc3, mc4 = st.columns(4)
            with mc1:
                st.markdown(f'<div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:6px; padding:8px 12px;"><div style="font-size:10px; color:#888; text-transform:uppercase;">Last 14 days</div><div style="font-size:18px; font-weight:700; margin-top:2px;">{last_14d}</div></div>', unsafe_allow_html=True)
            with mc2:
                st.markdown(f'<div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:6px; padding:8px 12px;"><div style="font-size:10px; color:#888; text-transform:uppercase;">Pre-PO (30d)</div><div style="font-size:18px; font-weight:700; margin-top:2px;">{pre_po}</div></div>', unsafe_allow_html=True)
            with mc3:
                st.markdown(f'<div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:6px; padding:8px 12px;"><div style="font-size:10px; color:#888; text-transform:uppercase;">Lifetime</div><div style="font-size:18px; font-weight:700; margin-top:2px;">{lifetime}</div></div>', unsafe_allow_html=True)
            with mc4:
                st.markdown(f'<div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:6px; padding:8px 12px;"><div style="font-size:10px; color:#888; text-transform:uppercase;">New PO</div><div style="font-size:13px; font-weight:600; margin-top:4px;">{po_text}</div><div style="font-size:11px; color:#888;">{po_detail}</div></div>', unsafe_allow_html=True)

        # Expandable graph
        with st.expander("Return rate trend", expanded=False):
            _render_tracking_graph(sku_prefix, td, created_on)

        # Dismiss button
        if st.button("Dismiss", key=f"dismiss_{sku_prefix}"):
            dismiss_sku(sku_prefix)
            st.toast(f"Dismissed: {name}")
            st.rerun()
```

- [ ] **Step 7: Add the `_render_tracking_graph` function**

Add right after `render_tracking_card`:

```python
SIZE_COLORS = ["#ef4444", "#3b82f6", "#22c55e", "#a855f7", "#f97316", "#06b6d4", "#ec4899", "#84cc16"]


def _render_tracking_graph(sku_prefix, td, action_date):
    """Render the Plotly time-series graph for a tracked SKU."""
    rolling_df = td["rolling_df"]
    if rolling_df.empty:
        st.caption("Not enough data for graph")
        return

    # Time filter
    tf1, tf2, tf3, tf4 = st.columns(4)
    tf_key = f"tf_{sku_prefix}"
    with tf1:
        if st.button("30d", key=f"{tf_key}_30"): st.session_state[tf_key] = 30
    with tf2:
        if st.button("60d", key=f"{tf_key}_60"): st.session_state[tf_key] = 60
    with tf3:
        if st.button("90d", key=f"{tf_key}_90"): st.session_state[tf_key] = 90
    with tf4:
        if st.button("All", key=f"{tf_key}_all"): st.session_state[tf_key] = 0

    days_filter = st.session_state.get(tf_key, 90)
    df = rolling_df.copy()
    if days_filter > 0:
        cutoff = pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=days_filter)
        df = df[df["date"] >= cutoff]

    if df.empty:
        st.caption("No data in selected range")
        return

    fig = go.Figure()

    # Overall line (bold)
    fig.add_trace(go.Scatter(
        x=df["date"], y=df["overall_rate"],
        mode="lines", name="Overall",
        line=dict(color="#333", width=3),
        hovertemplate="%{x|%d %b %Y}<br>Overall: %{y:.1%}<extra></extra>",
        connectgaps=False,
    ))

    # Per-size lines
    for i, size in enumerate(td["sizes"]):
        col_name = f"rate_{size}"
        if col_name not in df.columns:
            continue
        color = SIZE_COLORS[i % len(SIZE_COLORS)]
        fig.add_trace(go.Scatter(
            x=df["date"], y=df[col_name],
            mode="lines", name=size,
            line=dict(color=color, width=1.5),
            opacity=0.6,
            hovertemplate=f"{size}: %{{y:.1%}}<extra></extra>",
            connectgaps=False,
        ))

    # Action marker
    if action_date:
        fig.add_vline(
            x=action_date, line_dash="dash", line_color="#f59e0b", line_width=2,
            annotation_text="ACTION", annotation_position="top left",
            annotation_font_color="#f59e0b", annotation_font_size=10,
        )

    # PO received markers
    for po in td["pos"]:
        received = po.get("received_on")
        if received:
            units = sum(item.get("received", 0) for item in po.get("items", []))
            fig.add_vline(
                x=received, line_dash="dash", line_color="#16a34a", line_width=2,
                annotation_text=f"PO ({units}u)", annotation_position="top right",
                annotation_font_color="#16a34a", annotation_font_size=10,
            )

    fig.update_layout(
        yaxis=dict(tickformat=".0%", title="Return Rate", gridcolor="#f0f0f0"),
        xaxis=dict(title="", gridcolor="#f0f0f0"),
        height=360,
        margin=dict(t=30, b=40, l=50, r=20),
        plot_bgcolor="white",
        legend=dict(orientation="h", y=-0.15),
        hovermode="x unified",
    )

    st.plotly_chart(fig, use_container_width=True)

    # Timeline summary
    lines = [f"<span style='color:#f59e0b;'>&#9679;</span> Action taken {action_date.strftime('%d %b %Y') if action_date else '?'} — {st.session_state.get('_current_action_summary', '')}"]
    for po in td["pos"]:
        r_on = po.get("received_on")
        c_on = po.get("created_on")
        items = po.get("items", [])
        size_detail = ", ".join(f"{it['size']}={it.get('received', 0)}" for it in items if it.get("received", 0) > 0)
        total = sum(it.get("received", 0) for it in items)
        r_str = r_on.strftime("%d %b") if hasattr(r_on, "strftime") else str(r_on)[:10]
        c_str = c_on.strftime("%d %b") if hasattr(c_on, "strftime") else str(c_on)[:10]
        lines.append(f"<span style='color:#16a34a;'>&#9679;</span> PO created {c_str} &rarr; Received {r_str} ({total} units: {size_detail})")

    if td["pre_po_rate"] is not None and td["last_14d_rate"] is not None:
        lines.append(f"<span style='color:#333;'>&#9679;</span> 14-day return rate: <b>{td['pre_po_rate']:.1%}</b> pre-PO &rarr; <b>{td['last_14d_rate']:.1%}</b> now")

    st.markdown(
        f'<div style="font-size:12px; color:#555; padding:10px 14px; background:#f8fafc; border-radius:6px; line-height:1.7;">{"<br>".join(lines)}</div>',
        unsafe_allow_html=True,
    )
```

- [ ] **Step 8: Replace In Progress and Results tabs with Action Tracking tab**

Delete the entire `TAB 2: IN PROGRESS` section (the `with tab_prog:` block).

Delete the entire `TAB 3: RESULTS` section (the `with tab_res:` block).

Replace with:

```python
# =====================================================================
# TAB 2: ACTION TRACKING
# =====================================================================
with tab_track:
    if not tracking_data:
        st.info("No actions taken yet. Mark products as 'Action taken' from the Needs Attention tab.")
    else:
        st.caption(f"{len(tracking_data)} products being tracked")
        for sku_prefix, action_doc in sorted(tracking_data.items(), key=lambda x: x[1].get("createdOn", datetime.min), reverse=True):
            render_tracking_card(sku_prefix, action_doc)
```

- [ ] **Step 9: Update Parked tab reference**

Change `with tab_park:` to reference the new tab variable. The tab variable name from step 4 is already `tab_park` — verify it matches. If the old code had `tab_park` as the 4th tab, it's now the 3rd. The unpacking already handles this:

```python
tab_att, tab_track, tab_park = st.tabs([...])
```

- [ ] **Step 10: Add `plotly` back to requirements.txt**

```bash
cd "/Users/Chris/Claude/sessions/projects/return by sku"
```

Add `plotly>=5.18.0` to `requirements.txt`:

```
streamlit>=1.32.0
pymongo[srv]>=4.6.0
pandas>=2.1.0
plotly>=5.18.0
anthropic>=0.40.0
```

- [ ] **Step 11: Verify everything compiles**

```bash
cd "/Users/Chris/Claude/sessions/projects/return by sku"
python3 -c "
import py_compile
for f in ['engine/actions.py', 'engine/tracking.py', 'engine/pipelines.py', 'dashboard/app.py', 'config.py']:
    py_compile.compile(f, doraise=True)
print('All OK')
"
```

- [ ] **Step 12: Commit**

```bash
git add dashboard/app.py requirements.txt
git commit -m "feat: replace In Progress + Results tabs with Action Tracking tab

Collapsed cards show action summary, metrics (14d, pre-PO, lifetime),
PO status, and status badge. Expandable Plotly graph with rolling 7-day
return rate, ACTION and PO RECEIVED markers, time filter (30d/60d/90d/All)."
```

---

### Task 5: Add MONGO_FF_URI to secrets and test end-to-end

**Files:**
- Modify: `.streamlit/secrets.toml`

- [ ] **Step 1: Check if MONGO_FF_URI already exists in secrets**

```bash
grep -c "MONGO_FF_URI" "/Users/Chris/Claude/sessions/projects/return by sku/.streamlit/secrets.toml" || echo "NOT FOUND"
```

If not found, the `get_sku_pos` function falls back to `MONGO_URI` which connects to hiccup-prod. Since hiccup-ff is on the same cluster (hiccup-prod.clqls.mongodb.net), the same connection string should work — the function explicitly selects the `hiccup-ff` database. No secrets change needed unless the read user lacks access to hiccup-ff.

- [ ] **Step 2: Test PO lookup works with existing credentials**

```bash
cd "/Users/Chris/Claude/sessions/projects/return by sku"
python3 -c "
import sys; sys.path.insert(0, '.')
from engine.pipelines import get_sku_pos
from datetime import datetime, timedelta, timezone
pos = get_sku_pos('MBAJ1ZFU01', datetime.now(timezone.utc) - timedelta(days=365))
print(f'POs found: {len(pos)}')
for p in pos[:2]:
    print(f'  Created: {p[\"created_on\"]}, Received: {p[\"received_on\"]}, Items: {len(p[\"items\"])}')
"
```

If this fails with auth error, add `MONGO_FF_URI` to secrets with a user that has read access to hiccup-ff.

- [ ] **Step 3: Full end-to-end test — restart Streamlit and verify**

```bash
kill $(lsof -ti :8501) 2>/dev/null; sleep 1
cd "/Users/Chris/Claude/sessions/projects/return by sku"
/Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.9/Resources/Python.app/Contents/MacOS/Python -m streamlit run dashboard/app.py --server.headless true > /tmp/streamlit.log 2>&1 &
sleep 5
tail -15 /tmp/streamlit.log
```

Open http://localhost:8501 and verify:
- 3 tabs visible: Needs Attention, Action Tracking, Parked
- Action Tracking tab shows tracked SKUs (or empty message if none)
- Mark a product as "Action taken" from Needs Attention → it appears in Action Tracking
- Expand a tracked product → graph renders with markers
- Time filter buttons work
- Dismiss button works
- Hover tooltip shows all size values

- [ ] **Step 4: Commit any fixes**

```bash
git add -A
git commit -m "fix: end-to-end fixes for action tracking"
```

---

### Task 6: Migrate existing SkuActions data

**Files:** None (MongoDB operation only)

- [ ] **Step 1: Migrate existing `waiting_for_fix` and `fixed` documents to `tracking` status**

```bash
cd "/Users/Chris/Claude/sessions/projects/return by sku"
python3 -c "
import sys; sys.path.insert(0, '.')
from engine.actions import _coll

coll = _coll()

# Count current states
for status in ['waiting_for_fix', 'fixed', 'tracking', 'no_action', 'dismissed']:
    count = coll.count_documents({'status': status})
    print(f'{status}: {count}')

# Migrate waiting_for_fix -> tracking
result = coll.update_many(
    {'status': 'waiting_for_fix'},
    {'$set': {'status': 'tracking'}}
)
print(f'Migrated waiting_for_fix -> tracking: {result.modified_count}')

# Migrate fixed -> tracking
result = coll.update_many(
    {'status': 'fixed'},
    {'$set': {'status': 'tracking'}}
)
print(f'Migrated fixed -> tracking: {result.modified_count}')

# Verify
for status in ['waiting_for_fix', 'fixed', 'tracking', 'no_action', 'dismissed']:
    count = coll.count_documents({'status': status})
    print(f'{status}: {count}')
"
```

- [ ] **Step 2: Verify in the dashboard**

Refresh http://localhost:8501 — all previously tracked SKUs should now appear under the "Action Tracking" tab.

- [ ] **Step 3: Final commit and push**

```bash
cd "/Users/Chris/Claude/sessions/projects/return by sku"
git add -A
git status
git commit -m "chore: migrate SkuActions data to tracking status"
git push origin main
```
