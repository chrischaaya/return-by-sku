# Supplier Performance Analysis
**Generated:** 2026-04-22 16:36 UTC

**Methodology:** All-time return rates from CustomerReturns (ACCEPTED/PENDING/REJECTED) vs Orders (DISPATCHED/DELIVERED/PROCESSING). Delivery lag excluded (7d fast channels, 14d slow). merchantKey=hiccup only. Channels excluded: aboutYou, vogaCloset.

## Executive Summary

**Data scope:** 57 suppliers with ≥1000 units sold, covering 792,864 units sold and 157,362 returned (19.8% overall).

- **CRITICAL:** 9 suppliers
- **CONCERNING:** 2 suppliers
- **MONITOR:** 12 suppliers
- **ACCEPTABLE:** 34 suppliers

### Top 5 Suppliers Requiring Immediate Attention

| # | Supplier | Assessment | Return Rate | Benchmark | Excess Returns | Confidence |
|---|----------|------------|-------------|-----------|----------------|------------|
| 1 | Kovesa | MONITOR | 22.0% | 17.1% (cat median) | ~5720 units | HIGH |
| 2 | Karaca | CRITICAL | 19.3% | 13.7% (cat median) | ~1224 units | HIGH |
| 3 | Dormina Tekstil | MONITOR | 17.9% | 13.7% (cat median) | ~1048 units | HIGH |
| 4 | Atay Moda | CONCERNING | 26.5% | 22.4% (cat median) | ~988 units | HIGH |
| 5 | S-CL Denim | CRITICAL | 41.8% | 29.7% (cat median) | ~925 units | MEDIUM |

### Top 5 Suppliers Performing Well

| # | Supplier | Return Rate | Benchmark | Below by | Volume | Confidence |
|---|----------|-------------|-----------|----------|--------|------------|
| 1 | SMF | 14.2% | 29.7% | -15.5pp | 2,351 sold | MEDIUM |
| 2 | Sobe | 10.5% | 24.1% | -13.6pp | 4,222 sold | MEDIUM |
| 3 | Zdn Jeans | 16.4% | 29.7% | -13.4pp | 11,398 sold | HIGH |
| 4 | Cream Rouge | 11.1% | 24.1% | -13.0pp | 2,077 sold | MEDIUM |
| 5 | Dilvin | 6.7% | 17.1% | -10.4pp | 3,335 sold | MEDIUM |

## Category Benchmarks

These are the reference rates used for all supplier comparisons.

| Category | Total Sold | Weighted Avg Return Rate | Weighted Median Return Rate |
|----------|-----------|-------------------------|----------------------------|
| dresses | 176,532 | 26.0% | 25.4% |
| tops-blouses-tee | 172,835 | 15.5% | 17.1% |
| bottoms | 166,968 | 22.0% | 22.4% |
| knitwear | 152,316 | 14.6% | 13.7% |
| denim | 58,653 | 27.0% | 29.7% |
| activewear | 22,744 | 9.3% | 9.2% |
| loungewear | 16,402 | 10.6% | 10.9% |
| co-ords | 14,005 | 20.2% | 24.1% |
| outerwear | 12,158 | 21.5% | 21.8% |
| jumpsuits-bodysuits | 7,271 | 23.1% | 26.9% |
| beachwear | 3,346 | 6.5% | 4.7% |
| suits | 1,951 | 23.0% | 26.4% |

## Detailed Supplier Assessments

Sorted by commercial impact (volume x excess return rate). Only suppliers with assessment of CRITICAL, CONCERNING, or MONITOR are detailed below.

### Kovesa — MONITOR

- **Volume:** 118,368 units sold, 26,017 returned, **22.0% return rate**
- **Primary category:** tops-blouses-tee (benchmark: 17.1% weighted median)
- **Deviation:** +4.8pp absolute, 28.2% relative
- **Confidence:** HIGH (415 SKUs total, 260 with ≥100 units)
- **Excess returns:** ~5720 units above what the category median would predict

**SKU Concentration:** 4.9% of volume from top SKU

**Issue Type:** SIZING
  - Too Small: 28.2% | Too Large: 31.0% | Quality: 26.5% | Other: 14.2%
  - Sizing pattern across SKUs: **MIXED_SIZING** (consistent across multiple products)

**Return Rate by Category:**

| Category | Sold | Return Rate | Benchmark (wt. median) | Deviation | Underperforming? |
|----------|------|-------------|------------------------|-----------|------------------|
| tops-blouses-tee | 46,848 | 17.1% | 17.1% | 0.0pp | no |
| dresses | 36,196 | 28.4% | 25.4% | +3.0pp | no |
| bottoms | 27,926 | 21.9% | 22.4% | -0.5pp | no |
| jumpsuits-bodysuits | 4,767 | 26.9% | 26.9% | 0.0pp | no |
| loungewear | 1,757 | 8.3% | 10.9% | -2.6pp | no |
| co-ords | 494 | 17.2% | 24.1% | -6.9pp | no |
| outerwear | 261 | 27.6% | 21.8% | +5.8pp | YES |

**Return Rate by Size:**

| Size | Sold | Returned | Return Rate |
|------|------|----------|-------------|
| XXL | 5,608 | 1,333 | 23.8% |
| XXS | 2,576 | 612 | 23.8% |
| XL | 15,893 | 3,666 | 23.1% |
| L | 22,180 | 4,965 | 22.4% |
| M | 32,081 | 6,953 | 21.7% |
| XS | 14,314 | 3,048 | 21.3% |
| S | 25,716 | 5,440 | 21.2% |

Size spread: 2.6pp (worst: XXL at 23.8%, best: S at 21.2%)

**Robustness Check — Remove worst SKU:**
  - Worst SKU: `M67NLW0A01` (High Waist Wide Leg Satin Palazzo Pants) — 189 sold, 63.0% return rate
  - Supplier rate drops from 22.0% to 21.9% without this SKU
  - Removing it only changes the rate by 0.1pp — the issue is spread across the supplier's range

**Recommended Action:**
  - No immediate action required. Re-evaluate in 30 days
  - If trend continues, escalate to CONCERNING

**Suggested Supplier Conversation:**
  > "FYI — we're monitoring return rates and your products are slightly above the category benchmark. No action needed now, but wanted to flag it."

---

### Karaca — CRITICAL

- **Volume:** 22,140 units sold, 4,266 returned, **19.3% return rate**
- **Primary category:** knitwear (benchmark: 13.7% weighted median)
- **Deviation:** +5.5pp absolute, 40.2% relative
- **Confidence:** HIGH (42 SKUs total, 37 with ≥100 units)
- **Excess returns:** ~1224 units above what the category median would predict

**SKU Concentration:** 28.8% of volume from top SKU

**Issue Type:** SIZING
  - Too Small: 14.7% | Too Large: 42.8% | Quality: 17.6% | Other: 24.9%
  - Sizing pattern across SKUs: **MIXED_SIZING** (consistent across multiple products)

**Return Rate by Category:**

| Category | Sold | Return Rate | Benchmark (wt. median) | Deviation | Underperforming? |
|----------|------|-------------|------------------------|-----------|------------------|
| knitwear | 22,140 | 19.3% | 13.7% | +5.5pp | YES |

**Return Rate by Size:**

| Size | Sold | Returned | Return Rate |
|------|------|----------|-------------|
| L | 7,350 | 1,493 | 20.3% |
| M | 7,779 | 1,508 | 19.4% |
| S | 7,011 | 1,265 | 18.0% |

Size spread: 2.3pp (worst: L at 20.3%, best: S at 18.0%)

**Robustness Check — Remove worst SKU:**
  - Worst SKU: `MBANH0LL01` (Button Detailed Polo Collar Knit Dress) — 356 sold, 32.0% return rate
  - Supplier rate drops from 19.3% to 19.1% without this SKU
  - Removing it only changes the rate by 0.2pp — the issue is spread across the supplier's range

**Recommended Action:**
  - Request updated size charts and grading specs from Karaca
  - Consider mandatory fit samples before next order

**Suggested Supplier Conversation:**
  > "We need to discuss the return performance on your products. Your return rate is 19.3%, which is +5.5pp above the category average of 13.7%. This represents approximately 1224 excess returned units. We need a concrete improvement plan."

---

### Dormina Tekstil — MONITOR

- **Volume:** 25,065 units sold, 4,492 returned, **17.9% return rate**
- **Primary category:** knitwear (benchmark: 13.7% weighted median)
- **Deviation:** +4.2pp absolute, 30.4% relative
- **Confidence:** HIGH (32 SKUs total, 32 with ≥100 units)
- **Excess returns:** ~1048 units above what the category median would predict

