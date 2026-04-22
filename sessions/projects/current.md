# Projects Current State — 2026-04-22

## Active projects
| Project | Status | Next action |
|---|---|---|
| Return Investigation Tool | MVP complete, pre-presentation | Deploy to Streamlit Cloud + align on return filters |

## What's been built
- Dashboard with Needs Attention / In Progress / Results / Parked tabs
- Option D flagging: weighted median × 1.3 multiplier + 5pp floor
- Single thresholds: sizing 2x ratio, quality 25%
- Action tracking persisted in MongoDB (hiccup-tools)
- All settings configurable via UI (7 settings, stored in MongoDB)
- Data cache for instant page loads
- Supplier Performance Review document generated

## Deliverables
- `analysis/Supplier Performance Review — April 2026.md` — presentation-ready
- `analysis/supplier_analysis_2026-04-22.md` — full detailed analysis (1,294 lines)
- `analysis/run_supplier_analysis.py` — reproducible script

## Key findings from supplier analysis
- 9 CRITICAL suppliers (Karaca, S-CL Denim, Moda Ikra, ZRF Abiye, APS, Busem Marketplace, Egemay, Akabe Tekstil, Yildiz Triko)
- XXL is structurally problematic across 5/7 categories (industry issue, not supplier-specific)
- Top performers: Zdn Jeans, Zazzoni, Busem, Bigdart, Dilvin

## Open items for next session
1. **Return filter alignment** — our filters (DISPATCHED/DELIVERED/PROCESSING orders, ACCEPTED/PENDING/REJECTED returns) give ~20% overall. Chris sees ~34.5% for denim with different filters. Need to agree on which statuses count.
2. **Deploy to Streamlit Cloud** — add MONGO_WRITE_URI to secrets, reboot
3. **Rotate Anthropic API key** — shared in chat 2026-04-21
4. **New pipelines** — get_monthly_orders_summary, get_monthly_returns_summary, get_revenue_by_sku added to pipelines.py but not yet integrated into dashboard
5. **Stale cache** — recurring issue. Consider auto-clearing cache when code changes are deployed.
