# Metrics Definitions

Every metric used in the dashboard, precisely defined.

---

## Core Metrics

### Return Rate
```
return_rate = returned_units / sold_units
```
- **returned_units**: count of items in `CustomerReturns` where `items.status` IN (`ACCEPTED`, `PENDING`) and `items.merchantKey` = `hiccup`
- **sold_units**: sum of `lineItems.quantity` in `Orders` where `lineItems.merchantKey` = `hiccup` and order `status` != `CANCELLED`
- Both filtered to the selected time window
- Orders exclude the most recent 7 days (delivery lag)
- Returns are matched by `createdOn` within the time window

### Category Baseline
```
category_baseline = median(return_rate) across all SKUs in the same category_l3
```
- Computed per `cat.level3` (e.g. "dresses", "knitwear", "tops-blouses-tee")
- Only includes SKUs meeting the minimum volume threshold (20 units)
- Recalculated for each time window selection

### Deviation
```
deviation = sku_return_rate - category_baseline
deviation_pct = deviation / category_baseline
```
- Positive = worse than average, negative = better than average
- A SKU is flagged when `deviation_pct > 0.30` (30% above baseline)

### Severity Score
```
severity_score = deviation * sqrt(total_sold)
```
- Weights the deviation by volume: a 5% deviation on a 1,000-unit SKU matters more than a 20% deviation on a 25-unit SKU
- Used to sort the "Top Problems" list
- Square root dampens volume so mega-sellers don't always dominate

---

## Size Analysis Metrics

### Size Return Rate
```
size_return_rate = returned_units_for_size / sold_units_for_size
```
- Computed per (sku_prefix, size) pair
- Only shown when `sold_units_for_size >= 20` (MIN_SIZE_VOLUME)

### Size Concentration Index
```
size_concentration_index = max(size_return_rates) / mean(size_return_rates)
```
- Measures how uneven return rates are across sizes
- `> 1.5` suggests a sizing problem concentrated in specific sizes
- `~1.0` means returns are evenly distributed across sizes (not a sizing issue)

### Size Anomaly Flag
```
is_size_anomaly = (size_return_rate > sku_avg_return_rate * 1.5)
                  AND (size_volume >= MIN_SIZE_VOLUME)
```
- Flags individual sizes that are significantly worse than the SKU average

---

## Return Reason Metrics

### Top Reason
```
top_reason = mode(items.claim.reasonCode) for a given SKU
```
- Falls back to `items.claim.reasonKey` when `reasonCode` is null
- Only computed for channels with reason data

### Reason Concentration
```
reason_concentration = count(top_reason) / total_returned_items
```
- If `> 0.40`, the SKU has a clear single-cause problem
- If `< 0.40`, returns are spread across multiple reasons (harder to diagnose)

### Actionable Reason Rate
```
actionable_reason_rate = count(SIZING + QUALITY + LISTING reasons) / total_returned_items
```
- Measures what percentage of returns could be reduced through product/listing changes
- Logistics and Neutral reasons are not actionable from a product perspective

---

## Trend Metrics

### Period-over-Period Return Rate Change
```
trend = current_period_return_rate - previous_period_return_rate
```
- Default: current 30 days vs. previous 30 days
- Positive = worsening, negative = improving

### Trend Direction
```
if abs(trend) < 0.03:  STABLE
elif trend < 0:         IMPROVING
else:                   WORSENING
```
- 3 percentage point threshold avoids noise from small fluctuations

### Improvement Score (for "Winners" view)
```
improvement_score = (prev_return_rate - current_return_rate) * sqrt(current_sold)
```
- Positive = improved. Higher = bigger improvement on higher volume.
- Used to rank "winners" — SKUs where the team's actions are working

---

## Supplier Metrics

### Supplier Return Rate
```
supplier_return_rate = sum(returned across all supplier SKUs) / sum(sold across all supplier SKUs)
```
- Weighted by volume, not a simple average of per-SKU rates

### Supplier vs. Category Deviation
```
supplier_deviation = supplier_return_rate_in_category - category_baseline
```
- Computed per (supplier, category_l3) pair
- A supplier may be fine in "bags" but terrible in "dresses"

---

## Category Metrics

### Category Return Rate (per channel)
```
category_channel_rate = returned_in_category_on_channel / sold_in_category_on_channel
```
- Matrix of category × channel, each cell is a return rate

### Category Status
```
if rate < baseline * 0.85:   BELOW_BASELINE (good)
elif rate < baseline * 1.15: AT_BASELINE (normal)
else:                        ABOVE_BASELINE (problem)
```
- 15% tolerance band around the global baseline