**SKU Concentration:** 7.6% of volume from top SKU

**Issue Type:** SIZING
  - Too Small: 25.9% | Too Large: 40.5% | Quality: 18.4% | Other: 15.2%
  - Sizing pattern across SKUs: **RUNS_LARGE** (consistent across multiple products)

**Return Rate by Category:**

| Category | Sold | Return Rate | Benchmark (wt. median) | Deviation | Underperforming? |
|----------|------|-------------|------------------------|-----------|------------------|
| knitwear | 25,065 | 17.9% | 13.7% | +4.2pp | no |

**Return Rate by Size:**

| Size | Sold | Returned | Return Rate |
|------|------|----------|-------------|
| S | 7,715 | 1,426 | 18.5% |
| L | 7,811 | 1,388 | 17.8% |
| M | 9,539 | 1,678 | 17.6% |

Size spread: 0.9pp (worst: S at 18.5%, best: M at 17.6%)

**Robustness Check — Remove worst SKU:**
  - Worst SKU: `MAXVEKPX06` (Thick Knit V-neck Sweater) — 151 sold, 33.8% return rate
  - Supplier rate drops from 17.9% to 17.8% without this SKU
  - Removing it only changes the rate by 0.1pp — the issue is spread across the supplier's range

**Recommended Action:**
  - No immediate action required. Re-evaluate in 30 days
  - If trend continues, escalate to CONCERNING

**Suggested Supplier Conversation:**
  > "FYI — we're monitoring return rates and your products are slightly above the category benchmark. No action needed now, but wanted to flag it."

---

### Atay Moda — CONCERNING

- **Volume:** 24,321 units sold, 6,436 returned, **26.5% return rate**
- **Primary category:** bottoms (benchmark: 22.4% weighted median)
- **Deviation:** +4.1pp absolute, 18.1% relative
- **Confidence:** HIGH (84 SKUs total, 55 with ≥100 units)
- **Excess returns:** ~988 units above what the category median would predict

**SKU Concentration:** 9.7% of volume from top SKU

**Issue Type:** SIZING
  - Too Small: 34.3% | Too Large: 28.7% | Quality: 25.7% | Other: 11.3%
  - Sizing pattern across SKUs: **MIXED_SIZING** (consistent across multiple products)

**Return Rate by Category:**

| Category | Sold | Return Rate | Benchmark (wt. median) | Deviation | Underperforming? |
|----------|------|-------------|------------------------|-----------|------------------|
| bottoms | 13,448 | 24.3% | 22.4% | +1.9pp | no |
| dresses | 7,941 | 31.3% | 25.4% | +5.9pp | no |
| tops-blouses-tee | 2,184 | 23.6% | 17.1% | +6.5pp | YES |
| outerwear | 335 | 22.1% | 21.8% | +0.3pp | no |
| loungewear | 219 | 25.1% | 10.9% | +14.2pp | YES |

**Return Rate by Size:**

| Size | Sold | Returned | Return Rate |
|------|------|----------|-------------|
| XXL | 1,283 | 414 | 32.3% |
| XL | 2,921 | 795 | 27.2% |
| M | 5,820 | 1,553 | 26.7% |
| L | 4,288 | 1,143 | 26.7% |
| XS | 3,473 | 911 | 26.2% |
| S | 5,641 | 1,406 | 24.9% |
| XXS | 869 | 209 | 24.1% |

Size spread: 8.2pp (worst: XXL at 32.3%, best: XXS at 24.1%)

**Robustness Check — Remove worst SKU:**
  - Worst SKU: `M3X1QWQS01` (Maxi Satin Skirt with Side Slit) — 3 sold, 66.7% return rate
  - Supplier rate drops from 26.5% to 26.5% without this SKU
  - Removing it only changes the rate by 0.0pp — the issue is spread across the supplier's range

**Recommended Action:**
  - Raise in next regular supplier meeting. Document the +4.1pp deviation from category benchmark

**Suggested Supplier Conversation:**
  > "We're seeing your return rate at 26.5% against a category benchmark of 22.4%. Can we review the sizing/quality feedback together and identify improvements?"

---

### S-CL Denim — CRITICAL

- **Volume:** 7,651 units sold, 3,200 returned, **41.8% return rate**
- **Primary category:** denim (benchmark: 29.7% weighted median)
- **Deviation:** +12.1pp absolute, 40.7% relative
- **Confidence:** MEDIUM (4 SKUs total, 4 with ≥100 units)
- **Excess returns:** ~925 units above what the category median would predict

**SKU Concentration:** 69.8% of volume from top SKU
  - WARNING: Concentrated. Top SKU: `M6RLJVMH01` (Straight Leg Denim Jeans), return rate 39.5%
  - Evaluate this SKU separately from the supplier

**Issue Type:** SIZING
  - Too Small: 49.0% | Too Large: 20.2% | Quality: 20.2% | Other: 10.6%
  - Sizing pattern across SKUs: **RUNS_SMALL** (consistent across multiple products)

**Return Rate by Category:**

| Category | Sold | Return Rate | Benchmark (wt. median) | Deviation | Underperforming? |
|----------|------|-------------|------------------------|-----------|------------------|
| denim | 7,651 | 41.8% | 29.7% | +12.1pp | YES |

**Return Rate by Size:**

| Size | Sold | Returned | Return Rate |
|------|------|----------|-------------|
| XL | 559 | 289 | 51.7% |
| XXL | 324 | 161 | 49.7% |
| M | 2,360 | 1,037 | 43.9% |
| L | 1,416 | 601 | 42.4% |
| XS | 526 | 205 | 39.0% |
| S | 1,959 | 737 | 37.6% |
| XXS | 507 | 170 | 33.5% |

Size spread: 18.2pp (worst: XL at 51.7%, best: XXS at 33.5%)
  - FLAG: Size spread >10pp — potential grading issue

**Robustness Check — Remove worst SKU:**
  - Worst SKU: `M6RLJVMH02` (Straight Leg Denim Jeans) — 1,968 sold, 48.9% return rate
  - Supplier rate drops from 41.8% to 39.4% without this SKU
  - Removing it only changes the rate by 2.4pp — the issue is spread across the supplier's range

**Recommended Action:**
  - Request updated size charts and grading specs from S-CL Denim
  - Consider mandatory fit samples before next order
  - Specific: Products consistently run small — request upsizing across the range

**Suggested Supplier Conversation:**
  > "We need to discuss the return performance on your products. Your return rate is 41.8%, which is +12.1pp above the category average of 29.7%. This represents approximately 925 excess returned units. We need a concrete improvement plan."

---

### Moda İkra — CRITICAL

- **Volume:** 10,701 units sold, 3,167 returned, **29.6% return rate**
- **Primary category:** bottoms (benchmark: 22.4% weighted median)
- **Deviation:** +7.2pp absolute, 32.1% relative
- **Confidence:** HIGH (49 SKUs total, 32 with ≥100 units)
- **Excess returns:** ~769 units above what the category median would predict

**SKU Concentration:** 8.7% of volume from top SKU

**Issue Type:** QUALITY
  - Too Small: 25.5% | Too Large: 30.0% | Quality: 21.9% | Other: 22.6%
  - Sizing pattern across SKUs: **MIXED_SIZING** (consistent across multiple products)

**Return Rate by Category:**

| Category | Sold | Return Rate | Benchmark (wt. median) | Deviation | Underperforming? |
|----------|------|-------------|------------------------|-----------|------------------|
| bottoms | 4,212 | 25.3% | 22.4% | +2.9pp | no |
| dresses | 2,929 | 39.0% | 25.4% | +13.6pp | YES |
| outerwear | 1,595 | 32.2% | 21.8% | +10.5pp | YES |
| tops-blouses-tee | 1,335 | 21.8% | 17.1% | +4.7pp | no |
| loungewear | 278 | 14.4% | 10.9% | +3.5pp | no |

**Return Rate by Size:**

| Size | Sold | Returned | Return Rate |
|------|------|----------|-------------|
| XXL | 175 | 76 | 43.4% |
| L | 2,237 | 734 | 32.8% |
| XL | 1,530 | 472 | 30.8% |
| XS | 1,187 | 342 | 28.8% |
| M | 3,322 | 920 | 27.7% |
| S | 2,171 | 600 | 27.6% |

Size spread: 15.8pp (worst: XXL at 43.4%, best: S at 27.6%)
  - FLAG: Size spread >10pp — potential grading issue

