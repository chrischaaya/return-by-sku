# Returns Overview Dashboard — Context & Decisions

## Goal

Replicate the Looker Studio return dashboard (3 views) as a standalone Streamlit app, using our project's stricter MongoDB-based data rules instead of the BigQuery `looker_reports.return_report` table.

## Looker Studio Dashboard (original)

**URL:** `https://datastudio.google.com/u/1/reporting/d1a3b9b4-8e79-4a12-88ee-d6d086e2a7e9/page/p_ving4d9akd`

### Data pipeline

```
MongoDB (hiccup-app)
  → Airbyte sync → BigQuery mongo_db.* tables (raw)
    → "ReturnReport" scheduled query (daily 06:00, europe-west2)
      → looker_reports.return_report (1.1M rows)
        → Looker Studio calculated fields → Dashboard
```

### Scheduled query SQL

The `ReturnReport` scheduled query writes to `looker_reports.return_report` and reads from:

| CTE | Source tables |
|---|---|
| `coupons` | `mongo_db.coupons` |
| `sales_base` | `mongo_db.product_level_orders` JOIN `mongo_db.orders` |
| `product_base` | `mongo_db.products_daily` JOIN `mongo_db.variants_daily` |
| `discount_base` | `mongo_db.products_daily` JOIN `mongo_db.variants_daily` |
| `model_code_base` | `mongo_db.variants_daily` |
| `return_base` | `mongo_db.returns` |

Key logic:
- Revenue = `item_subtotal / exchange_rate` (converts to USD)
- Return reason keys are mapped to clean English labels (e.g. `SMALLSIZE` → `TooSmall`)
- `returned_quantity` is capped at `sales_volume` for DELIVERED orders
- Excludes `vogaCloset` channel
- No delivery lag, no merchant filter, includes all return statuses

### Dashboard views (3 screenshots)

**1. Historic Return Ratio** — monthly line chart
- X axis: months (format `24-M03`)
- Y axis: return ratio %
- Data labels on each point
- Filters: Month, Supplier, Category, Family SKU Color, Return Reason, Model, Sales Channel

**2. Supplier Return Breakdown** — table
- Columns: Supplier, Returned Quantity, Delivered Products, Return Ratio, Returned Amount, GMV, % Value of Return
- Sorted by Return Ratio descending
- Grand total row at bottom

**3. Category Return Breakdown** — table
- Same columns as supplier, grouped by category_level_1

## Our Streamlit version

### Data rules (CRITICAL — different from Looker)

These come from the Return by SKU project's `config.py` and `CLAUDE.md`:

1. **MongoDB direct** — reads from `CustomerReturns`, `Orders`, `Products` collections (not BigQuery)
2. **Hiccup products only** — filtered by `skuPrefix` from Products where `merchantKey = "hiccup"`
3. **Delisted SKU exclusion** — excludes variants with `delistedUntil` + specific delist reasons (poor customer feedback, high returns, being recreated, etc.)
4. **Return statuses**: `ACCEPTED`, `PENDING`, `REJECTED` only
5. **Order statuses**: `DISPATCHED`, `DELIVERED`, `PROCESSING`
6. **Excluded channels**: `aboutYou`, `vogaCloset` (configurable in MongoDB `hiccup-tools.Settings`)
7. **Delivery lag**: 7 days for fast channels (trendyol, hepsiburada), 14 days for others — applied to investigation tool data, NOT to the monthly trend chart
8. **Return reasons**: uses `items.claim.reasonCode` first, falls back to `items.claim.reasonKey`
9. **Date field**: always `createdOn`, never `updatedOn`

### Architecture

Standalone Streamlit app, separate from the investigation tool.

```
dashboard/overview.py     ← standalone entry point (port 8502)
dashboard/app.py          ← investigation tool (port 8501, unchanged)
engine/pipelines.py       ← shared MongoDB pipelines
engine/analyzer.py        ← shared analysis engine
engine/cache.py           ← shared pickle cache
```

### New pipeline functions added to `engine/pipelines.py`

```python
get_monthly_orders_summary()   # Monthly order totals, no delivery lag
get_monthly_returns_summary()  # Monthly return totals by createdOn month
get_revenue_by_sku()           # Revenue per skuPrefix in USD (via exchangeRate)
```

### Revenue calculation

Revenue is converted to USD in the MongoDB aggregation:
```
USD = subtotalAfterDiscount / (exchangeRate * 100)
```
Where:
- `subtotalAfterDiscount` is in minor currency units (cents/kuruş) on `Order.lineItems`
- `exchangeRate` on the Order document = local_currency_per_USD (e.g. 28.57 for TRY)
- Fallback: if exchangeRate is 0 or missing, divides by 100 only (assumes USD)

**Returned Amount** is approximated: `avg_unit_price_per_sku * returned_quantity` (since returns don't carry price data directly).

### Running

```bash
cd "sessions/projects/return by sku"

# Investigation tool (port 8501)
streamlit run dashboard/app.py

# Overview dashboard (port 8502)
streamlit run dashboard/overview.py --server.port 8502
```

### What's different from Looker

| Aspect | Looker Dashboard | Our Version |
|---|---|---|
| Data source | BigQuery (Airbyte sync) | MongoDB direct |
| Merchant filter | None | hiccup only |
| Return statuses | All | ACCEPTED, PENDING, REJECTED |
| Delivery lag | None | None (for overview) |
| Excluded channels | vogaCloset | aboutYou, vogaCloset |
| Delisted SKUs | Included | Excluded (specific reasons) |
| Revenue | `item_subtotal / exchange_rate` from BQ | `subtotalAfterDiscount / (exchangeRate * 100)` from MongoDB |
| Returned Amount | `selling_price * returned_quantity` per row | `avg_unit_price * returned_quantity` per SKU (approximation) |

### Files changed/created

- `engine/pipelines.py` — added 3 new functions at the end
- `dashboard/overview.py` — new standalone Streamlit app
- `dashboard/pages/1_overview.py` — deleted (was sub-page, moved to standalone)

### MongoDB connection

- Read-only: `claude-code-read-all` user against `hiccup-prod` (stored in `.streamlit/secrets.toml`)
- Settings write: `claude-hiccup-tools` user against `hiccup-tools` database

### BigQuery (reference only)

The BigQuery project is `hiccup-app-3b9a9`. All 38 scheduled queries live in `europe-west2` location. Service account: `umuts-service-account@hiccup-app-3b9a9.iam.gserviceaccount.com`.
