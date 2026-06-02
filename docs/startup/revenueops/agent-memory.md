# RevenueOps Agent — Operating Memory

_Last updated: 2026-06-02. This is the agent's persistent internal record (Level 1 autonomous: internal records). No external action has been taken._

## Mission
Generate >= EUR 500/week net revenue for the owner, lawfully, ethically, sustainably, with minimal owner involvement.

## Owner / Business Profile (UPDATED 2026-06-02 — approvals received)
- Jurisdiction: EU (assumed; FR/ES target markets) — confirm exact country later
- Languages: **French, English, Spanish** ✅
- Business name: **TenderPulse** ✅ (AgentPay reserved for the SaaS)
- Payment: **Stripe** ✅ (owner to create Payment Links — specs in setup/)
- Landing page: publish **approved** ✅ (site/index.html ready for free GitHub Pages)
- Cold B2B outreach: **approved** ✅ (≤10–20/day, opt-out, approved template, suppression list)
- Budget: **€0** ✅ (all tools free-tier)
- Owner instruction: "Make me proud. Put everything in the GitHub repo, well organized. Keep a tracker of who responded / who's waiting for approval."
- Domain / business email: NOT yet provided — blocking sender identity
- Risk tolerance: assume low — confirm later

## KEY CONSTRAINT
- No email-sending tool in this environment → outreach is prepared ready-to-send; owner must send OR connect an email tool.
- Cannot access owner's Stripe/GitHub settings → owner creates Payment Links + enables Pages (checklist in setup/).

## Current State (Observe)
- Net revenue this week: EUR 0. No customers. Pre-launch.
- Asset: well-documented startup "AgentPay" — business plan, financials (3 scenarios), GTM, content calendar, roadmap, and an early Next.js MVP (landing + dashboard skeleton).
- Repo: branch `startup-docs`, working tree clean.
- AgentPay model: freemium SaaS, $29/$99 tiers, targeting $5k MRR by month 6.

## Diagnosis
1. AgentPay is a credible 6–12 month venture but is a SLOW, BUILD-HEAVY path to the EUR 500/week mandate (financial product, Stripe Link integration, ToS/Privacy, beta users, launch). It is also a regulated-adjacent financial tool = higher compliance burden.
2. To hit EUR 500/week fast and low-touch, a productized B2B intelligence/report service is a better-fit primary path. The repo's own research already surfaced strong candidates: **Government/Tender Auction Aggregator** (fits my default offer model directly).
3. These are not mutually exclusive: productized service can fund/validate while AgentPay builds.

## COMPLIANCE FLAG (must resolve before any related work)
- `meta-founder-assessment.md` lists **"cPanel Exploit Scanner"** as a #3 "GO" opportunity, citing an *active authentication-bypass exploit* and scanning servers.
- RISK: An exploit scanner that probes third-party servers without authorization may breach computer-misuse / unauthorized-access laws and my non-negotiable rules (no unauthorized access, no bypassing security controls, no malicious code). Marketing around an active exploit also carries reputational/legal risk.
- RECOMMENDATION: Formally VETO the active-scanning version. A purely *defensive* offering (CVE-feed monitoring + alerts for subscribers about their OWN authorized assets) could be lawful but is out of scope unless the owner explicitly wants it and can authorize scans.
- STATUS: Not currently being built (chosen direction was AgentPay). Flagging so it is not picked up later.

## Open Questions for Owner
See initial setup message (jurisdiction, business name, payment method, outreach approval, budget, risk tolerance, primary direction).

## Decisions / Approvals Log
- 2026-06-02: Selected **Strategy A — Weekly EU Public-Sector Opportunity Brief** as primary revenue engine (score 119 vs B 102, C/AgentPay 90). AgentPay kept as parallel long-term bet. (Agent decision, Level 1; reversible — owner may override.)
- 2026-06-02: Produced Level 1 assets: `01-strategy-and-offer.md`, `sample-report/weekly-opportunity-brief-SAMPLE.md`, `02-launch-assets-DRAFTS.md`. Nothing published/sent/spent.

## Verified facts (sources)
- TED = official EU procurement portal, ~800k notices/yr (>€815B); free Open Data Service at data.ted.europa.eu. Lawful, automatable.
- Pricing benchmarks: Hermix €160/user/mo; BidStats ~£800/yr. Our €199/€499 sits in a defensible gap.

## Open approvals (blocking go-live)
1. Confirm jurisdiction/language. 2. Final brand name + sender identity. 3. Payment method (Stripe?). 4. Permission to publish landing page. 5. Cold B2B outreach (template + ≤10–20/day + opt-out). 6. Budget (or keep €0).

## Next Action
Owner to confirm direction (A / parallel) + answer the 6 approvals. Then I build the lead list (Level 1) and prep the first outreach batch for approval per the 7-day plan.
