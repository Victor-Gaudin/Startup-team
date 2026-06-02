# Lead Sourcing Method (lawful, repeatable, €0)

Goal: build a steady list of well-fit, **business** prospects without scraping restricted sources or harvesting personal data.

## Ideal target (ICP recap)
EU digital / IT / marketing agency or consultancy, ≈5–50 staff, that wants public-sector (B2G) work but has no dedicated bid team. Buyer = owner / BD lead / head of growth.

## Where to source (public, allowed)
1. **Public agency directories** — Sortlist, Clutch, SEMrush agency lists, national association directories. Use their filters (country, service, size) to shortlist.
2. **Each agency's own website** — confirm services, region focus, and the **public business contact** (contact page / generic info@ / contact form). This is the lawful contact channel.
3. **Public award notices on TED** — agencies that have *already* bid/won public contracts are warm-fit (they clearly want this work). TED award notices are public.
4. **Industry events / association member lists** — public membership pages.

## What we record (data minimisation)
- Company, city, country, website, service focus, language, source, fit notes.
- Contact = **public business channel** (generic email or contact form). 
- We do **not** store individuals' personal emails or names in the repo until verified, and only with a lawful B2B basis. Prefer role-based/generic business contacts.

## Verification gate (before any outreach)
A candidate moves `CANDIDATE_UNVERIFIED → VERIFIED` only when:
1. Fit confirmed (plausibly wants public-sector work, right size, right region).
2. A lawful public business contact exists.
3. A genuine, specific personalisation point is found (a real service/project to reference — never invented).

## Compliance guardrails
- B2B only; legitimate-interest basis; clear opt-out in every message; immediate suppression on opt-out.
- ≤10–20 personalised messages/day; one contact per company until they reply.
- Respect each directory's and site's terms; no scraping behind logins/paywalls; no bypassing rate limits.
- Keep the prospect file in a **private** repo once personal data is added.

## Current seed (2026-06-02)
8 candidates in `prospects.csv` (5 ES, 3 FR), all `CANDIDATE_UNVERIFIED`, pulled from public directories. Each still needs the verification gate above before it can be contacted. This is a demonstration seed — scale via the steps above once the sending channel is set up.
