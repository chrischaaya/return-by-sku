# Projects Current State — 2026-04-21

## Active projects
| Project | Status | Next action |
|---|---|---|
| Return Investigation Tool | MVP live on Streamlit Cloud | Persist AI recs to MongoDB + rotate API key |

## What's live
- Dashboard: https://github.com/chrischaaya/return-by-sku (Streamlit Cloud)
- Two views: Bestsellers / Rising Stars (mutually exclusive, 45-day cutoff)
- Size-level P75 flagging with reason breakdown (% small, % large, % quality, % other)
- AI recommendations via Sonnet (single call, ~$0.15 per refresh, separate button)
- Filters: search, category, supplier
- Product images from CloudFront

## Agreed data rules
- Products: 7,982 hiccup skuPrefixes from Products collection
- Orders: DISPATCHED + DELIVERED + PROCESSING status only
- Delivery lag: createdOn — 7 days trendyol/hepsiburada, 14 days others
- Returns: items.status ACCEPTED + PENDING + REJECTED
- Exclude channels: aboutYou, vogaCloset
- P75 at size level per category_l3 — SKU flagged if any size has ≥10 sales in last 30d AND return rate > P75
- Sizing and quality evaluated as separate axes
- All-time return rates, ranked by last 30d sales

## Key numbers (2026-04-21)
- 891k sold / 72k returned / 8.1% overall
- 206 SKUs with problematic sizes
- Global P75: 12.7%

## TODO next session
1. **Persist AI recommendations to MongoDB** — need write-capable user (current claude-code-read-all is read-only)
2. **Rotate Anthropic API key** — shared in chat, needs regeneration at console.anthropic.com/settings/keys, then update Streamlit Cloud secret
3. Review AI recommendation quality on more SKUs
4. Consider adding a "last updated" timestamp to the dashboard