**Robustness Check — Remove worst SKU:**
  - Worst SKU: `M9QV3I1R02` (Asymmetrical Collar Bodycon Midi Dress with Slit) — 228 sold, 47.4% return rate
  - Supplier rate drops from 29.6% to 29.2% without this SKU
  - Removing it only changes the rate by 0.4pp — the issue is spread across the supplier's range

**Recommended Action:**
  - Arrange quality audit with Moda İkra. 22% of returns cite quality issues
  - Consider reducing order depth until quality improves

**Suggested Supplier Conversation:**
  > "We need to discuss the return performance on your products. Your return rate is 29.6%, which is +7.2pp above the category average of 22.4%. This represents approximately 769 excess returned units. We need a concrete improvement plan."

---

### ZRF Abiye — CRITICAL

- **Volume:** 4,017 units sold, 1,634 returned, **40.7% return rate**
- **Primary category:** dresses (benchmark: 25.4% weighted median)
- **Deviation:** +15.3pp absolute, 60.4% relative
- **Confidence:** MEDIUM (34 SKUs total, 11 with ≥100 units)
- **Excess returns:** ~615 units above what the category median would predict

**SKU Concentration:** 8.9% of volume from top SKU

**Issue Type:** SIZING
  - Too Small: 21.7% | Too Large: 41.6% | Quality: 26.3% | Other: 10.4%
  - Sizing pattern across SKUs: **RUNS_LARGE** (consistent across multiple products)

**Return Rate by Category:**

| Category | Sold | Return Rate | Benchmark (wt. median) | Deviation | Underperforming? |
|----------|------|-------------|------------------------|-----------|------------------|
| dresses | 4,017 | 40.7% | 25.4% | +15.3pp | YES |

**Return Rate by Size:**

| Size | Sold | Returned | Return Rate |
|------|------|----------|-------------|
| S | 881 | 371 | 42.1% |
| L | 772 | 325 | 42.1% |
| M | 854 | 358 | 41.9% |
| XL | 728 | 284 | 39.0% |
| XS | 782 | 296 | 37.9% |

Size spread: 4.3pp (worst: S at 42.1%, best: XS at 37.9%)

**Robustness Check — Remove worst SKU:**
  - Worst SKU: `M34J4PND01` (Open Back Bodycon Mini Dress with Baloon Hem Detail) — 332 sold, 55.7% return rate
  - Supplier rate drops from 40.7% to 39.3% without this SKU
  - Removing it only changes the rate by 1.4pp — the issue is spread across the supplier's range

**Recommended Action:**
  - Request updated size charts and grading specs from ZRF Abiye
  - Consider mandatory fit samples before next order
  - Specific: Products consistently run large — request downsizing across the range

**Suggested Supplier Conversation:**
  > "We need to discuss the return performance on your products. Your return rate is 40.7%, which is +15.3pp above the category average of 25.4%. This represents approximately 615 excess returned units. We need a concrete improvement plan."

---

### APS — CRITICAL

- **Volume:** 7,197 units sold, 2,163 returned, **30.1% return rate**
- **Primary category:** bottoms (benchmark: 22.4% weighted median)
- **Deviation:** +7.7pp absolute, 34.2% relative
- **Confidence:** HIGH (30 SKUs total, 8 with ≥100 units)
- **Excess returns:** ~550 units above what the category median would predict

**SKU Concentration:** 49.8% of volume from top SKU

**Issue Type:** SIZING
  - Too Small: 35.3% | Too Large: 39.5% | Quality: 17.6% | Other: 7.6%
  - Sizing pattern across SKUs: **RUNS_SMALL** (consistent across multiple products)

**Return Rate by Category:**

| Category | Sold | Return Rate | Benchmark (wt. median) | Deviation | Underperforming? |
|----------|------|-------------|------------------------|-----------|------------------|
| bottoms | 6,803 | 30.1% | 22.4% | +7.7pp | YES |
| suits | 362 | 30.1% | 26.4% | +3.7pp | no |

**Return Rate by Size:**

| Size | Sold | Returned | Return Rate |
|------|------|----------|-------------|
| XL | 815 | 263 | 32.3% |
| M | 1,538 | 479 | 31.1% |
| S | 2,124 | 650 | 30.6% |
| L | 1,451 | 406 | 28.0% |
| XS | 1,184 | 321 | 27.1% |

Size spread: 5.2pp (worst: XL at 32.3%, best: XS at 27.1%)

**Robustness Check — Remove worst SKU:**
  - Worst SKU: `LX4BEPJA00` (Textured Animal Printed High Waist Trousers) — 15 sold, 46.7% return rate
  - Supplier rate drops from 30.1% to 30.0% without this SKU
  - Removing it only changes the rate by 0.0pp — the issue is spread across the supplier's range

**Recommended Action:**
  - Request updated size charts and grading specs from APS
  - Consider mandatory fit samples before next order
  - Specific: Products consistently run small — request upsizing across the range

**Suggested Supplier Conversation:**
  > "We need to discuss the return performance on your products. Your return rate is 30.1%, which is +7.7pp above the category average of 22.4%. This represents approximately 550 excess returned units. We need a concrete improvement plan."

---

### MSN Tekstil — MONITOR

- **Volume:** 11,768 units sold, 3,361 returned, **28.6% return rate**
- **Primary category:** dresses (benchmark: 25.4% weighted median)
- **Deviation:** +3.2pp absolute, 12.6% relative
- **Confidence:** HIGH (98 SKUs total, 27 with ≥100 units)
- **Excess returns:** ~377 units above what the category median would predict

**SKU Concentration:** 7.5% of volume from top SKU

**Issue Type:** SIZING
  - Too Small: 17.4% | Too Large: 36.5% | Quality: 24.1% | Other: 22.0%
  - Sizing pattern across SKUs: **RUNS_LARGE** (consistent across multiple products)

**Return Rate by Category:**

| Category | Sold | Return Rate | Benchmark (wt. median) | Deviation | Underperforming? |
|----------|------|-------------|------------------------|-----------|------------------|
| dresses | 9,819 | 29.8% | 25.4% | +4.5pp | no |
| co-ords | 1,949 | 22.1% | 24.1% | -2.0pp | no |

**Return Rate by Size:**

| Size | Sold | Returned | Return Rate |
|------|------|----------|-------------|
| S | 2,507 | 758 | 30.2% |
| M | 3,714 | 1,055 | 28.4% |
| L | 2,602 | 732 | 28.1% |
| XL | 2,537 | 712 | 28.1% |
| XS | 408 | 104 | 25.5% |

Size spread: 4.7pp (worst: S at 30.2%, best: XS at 25.5%)

**Robustness Check — Remove worst SKU:**
  - Worst SKU: `M9R3S6P801` (V-Neck Mini Dress with Floral Print) — 35 sold, 54.3% return rate
  - Supplier rate drops from 28.6% to 28.5% without this SKU
  - Removing it only changes the rate by 0.1pp — the issue is spread across the supplier's range

**Recommended Action:**
  - No immediate action required. Re-evaluate in 30 days
  - If trend continues, escalate to CONCERNING

**Suggested Supplier Conversation:**
  > "FYI — we're monitoring return rates and your products are slightly above the category benchmark. No action needed now, but wanted to flag it."

---

### Busem Marketplace — CRITICAL

- **Volume:** 4,677 units sold, 1,086 returned, **23.2% return rate**
- **Primary category:** tops-blouses-tee (benchmark: 17.1% weighted median)
- **Deviation:** +6.1pp absolute, 35.4% relative
- **Confidence:** MEDIUM (131 SKUs total, 1 with ≥100 units)
- **Excess returns:** ~284 units above what the category median would predict

**SKU Concentration:** 2.7% of volume from top SKU

**Issue Type:** SIZING
  - Too Small: 34.8% | Too Large: 21.2% | Quality: 25.1% | Other: 18.9%
  - Sizing pattern across SKUs: **MIXED_SIZING** (consistent across multiple products)

**Return Rate by Category:**

| Category | Sold | Return Rate | Benchmark (wt. median) | Deviation | Underperforming? |
|----------|------|-------------|------------------------|-----------|------------------|
| tops-blouses-tee | 2,197 | 19.1% | 17.1% | +2.0pp | no |
| dresses | 1,251 | 29.0% | 25.4% | +3.7pp | no |
| bottoms | 1,068 | 26.2% | 22.4% | +3.8pp | no |

**Return Rate by Size:**

| Size | Sold | Returned | Return Rate |
|------|------|----------|-------------|
| L | 1,371 | 331 | 24.1% |
| M | 1,551 | 365 | 23.5% |
| S | 1,614 | 364 | 22.6% |
| XL | 141 | 26 | 18.4% |

