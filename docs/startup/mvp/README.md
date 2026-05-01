# AgentPay — AI Agent Payments Dashboard

## Product
The Stripe dashboard for AI agents. Give your autonomous agents their own payment accounts with spend limits and transaction visibility.

## Tech Stack
- **Frontend:** React + Next.js + TypeScript
- **Backend:** Node.js API routes (Next.js)
- **Payments:** Stripe Link API for AI agents
- **Database:** Supabase (PostgreSQL)
- **Hosting:** Vercel

## Quick Start
```bash
npm install
cp .env.example .env.local  # fill in your Stripe + Supabase keys
npm run dev
```

## Environment Variables
```
STRIPE_SECRET_KEY=sk_...
STRIPE_LINK_API_KEY=link_...
NEXT_PUBLIC_SUPABASE_URL=https://...
NEXT_PUBLIC_SUPABASE_ANON_KEY=...
```

## Project Structure
```
/app                    # Next.js app router pages
/components             # React components
/lib                    # Stripe Link SDK wrapper, Supabase client
/routes/api             # API routes (webhooks, agent creation)
/mvp/                   # Landing page MVP
```

## Status
MVP landing page deployed. Core dashboard in progress.
