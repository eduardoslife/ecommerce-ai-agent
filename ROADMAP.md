# Roadmap

## Done
- [x] PRD with goals, non-goals, risk register, eval plan and success metrics
- [x] Google Sheets ledger: Inventory, Sales, Expenses, Mileage, Tax Summary
- [x] Jan–Nov 2026 sales imported (85 orders), reconciled to eBay's Financial Summary
- [x] Live business dashboard on top of the ledger
- [x] Transaction report importer with automatic reconciliation
- [x] Reports: true profit per item, return by category, sourcing channels, inventory aging, monthly net profit
- [x] Photo-to-verdict agent: Claude vision identifier, authenticity risk scoring, pricer, coordinator
- [x] MCP server with read tools and propose-only write tools
- [x] Human approval gate and audit log

## Next: eBay integration (waiting on developer account approval)
- [ ] Sandbox OAuth flow, tokens kept in a secrets store
- [ ] Connect the seller account with read-only scopes first
- [ ] Pricer pulls comps from the Browse API instead of manual input
- [ ] Daily sync of new orders, refunds and shipping labels into the ledger
- [ ] Lister agent: draft listings through the Sell Inventory API, publish only after approval

## Then: evaluation and launch gate
- [ ] Build a 50-item test set from past inventory with known outcomes, including at least 5 fakes, repros or replaced-part items
- [ ] Run the agent blind (photo and asking price only) and score identification, authenticity flags, price error and listing edits
- [ ] Launch gate: 90%+ identification accuracy and every known fake flagged
- [ ] Measure baselines (minutes from photo to decision, purchase to live listing) before launch

## After launch
- [ ] Monthly email report on the 1st: revenue, net profit, margin, top and bottom flips, aging stock to mark down, agent stats
- [ ] Agent performance panel on the dashboard
- [ ] Weekly review of misses, added back into the test set
