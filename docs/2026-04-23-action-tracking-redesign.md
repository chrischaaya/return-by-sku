# Action Tracking Redesign — Design Spec

## Problem

The current "Waiting for Fix" → "Fixed" lifecycle assumes FIFO stock flow (old stock depletes, new stock arrives, measure new stock performance). Our warehouse doesn't operate FIFO, making the transition logic unreliable and misleading.

## Solution

Replace the batch-based system with a **trend-based monitoring page** that tracks return rate evolution over time, anchored to action dates and PO arrivals — without assumptions about which stock is being sold.

---

## Architecture

### Single Tab: "Action Tracking"

Replaces the current "In Progress" and "Results" tabs with one unified tab. Contains all SKUs where an action has been taken. Each SKU appears as a collapsible card.

### Two States

1. **Collapsed (default)** — compact card for quick scanning
2. **Expanded** — full time-series graph for investigation

---

## Collapsed Card

Shows at a glance whether things are improving.

### Layout

```
[Image] [Product name]                              [STATUS BADGE]
        SKU · Supplier · PM: Name                    [Dismiss]
        ┌─────────────────────────────────────────┐
        │ Action: description of what was done     │
        │ Taken: 18 Mar 2026 (36 days ago)         │
        └─────────────────────────────────────────┘
        ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐
        │ Last 14d │ │ Pre-PO   │ │ Lifetime │ │ New PO   │
        │  12.4%   │ │  21.3%   │ │  18.1%   │ │ Rcvd 2Apr│
        │          │ │          │ │          │ │ 320 units │
        └──────────┘ └──────────┘ └──────────┘ └──────────┘
```

### Metrics

| Metric | Definition |
|---|---|
| **Last 14 days** | Return rate over the last 14 days (excluding grace period). `returned / sold` for orders created in the 14-day window before the channel-specific delivery lag cutoff. |
| **Pre-PO (30d)** | Return rate for the 30 days before the first relevant PO was received at warehouse. This is the baseline — what performance looked like before new stock arrived. If no PO received yet, show "—". |
| **Lifetime** | All-time return rate for this SKU. |
| **New PO** | First PO created AND received after action date. Shows received date + total units. If no qualifying PO yet: "No PO yet". |

### Status Badge

Computed by comparing "Last 14 days" to "Pre-PO (30d)":

| Badge | Condition |
|---|---|
| **IMPROVING** (green) | Last 14d rate < Pre-PO rate by ≥ 3 percentage points |
| **NO CHANGE** (grey) | Difference < 3 percentage points either way |
| **WORSENING** (red) | Last 14d rate > Pre-PO rate by ≥ 3 percentage points |
| **WAITING** (amber) | No relevant PO received yet — too early to assess |

### Dismiss CTA

- Each card has a "Dismiss" button
- Dismissed SKUs are removed from this page permanently
- Status set to `dismissed` in MongoDB

---

## Expanded Card

Opened by clicking/expanding the collapsed card. Shows a Plotly time-series graph.

### Graph Specification

**Axes:**
- X-axis: calendar dates
- Y-axis: return rate (percentage)

**Lines:**
- 1 line per size (thin, colored, semi-transparent)
- 1 overall product line (thick, dark)
- All lines use **rolling 7-day window**: each day's point = returns / sales for orders in the 7 days ending on that date (respecting delivery lag)

**Vertical Markers:**
- **ACTION** marker (amber dashed line): date the action was taken
- **PO RECEIVED** marker(s) (green dashed line): `warehouseTransactionDate` of each qualifying PO. Multiple markers if multiple POs.

**Hover Tooltip:**
- On hover, shows crosshair + tooltip with: date, overall rate, and each size's rate

**Time Filter:**
- Buttons above the graph: `30d | 60d | 90d | All`
- Default: `90d`
- Controls the visible time window on the X-axis

**Sizing:**
- Full width of the card
- Height: ~320px minimum
- Responsive via Plotly's built-in layout

### Timeline Summary

Below the graph, a text summary:
```
● Action taken 18 Mar — Revised size chart
● PO created 20 Mar → Received 2 Apr (320 units: S=80, M=100, L=90, XL=50)
● 14-day return rate: 21.3% pre-PO → 12.4% now
```

---

## Data Model

### MongoDB: `hiccup-tools.SkuActions`

Updated document structure (replaces current fields):

```javascript
{
  skuPrefix: "MBAJ1ZFU01",
  status: "tracking",           // tracking | dismissed
  actionSummary: "Revised size chart...",
  createdOn: ISODate(),         // when action was recorded
  updatedOn: ISODate(),

  // Snapshot at action time
  overallRateAtAction: 0.213,   // lifetime rate when action was taken
}
```

Removed fields (no longer needed):
- `stockAtAction`, `returnRateAtAction` (per-size snapshots for FIFO)
- `oldStockDepletedOn`, `newStockFirstSeenOn` (FIFO tracking)
- `newBatchReturnRate`, `newBatchSales` (FIFO evaluation)
- `flaggedSizes` (no longer relevant — we track all sizes)
- `fixedOn` (no "fixed" state — just tracking or dismissed)

