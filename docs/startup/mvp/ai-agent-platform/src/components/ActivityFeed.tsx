'use client';

import { useEffect, useState } from "react";
import { createClient } from "@supabase/supabase-js";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Avatar, AvatarFallback } from "@/components/ui/Avatar";

const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
);

type Transaction = {
  id: string;
  amount: number;
  description: string | null;
  status: string;
  created_at: string;
  agents: { name: string } | null;
};

export function ActivityFeed() {
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchActivity() {
      const { data, error } = await supabase
        .from("transactions")
        .select("id, amount, description, status, created_at, agents(name)")
        .order("created_at", { ascending: false })
        .limit(10);

      if (!error && data) setTransactions(data as Transaction[]);
      setLoading(false);
    }
    fetchActivity();
  }, []);

  const getInitials = (name: string) =>
    name.split(/[\s-_]/).map((w) => w[0]).join("").toUpperCase().slice(0, 2);

  const timeAgo = (dateStr: string) => {
    const diff = Math.floor((Date.now() - new Date(dateStr).getTime()) / 1000);
    if (diff < 60) return `${diff}s ago`;
    if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
    if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
    return `${Math.floor(diff / 86400)}d ago`;
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Recent Activity</CardTitle>
      </CardHeader>
      <CardContent>
        {loading ? (
          <p className="text-sm text-muted-foreground">Loading activity...</p>
        ) : transactions.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            No transactions yet.
          </p>
        ) : (
          <div className="space-y-8">
            {transactions.map((tx) => {
              const agentName = tx.agents?.name ?? "Unknown Agent";
              return (
                <div key={tx.id} className="flex items-center">
                  <Avatar className="h-9 w-9">
                    <AvatarFallback>{getInitials(agentName)}</AvatarFallback>
                  </Avatar>
                  <div className="ml-4 space-y-1">
                    <p className="text-sm font-medium leading-none">
                      {agentName}
                    </p>
                    <p className="text-sm text-muted-foreground">
                      {tx.description ?? "Payment"}{" "}
                      <span className="font-bold text-foreground">
                        ${Number(tx.amount).toFixed(2)}
                      </span>
                    </p>
                  </div>
                  <div className="ml-auto text-xs text-muted-foreground">
                    {timeAgo(tx.created_at)}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
