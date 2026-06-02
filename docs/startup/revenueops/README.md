# TenderPulse — RevenueOps Workspace

**TenderPulse** is a productized B2B service: a curated **weekly brief of open EU public-sector contracts** matched to an agency's services and regions, built entirely on free official data ([TED](https://ted.europa.eu/en/) + national portals + the [EU Funding & Tenders Portal](https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/home)).

- **Goal:** ≥ €500/week net revenue, minimal owner involvement.
- **Languages:** French · English · Spanish (target markets: FR, ES, EU-wide).
- **Pricing:** €49 sample · €199/mo Starter · €499/mo Premium.
- **Payments:** Stripe (Payment Links — owner-created).
- **Budget:** €0 (all tools used are free tiers).

## Operating status
| Item | Status |
|---|---|
| Brand name | ✅ TenderPulse (approved) |
| Languages | ✅ FR / EN / ES |
| Payment | ✅ Stripe (links to be created by owner — see `setup/`) |
| Landing page | ✅ Built (`site/index.html`); publish via free GitHub Pages |
| Cold B2B outreach | ✅ Approved (≤10–20/day, opt-out, approved template) |
| Budget | €0 |
| Sending channel | ⏳ Needs owner business email / connected email tool |

## Folder map
| Path | What's inside |
|---|---|
| `strategy/01-strategy-and-offer.md` | Scored strategy, full offer, ICP, 7-day plan |
| `offer/sample-report/` | The sample brief (main sales asset) |
| `assets/launch-assets.md` | Landing copy + outreach/follow-up templates (FR/EN/ES) |
| `site/index.html` | Publishable landing page (GitHub Pages, €0) |
| `crm/` | Trackers: prospects, outreach log, suppression, ledgers + `tracker.md` dashboard |
| `outreach/batch-01/` | First personalized, ready-to-send outreach drafts |
| `setup/owner-setup-checklist.md` | The few owner-only steps to go live |
| `agent-memory.md` | Agent's persistent state & decision log |

## ⚠️ Privacy / repo note
The `crm/` files hold **business** prospect data (company, city, public website). Personal data is minimized — no personal emails or names are stored until verified. **Recommendation: set this repository to Private** before adding any personal contact details, to stay GDPR-aligned.

## What I cannot do from here (needs owner)
1. **Send emails** — no email-sending tool is connected; outreach drafts are prepared ready-to-send.
2. **Create Stripe payment links** — requires owner's Stripe account (steps in `setup/`).
3. **Toggle GitHub Pages on** — one settings click by owner to publish the site.