Size spread: 5.7pp (worst: L at 24.1%, best: XL at 18.4%)

**Robustness Check — Remove worst SKU:**
  - Worst SKU: `MCDC4D5G01` (Maxi A-Form Dress with Crew Neck and Zipper) — 64 sold, 67.2% return rate
  - Supplier rate drops from 23.2% to 22.6% without this SKU
  - Removing it only changes the rate by 0.6pp — the issue is spread across the supplier's range

**Recommended Action:**
  - Request updated size charts and grading specs from Busem Marketplace
  - Consider mandatory fit samples before next order

**Suggested Supplier Conversation:**
  > "We need to discuss the return performance on your products. Your return rate is 23.2%, which is +6.1pp above the category average of 17.1%. This represents approximately 284 excess returned units. We need a concrete improvement plan."

---

### DUEE — CONCERNING

- **Volume:** 1,557 units sold, 603 returned, **38.7% return rate**
- **Primary category:** bottoms (benchmark: 22.4% weighted median)
- **Deviation:** +16.3pp absolute, 72.9% relative
- **Confidence:** LOW (2 SKUs total, 2 with ≥100 units)
- **Excess returns:** ~254 units above what the category median would predict

**SKU Concentration:** 89.8% of volume from top SKU
  - WARNING: Concentrated. Top SKU: `M6GKY31U02` (High Waist Elastic Crepe Palazzo Pants), return rate 39.8%
  - Evaluate this SKU separately from the supplier

**Issue Type:** SIZING
  - Too Small: 15.0% | Too Large: 40.7% | Quality: 31.9% | Other: 12.4%

**Return Rate by Category:**

| Category | Sold | Return Rate | Benchmark (wt. median) | Deviation | Underperforming? |
|----------|------|-------------|------------------------|-----------|------------------|
| bottoms | 1,557 | 38.7% | 22.4% | +16.3pp | YES |

**Return Rate by Size:**

| Size | Sold | Returned | Return Rate |
|------|------|----------|-------------|
| S | 355 | 156 | 43.9% |
| XXS | 161 | 63 | 39.1% |
| XS | 241 | 90 | 37.3% |
| L | 298 | 109 | 36.6% |
| XL | 149 | 52 | 34.9% |
| M | 265 | 92 | 34.7% |

Size spread: 9.2pp (worst: S at 43.9%, best: M at 34.7%)

**Robustness Check — Remove worst SKU:**
  - Worst SKU: `M6GKY31U02` (High Waist Elastic Crepe Palazzo Pants) — 1,398 sold, 39.8% return rate
  - Supplier rate drops from 38.7% to 29.6% without this SKU
  - This single SKU accounts for ~9.2pp of the supplier's rate — the problem may be SKU-specific, not supplier-wide

**Recommended Action:**
  - Raise in next regular supplier meeting. Document the +16.3pp deviation from category benchmark
  - Focus conversation on top SKU `M6GKY31U02` which drives most of the volume

**Suggested Supplier Conversation:**
  > "We're seeing your return rate at 38.7% against a category benchmark of 22.4%. Can we review the sizing/quality feedback together and identify improvements?"

---

### Karabay Tekstil — MONITOR

- **Volume:** 34,388 units sold, 3,387 returned, **9.8% return rate**
- **Primary category:** activewear (benchmark: 9.2% weighted median)
- **Deviation:** +0.6pp absolute, 6.7% relative
- **Confidence:** HIGH (64 SKUs total, 35 with ≥100 units)
- **Excess returns:** ~213 units above what the category median would predict

**SKU Concentration:** 38.1% of volume from top SKU

**Issue Type:** SIZING
  - Too Small: 43.5% | Too Large: 14.0% | Quality: 26.7% | Other: 15.8%
  - Sizing pattern across SKUs: **RUNS_SMALL** (consistent across multiple products)

**Return Rate by Category:**

| Category | Sold | Return Rate | Benchmark (wt. median) | Deviation | Underperforming? |
|----------|------|-------------|------------------------|-----------|------------------|
| activewear | 22,085 | 9.2% | 9.2% | 0.0pp | no |
| tops-blouses-tee | 11,695 | 10.6% | 17.1% | -6.5pp | no |
| jumpsuits-bodysuits | 358 | 14.0% | 26.9% | -12.9pp | no |
| dresses | 250 | 23.2% | 25.4% | -2.2pp | no |

**Return Rate by Size:**

| Size | Sold | Returned | Return Rate |
|------|------|----------|-------------|
| XL | 1,462 | 184 | 12.6% |
| L | 7,645 | 848 | 11.1% |
| M | 11,470 | 1,171 | 10.2% |
| S | 12,746 | 1,122 | 8.8% |
| XS | 1,065 | 62 | 5.8% |

Size spread: 6.8pp (worst: XL at 12.6%, best: XS at 5.8%)

**Robustness Check — Remove worst SKU:**
  - Worst SKU: `ME6V1V3101` (Boat Neck Long Sleeve Knitted Top) — 1 sold, 100.0% return rate
  - Supplier rate drops from 9.8% to 9.8% without this SKU
  - Removing it only changes the rate by 0.0pp — the issue is spread across the supplier's range

**Recommended Action:**
  - No immediate action required. Re-evaluate in 30 days
  - If trend continues, escalate to CONCERNING

**Suggested Supplier Conversation:**
  > "FYI — we're monitoring return rates and your products are slightly above the category benchmark. No action needed now, but wanted to flag it."

---

### Bianco Lucci — MONITOR

- **Volume:** 4,884 units sold, 849 returned, **17.4% return rate**
- **Primary category:** knitwear (benchmark: 13.7% weighted median)
- **Deviation:** +3.6pp absolute, 26.5% relative
- **Confidence:** MEDIUM (30 SKUs total, 14 with ≥100 units)
- **Excess returns:** ~177 units above what the category median would predict

**SKU Concentration:** 15.2% of volume from top SKU

**Issue Type:** QUALITY
  - Too Small: 28.0% | Too Large: 24.1% | Quality: 29.4% | Other: 18.5%
  - Sizing pattern across SKUs: **RUNS_SMALL** (consistent across multiple products)

**Return Rate by Category:**

| Category | Sold | Return Rate | Benchmark (wt. median) | Deviation | Underperforming? |
|----------|------|-------------|------------------------|-----------|------------------|
| knitwear | 2,571 | 13.5% | 13.7% | -0.2pp | no |
| tops-blouses-tee | 2,313 | 21.7% | 17.1% | +4.5pp | no |

**Return Rate by Size:**

| Size | Sold | Returned | Return Rate |
|------|------|----------|-------------|
| S | 897 | 202 | 22.5% |
| M | 841 | 182 | 21.6% |
| L | 535 | 115 | 21.5% |
| S/M | 2,571 | 348 | 13.5% |

Size spread: 9.0pp (worst: S at 22.5%, best: S/M at 13.5%)

**Robustness Check — Remove worst SKU:**
  - Worst SKU: `MDYEYZEQ01` (Embroidered Cotton Sweatshirt) — 211 sold, 32.2% return rate
  - Supplier rate drops from 17.4% to 16.7% without this SKU
  - Removing it only changes the rate by 0.7pp — the issue is spread across the supplier's range

**Recommended Action:**
  - No immediate action required. Re-evaluate in 30 days
  - If trend continues, escalate to CONCERNING

**Suggested Supplier Conversation:**
  > "FYI — we're monitoring return rates and your products are slightly above the category benchmark. No action needed now, but wanted to flag it."

---

### Egemay — CRITICAL

- **Volume:** 2,815 units sold, 626 returned, **22.2% return rate**
- **Primary category:** tops-blouses-tee (benchmark: 17.1% weighted median)
- **Deviation:** +5.1pp absolute, 29.7% relative
- **Confidence:** MEDIUM (20 SKUs total, 8 with ≥100 units)
- **Excess returns:** ~143 units above what the category median would predict

**SKU Concentration:** 25.5% of volume from top SKU

**Issue Type:** SIZING
  - Too Small: 20.4% | Too Large: 34.9% | Quality: 29.8% | Other: 14.9%
  - Sizing pattern across SKUs: **MIXED_SIZING** (consistent across multiple products)

**Return Rate by Category:**

| Category | Sold | Return Rate | Benchmark (wt. median) | Deviation | Underperforming? |
|----------|------|-------------|------------------------|-----------|------------------|
| tops-blouses-tee | 1,884 | 17.4% | 17.1% | +0.2pp | no |
| dresses | 819 | 31.7% | 25.4% | +6.4pp | YES |

**Return Rate by Size:**

