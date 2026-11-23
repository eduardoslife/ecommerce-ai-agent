# Product requirements (summary)

Condensed from the full PRD.

## Summary
An e-commerce business selling used electronics, focused on its two highest-margin categories (cameras and high-end audio), runs an AI agent that turns one product photo into a buy/pass verdict, an authenticity risk score and a ready-to-approve listing. The agent is built on a custom MCP server that connects Claude to the marketplace, a Google Sheets ledger and a monitoring dashboard. A human approves every purchase and every listing.

## Goals
- Cut time from photo to buy decision, and from purchase to live listing
- Catch counterfeit, repro and high-risk items before purchase
- Log every purchase, sale and expense automatically for tax season
- One live view of inventory, margin and agent performance

## Non-goals (v1)
- Fully autonomous buying or listing
- Guaranteed authentication (risk score, not proof)
- Multiple marketplaces and automatic repricing

## Success metrics
Every metric needs a measured baseline before launch and a measured result after. Only measured numbers are reported.

| Metric | Baseline | Target | How measured |
|---|---|---|---|
| Minutes from photo to buy decision | Time 10 manual decisions | 50% faster | Timestamps in the ledger |
| Minutes from purchase to live listing | Time 10 manual listings | 60% faster | Purchase date vs listing start |
| Identification accuracy | n/a | 90%+ | 50-item eval set |
| Authenticity flag recall | n/a | Every known fake flagged | Eval set with seeded fakes |
| Listings approved without edits | n/a | 70%+ | Logged per listing |
| Pricing error | n/a | Within 15% of sale price | Predicted vs final |
| Tax records captured | Current manual records | 100% | Ledger vs marketplace and bank |

## Risk register

| Risk | Impact | Safeguard |
|---|---|---|
| False "authentic" call on a fake | Lost cost, buyer claim, account risk | Risk score with reasons, never yes/no. Low confidence forces close-ups. Human decides. |
| Made-up specs in a listing | "Not as described" returns | Lister uses only photo and identifier facts. Human approves every listing. |
| Over- or underpriced buy | Lost margin | Price range with comp count. Flag under 5 comps. |
| Agent has too much access | Unwanted listings or edits | Least-privilege scopes, propose-only writes, full action log |
| Marketplace policy violation | Listing removal, penalties | Policy check before draft, banned-terms list |
| Credential leak | Account takeover | Secrets store, never in code or the sheet |
| Incomplete tax records | Missed deductions | Monthly reconcile against payouts and bank records |

## Evaluation plan
1. Build a 50-item test set from past inventory with known outcomes, including at least 5 fakes, repros or replaced-part items.
2. Run the agent blind: photo and asking price only.
3. Score model identification, authenticity flag, price error and listing edits.
4. Tune prompts and checklists, then re-run the full set to confirm nothing got worse.
5. After launch, log every verdict, review misses weekly and add them to the set.

**Launch gate:** meets the identification and authenticity targets on the full test set.
