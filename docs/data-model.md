# Data Model

## Source Collections

### CustomerReturns
The primary source for return events. Each document is a return request containing one or more items.

**Key fields used:**
| Field | Type | Usage |
|---|---|---|
| `createdOn` | Date | When the return was initiated. **Only reliable date field.** |
| `salesChannel` | String | Channel key (e.g. `trendyol`, `emag`). Used for filtering. |
| `items[]` | Array | Line items in this return. We unwind and analyze per-item. |
| `items[].sku` | String | Full SKU including size suffix (e.g. `MDMCWLFD060C`) |
| `items[].skuPrefix` | String | SKU without size (e.g. `MDMCWLFD06`). Groups all sizes of same product. |
| `items[].size` | String | Size label (e.g. `S`, `M`, `L`, `XL`, `S/M`) |
| `items[].name` | String | Product name in English |
| `items[].status` | String | Item-level status. **Only count `ACCEPTED` and `PENDING`.** |
| `items[].claim.reasonCode` | String | Mapped return reason (primary field). |
| `items[].claim.reasonKey` | String | Fallback return reason (used when reasonCode is absent). |
| `items[].claim.channelReason` | String | Raw reason text from the channel (human-readable). |
| `items[].merchantKey` | String | `hiccup` for Lykia's own products. |

**Item status values:**
- `ACCEPTED` — return accepted, count this
- `PENDING` — return in progress, count this
- `CANCELLED` — aborted, exclude
- `REJECTED` — refused, exclude
- `NOT_DELIVERED` — customer never shipped, exclude
- `NOT_RECEIVED_IN_RETURN` — lost in transit, exclude

**Date warning:** `updatedOn` was bulk-modified on 2026-04-16 and is unreliable. Always use `createdOn`.

### Orders
Sales data — provides the denominator for return rate calculations.

**Key fields used:**
| Field | Type | Usage |
|---|---|---|
| `createdOn` | Date | Order creation date |
| `salesChannel` | String | Channel key |
| `country` | String | Customer country |
| `lineItems[]` | Array | Ordered items. We unwind and count per-item. |
| `lineItems[].sku` | String | Full SKU |
| `lineItems[].skuPrefix` | String | SKU prefix (groups sizes) |
| `lineItems[].size` | String | Size |
| `lineItems[].category` | String | Category path (e.g. `women/clothing/dresses/midi`) |
| `lineItems[].merchantKey` | String | Filter to `hiccup` only |
| `lineItems[].quantity` | Number | Units ordered (usually 1) |
| `status` | String | Order status — exclude `CANCELLED` orders |

### Products
Product catalog — provides metadata for enriching SKU-level analysis.

**Key fields used:**
| Field | Type | Usage |
|---|---|---|
| `familySku` | String | Product family identifier |
| `category` | String | Category path |
| `cat` | Object | Parsed category: `cat.level1` through `cat.level4` |
| `merchantKey` | String | Filter to `hiccup` |
| `merchantName` | String | Always "Hiccup" for our products |
| `productVariants[]` | Array | Color variants |
| `productVariants[].skuPrefix` | String | Variant SKU prefix |
| `productVariants[].suppliers[]` | Array | Supplier info per variant |
| `productVariants[].suppliers[].name` | String | Supplier name (e.g. "Dilvin", "Sobe") |
| `productVariants[].suppliers[].id` | String | Supplier ID |
| `name.en` | String | Product name in English |
| `sizes` | Array | Available sizes |
| `fitType` | String | Fit type (e.g. "regular", "slim") — can be null |

---

## Computed DataFrames

The analysis engine produces these DataFrames, stored in Streamlit session state:

### `df_sku` — SKU-level analysis (main table)
| Column | Type | Description |
|---|---|---|
| `sku_prefix` | str | SKU prefix (groups all sizes) |
| `product_name` | str | English product name |
| `category_l3` | str | Category level 3 (e.g. "dresses") |
| `category_l4` | str | Category level 4 (e.g. "midi") |
| `supplier_name` | str | Primary supplier |
| `total_sold` | int | Units sold in time window |
| `total_returned` | int | Units returned (ACCEPTED + PENDING) |
| `return_rate` | float | total_returned / total_sold |
| `category_baseline` | float | Median return rate for same category_l3 |
| `deviation` | float | return_rate - category_baseline |
| `deviation_pct` | float | deviation / category_baseline (percentage above) |
| `severity_score` | float | deviation * sqrt(total_sold) — prioritizes volume |
| `top_reason` | str | Most common return reason code |
| `top_reason_pct` | float | Share of returns with that reason |
| `has_sizing_issue` | bool | Size concentration index > threshold |
| `problem_type` | str | SIZING / QUALITY / LISTING / MIXED / UNKNOWN |
| `recommendation` | str | Plain English action |
| `channels` | list[str] | Channels where this SKU was returned |
| `prev_return_rate` | float | Return rate in previous comparison period |
| `trend` | float | current return_rate - prev_return_rate |
| `trend_direction` | str | IMPROVING / WORSENING / STABLE |

### `df_sku_size` — Size-level breakdown
| Column | Type | Description |
|---|---|---|
| `sku_prefix` | str | Parent SKU |
| `size` | str | Size label |
| `sold` | int | Units sold |
| `returned` | int | Units returned |
| `return_rate` | float | Size-specific return rate |
| `sku_avg_rate` | float | Overall SKU return rate |
| `is_anomaly` | bool | This size's rate is significantly above SKU average |

### `df_supplier` — Supplier scorecard
| Column | Type | Description |
|---|---|---|
| `supplier_name` | str | Supplier name |
| `total_skus` | int | Number of SKUs from this supplier |
| `total_sold` | int | Total units sold |
| `total_returned` | int | Total units returned |
| `return_rate` | float | Overall return rate |
| `worst_category` | str | Category with highest return rate |
| `top_reason` | str | Most common return reason |
| `recommendation` | str | Plain English action |

### `df_category` — Category overview
| Column | Type | Description |
|---|---|---|
| `category_l3` | str | Category level 3 |
| `channel` | str | Sales channel |
| `sold` | int | Units sold |
| `returned` | int | Units returned |
| `return_rate` | float | Return rate |
| `baseline` | float | Global baseline for this category |
| `status` | str | BELOW_BASELINE / AT_BASELINE / ABOVE_BASELINE |

---

## Return Reason Mapping

Reasons are grouped into action categories:

| Group | Codes | Implication |
|---|---|---|
| **Sizing** | `TOO_LARGE`, `TOO_SMALL` | Product measurements or labeling issue |
| **Quality** | `DEFECTIVE_PRODUCT` | Manufacturing defect, supplier quality issue |
| **Listing** | `EXPECTATION_MISMATCH` | Photos/description don't match reality |
| **Logistics** | `NOT_DELIVERED`, `DELIVERY_ISSUE`, `WRONG_PRODUCT` | Fulfillment problem, not product problem |
| **Neutral** | `NO_LONGER_WANTED`, `SURPLUS_PRODUCT`, `OTHER` | Customer-side, not actionable |

For the dashboard, **Sizing + Quality + Listing** are actionable. Logistics and Neutral are shown but not prioritized.