| Size | Sold | Returned | Return Rate |
|------|------|----------|-------------|
| XL | 427 | 115 | 26.9% |
| L | 512 | 124 | 24.2% |
| M | 745 | 162 | 21.7% |
| S | 706 | 145 | 20.5% |
| XS | 395 | 69 | 17.5% |

Size spread: 9.5pp (worst: XL at 26.9%, best: XS at 17.5%)

**Robustness Check — Remove worst SKU:**
  - Worst SKU: `M98FBLPD01` (Slim Fit Printed Crew Neck T-Shirt) — 9 sold, 44.4% return rate
  - Supplier rate drops from 22.2% to 22.2% without this SKU
  - Removing it only changes the rate by 0.1pp — the issue is spread across the supplier's range

**Recommended Action:**
  - Request updated size charts and grading specs from Egemay
  - Consider mandatory fit samples before next order

**Suggested Supplier Conversation:**
  > "We need to discuss the return performance on your products. Your return rate is 22.2%, which is +5.1pp above the category average of 17.1%. This represents approximately 143 excess returned units. We need a concrete improvement plan."

---

### Akabe Tekstil — CRITICAL

- **Volume:** 2,459 units sold, 550 returned, **22.4% return rate**
- **Primary category:** tops-blouses-tee (benchmark: 17.1% weighted median)
- **Deviation:** +5.2pp absolute, 30.4% relative
- **Confidence:** MEDIUM (17 SKUs total, 6 with ≥100 units)
- **Excess returns:** ~128 units above what the category median would predict

**SKU Concentration:** 15.4% of volume from top SKU

**Issue Type:** SIZING
  - Too Small: 24.9% | Too Large: 32.3% | Quality: 24.9% | Other: 17.9%
  - Sizing pattern across SKUs: **RUNS_LARGE** (consistent across multiple products)

**Return Rate by Category:**

| Category | Sold | Return Rate | Benchmark (wt. median) | Deviation | Underperforming? |
|----------|------|-------------|------------------------|-----------|------------------|
| tops-blouses-tee | 1,363 | 18.6% | 17.1% | +1.4pp | no |
| bottoms | 621 | 24.8% | 22.4% | +2.4pp | no |
| dresses | 379 | 30.1% | 25.4% | +4.7pp | no |

**Return Rate by Size:**

| Size | Sold | Returned | Return Rate |
|------|------|----------|-------------|
| XXL | 232 | 67 | 28.9% |
| XXS | 109 | 27 | 24.8% |
| XS | 305 | 70 | 23.0% |
| M | 490 | 111 | 22.7% |
| XL | 379 | 83 | 21.9% |
| S | 499 | 102 | 20.4% |
| L | 445 | 90 | 20.2% |

Size spread: 8.7pp (worst: XXL at 28.9%, best: L at 20.2%)

**Robustness Check — Remove worst SKU:**
  - Worst SKU: `M52ZFISD01` (Fitted V-Neck Sleeveless Top) — 97 sold, 38.1% return rate
  - Supplier rate drops from 22.4% to 21.7% without this SKU
  - Removing it only changes the rate by 0.6pp — the issue is spread across the supplier's range

**Recommended Action:**
  - Request updated size charts and grading specs from Akabe Tekstil
  - Consider mandatory fit samples before next order
  - Specific: Products consistently run large — request downsizing across the range

**Suggested Supplier Conversation:**
  > "We need to discuss the return performance on your products. Your return rate is 22.4%, which is +5.2pp above the category average of 17.1%. This represents approximately 128 excess returned units. We need a concrete improvement plan."

---

### Yıldız Triko — CRITICAL

- **Volume:** 1,893 units sold, 384 returned, **20.3% return rate**
- **Primary category:** knitwear (benchmark: 13.7% weighted median)
- **Deviation:** +6.5pp absolute, 47.6% relative
- **Confidence:** MEDIUM (20 SKUs total, 9 with ≥100 units)
- **Excess returns:** ~123 units above what the category median would predict

**SKU Concentration:** 8.1% of volume from top SKU

**Issue Type:** QUALITY
  - Too Small: 27.0% | Too Large: 24.9% | Quality: 27.6% | Other: 20.5%
  - Sizing pattern across SKUs: **MIXED_SIZING** (consistent across multiple products)

**Return Rate by Category:**

| Category | Sold | Return Rate | Benchmark (wt. median) | Deviation | Underperforming? |
|----------|------|-------------|------------------------|-----------|------------------|
| knitwear | 1,893 | 20.3% | 13.7% | +6.5pp | YES |

**Return Rate by Size:**

| Size | Sold | Returned | Return Rate |
|------|------|----------|-------------|
| M | 738 | 161 | 21.8% |
| L | 429 | 85 | 19.8% |
| S | 726 | 138 | 19.0% |

Size spread: 2.8pp (worst: M at 21.8%, best: S at 19.0%)

**Robustness Check — Remove worst SKU:**
  - Worst SKU: `M3EBETKM01` (Textured Wide Leg Knit Pants) — 100 sold, 41.0% return rate
  - Supplier rate drops from 20.3% to 19.1% without this SKU
  - Removing it only changes the rate by 1.2pp — the issue is spread across the supplier's range

**Recommended Action:**
  - Arrange quality audit with Yıldız Triko. 28% of returns cite quality issues
  - Consider reducing order depth until quality improves

**Suggested Supplier Conversation:**
  > "We need to discuss the return performance on your products. Your return rate is 20.3%, which is +6.5pp above the category average of 13.7%. This represents approximately 123 excess returned units. We need a concrete improvement plan."

---

### Uraz Triko — MONITOR

- **Volume:** 43,386 units sold, 6,073 returned, **14.0% return rate**
- **Primary category:** knitwear (benchmark: 13.7% weighted median)
- **Deviation:** +0.3pp absolute, 1.9% relative
- **Confidence:** HIGH (108 SKUs total, 53 with ≥100 units)
- **Excess returns:** ~112 units above what the category median would predict

**SKU Concentration:** 36.0% of volume from top SKU

**Issue Type:** QUALITY
  - Too Small: 28.3% | Too Large: 29.6% | Quality: 27.5% | Other: 14.7%
  - Sizing pattern across SKUs: **MIXED_SIZING** (consistent across multiple products)

**Return Rate by Category:**

| Category | Sold | Return Rate | Benchmark (wt. median) | Deviation | Underperforming? |
|----------|------|-------------|------------------------|-----------|------------------|
| knitwear | 42,274 | 13.7% | 13.7% | 0.0pp | no |
| bottoms | 1,112 | 23.8% | 22.4% | +1.4pp | no |

**Return Rate by Size:**

| Size | Sold | Returned | Return Rate |
|------|------|----------|-------------|
| XS | 177 | 54 | 30.5% |
| XL | 586 | 97 | 16.6% |
| M | 14,841 | 2,138 | 14.4% |
| L | 13,622 | 1,956 | 14.4% |
| S | 14,062 | 1,802 | 12.8% |

Size spread: 17.7pp (worst: XS at 30.5%, best: S at 12.8%)
  - FLAG: Size spread >10pp — potential grading issue

**Robustness Check — Remove worst SKU:**
  - Worst SKU: `M03LMRWF02` (Relaxed Fit Turtleneck Sweater Vest) — 79 sold, 43.0% return rate
  - Supplier rate drops from 14.0% to 13.9% without this SKU
  - Removing it only changes the rate by 0.1pp — the issue is spread across the supplier's range

**Recommended Action:**
  - No immediate action required. Re-evaluate in 30 days
  - If trend continues, escalate to CONCERNING

**Suggested Supplier Conversation:**
  > "FYI — we're monitoring return rates and your products are slightly above the category benchmark. No action needed now, but wanted to flag it."

---

### Hunk/Bufalo — MONITOR

- **Volume:** 3,461 units sold, 1,135 returned, **32.8% return rate**
- **Primary category:** denim (benchmark: 29.7% weighted median)
- **Deviation:** +3.1pp absolute, 10.3% relative
- **Confidence:** MEDIUM (3 SKUs total, 3 with ≥100 units)
- **Excess returns:** ~106 units above what the category median would predict

**SKU Concentration:** 78.6% of volume from top SKU
  - WARNING: Concentrated. Top SKU: `MBRNISKN02` (Straight Leg Denim Jeans), return rate 32.3%
  - Evaluate this SKU separately from the supplier

**Issue Type:** SIZING
  - Too Small: 35.5% | Too Large: 36.1% | Quality: 19.0% | Other: 9.5%
  - Sizing pattern across SKUs: **RUNS_SMALL** (consistent across multiple products)

