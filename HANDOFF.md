# HANDOFF: dropkit eBay automation

Everything you need to take this from code to a running store. Read sections
1–3 first, then follow 4–8 in order.

Repo: `victor-gaudin/startup-team`, branch `claude/ebay-ebx-army-earnings-vtwkuv`
(not merged into the main branch yet).

---

## 1. Where things stand

| Area | Status |
|---|---|
| Code (`dropkit/`) | Built. 80 automated tests pass, all against **simulated** eBay, AliExpress, CJ and Claude APIs |
| Real-world use | **Never run against real accounts.** No credentials were available while building it |
| eBay listings | **None published.** Needs your eBay keys and seller account |
| Product research | 15 candidates (`research/2026-10-04.md`, `research/candidates.json`) and 1 routine pick (`research/2026-10-05.md`). **All costs and demand are estimates; none verified on eBay yet** |
| Every-2-days research routine | Runs, but **can't save its report** (no repo access). Fix in §9 |
| GitHub Action research backup | Inactive until the branch is merged to main and an `ANTHROPIC_API_KEY` secret is added |
| Hosting | Not set up. You rent a $5/month server (§6) |

The one uncomfortable truth: **eBay only allows dropshipping from wholesale
suppliers.** Buying from AliExpress, Amazon or Walmart and shipping straight to
your buyer breaks its rules. eBay can restrict the account and hold your
payouts. CJdropshipping, supplier dropship programs and wholesalers are the
safer route. AliExpress is a grey area; that's your call.

---

## 2. What dropkit does

```
 research ──► verify (score + revenue) ──► import from supplier ──► prepare (AI copy, price, VeRO)
                                                                          │
   eBay buyer pays ──► eBay order ──► dropkit auto-orders from CJ/AliExpress ◄─ publish to eBay
                                         │
                       supplier ships ──► tracking pushed to eBay automatically
   monitor: supplier price/stock changes ──► reprice, or pause the listing
```

| Command | What it does |
|---|---|
| `dropkit status` | Shows what's configured and what's missing |
| `dropkit verify "<name>" --cost --shipping --days --sold --active --market` | Scores a product 0–100 and estimates monthly sales, revenue and profit |
| `dropkit candidates` | Loads the 15 researched products into the verification list |
| `dropkit checks` | Lists verified products, best first |
| `dropkit suppliers "<keywords>"` | Live CJ offers, fastest delivery first, plus links to other suppliers |
| `dropkit import <url>` | Imports a product (AliExpress, CJ URL or `cj:<pid>`, Amazon, Cdiscount, any shop) |
| `dropkit import-csv feed.csv` | Imports a wholesaler's price list |
| `dropkit prepare <SKU>` / `all` | AI title and description, price for your target margin, VeRO and competition checks |
| `dropkit publish <SKU>` / `all` | Publishes to eBay, or pushes changes to a listing that's already live |
| `dropkit orders` | Pulls sales, auto-orders, pushes tracking, and lists what needs you |
| `dropkit ship <order> <tracking> <carrier>` | Uploads tracking for an order you placed by hand |
| `dropkit monitor` | Re-checks supplier price and stock, then reprices or pauses |
| `dropkit research --niche ... --count N` | Claude plus web search product ideas, saved to `research/` |
| `dropkit margin <cost> --shipping <x>` | Quick price and margin calculator |
| `dropkit serve` | Web dashboard at http://127.0.0.1:8000 |

Built-in safety rails:

- It won't publish below 10% margin, with a high VeRO risk, out of stock, or
  without images.
- It publishes at most 20 new listings a day.
- Auto-order re-checks profit and stock before buying. If the sale would now
  lose money, the order goes to your manual queue.
- Supplier errors never lose an order; they fall back to the manual queue.

---

## 3. How money flows (nobody holds your bank login)

| Step | Who does it | Your one-time setup |
|---|---|---|
| Buyer pays | eBay | — |
| eBay pays out to the business bank account | eBay, automatically | Seller Hub → Payments → link the business account |
| Supplier order is placed | dropkit, automatically | API keys (§4) |
| Supplier order is paid | CJ wallet or AliExpress saved card, auto-pay | **CJ:** top up the wallet (e.g. $100) and enable auto-pay. **AliExpress:** save a business debit card and enable auto-pay |
| Tracking reaches the buyer | dropkit, automatically | — |

What can go wrong is capped at the CJ wallet balance or the card limit. Your
only recurring money task is topping up the CJ wallet. Don't paste bank
logins into Claude chats: they end up in transcripts, and no session runs
between messages anyway.

---

## 4. Accounts and keys to create

