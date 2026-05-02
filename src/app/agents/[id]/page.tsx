
import { Suspense } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { ChevronLeft, Play, Square, RefreshCcw } from "lucide-react";
import Link from "next/link";

export default function AgentDetails({ params }: { params: { id: string } }) {
  // Mock data for the specific agent
  const agent = {
    id: params.id,
    name: "CodeReviewer",
    framework: "Pu.sh",
    status: "running",
    balance: 45.20,
    uptime: "4h 12m",
    totalSpent: "$240.15",
  };

  const logs = [
    { id: "1", time: "10:45:02", level: "info", message: "Starting file scan..." },
    { id: "2", time: "10:45:05", level: "info", message: "Detected 12 files changed in /src" },
    { id: "3", time: "10:45:10", level: "info", message: "Authorizing Stripe Link payment for LLM token usage: $0.15" },
    { id: "4", time: "10:45:11", level: "success", message: "Payment authorized (pi_3O9...)" },
    { id: "5", time: "10:45:15", level: "warn", message: "Potential security issue in auth.ts: line 42" },
  ];

  return (
    <div className="flex-1 space-y-4 p-8 pt-6">
      <div className="flex items-center space-x-4">
        <Link href="/">
          <Button variant="ghost" size="icon">
            <ChevronLeft className="h-4 w-4" />
          </Button>
        </Link>
        <h2 className="text-3xl font-bold tracking-tight">{agent.name}</h2>
        <Badge className="ml-2">{agent.status}</Badge>
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Uptime</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{agent.uptime}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Current Balance</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">${agent.balance.toFixed(2)}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Total Lifetime Spend</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{agent.totalSpent}</div>
          </CardContent>
        </Card>
        <Card className="flex items-center justify-center p-6">
          <div className="flex space-x-2">
            <Button variant="outline" size="icon">
              <RefreshCcw className="h-4 w-4" />
            </Button>
            {agent.status === 'running' ? (
              <Button variant="destructive" size="icon">
                <Square className="h-4 w-4" />
              </Button>
            ) : (
              <Button size="icon">
                <Play className="h-4 w-4" />
              </Button>
            )}
          </div>
        </Card>
      </div>

      <Card className="col-span-4">
        <CardHeader>
          <CardTitle>Session Replay & Logs</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="bg-black text-green-400 p-4 rounded-md font-mono text-sm h-[400px] overflow-y-auto">
            {logs.map((log) => (
              <div key={log.id} className="mb-1">
                <span className="text-gray-500">[{log.time}]</span>{" "}
                <span className={log.level === 'error' ? 'text-red-500' : log.level === 'warn' ? 'text-yellow-500' : log.level === 'success' ? 'text-blue-400' : 'text-green-400'}>
                  {log.level.toUpperCase()}:
                </span>{" "}
                {log.message}
              </div>
            ))}
            <div className="animate-pulse">_</div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