**Return Rate by Category:**

| Category | Sold | Return Rate | Benchmark (wt. median) | Deviation | Underperforming? |
|----------|------|-------------|------------------------|-----------|------------------|
| denim | 3,461 | 32.8% | 29.7% | +3.1pp | no |

**Return Rate by Size:**

| Size | Sold | Returned | Return Rate |
|------|------|----------|-------------|
| XXL | 216 | 86 | 39.8% |
| XL | 399 | 143 | 35.8% |
| L | 626 | 213 | 34.0% |
| M | 922 | 300 | 32.5% |
| S | 756 | 233 | 30.8% |
| XXS | 136 | 41 | 30.1% |
| XS | 406 | 119 | 29.3% |

Size spread: 10.5pp (worst: XXL at 39.8%, best: XS at 29.3%)
  - FLAG: Size spread >10pp — potential grading issue

**Robustness Check — Remove worst SKU:**
  - Worst SKU: `MBRNISKN01` (Straight Leg Denim Jeans) — 318 sold, 39.6% return rate
  - Supplier rate drops from 32.8% to 32.1% without this SKU
  - Removing it only changes the rate by 0.7pp — the issue is spread across the supplier's range

**Recommended Action:**
  - No immediate action required. Re-evaluate in 30 days
  - If trend continues, escalate to CONCERNING

**Suggested Supplier Conversation:**
  > "FYI — we're monitoring return rates and your products are slightly above the category benchmark. No action needed now, but wanted to flag it."

---

### Nur Tekstil — MONITOR

- **Volume:** 7,172 units sold, 1,644 returned, **22.9% return rate**
- **Primary category:** bottoms (benchmark: 22.4% weighted median)
- **Deviation:** +0.5pp absolute, 2.3% relative
- **Confidence:** HIGH (23 SKUs total, 14 with ≥100 units)
- **Excess returns:** ~37 units above what the category median would predict

**SKU Concentration:** 30.3% of volume from top SKU

**Issue Type:** SIZING
  - Too Small: 35.6% | Too Large: 23.8% | Quality: 26.3% | Other: 14.3%
  - Sizing pattern across SKUs: **RUNS_SMALL** (consistent across multiple products)

**Return Rate by Category:**

| Category | Sold | Return Rate | Benchmark (wt. median) | Deviation | Underperforming? |
|----------|------|-------------|------------------------|-----------|------------------|
| bottoms | 2,919 | 14.6% | 22.4% | -7.8pp | no |
| co-ords | 1,838 | 25.1% | 24.1% | +1.0pp | no |
| tops-blouses-tee | 1,542 | 31.9% | 17.1% | +14.8pp | YES |
| dresses | 715 | 31.0% | 25.4% | +5.7pp | no |

**Return Rate by Size:**

| Size | Sold | Returned | Return Rate |
|------|------|----------|-------------|
| XXL | 735 | 202 | 27.5% |
| XL | 938 | 250 | 26.7% |
| L | 1,278 | 318 | 24.9% |
| M | 1,797 | 404 | 22.5% |
| XS | 719 | 146 | 20.3% |
| S | 1,484 | 290 | 19.5% |
| XXS | 221 | 34 | 15.4% |

Size spread: 12.1pp (worst: XXL at 27.5%, best: XXS at 15.4%)
  - FLAG: Size spread >10pp — potential grading issue

**Robustness Check — Remove worst SKU:**
  - Worst SKU: `M3X1QWO701` (Kare Yaka Saten Maxi Elbise) — 162 sold, 52.5% return rate
  - Supplier rate drops from 22.9% to 22.2% without this SKU
  - Removing it only changes the rate by 0.7pp — the issue is spread across the supplier's range

**Recommended Action:**
  - No immediate action required. Re-evaluate in 30 days
  - If trend continues, escalate to CONCERNING

**Suggested Supplier Conversation:**
  > "FYI — we're monitoring return rates and your products are slightly above the category benchmark. No action needed now, but wanted to flag it."

---

### Qu Style — MONITOR

- **Volume:** 2,764 units sold, 415 returned, **15.0% return rate**
- **Primary category:** knitwear (benchmark: 13.7% weighted median)
- **Deviation:** +1.3pp absolute, 9.3% relative
- **Confidence:** MEDIUM (13 SKUs total, 9 with ≥100 units)
- **Excess returns:** ~35 units above what the category median would predict

**SKU Concentration:** 11.9% of volume from top SKU

**Issue Type:** SIZING
  - Too Small: 19.8% | Too Large: 33.4% | Quality: 33.2% | Other: 13.6%
  - Sizing pattern across SKUs: **RUNS_LARGE** (consistent across multiple products)

**Return Rate by Category:**

| Category | Sold | Return Rate | Benchmark (wt. median) | Deviation | Underperforming? |
|----------|------|-------------|------------------------|-----------|------------------|
| knitwear | 2,764 | 15.0% | 13.7% | +1.3pp | no |

**Return Rate by Size:**

| Size | Sold | Returned | Return Rate |
|------|------|----------|-------------|
| S/M | 2,629 | 385 | 14.6% |

Size spread: 0.0pp (worst: S/M at 14.6%, best: S/M at 14.6%)

**Robustness Check — Remove worst SKU:**
  - Worst SKU: `MDWQZ3E203` (Ultra Soft Crew Neck Buttoned Dual-use Cardigan) — 15 sold, 26.7% return rate
  - Supplier rate drops from 15.0% to 15.0% without this SKU
  - Removing it only changes the rate by 0.1pp — the issue is spread across the supplier's range

**Recommended Action:**
  - No immediate action required. Re-evaluate in 30 days
  - If trend continues, escalate to CONCERNING

**Suggested Supplier Conversation:**
  > "FYI — we're monitoring return rates and your products are slightly above the category benchmark. No action needed now, but wanted to flag it."

---

### Elissa — MONITOR

- **Volume:** 1,061 units sold, 302 returned, **28.5% return rate**
- **Primary category:** dresses (benchmark: 25.4% weighted median)
- **Deviation:** +3.1pp absolute, 12.3% relative
- **Confidence:** MEDIUM (22 SKUs total, 1 with ≥100 units)
- **Excess returns:** ~32 units above what the category median would predict

**SKU Concentration:** 68.5% of volume from top SKU
  - WARNING: Concentrated. Top SKU: `W3000001009BE` (İşlemeli Kalp Kesimli Pamuklu Maxi Elbise), return rate 34.5%
  - Evaluate this SKU separately from the supplier

**Issue Type:** SIZING
  - Too Small: 39.7% | Too Large: 25.7% | Quality: 20.3% | Other: 14.3%
  - Sizing pattern across SKUs: **RUNS_SMALL** (consistent across multiple products)

**Return Rate by Category:**

| Category | Sold | Return Rate | Benchmark (wt. median) | Deviation | Underperforming? |
|----------|------|-------------|------------------------|-----------|------------------|
| dresses | 960 | 30.3% | 25.4% | +5.0pp | no |

**Return Rate by Size:**

| Size | Sold | Returned | Return Rate |
|------|------|----------|-------------|
| L | 277 | 99 | 35.7% |
| S | 347 | 91 | 26.2% |
| M | 314 | 71 | 22.6% |

Size spread: 13.1pp (worst: L at 35.7%, best: M at 22.6%)
  - FLAG: Size spread >10pp — potential grading issue

**Robustness Check — Remove worst SKU:**
  - Worst SKU: `W3000001009BE` (İşlemeli Kalp Kesimli Pamuklu Maxi Elbise) — 727 sold, 34.5% return rate
  - Supplier rate drops from 28.5% to 15.3% without this SKU
  - This single SKU accounts for ~13.2pp of the supplier's rate — the problem may be SKU-specific, not supplier-wide

**Recommended Action:**
  - No immediate action required. Re-evaluate in 30 days
  - If trend continues, escalate to CONCERNING

**Suggested Supplier Conversation:**
  > "FYI — we're monitoring return rates and your products are slightly above the category benchmark. No action needed now, but wanted to flag it."

---

### My Fashion — MONITOR

- **Volume:** 3,635 units sold, 532 returned, **14.6% return rate**
- **Primary category:** knitwear (benchmark: 13.7% weighted median)
- **Deviation:** +0.9pp absolute, 6.5% relative
- **Confidence:** MEDIUM (30 SKUs total, 10 with ≥100 units)
- **Excess returns:** ~32 units above what the category median would predict

**SKU Concentration:** 32.1% of volume from top SKU

