# Return by SKU — Dashboard Project

## Purpose
Operational dashboard that helps a non-technical team reduce product return rates in fashion e-commerce.
Not a data exploration tool — a **decision-making tool**. Every screen tells the user what's wrong, why, and what to do.

## Tech Stack
- **Python 3.11+** / Streamlit
- **MongoDB** (read-only against `hiccup-prod`)
- No frontend framework, no build step

## Quick Start
```bash
cd "/Users/Chris/Claude/sessions/projects/return by sku"
pip install -r requirements.txt
streamlit run dashboard/app.py
```

## Project Structure
```
config.py                 # Thresholds, connection, excluded channels
engine/
  connection.py           # MongoDB connection singleton
  pipelines.py            # Aggregation pipelines (returns + orders)
  analyzer.py             # Anomaly detection, scoring, trend analysis
  recommender.py          # Translates analysis → plain English actions
dashboard/
  app.py                  # Streamlit entry point + "Update Data" button
  pages/
    1_executive_summary.py
    2_sku_deep_dive.py
    3_supplier_scorecard.py
    4_category_overview.py
  components/
    insight_card.py       # Reusable problem→why→action card
    filters.py            # Date range, channel, category selectors
docs/                     # Architecture, data model, metrics, recommendations
tests/                    # Test scenarios with fixture data
```

## Data Rules (CRITICAL — do not change without discussion)
1. Return rates computed from `CustomerReturns` collection, NOT pre-computed tables
2. Only count items where `items.status` is `ACCEPTED` or `PENDING`
3. Only products with `merchantKey: "hiccup"` (Lykia's own inventory)
4. Exclude channels: `aboutYou`, `vogaCloset`
5. Exclude last 7 days of order data (delivery lag — items not yet deliverable)
6. Minimum 20 units sold per size for size-level flagging
7. Return reason: use `items.claim.reasonCode` first, fall back to `items.claim.reasonKey`
8. No grading analysis, no financial impact calculations
9. Use `createdOn` for all date logic — NEVER `updatedOn` (unreliable, bulk-touched)

## Channels with Return Reason Data
Full coverage: trendyol, fashiondays, fashiondaysBG, hepsiburada, emag, trendyolRO
Partial: hiccup (newer returns only)
None: namshi, debenhams, tiktokShop, amazonUS, amazonUK, allegro

## Build Commands
```bash
pip install -r requirements.txt          # Install dependencies
streamlit run dashboard/app.py           # Run dashboard locally
python -m pytest tests/ -v               # Run tests
```

## MongoDB
- Database: `hiccup-app`
- Connection: stored in `config.py` (read-only user)
- Key collections: `CustomerReturns`, `Orders`, `Products`, `ReturnReasons`, `Categories`, `SalesChannels`
