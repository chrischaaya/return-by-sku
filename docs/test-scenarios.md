# Test Scenarios

Scenarios to validate that the analysis engine produces correct, actionable output.

---

## Scenario 1: Classic Sizing Problem (runs small)

**Setup:**
- SKU `TEST-SIZING-SM` in category "dresses/midi"
- Sold: S=30, M=40, L=35, XL=25 (total 130)
- Returned: S=18, M=8, L=5, XL=3 (total 34)
- Return rate: S=60%, M=20%, L=14%, XL=12% (overall 26%)
- Category baseline: 18%
- Top reason on S returns: TOO_SMALL (14 of 18)

**Expected output:**
- `return_rate`: 0.26
- `deviation`: +0.08 (above baseline)
- `size_concentration_index`: > 2.0 (S is 60% vs avg ~26%)
- `has_sizing_issue`: True
- `problem_type`: SIZING
- Recommendation mentions "runs small", suggests reviewing spec sheet
- S flagged as anomaly size

---

## Scenario 2: Quality Issue from Supplier

**Setup:**
- SKU `TEST-QUALITY-01` in category "knitwear/sweaters"
- Sold: 80 total across sizes
- Returned: 28 total
- Return rate: 35% (category baseline: 15%)
- Return reasons: DEFECTIVE_PRODUCT = 16, EXPECTATION_MISMATCH = 6, OTHER = 6
- Supplier: "TestSupplier"
- Size distribution: roughly even

**Expected output:**
- `return_rate`: 0.35
- `severity_score`: high (large deviation * decent volume)
- `has_sizing_issue`: False (sizes are even)
- `top_reason`: DEFECTIVE_PRODUCT
- `reason_concentration`: 0.57 (> 0.40 threshold)
- `problem_type`: QUALITY
- Recommendation mentions defects, names the supplier, suggests QC inspection

---

## Scenario 3: Listing Mismatch

**Setup:**
- SKU `TEST-LISTING-01` in category "tops-blouses-tee/t-shirts"
- Sold: 60 total
- Returned: 18 total (30%)
- Category baseline: 19%
- Return reasons: EXPECTATION_MISMATCH = 10, NO_LONGER_WANTED = 5, OTHER = 3
- Size distribution: even

**Expected output:**
- `problem_type`: LISTING
- `top_reason`: EXPECTATION_MISMATCH
- `reason_concentration`: 0.56
- Recommendation mentions photos/description accuracy

---

## Scenario 4: High Returns, No Clear Cause

**Setup:**
- SKU `TEST-MIXED-01` in category "co-ords/two-pieces"
- Sold: 50 total
- Returned: 15 total (30%)
- Category baseline: 17%
- Return reasons: TOO_SMALL=4, EXPECTATION_MISMATCH=4, NO_LONGER_WANTED=4, OTHER=3
- Size distribution: roughly even

**Expected output:**
- `problem_type`: MIXED or UNKNOWN
- No single reason > 0.40
- `size_concentration_index` < 1.5
- Recommendation suggests manual review, lists checklist of things to examine

---

## Scenario 5: SKU Below Minimum Volume

**Setup:**
- SKU `TEST-LOWVOL-01`
- Sold: 8 total
- Returned: 4 total (50%)

**Expected output:**
- SKU does NOT appear in the flagged list (below MIN_SKU_VOLUME of 20)
- Not included in category baseline calculation

---

## Scenario 6: Improving SKU ("Winner")

**Setup:**
- SKU `TEST-WINNER-01`
- Previous 30 days: sold 60, returned 21 (35%)
- Current 30 days: sold 55, returned 8 (15%)
- Category baseline: 20%

**Expected output:**
- `trend_direction`: IMPROVING
- `trend`: -0.20 (20 percentage points better)
- `improvement_score`: high
- Appears in "Winners" view
- Recommendation says actions are working

---

## Scenario 7: Worsening SKU

**Setup:**
- SKU `TEST-WORSE-01`
- Previous 30 days: sold 50, returned 6 (12%)
- Current 30 days: sold 45, returned 14 (31%)
- Category baseline: 18%

**Expected output:**
- `trend_direction`: WORSENING
- `trend`: +0.19
- Recommendation flags the deterioration, suggests investigating what changed (new batch, new channel)

---

## Scenario 8: Supplier with Multiple Bad SKUs

**Setup:**
- Supplier "BadSupplierCo" has 5 SKUs in "dresses":
  - SKU-A: 30% return rate
  - SKU-B: 28% return rate
  - SKU-C: 35% return rate
  - SKU-D: 22% return rate (near baseline)
  - SKU-E: 33% return rate
- Category baseline for dresses: 20%
- 4 of 5 SKUs are above baseline

**Expected output:**
- Supplier scorecard shows BadSupplierCo flagged
- Recommendation mentions systematic issue, suggests supplier review meeting
- Worst category: "dresses"

---

## Scenario 9: Channel Without Return Reasons

**Setup:**
- SKU `TEST-NOREASON-01` sold on Namshi
- Sold: 40, Returned: 14 (35%)
- No reason data available

**Expected output:**
- `top_reason`: null or "N/A"
- `problem_type`: UNKNOWN (can't diagnose without reasons)
- Recommendation acknowledges no reason data, suggests reviewing product page and customer feedback
- Dashboard shows "No reason data available for this channel" rather than empty charts

---

## Scenario 10: Excluded Channel (aboutYou)

**Setup:**
- SKU `TEST-EXCLUDED-01` has returns on aboutYou

**Expected output:**
- This SKU's aboutYou returns are NOT counted in any metric
- aboutYou does not appear in any channel dropdown or filter

---

## Validation Checklist

For each scenario, verify:
- [ ] Return rate calculation is correct (numerator / denominator)
- [ ] Category baseline is computed from qualifying SKUs only (volume >= 20)
- [ ] Deviation is calculated against the correct category
- [ ] Size-level anomalies are detected when present
- [ ] Correct problem type is assigned
- [ ] Recommendation text is appropriate and actionable
- [ ] Trend direction is correct (current vs previous period)
- [ ] Volume threshold is enforced (low-volume SKUs excluded)
- [ ] Excluded channels are not in any output
- [ ] Only merchantKey="hiccup" products are included