**Issue Type:** SIZING
  - Too Small: 17.2% | Too Large: 37.3% | Quality: 27.7% | Other: 17.9%
  - Sizing pattern across SKUs: **MIXED_SIZING** (consistent across multiple products)

**Return Rate by Category:**

| Category | Sold | Return Rate | Benchmark (wt. median) | Deviation | Underperforming? |
|----------|------|-------------|------------------------|-----------|------------------|
| knitwear | 3,153 | 15.8% | 13.7% | +2.0pp | no |
| tops-blouses-tee | 444 | 6.1% | 17.1% | -11.1pp | no |

**Return Rate by Size:**

| Size | Sold | Returned | Return Rate |
|------|------|----------|-------------|
| L | 920 | 150 | 16.3% |
| S | 1,278 | 186 | 14.6% |
| M | 1,338 | 188 | 14.1% |

Size spread: 2.3pp (worst: L at 16.3%, best: M at 14.1%)

**Robustness Check — Remove worst SKU:**
  - Worst SKU: `M1RS2FU501` (Crop Top With Zipper & Pants Knit Coord) — 15 sold, 40.0% return rate
  - Supplier rate drops from 14.6% to 14.5% without this SKU
  - Removing it only changes the rate by 0.1pp — the issue is spread across the supplier's range

**Recommended Action:**
  - No immediate action required. Re-evaluate in 30 days
  - If trend continues, escalate to CONCERNING

**Suggested Supplier Conversation:**
  > "FYI — we're monitoring return rates and your products are slightly above the category benchmark. No action needed now, but wanted to flag it."

---

### BYATALAY Tekstil — MONITOR

- **Volume:** 8,067 units sold, 2,076 returned, **25.7% return rate**
- **Primary category:** dresses (benchmark: 25.4% weighted median)
- **Deviation:** +0.4pp absolute, 1.5% relative
- **Confidence:** HIGH (26 SKUs total, 13 with ≥100 units)
- **Excess returns:** ~30 units above what the category median would predict

**SKU Concentration:** 33.3% of volume from top SKU

**Issue Type:** SIZING
  - Too Small: 21.2% | Too Large: 32.7% | Quality: 30.2% | Other: 15.9%
  - Sizing pattern across SKUs: **MIXED_SIZING** (consistent across multiple products)

**Return Rate by Category:**

| Category | Sold | Return Rate | Benchmark (wt. median) | Deviation | Underperforming? |
|----------|------|-------------|------------------------|-----------|------------------|
| dresses | 3,667 | 31.9% | 25.4% | +6.6pp | YES |
| bottoms | 2,316 | 34.3% | 22.4% | +11.9pp | YES |
| beachwear | 1,956 | 4.7% | 4.7% | 0.0pp | no |

**Return Rate by Size:**

| Size | Sold | Returned | Return Rate |
|------|------|----------|-------------|
| L | 954 | 353 | 37.0% |
| XL | 595 | 207 | 34.8% |
| M | 1,729 | 590 | 34.1% |
| S | 1,535 | 481 | 31.3% |
| XS | 1,160 | 312 | 26.9% |
| S/M | 1,956 | 92 | 4.7% |

Size spread: 32.3pp (worst: L at 37.0%, best: S/M at 4.7%)
  - FLAG: Size spread >10pp — potential grading issue

**Robustness Check — Remove worst SKU:**
  - Worst SKU: `MAXO7J5K01` (High Waist Plaid Mini Skirt) — 14 sold, 78.6% return rate
  - Supplier rate drops from 25.7% to 25.6% without this SKU
  - Removing it only changes the rate by 0.1pp — the issue is spread across the supplier's range

**Recommended Action:**
  - No immediate action required. Re-evaluate in 30 days
  - If trend continues, escalate to CONCERNING

**Suggested Supplier Conversation:**
  > "FYI — we're monitoring return rates and your products are slightly above the category benchmark. No action needed now, but wanted to flag it."

---

## All Qualifying Suppliers — Full Table

| Supplier | Sold | Returned | Return Rate | Primary Cat | Cat Benchmark | Deviation | SKUs | Confidence | Assessment |
|----------|------|----------|-------------|-------------|---------------|-----------|------|------------|------------|
| Kovesa | 118,368 | 26,017 | 22.0% | tops-blouses-tee | 17.1% | +4.8pp | 415 | HIGH | MONITOR |
| Karaca | 22,140 | 4,266 | 19.3% | knitwear | 13.7% | +5.5pp | 42 | HIGH | CRITICAL |
| Dormina Tekstil | 25,065 | 4,492 | 17.9% | knitwear | 13.7% | +4.2pp | 32 | HIGH | MONITOR |
| Atay Moda | 24,321 | 6,436 | 26.5% | bottoms | 22.4% | +4.1pp | 84 | HIGH | CONCERNING |
| S-CL Denim | 7,651 | 3,200 | 41.8% | denim | 29.7% | +12.1pp | 4 | MEDIUM | CRITICAL |
| Moda İkra | 10,701 | 3,167 | 29.6% | bottoms | 22.4% | +7.2pp | 49 | HIGH | CRITICAL |
| ZRF Abiye | 4,017 | 1,634 | 40.7% | dresses | 25.4% | +15.3pp | 34 | MEDIUM | CRITICAL |
| APS | 7,197 | 2,163 | 30.1% | bottoms | 22.4% | +7.7pp | 30 | HIGH | CRITICAL |
| MSN Tekstil | 11,768 | 3,361 | 28.6% | dresses | 25.4% | +3.2pp | 98 | HIGH | MONITOR |
| Busem Marketplace | 4,677 | 1,086 | 23.2% | tops-blouses-tee | 17.1% | +6.1pp | 131 | MEDIUM | CRITICAL |
| DUEE | 1,557 | 603 | 38.7% | bottoms | 22.4% | +16.3pp | 2 | LOW | CONCERNING |
| Karabay Tekstil | 34,388 | 3,387 | 9.8% | activewear | 9.2% | +0.6pp | 64 | HIGH | MONITOR |
| Bianco Lucci | 4,884 | 849 | 17.4% | knitwear | 13.7% | +3.6pp | 30 | MEDIUM | MONITOR |
| Egemay | 2,815 | 626 | 22.2% | tops-blouses-tee | 17.1% | +5.1pp | 20 | MEDIUM | CRITICAL |
| Akabe Tekstil | 2,459 | 550 | 22.4% | tops-blouses-tee | 17.1% | +5.2pp | 17 | MEDIUM | CRITICAL |
| Yıldız Triko | 1,893 | 384 | 20.3% | knitwear | 13.7% | +6.5pp | 20 | MEDIUM | CRITICAL |
| Uraz Triko | 43,386 | 6,073 | 14.0% | knitwear | 13.7% | +0.3pp | 108 | HIGH | MONITOR |
| Hunk/Bufalo | 3,461 | 1,135 | 32.8% | denim | 29.7% | +3.1pp | 3 | MEDIUM | MONITOR |
| Nur Tekstil | 7,172 | 1,644 | 22.9% | bottoms | 22.4% | +0.5pp | 23 | HIGH | MONITOR |
| Qu Style | 2,764 | 415 | 15.0% | knitwear | 13.7% | +1.3pp | 13 | MEDIUM | MONITOR |
| Elissa | 1,061 | 302 | 28.5% | dresses | 25.4% | +3.1pp | 22 | MEDIUM | MONITOR |
| My Fashion | 3,635 | 532 | 14.6% | knitwear | 13.7% | +0.9pp | 30 | MEDIUM | MONITOR |
| BYATALAY Tekstil | 8,067 | 2,076 | 25.7% | dresses | 25.4% | +0.4pp | 26 | HIGH | MONITOR |
| MBA Denim | 22,943 | 6,821 | 29.7% | denim | 29.7% | 0.0pp | 25 | HIGH | ACCEPTABLE |
| Ay Tekstil | 6,087 | 1,542 | 25.3% | dresses | 25.4% | -0.0pp | 42 | HIGH | ACCEPTABLE |
| Dema Fashion | 7,634 | 1,910 | 25.0% | denim | 29.7% | -4.7pp | 19 | HIGH | ACCEPTABLE |
| Yiğit Tekstil | 38,486 | 9,131 | 23.7% | dresses | 25.4% | -1.6pp | 105 | HIGH | ACCEPTABLE |
| Elo Moda Tekstil | 1,238 | 292 | 23.6% | co-ords | 24.1% | -0.5pp | 10 | MEDIUM | ACCEPTABLE |
| Sinyor Tekstil | 28,804 | 6,738 | 23.4% | dresses | 25.4% | -2.0pp | 84 | HIGH | ACCEPTABLE |
| Lady Berşan | 4,720 | 1,095 | 23.2% | co-ords | 24.1% | -0.9pp | 190 | MEDIUM | ACCEPTABLE |
| HiCCUP | 24,160 | 5,264 | 21.8% | bottoms | 22.4% | -0.6pp | 254 | HIGH | ACCEPTABLE |
| Pikalife | 31,762 | 6,805 | 21.4% | bottoms | 22.4% | -1.0pp | 196 | HIGH | ACCEPTABLE |
| FMC  | 44,914 | 9,543 | 21.2% | dresses | 25.4% | -4.1pp | 128 | HIGH | ACCEPTABLE |
| Desperado | 1,414 | 297 | 21.0% | denim | 29.7% | -8.7pp | 29 | MEDIUM | ACCEPTABLE |
| Bigdart | 28,634 | 5,403 | 18.9% | dresses | 25.4% | -6.5pp | 318 | HIGH | ACCEPTABLE |
| Bye Bye | 1,973 | 368 | 18.7% | bottoms | 22.4% | -3.7pp | 114 | MEDIUM | ACCEPTABLE |
| Zipon | 1,084 | 196 | 18.1% | dresses | 25.4% | -7.3pp | 42 | MEDIUM | ACCEPTABLE |
| Lefon | 3,345 | 581 | 17.4% | bottoms | 22.4% | -5.0pp | 252 | MEDIUM | ACCEPTABLE |
| Reyon | 9,468 | 1,590 | 16.8% | tops-blouses-tee | 17.1% | -0.4pp | 437 | HIGH | ACCEPTABLE |
| BSL | 1,174 | 194 | 16.5% | tops-blouses-tee | 17.1% | -0.6pp | 58 | MEDIUM | ACCEPTABLE |
| Zdn Jeans | 11,398 | 1,867 | 16.4% | denim | 29.7% | -13.4pp | 104 | HIGH | ACCEPTABLE |
| Quzu | 1,126 | 183 | 16.3% | bottoms | 22.4% | -6.1pp | 65 | MEDIUM | ACCEPTABLE |
| Mir Poyraz | 37,414 | 5,937 | 15.9% | tops-blouses-tee | 17.1% | -1.3pp | 124 | HIGH | ACCEPTABLE |
| Cennet | 1,368 | 210 | 15.4% | dresses | 25.4% | -10.0pp | 70 | MEDIUM | ACCEPTABLE |
| Busem | 53,319 | 8,144 | 15.3% | bottoms | 22.4% | -7.1pp | 879 | HIGH | ACCEPTABLE |
| SMF | 2,351 | 334 | 14.2% | denim | 29.7% | -15.5pp | 35 | MEDIUM | ACCEPTABLE |
| Akyüz Tekstil | 3,287 | 431 | 13.1% | tops-blouses-tee | 17.1% | -4.0pp | 15 | MEDIUM | ACCEPTABLE |
| Mixray | 35,382 | 4,574 | 12.9% | knitwear | 13.7% | -0.8pp | 300 | HIGH | ACCEPTABLE |
| Volumex | 11,376 | 1,308 | 11.5% | knitwear | 13.7% | -2.2pp | 474 | HIGH | ACCEPTABLE |
| Cream Rouge | 2,077 | 230 | 11.1% | co-ords | 24.1% | -13.0pp | 121 | MEDIUM | ACCEPTABLE |
| Sobe | 4,222 | 444 | 10.5% | co-ords | 24.1% | -13.6pp | 313 | MEDIUM | ACCEPTABLE |
| Berne | 1,454 | 141 | 9.7% | knitwear | 13.7% | -4.0pp | 59 | MEDIUM | ACCEPTABLE |
| Black Fashion | 4,961 | 481 | 9.7% | knitwear | 13.7% | -4.0pp | 364 | MEDIUM | ACCEPTABLE |
| Zen Tekstil | 1,428 | 123 | 8.6% | loungewear | 10.9% | -2.3pp | 22 | MEDIUM | ACCEPTABLE |
| Vadi Tekstil | 1,203 | 103 | 8.6% | knitwear | 13.7% | -5.2pp | 42 | MEDIUM | ACCEPTABLE |
| Zazzoni | 5,876 | 460 | 7.8% | tops-blouses-tee | 17.1% | -9.3pp | 38 | HIGH | ACCEPTABLE |
| Dilvin | 3,335 | 224 | 6.7% | tops-blouses-tee | 17.1% | -10.4pp | 258 | MEDIUM | ACCEPTABLE |

