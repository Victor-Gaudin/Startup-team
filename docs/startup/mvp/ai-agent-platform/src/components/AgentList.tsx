'use client';

import { useEffect, useState } from "react";
import { createClient } from "@supabase/supabase-js";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";

const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
);

type Agent = {
  id: string;
  name: string;
  framework: string | null;
  status?: string;
  balance: number;
};

export function AgentList() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchAgents() {
      const { data, error } = await supabase
        .from("agents")
        .select("*")
        .order("created_at", { ascending: false });

      if (!error && data) setAgents(data);
      setLoading(false);
    }
    fetchAgents();
  }, []);

  const getStatus = (agent: Agent) => agent.status ?? "idle";

  const badgeVariant = (status: string) => {
    if (status === "running") return "default";
    if (status === "failed") return "destructive";
    return "secondary";
  };

  if (loading) {
    return (
      <Card>
        <CardHeader><CardTitle>My Agents</CardTitle></CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">Loading agents...</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>My Agents</CardTitle>
      </CardHeader>
      <CardContent>
        {agents.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            No agents yet. Create your first one above.
          </p>
        ) : (
          <div className="space-y-4">
            {agents.map((agent) => (
              <div
                key={agent.id}
                className="flex items-center justify-between p-4 border rounded-lg"
              >
                <div className="space-y-1">
                  <p className="text-sm font-medium leading-none">{agent.name}</p>
                  <p className="text-xs text-muted-foreground">
                    {agent.framework ?? "No framework"}
                  </p>
                </div>
                <div className="flex items-center space-x-4">
                  <div className="text-right space-y-1">
                    <p className="text-sm font-medium">
                      ${Number(agent.balance).toFixed(2)}
                    </p>
                    <p className="text-xs text-muted-foreground">Wallet Balance</p>
                  </div>
                  <Badge variant={badgeVariant(getStatus(agent))}>
                    {getStatus(agent)}
                  </Badge>
                </div>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
