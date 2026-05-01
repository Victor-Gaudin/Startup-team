'use client';

import { Suspense, useState } from "react";
import { createClient } from "@supabase/supabase-js";
import { AgentList } from "@/components/AgentList";
import { StatsCards } from "@/components/StatsCards";
import { ActivityFeed } from "@/components/ActivityFeed";
import { Button } from "@/components/ui/Button";
import { Plus } from "lucide-react";

const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
);

export default function Dashboard() {
  const [showForm, setShowForm] = useState(false);
  const [name, setName] = useState("");
  const [framework, setFramework] = useState("");
  const [saving, setSaving] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);

  async function createAgent() {
    if (!name.trim()) return;
    setSaving(true);
    await supabase.from("agents").insert({
      name: name.trim(),
      framework: framework.trim() || null,
      balance: 0.00,
    });
    setName("");
    setFramework("");
    setShowForm(false);
    setSaving(false);
    setRefreshKey((k) => k + 1);
  }

  return (
    <div className="flex-1 space-y-4 p-8 pt-6">
      <div className="flex items-center justify-between space-y-2">
        <h2 className="text-3xl font-bold tracking-tight">Agent Dashboard</h2>
        <div className="flex items-center space-x-2">
          <Button onClick={() => setShowForm((v) => !v)}>
            <Plus className="mr-2 h-4 w-4" />
            New Agent
          </Button>
        </div>
      </div>

      {showForm && (
        <div className="border rounded-lg p-4 space-y-3 max-w-md bg-card">
          <p className="text-sm font-semibold">Create a new agent</p>
          <input
            className="w-full border rounded px-3 py-2 text-sm bg-background"
            placeholder="Agent name (e.g. ResearchBot)"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
          <input
            className="w-full border rounded px-3 py-2 text-sm bg-background"
            placeholder="Framework (e.g. LangChain) — optional"
            value={framework}
            onChange={(e) => setFramework(e.target.value)}
          />
          <div className="flex space-x-2">
            <Button onClick={createAgent} disabled={saving || !name.trim()}>
              {saving ? "Creating..." : "Create"}
            </Button>
            <Button variant="outline" onClick={() => setShowForm(false)}>
              Cancel
            </Button>
          </div>
        </div>
      )}

      <StatsCards key={`stats-${refreshKey}`} />

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-7">
        <div className="col-span-4">
          <Suspense fallback={<div>Loading agents...</div>}>
            <AgentList key={`agents-${refreshKey}`} />
          </Suspense>
        </div>
        <div className="col-span-3">
          <Suspense fallback={<div>Loading activity...</div>}>
            <ActivityFeed key={`activity-${refreshKey}`} />
          </Suspense>
        </div>
      </div>
    </div>
  );
}