| # | Account | Where | What to copy into `.env` | Cost |
|---|---|---|---|---|
| 1 | eBay seller account (business) | ebay.com → register as business | — (verify identity, link payout bank) | Free; eBay fees per sale |
| 2 | eBay developer keys | developer.ebay.com → My Account → Application Keys | `EBAY_CLIENT_ID` (App ID), `EBAY_CLIENT_SECRET` (Cert ID) | Free |
| 3 | eBay redirect URL (RuName) | Same page → User Tokens → "Get a Token from eBay via Your Application" → add an eBay Redirect URL | `EBAY_RU_NAME` | Free |
| 4 | Anthropic API key | platform.claude.com → API keys (**separate from claude.ai credits**) | `ANTHROPIC_API_KEY` | ~$0.02–0.05 per listing; $10–20 lasts months |
| 5 | CJdropshipping | cjdropshipping.com → Authorization → API → generate key | `CJ_API_KEY` | Free; you pay product + shipping |
| 6 | AliExpress Dropshipping API (optional) | openservice.aliexpress.com → create a Dropshipping app → authorize your buyer account | `ALIEXPRESS_APP_KEY`, `ALIEXPRESS_APP_SECRET`, `ALIEXPRESS_ACCESS_TOKEN` | Free |
| 7 | Server | Hetzner, DigitalOcean, Vultr… (Ubuntu 24.04, 1 GB RAM) | — | ~$5/month |

Start with eBay **Sandbox** keys (`EBAY_ENV=sandbox`). Switch to production
keys once a full test passes (§7).

---

## 5. Set up and test locally (~30 min)

```bash
git clone https://github.com/victor-gaudin/startup-team && cd startup-team
git checkout claude/ebay-ebx-army-earnings-vtwkuv
python3 -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
pytest -q                              # expect: 80 passed
cp .env.example .env && nano .env      # fill in keys from §4
dropkit status                         # shows what's still missing

dropkit ebay-connect                   # open the URL, log in, accept
dropkit ebay-code '<the URL you were redirected to>'
dropkit ebay-policies                  # copy the 3 IDs into .env (create policies in Seller Hub first)
dropkit ebay-location Austin TX 78701 --country US   # use your real ship-from city
dropkit status                         # everything should now say configured/connected
```

Business policies to create in Seller Hub → Account → Business policies:

- **Shipping:** free shipping, handling time 2–3 days, delivery estimate
  matching the supplier.
- **Payment:** eBay managed payments.
- **Returns:** 30 days, buyer pays return shipping, or free returns if you can
  absorb them.

---

## 6. Put it on a server (runs 24/7)

On a fresh Ubuntu server, as a normal user with sudo:

```bash
sudo apt update && sudo apt install -y python3-venv git
git clone https://github.com/victor-gaudin/startup-team ~/dropkit && cd ~/dropkit
git checkout claude/ebay-ebx-army-earnings-vtwkuv
python3 -m venv .venv && .venv/bin/pip install -e .
scp your-laptop:startup-team/.env ~/dropkit/.env     # or recreate it
cp your-laptop:startup-team/dropkit.db ~/dropkit/   # keeps the eBay login and your data
chmod 600 .env dropkit.db
mkdir -p logs
```

Scheduled jobs (`crontab -e`):

```cron
*/15 * * * * cd ~/dropkit && .venv/bin/dropkit orders  >> logs/orders.log 2>&1
0 */6 * * *  cd ~/dropkit && .venv/bin/dropkit monitor >> logs/monitor.log 2>&1
30 3 * * *   cp ~/dropkit/dropkit.db ~/dropkit/backup-$(date +\%a).db
```

Dashboard as a service (`/etc/systemd/system/dropkit.service`):

```ini
[Unit]
Description=dropkit dashboard
After=network-online.target

[Service]
User=YOUR_USER
WorkingDirectory=/home/YOUR_USER/dropkit
ExecStart=/home/YOUR_USER/dropkit/.venv/bin/dropkit serve --host 127.0.0.1 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable --now dropkit
```

The dashboard has **no login**, so never bind it to `0.0.0.0`. Open it from
your laptop through an SSH tunnel:

```bash
ssh -L 8000:127.0.0.1:8000 you@your-server   # then browse http://127.0.0.1:8000
```

The database holds buyer names and addresses. Keep it on the server and in
backups only, and never commit it (`.gitignore` already excludes `*.db` and
`.env`).

---

## 7. Launch plan

**Day 1: Sandbox dry run**
1. Import 1 product, then `prepare` and `publish` with Sandbox keys.
2. Buy it with an eBay Sandbox test buyer.
3. Run `dropkit orders`. The order should show up. In Sandbox, let it go to
   the manual queue; don't auto-order real goods yet.

**Day 2: one real test order**
1. Switch to production keys and reconnect (`ebay-connect` again).
2. Pick your best CJ US-warehouse product. Import it, prepare it, publish it.
3. Buy it yourself from a second eBay account, shipped to your own address.
4. Watch for:
   - the order created in CJ with the right address and shipping method;
   - payment from the CJ wallet;
   - the tracking number appearing on the eBay order;
   - delivery days matching what the dashboard said.
5. **Only then** leave auto-order on unattended.

**Days 3–7: build to 15 listings**
1. `dropkit candidates`, then open each product's "eBay sold listings" link and
   enter the 30-day sold count, active listings and typical price in the
   dashboard.
