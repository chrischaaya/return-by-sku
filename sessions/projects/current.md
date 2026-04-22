# Projects Current State — 2026-04-22

## Active projects
| Project | Status | Next action |
|---|---|---|
| Return Investigation Tool | Pre-CTO/CEO presentation | Final QA pass + deploy to Streamlit Cloud |

## What's live
- Local: localhost:8501
- GitHub: chrischaaya/return-by-sku (public)
- Streamlit Cloud: needs redeploy with latest code + updated secrets (MONGO_WRITE_URI)

## Architecture
- Read: MongoDB hiccup-app (claude-code-read-all)
- Write: MongoDB hiccup-tools (claude-hiccup-tools) — SkuActions, Settings, DataCache collections
- Cache: pre-computed DataFrames in hiccup-tools.DataCache (compressed, split per DataFrame)
- Settings: persisted in hiccup-tools.Settings, configurable via gear icon

## Data rules (verified)
- Products: 7,982 hiccup skuPrefixes from Products collection
- Orders: DISPATCHED + DELIVERED + PROCESSING status
- Delivery lag on createdOn: 7d trendyol/hepsiburada, 14d others
- Returns: items.status ACCEPTED/PENDING/REJECTED, all-time, no date filter
- Exclude channels: aboutYou, vogaCloset
- P75 at size level per category_l3 for flagging
- All thresholds configurable via Settings panel

## Pages
1. **Needs Attention** — flagged products, toggle for new products only, sort by priority/sales/newest
2. **In Progress** — action taken, waiting for old stock to sell through
3. **Results** — before/after comparison with green/red
4. **Parked** — no action possible, with revert

## Action text (agreed)
- Too small/large (high confidence) / (mid confidence)
- Relabel existing stock (only when conditions met)
- Mixed results (X% small, Y% large). Inspect product.
- Quality issue (high/mid confidence). Inspect product.
- No clear pattern. Inspect product.

## Key numbers (2026-04-22)
- 912k sold / 200k returned / 21.9% overall (all statuses)
- Trendyol: 661k sold, 21.6%
- Hiccup: 133k sold, 21.4%

## Open questions
- Should CANCELLED returns (return-level status) be excluded? Currently included if item-level status is ACCEPTED/PENDING/REJECTED
- Trendyol return rate jumped from 4.5% (DELIVERED only) to 21.6% (all statuses) — need to validate which is correct

## TODO next session
1. Resolve the return rate discrepancy (DELIVERED-only vs all statuses)
2. Final QA with Chris before CEO/CTO presentation
3. Deploy latest to Streamlit Cloud (add MONGO_WRITE_URI to secrets)
4. Rotate Anthropic API key (shared in chat 2026-04-21)
5. Remove "Load Test Data" / "Clear Test Data" buttons before presentation
