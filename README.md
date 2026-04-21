# Return Rate Dashboard

An operational dashboard for Lykia Fashion's ops team to identify, diagnose, and act on product return problems.

## What it does

- Shows the **top return-rate problems** across SKUs, suppliers, and categories
- Explains **why** returns are happening (sizing, quality, listing mismatch)
- Recommends **specific actions** the team should take
- Tracks **evolution** over time so the team can see if their actions are working
- Highlights **"winners"** — SKUs that improved after intervention

## Who it's for

Non-technical operations team. Every screen is designed to be read without data expertise.

## Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Run the dashboard
streamlit run dashboard/app.py
```

The dashboard will open at `http://localhost:8501`.

## How data flows

```
MongoDB (hiccup-prod, read-only)
    │
    ├── CustomerReturns  → return events per item
    ├── Orders           → sales events (denominator)
    └── Products         → product metadata, supplier info, categories
    │
    ▼
Python Analysis Engine
    │
    ├── Aggregation pipelines compute return rates at SKU/size/supplier/category level
    ├── Anomaly detection flags deviations from category baselines
    ├── Trend analysis compares current vs previous period
    └── Recommender generates plain-English actions
    │
    ▼
Streamlit Dashboard
    │
    ├── Executive Summary — top problems at a glance
    ├── SKU Deep-Dive — top 200 sellers with return analysis
    ├── Supplier Scorecard — supplier-level quality signals
    └── Category Overview — category × channel heatmap
```

## Data freshness

Click "Update Data" in the dashboard sidebar to refresh from MongoDB.
Data excludes the most recent 7 days of orders (items may not yet be delivered).

## Configuration

All thresholds and settings are in `config.py`:
- Time window (default: 90 days)
- Minimum volume thresholds
- Excluded channels
- Anomaly detection parameters