2. Keep products scoring 70 or more ("List it"). Try 50–69 with one listing
   each, and drop the rest.
3. For each keeper:
   - run `dropkit suppliers "<keywords>"` and pick a US-warehouse offer;
   - `import`, then `prepare` (read the AI title; fix it if wrong), then
     `publish`.
4. New accounts have listing limits; check Seller Hub → Selling limits.

**Week 2 onward**
- Delete listings with zero views after 7–10 days, or change their title and
  first photo.
- Run Promoted Listings at 3–5%. It's already counted in the margin
  (`DROPKIT_PROMOTED_RATE`).

---

## 8. Your routine once it's live

| When | What | Time |
|---|---|---|
| Daily | Dashboard: **"need manual order"** count, **errors** in the activity log, buyer messages in Seller Hub | 10 min |
| Daily | Place manual-queue orders yourself, then `dropkit ship <order> <tracking> <carrier>` | as needed |
| Weekly | Top up the CJ wallet; review paused listings (supplier out of stock or price jump) | 15 min |
| Every 2 days | Read the new research pick, verify it, decide | 10 min |
| Monthly | Check eBay fee rates for your categories against `dropkit/pricing.py`; set aside tax | 15 min |

---

## 9. Fix the research routine

The routine "eBay product research (every 2 days)" (id
`trig_01Vkv135n8sX3kRD2AUvWn6v`) runs at 06:52 UTC every 2 days. Its sessions
start **without the repo attached**, so they can research but can't push.

To fix it, open the routine in claude.ai → Routines and add the repository
`victor-gaudin/startup-team`. If the routine can't take a repo, delete it and
create a new one there with the repo selected, using the same prompt.

Alternatively, merge the branch to main and add the `ANTHROPIC_API_KEY`
repository secret. The GitHub Action (`.github/workflows/research.yml`) then
does the same job every 2 days and commits the report itself.

---

## 10. Things that might break, and what to do

| Symptom | Likely cause | Fix |
|---|---|---|
| `eBay account not connected` | Refresh token missing or expired (~18 months) | `dropkit ebay-connect` + `ebay-code` |
| Publish fails: category or aspect errors | eBay requires extra item specifics for that category | Edit the copy (`prepare --notes "..."`) or `set-category <SKU> <id>` |
| Import fails with captcha / 403 | Retail site blocks bots | Use CJ/AliExpress API URLs, or set `DROPKIT_SCRAPER_PROXY` |
| CJ order created but unpaid | CJ auto-pay off or wallet empty | Top up and enable auto-pay in CJ |
| No tracking after 3+ days | Supplier hasn't shipped, or the CJ tracking field differs from expected [least-tested part] | Check the order in CJ; upload it manually with `dropkit ship`. Report it so the code can be fixed |
| Lots of "paused" listings | Supplier stock or price swings | Review them, change supplier, or end the listing |
| Orders stuck in "manual" | No API supplier for that product, or auto-order skipped because it was unprofitable | The dashboard note says why |

---

## 11. Costs to expect

| Item | Cost |
|---|---|
| eBay | ~13.6% + $0.40 per order, plus your promoted rate (4% default) |
| Anthropic API | ~$0.02–0.05 per listing, ~$0.25–1 per research run |
| Server | ~$5/month |
| CJ / AliExpress | Product + shipping, paid per order |
| Working capital | Keep $100–200 in the CJ wallet. eBay holds payouts for new sellers for up to ~30 days, so you pay suppliers before you're paid |

---

## 12. Known gaps / next work

- **Not tested against live APIs.** The first real runs (§7) are the test. The
  CJ order-detail tracking fields and the AliExpress order response shape are
  the parts most likely to need a small fix.
- No alerts yet. A CJ low-balance alert and a daily email or phone summary
  were proposed but not built.
- No Docker file yet. §6 uses plain Python with systemd and cron, which is
  enough for one server.
- Sold-listing counts are entered by hand. eBay's sold-data API (Marketplace
  Insights) needs eBay's approval to access.
- Amazon/Walmart auto-ordering is deliberately not built: it breaks their
  rules and eBay's.
- Fee rates in `dropkit/pricing.py` are approximations for "most categories".

## 13. Key files

| Path | What |
|---|---|
| `README.md` | Feature overview and scoring model |
| `.env.example` | Every setting, with comments |
| `dropkit/engine.py` | Import, prepare, publish, orders, verify, monitor |
| `dropkit/ebay.py` | eBay API client |
| `dropkit/suppliers/cj.py`, `aliexpress.py`, `generic.py`, `csv_feed.py` | Supplier adapters |
| `dropkit/scoring.py` | Verification score and revenue model |
| `dropkit/pricing.py` | Fee model and margin pricing |
| `dropkit/vero.py` | Brand and counterfeit screening |
| `dropkit/web/` | Dashboard |
| `research/` | Research reports and `candidates.json` |
| `tests/` | 80 offline tests (`pytest -q`) |
