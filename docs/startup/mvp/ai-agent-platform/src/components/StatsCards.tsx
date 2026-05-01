'use client';

import { useEffect, useState } from "react";
import { createClient } from "@supabase/supabase-js";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { CreditCard, Activity, Users, AlertCircle } from "lucide-react";

const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
);

export function StatsCards() {
  const [totalAgents, setTotalAgents] = useState(0);
  const [activeSessions, setActiveSessions] = useState(0);
  const [totalSpent, setTotalSpent] = useState(0);
  const [failedRuns, setFailedRuns] = useState(0);

  useEffect(() => {
    async function fetchStats() {
      const { count: agentCount } = await supabase
        .from("agents")
        .select("*", { count: "exact", head: true });

      const { count: sessionCount } = await supabase
        .from("sessions")
        .select("*", { count: "exact", head: true })
        .eq("status", "running");

      const { data: txData } = await supabase
        .from("transactions")
        .select("amount");

      const { count: failedCount } = await supabase
        .from("sessions")
        .select("*", { count: "exact", head: true })
        .eq("status", "failed");

      setTotalAgents(agentCount ?? 0);
      setActiveSessions(sessionCount ?? 0);
      setTotalSpent(
        txData?.reduce((sum, tx) => sum + Number(tx.amount), 0) ?? 0
      );
      setFailedRuns(failedCount ?? 0);
    }
    fetchStats();
  }, []);

  const stats = [
    {
      title: "Total Agents",
      value: totalAgents.toString(),
      description: "All registered agents",
      icon: Users,
    },
    {
      title: "Active Sessions",
      value: activeSessions.toString(),
      description: "Running now",
      icon: Activity,
    },
    {
      title: "Total Spent",
      value: `$${totalSpent.toFixed(2)}`,
      description: "Across all agents",
      icon: CreditCard,
    },
    {
      title: "Failed Runs",
      value: failedRuns.toString(),
      description: failedRuns > 0 ? "Requires attention" : "All clear",
      icon: AlertCircle,
    },
  ];

  return (
    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
      {stats.map((stat) => (
        <Card key={stat.title}>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">{stat.title}</CardTitle>
            <stat.icon className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stat.value}</div>
            <p className="text-xs text-muted-foreground">{stat.description}</p>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
