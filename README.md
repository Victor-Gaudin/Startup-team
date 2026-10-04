# dropkit

Self-hosted replacement for EBX-style eBay automation tools. It does what EBX's
paid plans do, without the monthly fee or listing caps. You pay only for your
own Claude API usage, roughly $0.02–0.05 per listing.

| EBX feature | dropkit |
|---|---|
| Multi-supplier import (AliExpress, Amazon, Cdiscount) | `dropkit import <url>`. AliExpress goes through the official Dropshipping API when keys are set; any other shop is read from the page's schema.org/OpenGraph data. Wholesale CSV feeds via `dropkit import-csv`. |
| AI titles (80 chars, SEO) + HTML descriptions | Claude (`claude-opus-5-5` by default) writes copy in en-US, en-GB, fr-FR or de-DE. Output is length-checked and the HTML sanitized (no scripts, links or styles, which eBay rejects). |
| Margin estimate / "Snipe Bot" price comparison | Fee-accurate margin engine for each marketplace, a target-margin price (rounded to .99), and live competitor prices from eBay's Browse API. |
| Auto-Order | eBay orders are pulled automatically. AliExpress orders are placed through the API with the buyer's address, but only after re-checking that the sale is still profitable. Tracking is pushed back to eBay automatically. |
| Price/stock sync | `dropkit monitor` reprices when supplier cost moves, sets quantity to 0 when the supplier runs out, restocks when it returns, and pauses for review on large price jumps. |
| VeRO protection | Blocks counterfeit wording, authenticity claims next to brands, and brands in titles not phrased as compatibility. |
| Product research | `dropkit research` uses Claude with live web search to rank fast-selling products and links to eBay "sold" searches so you can verify demand. A GitHub Action runs it every 2 days. |
| Dashboard | `dropkit serve` opens a local web UI with listings, margins, orders, a manual-order queue and an activity log. |
| Official eBay API, OAuth 2.0 | Yes: Sell Inventory, Account, Fulfillment, Commerce Taxonomy and Buy Browse APIs. |

### Deliberate differences

- **No anti-detection tricks.** EBX advertises random delays that "mimic human
  behavior" to avoid account restrictions. dropkit only uses eBay's official API
  with plain rate limiting and retries. Disguising automation doesn't fix a
  policy violation, and it isn't something this tool does.
- **No Amazon auto-ordering.** Amazon has no ordering API for this. Scripted
  checkout breaks Amazon's terms and gets accounts closed. Amazon and Cdiscount
  sales go to a manual-order queue that includes the supplier link and buyer
  address.
- **Read eBay's dropshipping policy.** eBay allows dropshipping only from
  wholesale suppliers. Buying from another retailer or marketplace and shipping
  directly to your buyer is not allowed and can get the account restricted.
  The safest setup is a wholesaler or a supplier dropship program
  (`dropkit import-csv`). The AliExpress Dropshipping API is a grey area; that
  call is yours.

## Setup (about 30 minutes)

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env        # then fill it in
pytest                      # 66 tests, all offline
```

1. **Claude API key**: create one at https://platform.claude.com and set
   `ANTHROPIC_API_KEY` in `.env`.
2. **eBay developer keys**: sign up at https://developer.ebay.com, create a
   keyset (start with Sandbox) and copy the App ID (`EBAY_CLIENT_ID`) and Cert
   ID (`EBAY_CLIENT_SECRET`). Under *User Tokens → Get a Token from eBay via
   Your Application*, create a redirect URL and copy its **RuName**
   (`EBAY_RU_NAME`).
3. **Connect your seller account**:
   ```bash
   dropkit ebay-connect                  # open the printed URL, accept
   dropkit ebay-code '<redirect url>'    # paste the URL you land on
   ```
4. **Business policies**: create shipping, payment and return policies in
   Seller Hub. Then run `dropkit ebay-policies` and put the three IDs in `.env`.
   Set the shipping policy's handling time and delivery estimate to match your
   supplier.
5. **Inventory location** (required by eBay once):
   `dropkit ebay-location Austin TX 78701 --country US`.
6. **AliExpress auto-order (optional)**: create a Dropshipping app at
   https://openservice.aliexpress.com, authorize your buyer account and set
   `ALIEXPRESS_APP_KEY`, `ALIEXPRESS_APP_SECRET` and `ALIEXPRESS_ACCESS_TOKEN`.
   Enable auto-pay in AliExpress, or pay orders there yourself.

When everything works in Sandbox, switch to `EBAY_ENV=production` with your
production keyset and reconnect.

## Daily use

```bash
dropkit research --niche "phone and gaming accessories" --count 5   # ideas -> research/YYYY-MM-DD.md
dropkit import https://www.aliexpress.com/item/1005006123456789.html
dropkit prepare DK-00001          # AI copy + price + VeRO + competitor check
dropkit list
dropkit publish DK-00001          # or: dropkit publish all
dropkit orders                    # sync sales, auto-order, push tracking, show manual queue
dropkit ship <order-key> <tracking> USPS   # for manually ordered sales
dropkit monitor                   # supplier price/stock -> reprice/pause
dropkit serve                     # dashboard at http://127.0.0.1:8000
dropkit margin 4.50 --shipping 1  # quick calculator
```

Run automation unattended with `dropkit run --interval-minutes 30`, or with
cron:

```cron
*/30 * * * * cd /path/to/repo && .venv/bin/dropkit orders  >> logs/orders.log 2>&1
15 */6 * * * cd /path/to/repo && .venv/bin/dropkit monitor >> logs/monitor.log 2>&1
```

### Safety rails built in

- Won't publish below `DROPKIT_MIN_MARGIN`, with a high VeRO risk, out of stock,
  or without images.
- Publishes at most 20 listings a day, because new eBay accounts have selling
  limits.
- Auto-order re-checks supplier price and stock first. If the sale would now
  lose money, it moves to the manual queue instead.
- Supplier fetch failures never end a listing or lose an order. They are logged
  and reported.

## Settings that matter

| Variable | Default | Meaning |
|---|---|---|
| `DROPKIT_TARGET_MARGIN` | 0.20 | Net margin used to price new listings |
| `DROPKIT_MIN_MARGIN` | 0.10 | Below this, publishing is refused and the monitor reprices |
| `DROPKIT_PROMOTED_RATE` | 0.04 | Promoted Listings ad rate, included in the margin |
| `DROPKIT_FX_RATE` | 1.0 | Supplier currency → marketplace currency |
| `DROPKIT_MODEL` | claude-opus-5-5 | Claude model for copy and research |
| `DROPKIT_SCRAPER_PROXY` | — | Proxy for supplier pages (e.g. OxyLabs) when sites block plain requests |

Fee rates in `dropkit/pricing.py` approximate eBay's "most categories" rates
for business sellers. Check them against your category's fees.

## Project layout

```
dropkit/
  ai.py            Claude listing writer + web-search product researcher
  ebay.py          eBay REST client (OAuth, inventory, offers, orders, taxonomy, browse)
  engine.py        import -> prepare -> publish, order sync/auto-order/tracking, monitor
  pricing.py       fee model, margin, target-margin pricing
  vero.py          brand / counterfeit risk screening
  suppliers/       aliexpress (official DS API), generic page parser, csv feed
  web/             FastAPI dashboard
  cli.py           `dropkit` command
tests/             offline tests with mocked eBay, AliExpress and Claude APIs
```
