# Return by SKU — Investigation Tool

## Purpose
Operational dashboard for a non-technical team to reduce product return rates in fashion e-commerce.
Two core workflows: investigate problematic products (Needs Attention) and track impact of actions taken (Action Tracking).

## Tech Stack
- **Python 3.9+** / Streamlit 1.42+
- **MongoDB**: hiccup-app (orders, returns, products), hiccup-ff (POs), hiccup-tools (settings, actions cache), scripts (TrendyolReviewStats)
- **Plotly** for action tracking graphs
- **Anthropic API** for sidebar AI chat
- **Google OAuth** (Streamlit native OIDC) — restricted to @hiccup.com

## Authentication
- Google OAuth via Streamlit's native OIDC (requires Authlib)
- Only @hiccup.com domain emails allowed (validated server-side)
- `st.user.email` is used as `actor` on all write operations
- Config: `.streamlit/secrets.toml` under `[auth]` and `[auth.google]`

## Quick Start
```bash
cd "/Users/Chris/Claude/sessions/projects/return by sku"
pip install -r requirements.txt
streamlit run dashboard/app.py
```

## Project Structure
```
config.py                 # Thresholds, connection, excluded channels (dynamic from MongoDB)
migrate.py                # One-time migration script (collection renames + backfill)
engine/
  connection.py           # MongoDB connection singleton (hiccup-app)
  pipelines.py            # All MongoDB aggregation pipelines
  analyzer.py             # Joins returns+orders, computes metrics, baselines
  tracking.py             # Action tracking: rolling return rates, PO lookup, badges
  recommender.py          # Size-level and SKU-level action recommendations
  actions.py              # SkuActions CRUD (hiccup-tools.returns.SkuActions)
  cache.py                # DataFrame cache in MongoDB (hiccup-tools.returns.DataCache)
  settings.py             # Settings CRUD (hiccup-tools.returns.Settings)
dashboard/
  app.py                  # Streamlit entry point — all UI
  chat_context.md         # Business context for AI chat
docs/                     # Architecture, data model, metrics, specs
```

## Tabs
1. **Needs Attention** — all products with return issues. Cards with size breakdown, return reasons, customer fit, reviews.
2. **Action Tracking** — split layout: product list (left) + return rate graph (right). Timeline of actions, PO markers, Resolved/New Action CTAs.
3. **Parked** — products marked "no action possible".

## Data Rules (CRITICAL)
1. Return rates from `CustomerReturns` + `Orders` collections
2. Return statuses counted: `ACCEPTED`, `PENDING`, `REJECTED`
3. Order statuses counted: `DISPATCHED`, `DELIVERED`, `PROCESSING`
4. Only `merchantKey: "hiccup"` products (via skuPrefix from Products)
5. Excluded channels: configurable in settings (stored in hiccup-tools.returns.Settings)
6. **Returns use `date` field** (not `createdOn` — `createdOn` is unreliable due to bulk Trendyol syncs)
7. **Action tracking returns grouped by ORDER date** — uses `$lookup` on `orderId` to get original order `createdOn`. A return counts on the day its order was placed, not when the return was filed.
8. Return reason: `items.claim.reasonCode` first, fall back to `items.claim.reasonKey`
9. Customer reviews: `originalComment` preferred over `comments` (shows original language)
10. Product review stats in card view: from `scripts.TrendyolReviewStats` (hiccupStats → merchantStats fallback)
11. Fast delivery channels (trendyol, hepsiburada): 7-day order lag. Others: 14 days. Both respect excluded channels list.
12. Action tracking graph: 7-day rolling average, excludes last 7 days, data from Jan 1 of current year.

## MongoDB Collections Used

| Collection | Database | Purpose |
|---|---|---|
| Orders | hiccup-app | Sales data (denominator) |
| CustomerReturns | hiccup-app | Return data (numerator) — use `date` field |
| Products | hiccup-app | Product metadata, skuPrefixes, productManager |
| ProductReviews | hiccup-app | Per-size reviews, fit data, comments |
| ProductStocks | hiccup-app | Parkpalet warehouse stock levels |
| TrendyolReviewStats | scripts | Product-level review counts (for card view) |
| SupplierProductOrders | hiccup-ff | PO data (creation, receipt, per-size quantities) |
| returns.SkuActions | hiccup-tools | Action tracking state + history |
| returns.DataCache | hiccup-tools | Cached DataFrames (compressed) |
| returns.Settings | hiccup-tools | App settings (thresholds, channels, lags) |

### hiccup-tools naming convention
All collections in hiccup-tools are prefixed with the tool name: `returns.*` for this tool.
Future tools should follow the same pattern (e.g., `pricing.*`, `inventory.*`).

## Settings (stored in hiccup-tools.returns.Settings)
- `filter_threshold` (default 0.0) — which products appear in Needs Attention. 0 = all.
- `problematic_threshold` (default 1.3) — sizes above this highlighted red.
- `min_recent_sales_per_size` (default 10) — minimum lifetime sales for a size to qualify.
- `excluded_channels` — channels excluded from all calculations.
- `fast_delivery_lag_days` (default 7), `slow_delivery_lag_days` (default 14)

## Action Tracking Data Model (hiccup-tools.returns.SkuActions)
```javascript
{
  skuPrefix: "MBAJ1ZFU01",        // UNIQUE INDEX
  status: "tracking",              // tracking | resolved | no_action | reverted
  actionSummary: "Latest action text",
  createdOn: ISODate(),
  updatedOn: ISODate(),
  overallRateAtAction: 0.21,
  actions: [                       // Full history, append-only
    {summary: "...", date: ISODate(), overallRate: 0.21, actor: "chris"},
  ],
  statusHistory: [                 // Every status transition, append-only
    {from: null, to: "tracking", date: ISODate(), actor: "chris"},
    {from: "tracking", to: "resolved", date: ISODate(), actor: "chris"},
  ]
}
```

### Status lifecycle
- `tracking` → shown in Action Tracking tab, excluded from Needs Attention
- `resolved` → removed from Action Tracking, NOT excluded from Needs Attention (can reappear)
- `no_action` → shown in Parked tab, excluded from Needs Attention
- `reverted` → removed from all tabs, returns to Needs Attention (soft delete — document preserved)

### Indexes
- `skuPrefix` — unique
- `status` — regular

### Design rules
- **No hard deletes.** Reverting sets status to `reverted`, preserving full history.
- **All writes record actor.** The logged-in user's email prefix (e.g., "chris") is stored on actions and status transitions.
- **statusHistory is append-only.** Every status change is recorded with from/to/date/actor.

## Deployment
- GitHub: `chrischaaya/return-by-sku` (main branch)
- Streamlit Cloud: auto-deploys from main
- Local: `streamlit run dashboard/app.py` (port 8501)
- **Migration:** Run `python migrate.py` once before first deploy with new code
