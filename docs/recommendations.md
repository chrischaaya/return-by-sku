# Recommendation Engine

## Principle
Every flagged item gets a recommendation. The recommendation must:
1. State the **problem** in one line
2. Explain the **likely cause**
3. Suggest a **specific action**

No raw numbers without context. No "investigate further" without guidance on what to look for.

---

## Decision Tree

The recommender evaluates conditions in order. First match wins.

### 1. Sizing Issue (concentrated in small sizes)
**Condition:**
- `size_concentration_index > 1.5`
- Top returning sizes are XS, S, or S/M
- `TOO_SMALL` is among top 2 reasons (if reason data available)

**Output:**
```
Problem: High returns concentrated in smaller sizes (XS, S).
Likely cause: Product runs small — customers ordering their usual size find it too tight.
Action: Review the spec sheet and actual measurements for this SKU. Compare against
size chart. Consider adding "runs small — order one size up" to the product listing,
or adjust measurements with the supplier for next production run.
```

### 2. Sizing Issue (concentrated in large sizes)
**Condition:**
- `size_concentration_index > 1.5`
- Top returning sizes are XL, XXL, or 3XL+
- `TOO_LARGE` is among top 2 reasons (if reason data available)

**Output:**
```
Problem: High returns concentrated in larger sizes (XL, XXL).
Likely cause: Product runs large — customers find it too loose or oversized.
Action: Review the spec sheet and actual measurements. Consider adding "runs large —
order one size down" to the listing, or tighten measurements with the supplier.
```

### 3. Sizing Issue (general / mixed)
**Condition:**
- `size_concentration_index > 1.5`
- No clear small-vs-large pattern
- OR both TOO_SMALL and TOO_LARGE are significant

**Output:**
```
Problem: Return rates vary significantly across sizes.
Likely cause: Inconsistent sizing — some sizes run true while others don't.
Action: Check measurement consistency across the size range with the supplier.
The size grading (increments between sizes) may be off. Request a measurement
check on the problematic sizes: {list_anomaly_sizes}.
```

### 4. Quality / Defect Issue
**Condition:**
- `DEFECTIVE_PRODUCT` reason concentration > 0.30
- OR `DEFECTIVE_PRODUCT` is top reason AND return rate > baseline * 1.5

**Output:**
```
Problem: Significant share of returns cite product defects.
Likely cause: Manufacturing quality issue from supplier {supplier_name}.
Action: Pull a sample from current stock and inspect. If defects confirmed,
raise with {supplier_name} immediately. Consider holding stock from sale until
quality is verified. Check if this is a single batch issue or recurring.
```

### 5. Listing / Expectation Mismatch
**Condition:**
- `EXPECTATION_MISMATCH` reason concentration > 0.35
- OR `EXPECTATION_MISMATCH` is top reason AND return rate > baseline * 1.3

**Output:**
```
Problem: Customers say the product doesn't match what they expected.
Likely cause: Product photos, description, or color representation may be misleading.
Action: Compare product listing photos against the actual product. Check: Does the
color look accurate? Do photos show the true fit and fabric texture? Is the description
accurate about material, thickness, and stretch? Update listing where needed.
```

### 6. High Return Rate, No Clear Single Cause
**Condition:**
- `return_rate > category_baseline * 1.5`
- `reason_concentration < 0.35` (no dominant reason)
- `size_concentration_index < 1.5` (no sizing pattern)

**Output:**
```
Problem: Return rate is {rate}% vs. category average of {baseline}%.
No single dominant cause identified — returns are spread across multiple reasons.
Action: This SKU needs a manual review. Check: (1) Are customer reviews mentioning
specific issues? (2) Is the product priced appropriately for its quality level?
(3) Is this product being promoted on channels where fit expectations differ?
Consider running a small test: hold this SKU from one channel and monitor if
overall returns improve.
```

### 7. Supplier-Level Pattern
**Condition:**
- Supplier's average return rate across multiple SKUs > category baseline * 1.3
- At least 3 SKUs from this supplier are flagged

**Output:**
```
Problem: Supplier {name} has elevated return rates across multiple products
in {category}.
Likely cause: Systematic production quality or sizing inconsistency.
Action: Schedule a supplier review meeting. Bring data: {n} SKUs affected,
average return rate {rate}% vs. category norm {baseline}%. Request corrective
action plan. If pattern continues, consider alternative suppliers for new orders.
```

### 8. Improving SKU ("Winner")
**Condition:**
- `trend_direction == IMPROVING`
- `improvement_score` in top 20

**Output:**
```
Good news: Return rate dropped from {prev}% to {current}% ({delta} improvement).
This is one of the most improved SKUs this period.
Status: Whatever action was taken is working. No further action needed unless
rate is still above category average ({baseline}%).
```

### 9. Worsening SKU
**Condition:**
- `trend_direction == WORSENING`
- `trend > 0.05` (more than 5 percentage points worse)

**Output:**
```
Warning: Return rate increased from {prev}% to {current}% in the last period.
Action: Investigate what changed. New production batch? New channel listing?
Seasonal fit issues? If this SKU was previously stable, the change likely
correlates with a specific event.
```

### 10. Fallback
**Condition:** None of the above matched, but SKU is in the flagged list.

**Output:**
```
Return rate is {rate}% (category average: {baseline}%).
Reason data: {available/not available for this channel}.
Action: Review product page and recent customer feedback.
Monitor for the next reporting period.
```

---

## Supplier Scorecard Recommendations

Supplier-level recommendations aggregate SKU-level signals:

| Condition | Recommendation |
|---|---|
| >50% of supplier's SKUs have sizing issues | "Sizing standards need review. Multiple products run small/large. Request measurement audit." |
| >30% of supplier's returns cite defects | "Quality control issue. Request factory inspection or tighter QC on incoming stock." |
| Return rate improving across supplier's SKUs | "Positive trend. Whatever improvements were made are working. Continue monitoring." |
| Return rate worsening | "Deteriorating quality. Prioritize for supplier review." |

---

## Category Overview Recommendations

Category-level recommendations are broader:

| Condition | Recommendation |
|---|---|
| Category above baseline on all channels | "Category-wide issue — likely inherent to product type. Review sizing standards for entire category." |
| Category above baseline on specific channel | "Channel-specific issue — may be customer demographic or listing quality on {channel}." |
| Category improving | "Returns declining in this category. Continue current approach." |
