# Architecture

## System Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    Streamlit Dashboard                       │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌───────────────┐  │
│  │Executive │ │SKU Deep  │ │Supplier  │ │Category       │  │
│  │Summary   │ │Dive      │ │Scorecard │ │Overview       │  │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └──────┬────────┘  │
│       └─────────────┴────────────┴──────────────┘           │
│                          │                                   │
│                   Streamlit Session State                    │
│                   (cached DataFrames)                        │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────┴──────────────────────────────────┐
│                    Analysis Engine                            │
│  ┌────────────┐  ┌────────────┐  ┌────────────────────────┐ │
│  │ pipelines  │  │ analyzer   │  │ recommender            │ │
│  │            │  │            │  │                        │ │
│  │ MongoDB    │  │ Anomaly    │  │ reason code → why      │ │
│  │ agg pipes  │  │ detection  │  │ deviation  → severity  │ │
│  │ → raw data │  │ scoring    │  │ pattern    → action    │ │
│  │            │  │ trending   │  │                        │ │
│  └─────┬──────┘  └────────────┘  └────────────────────────┘ │
│        │                                                     │
│  ┌─────┴──────┐                                              │
│  │ connection │                                              │
│  │ (singleton)│                                              │
│  └─────┬──────┘                                              │
└────────┼────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────┐
│  MongoDB Atlas   │
│  hiccup-prod     │
│  (read-only)     │
│                  │
│  CustomerReturns │
│  Orders          │
│  Products        │
└─────────────────┘
```

## Data Flow

### On "Update Data" click:

1. **pipelines.py** runs MongoDB aggregation pipelines:
   - `get_returns_by_sku()` — unwinds CustomerReturns items, groups by skuPrefix + size
   - `get_orders_by_sku()` — unwinds Orders lineItems, groups by skuPrefix + size
   - `get_product_metadata()` — fetches category, supplier, product name from Products

2. **analyzer.py** joins the results in pandas:
   - Computes return rates at SKU, size, supplier, and category levels
   - Calculates category baselines (median return rate per category)
   - Detects anomalies (deviation from baseline, size concentration)
   - Computes trends (current period vs previous period)
   - Identifies "winners" (SKUs with significant improvement)

3. **recommender.py** generates recommendations:
   - Examines return reason distribution per SKU
   - Applies decision tree to classify problem type (sizing, quality, listing, etc.)
   - Generates plain-English recommendation text

4. Results are stored in **Streamlit session state** as DataFrames.

### On page navigation:

Pages read from session state — no re-querying MongoDB.

## Design Decisions

### Why Streamlit?
- Users are non-technical. Streamlit gives us a hosted URL with zero frontend knowledge.
- Python-native — same language as the analysis engine, no API layer needed.
- Built-in caching, session state, and "rerun" mechanics.

### Why compute baselines ourselves?
- The existing `ReturnRatesByCategory` and `ChannelReturnRates` collections are static snapshots.
- We need baselines that respect the user's selected time window.
- We need baselines that only count Hiccup-owned products.

### Why exclude last 7 days of orders?
- Orders placed in the last week likely haven't been delivered yet.
- Including them inflates the denominator (sold units) without giving customers time to initiate returns.
- This would artificially deflate return rates for recent periods.

### Why top 200 SKUs?
- Showing everything overwhelms a non-technical user.
- 200 is enough to cover all actionable problems while keeping the page manageable.
- Sorted by severity score, so the worst problems are always visible.

### Why "winners"?
- The team takes actions (reviews sizing, contacts suppliers, updates listings).
- Without feedback on what's working, they can't learn or prioritize.
- Showing improved SKUs reinforces good behavior and builds trust in the tool.
