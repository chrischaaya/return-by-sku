# Projects Current State — 2026-04-21

## Active projects
| Project | Status | Next action |
|---|---|---|
| Return Investigation Tool | In progress — MVP live on Streamlit Cloud | Persist AI recommendations to MongoDB |

## Key decisions made recently
- P75 at size level for flagging (not median, not product level)
- Qualification: ≥10 sales per size in last 30 days
- Order filter: DISPATCHED + DELIVERED + PROCESSING only
- Channel-specific delivery lag: 7 days for trendyol/hepsiburada, 14 days for others
- Product identification: by skuPrefix from Products collection (not merchantKey on orders/returns — unreliable)
- Exclude channels: aboutYou, vogaCloset
- Return item statuses: ACCEPTED + PENDING + REJECTED
- Single Opus call for AI recommendations (~$0.50-0.75 per refresh)
- Two views: Bestsellers (established) and Rising Stars (launched <45 days) — mutually exclusive
- Sizing and quality analyzed as separate axes in recommendations
