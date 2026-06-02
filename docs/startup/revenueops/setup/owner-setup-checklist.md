# Owner Setup Checklist — go live with TenderPulse (all €0)

Everything I can build is built. These are the steps only **you** can do (account access / publishing / sending). Total time ≈ 25–30 min.

## 1. Business email (5 min) — €0
Create a free address for sending outreach and receiving sample requests, e.g. `tenderpulse.eu@gmail.com` (or on a domain later).
→ Send it to me and I'll drop it into the landing page, templates, and outreach drafts.

## 2. Stripe Payment Links (15 min) — €0 to set up (fees only per transaction)
In your Stripe Dashboard → **Payment Links → New**. Create three:

| Product | Type | Price | Currency |
|---|---|---|---|
| TenderPulse Sample Brief | One-time | €49 | EUR |
| TenderPulse Starter | Recurring · monthly | €199 | EUR |
| TenderPulse Premium | Recurring · monthly | €499 | EUR |

Tips: turn on **card + the EU methods** you want; enable **Stripe Tax** if you need VAT handling; add the TenderPulse name/logo. Payment Links have **no monthly fee** — Stripe takes a per-transaction fee only.
→ Paste the 3 link URLs back to me; I'll wire them into `site/index.html` (replace the `#` hrefs) and the landing copy.

## 3. Publish the landing page (2 min) — €0
Option A (simplest): **GitHub Pages** — repo **Settings → Pages →** deploy from this branch, folder `docs/startup/revenueops/site` (or move `index.html` to repo root / `/docs`). 
Option B: free host (Cloudflare Pages / Netlify free tier).
→ Tell me which and I'll adjust paths if needed.

## 4. Sending channel decision (decision) — €0
I have **no email-sending capability** here. Choose one:
- **A. You send batch-01 yourself** from the new email (I provide the verified, ready-to-paste messages), or
- **B. Connect an email tool/integration** so I can send within the approved limits (≤10–20/day, opt-out, logging).

## 5. Repo privacy (1 min) — recommended
Set this repository to **Private** before we add any personal contact details to the CRM (GDPR/privacy). Public business info is lower risk, but private is safer for an operations repo.

---

## What happens after you complete these
1. I verify the 8 candidate agencies (fit + public contact) and expand the list using `crm/lead-sourcing-method.md`.
2. I finalise batch-01 with real personalisation and either hand it to you (Option A) or send it (Option B).
3. I log every send in `crm/outreach-log.csv`, update `crm/tracker.md`, and route replies.
4. When someone wants to buy, they use your Stripe link; I record it in `revenue-ledger.csv` and prep fulfilment of their first weekly brief.
5. You get one concise **weekly report** (template in `strategy/01`).

## Honest expectation setting
I can't guarantee revenue or a timeline. Realistic aim: first paying customer within a few weeks of outreach starting, and €500/week net within ~8–12 weeks **if** reply/close rates hold. I'll report the real numbers and adjust.