Status values simplified:
- `tracking` — action taken, monitoring performance (replaces `waiting_for_fix` and `fixed`)
- `dismissed` — reviewed and closed (replaces `dismissed`)
- `no_action` — parked, no action taken (unchanged, still used by Parked tab)

### PO Data Source: `hiccup-ff.SupplierProductOrders`

Queried on-demand (not cached in SkuActions). For a given skuPrefix:

```javascript
{
  // Match criteria:
  skuPrefix: "MBAJ1ZFU01",
  createdOn: { $gt: actionDate },           // PO created after action
  warehouseTransactionDate: { $exists: true, $ne: null },  // actually received
  status: { $nin: ["ORDER_CANCELLED"] },

  // Fields used:
  createdOn,                    // PO creation date
  warehouseTransactionDate,     // when stock arrived at warehouse
  items: [{
    size, ordered, received     // per-size quantities
  }]
}
```

### Rolling Return Rate Computation

For the time-series graph, compute daily rolling 7-day return rate:

```
For each day D in the time window:
  window_start = D - 7 days
  window_end = D

  sold = orders where createdOn in [window_start, window_end - delivery_lag]
  returned = returns where createdOn in [window_start, window_end]
         and items.status in [ACCEPTED, PENDING, REJECTED]

  rate = returned / sold (or 0 if sold = 0)
```

This is computed per-size and as an overall product aggregate.

**Performance note:** This requires querying Orders and CustomerReturns with date ranges. For the graph, we fetch raw daily counts once and compute the rolling window in Python/pandas — no per-day MongoDB queries.

### Pre-PO Baseline Computation

The "30 days before PO received" rate. Uses the same channel-specific delivery lag as the rest of the tool (7d for fast channels, 14d for slow).

```
po_received_date = warehouseTransactionDate of first qualifying PO

# Orders window: 30 days ending at (po_received_date - max_delivery_lag)
# This ensures we only count orders that had time to be delivered and returned
orders_end = po_received_date - 14 days   (use slow channel lag as conservative cutoff)
orders_start = orders_end - 30 days

sold = orders where createdOn in [orders_start, orders_end]
returned = returns where createdOn in [orders_start, po_received_date]
       and items.status in [ACCEPTED, PENDING, REJECTED]

pre_po_rate = returned / sold
```

If no qualifying PO exists yet, pre-PO rate = null (show "—").

---

## Pipeline Functions (new)

### `get_sku_pos(sku_prefix, after_date)` → list
Query `hiccup-ff.SupplierProductOrders` for POs created after `after_date` that have been received at the warehouse. Return: creation date, warehouse transaction date, per-size received quantities.

### `get_daily_returns(sku_prefix, start_date, end_date)` → list
Daily return counts per size from CustomerReturns. Used to compute rolling window.

### `get_daily_orders(sku_prefix, start_date, end_date)` → list
Daily order counts per size from Orders. Used to compute rolling window.

---

## UI Changes

### Tab Structure

Current: `Needs Attention | In Progress | Results | Parked`

New: `Needs Attention | Action Tracking | Parked`

- "In Progress" and "Results" merge into **"Action Tracking"**
- "Parked" stays as-is

### Action Tracking Tab

- Lists all SKUs with `status: "tracking"` from SkuActions
- Sorted by action date (most recent first)
- Each SKU renders as the collapsed card described above
- Click to expand shows the graph
- "Dismiss" button on each card

### Changes to "Needs Attention" Tab

When user clicks "Action taken" on a SKU in Needs Attention:
- Prompt for action summary (existing behavior)
- Save to SkuActions with `status: "tracking"` (was `waiting_for_fix`)
- Record `overallRateAtAction` (lifetime rate at that moment)
- SKU moves to Action Tracking tab

### Removed Code

- `check_transitions()` function and all FIFO transition detection
- `_check_stock_depleted()`, `_check_new_inbound()`, `_check_new_batch_performance()`
- `seed_test_scenarios()`, `clear_test_scenarios()` (already removed from UI)
- The old "In Progress" and "Results" tab rendering code

---

## Edge Cases

| Scenario | Behavior |
|---|---|
| **No PO yet** | Pre-PO shows "—". Badge shows WAITING. Graph still shows return rate trend with just the ACTION marker. |
| **PO created but not received** | Same as no PO — we only count POs with `warehouseTransactionDate`. |
| **Multiple POs after action** | Show all as green markers on graph. Use the FIRST one's received date for Pre-PO baseline. New PO metric in collapsed card shows the first one. |
| **Partial delivery** | Use `items[].received` count (actual received), not `ordered`. |
| **Very recent action (< 14 days)** | Last 14d metric may not be meaningful yet. Show the number but badge shows WAITING if no PO. |
| **Low volume (few sales/returns per day)** | Rolling 7-day window smooths this. Graph may still be noisy — that's expected and honest. |
| **SKU with 0 sales in a period** | Rate = 0 for that window. Line drops to 0. |
| **Missing PO data** | If `hiccup-ff` is unreachable, show "PO data unavailable" in the card. Graph still works (just no PO markers). |

---

## What This Does NOT Do

- No FIFO assumptions about stock batches
- No automatic "fixed" transition — human reviews and dismisses
- No before/after comparison of specific stock batches
- No financial impact calculations
- No per-channel breakdown in the graph (keeps it simple — overall + sizes)
