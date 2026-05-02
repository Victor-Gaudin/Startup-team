
# AI Agent Hosting & Observability Platform (AgentPay)

This is an MVP for a platform that provides infrastructure, identity, and observability for autonomous AI agents, with a focus on Stripe Link integration for agentic payments.

## Features
- **Agent Dashboard**: Monitor active agents, session status, and wallet balances.
- **Stripe Link Integration**: Standardized layer for AI agents to authorize and process payments autonomously.
- **Observability**: Real-time logs and session replay for debugging non-deterministic agent behavior.
- **Agent SDK**: Lightweight wrapper for integrating agents with the platform.

## Tech Stack
- **Framework**: Next.js 16 (App Router)
- **Styling**: Tailwind CSS v4
- **Database**: Supabase (PostgreSQL)
- **Payments**: Stripe (Link for Agents API)
- **Deployment**: Vercel

## Setup

1. **Clone the repo**
2. **Install dependencies**: `npm install`
3. **Environment Variables**: Copy `.env.example` to `.env.local` and fill in your Stripe and Supabase keys.
4. **Database Schema**: Run the SQL in `schema.sql` in your Supabase SQL editor.
5. **Run Dev Server**: `npm run dev`

## API Endpoints
- `/api/health`: Health monitoring
- `/api/webhooks/stripe`: Stripe webhook handler (TBD)
- `/api/agents`: Agent management (TBD)

## Standards
- Health endpoint: `/api/health`
- Managed services: Supabase, Stripe, Vercel
- Environment variables documented in `.env.example`
