
-- Enable UUID extension
create extension if not exists "uuid-ossp";

-- Agents table
create table if not exists agents (
  id uuid primary key default uuid_generate_v4(),
  name text not null,
  framework text,
  stripe_link_account_id text unique,
  balance decimal(10, 2) default 0.00,
  created_at timestamp with time zone default timezone('utc'::text, now()) not null,
  updated_at timestamp with time zone default timezone('utc'::text, now()) not null
);

-- Sessions table
create table if not exists sessions (
  id uuid primary key default uuid_generate_v4(),
  agent_id uuid references agents(id) on delete cascade,
  status text check (status in ('idle', 'running', 'failed', 'completed')) default 'idle',
  started_at timestamp with time zone default timezone('utc'::text, now()) not null,
  ended_at timestamp with time zone,
  metadata jsonb default '{}'::jsonb
);

-- Transactions table
create table if not exists transactions (
  id uuid primary key default uuid_generate_v4(),
  agent_id uuid references agents(id) on delete cascade,
  session_id uuid references sessions(id) on delete set null,
  amount decimal(10, 2) not null,
  currency text default 'USD',
  stripe_payment_intent_id text,
  status text not null,
  description text,
  created_at timestamp with time zone default timezone('utc'::text, now()) not null
);

-- Logs table for observability
create table if not exists logs (
  id uuid primary key default uuid_generate_v4(),
  session_id uuid references sessions(id) on delete cascade,
  timestamp timestamp with time zone default timezone('utc'::text, now()) not null,
  level text check (level in ('info', 'warn', 'error', 'debug')) default 'info',
  message text not null,
  metadata jsonb default '{}'::jsonb
);
