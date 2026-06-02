# TenderPulse — Live Tracker / Dashboard

_Last updated: 2026-06-02 by RevenueOps Agent. Source data: the CSVs in this folder._

## Revenue vs target
| Metric | This week | Target |
|---|---|---|
| Gross revenue | €0 | — |
| **Net revenue** | **€0** | **€500 / week** |
| Active customers | 0 | 3–5 |
| MRR | €0 | ~€2,170 |

## Pipeline funnel
| Stage | Count |
|---|---|
| Candidates (unverified) | 8 |
| Verified & ready to send | 0 |
| Contacted | 0 |
| Replied — positive | 0 |
| Replied — negative / opt-out | 0 |
| Samples sent | 0 |
| Proposals sent | 0 |
| **Won (paying)** | **0** |

## 🔴 Waiting on OWNER (action queue)
| # | What | Why it's blocked | Effort |
|---|---|---|---|
| 1 | Provide a **business email** for TenderPulse (free Gmail is fine at €0) | Needed as sender identity + sample-request inbox; no email tool is connected here | 5 min |
| 2 | Create **3 Stripe Payment Links** (€49 / €199-mo / €499-mo) | I can't access your Stripe account; specs are in `setup/` | 15 min |
| 3 | Enable **GitHub Pages** on this repo (or confirm host) to publish `site/index.html` | One settings toggle; publishing is owner-gated | 2 min |
| 4 | Decide: do you **send batch-01 yourself**, or connect an email tool so I can? | No sending capability in this environment | decision |
| 5 | Recommend setting this **repo to Private** before adding personal contact data | GDPR / privacy — repo may be public | 1 min |

## 👥 Who responded
_None yet — no outreach has been sent. This table fills automatically as replies come in._

| Date | Company | Reply | Sentiment | Next step | Owner action? |
|---|---|---|---|---|---|
| — | — | — | — | — | — |

## 📇 Prospects (candidates — see `prospects.csv`)
All 8 are **unverified candidates** from public agency directories. Before any outreach each needs: (a) fit check (do they plausibly want public-sector work?), (b) a lawful public business contact, (c) a personalised first line. **None have been contacted.**

| ID | Company | Country | Status |
|---|---|---|---|
| P001 | Arimetrics | ES | candidate (verify) |
| P002 | Bautista Consulting | ES | candidate (verify) |
| P003 | Wola Publicidad | ES | candidate (verify) |
| P004 | Retrazos | ES | candidate (verify) |
| P005 | Agencia Fenix 360 | ES | candidate (verify) |
| P006 | Agence THRIVE | FR | candidate (verify domain) |
| P007 | My Andrea | FR | candidate (verify domain) |
| P008 | Clutch (Paris) | FR | candidate (verify domain) |

## 🚫 Suppression list
0 entries. Opt-outs are added immediately to `suppression-list.csv` and never contacted again.

## 💸 Ledgers
- Revenue: `revenue-ledger.csv` — €0 recorded.
- Expenses: `expense-ledger.csv` — €0 (budget €0; all tools free-tier).

---
### How this tracker is maintained
- Agent updates the CSVs as the source of truth, then refreshes the counts above.
- Statuses: `CANDIDATE_UNVERIFIED → VERIFIED → READY_TO_SEND → SENT → REPLIED_POSITIVE/REPLIED_NEGATIVE → SAMPLE_SENT → PROPOSAL_SENT → WON/LOST/OPT_OUT`.
- Anything needing a human decision appears in **🔴 Waiting on OWNER** above.
