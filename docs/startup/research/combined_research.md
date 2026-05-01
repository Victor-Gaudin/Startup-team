# Research: LinkedIn Extension Privacy Tool
- **Signal**: LinkedIn scans for 6,278 extensions.
- **Mechanism**: `fetch()` to `chrome-extension://` URLs + DOM "Spectroscopy".
- **Competitors**: browsergate.eu (Legal/Monitoring), 404privacy.com (Blogging/Awareness).
- **Validation**: High user frustration; Criminal investigation in Germany (Bavarian central cybercrime office).

# Research: Government Auction Aggregator
- **Target**: US Federal/State auctions.
- **Competitor**: BidProwl.com (28 sources, "Daily Picks" newsletter).
- **Pricing**: BidProwl appears free/newsletter-led. Paid competitors like GovernmentAuctions.org charge $18-40/mo for a "directory".
- **Gap**: Real-time alerts and better "scoring" of deals (BidProwl does scoring, but there's room for more niche filters).

# Research: SQLite Infrastructure (Turso)
- **Maturity**: High. SOC2, HIPAA, Point-In-Time Restore, SSO.
- **Competitors**: Cloudflare D1, SQLite Cloud, honker.dev (Durable queues).
- **Gap**: "Infra-in-a-box" for agents (Durable Task Queues specifically optimized for long-running agents).

# Research: AI Model Routing (Claude Code/OpenClaw)
- **Signal**: Claude Code instability + "OpenClaw" alternative momentum.
- **Pain**: Usage limits, lack of SLA, brand-sensitive blocking.
- **Competitors**: ACP (Agentic Control Plane), OneManCompany Talent Market.
- **Validation**: Power users are double-prompting due to errors; high demand for "governance" and "routing" layers.

# Research: AI Agent Stripe SDK (Stripe Link)
- **Signal**: Stripe Link for Agents launched.
- **Status**: Nascent. No dominant "Agent SDK" for payments yet.
- **Opportunity**: A unified SDK that handles agent identity + payment authorization + cost tracking.

# Research: AI Agent Hosting & Observability (Winner)
- **Why**: Framework explosion (Pu.sh, Craft-agents) + Stripe payments.
- **Problem**: Vercel isn't built for long-running browser-heavy agents.
- **Competitors**: Browserbase (browser-only), Vercel (general), LangGraph (orchestration, not hosting).