## Size x Category Structural Patterns

Sizes that are structurally problematic across all suppliers in a category (not supplier-specific). Only sizes with ≥200 units sold shown.

### Sizes with Above-Average Return Rates (>3pp above category avg)

| Category | Size | Sold | Return Rate | Category Avg | Deviation |
|----------|------|------|-------------|--------------|-----------|
| bottoms | XXL | 3,087 | 31.1% | 22.0% | +9.1pp |
| outerwear | XS | 747 | 29.7% | 21.5% | +8.2pp |
| denim | XXL | 3,293 | 34.6% | 27.0% | +7.6pp |
| outerwear | XXL | 463 | 28.7% | 21.5% | +7.2pp |
| jumpsuits-bodysuits | XL | 897 | 28.3% | 23.1% | +5.2pp |
| jumpsuits-bodysuits | XXS | 228 | 27.6% | 23.1% | +4.5pp |
| tops-blouses-tee | XXL | 4,014 | 19.1% | 15.5% | +3.6pp |
| co-ords | XXL | 408 | 23.8% | 20.2% | +3.5pp |
| activewear | XL | 1,383 | 12.6% | 9.3% | +3.3pp |

### Sizes with Below-Average Return Rates (<-3pp below category avg)

| Category | Size | Sold | Return Rate | Category Avg | Deviation |
|----------|------|------|-------------|--------------|-----------|
| dresses | S/M | 365 | 13.4% | 26.0% | -12.6pp |
| tops-blouses-tee | S/M | 509 | 6.5% | 15.5% | -9.1pp |
| denim | XS | 6,226 | 23.7% | 27.0% | -3.3pp |

### Cross-Category Size Summary

Does a size consistently over-index on returns regardless of category?

| Size | Categories Measured | Above Avg (>3pp) | Below Avg (<-3pp) | Interpretation |
|------|--------------------|------------------|-------------------|----------------|
| XXL | 7 | 5 (71%) | 0 | Structurally problematic |
| XL | 10 | 2 (20%) | 0 | Not consistently problematic |
| XS | 9 | 1 (11%) | 1 | Not consistently problematic |
| XXS | 5 | 1 (20%) | 0 | Not consistently problematic |
| L | 11 | 0 (0%) | 0 | Not consistently problematic |
| M | 11 | 0 (0%) | 0 | Not consistently problematic |
| S | 11 | 0 (0%) | 0 | Not consistently problematic |
| S/M | 4 | 0 (0%) | 2 | Not consistently problematic |
| STD | 3 | 0 (0%) | 0 | Not consistently problematic |

## Methodology & Caveats

### Thresholds Applied
- Supplier minimum: 1000 units sold
- Size×supplier minimum: 100 units sold for size-level conclusions
- Category×supplier minimum: 200 units sold for category-level breakdown, 500 for underperformance flagging
- Underperforming threshold: >5.0pp absolute AND >25.0% relative above benchmark
- SKU concentration flag: >60% of volume from 1 SKU
- Size spread flag: >10pp between best and worst size

### Confidence Levels
- HIGH: ≥5000 units, ≥5 SKUs with ≥100 units each
- MEDIUM: ≥1000 units, ≥3 SKUs
- LOW: anything below these thresholds

### Return Reason Coverage
Return reason data (too small / too large / quality / other) is only available for channels: trendyol, fashiondays, fashiondaysBG, hepsiburada, emag, trendyolRO. Suppliers selling primarily through other channels will show 0% for all reason categories — this does not mean there are no sizing issues, just that we cannot measure them.

### Benchmarking Approach
- Category benchmarks use **weighted median** return rate across all suppliers in that category, weighted by volume. This is more robust than a simple average (resistant to outliers).
- A supplier is flagged as underperforming only when they exceed the benchmark by BOTH >5pp absolute AND >25% relative. This dual threshold prevents flagging low-rate categories (where 5pp is huge) and high-rate categories (where 5pp is noise).

### What This Analysis Does NOT Cover
- Financial impact (cost of returns, logistics, lost margin)
- Temporal trends (is the supplier improving or getting worse?)
- Channel-specific performance (a supplier may perform differently on Trendyol vs. other channels)
- New products launched in the last 45 days (insufficient return data)
