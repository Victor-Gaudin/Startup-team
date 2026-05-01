
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";

const agents = [
  {
    id: "1",
    name: "CodeReviewer",
    framework: "Pu.sh",
    status: "running",
    lastRun: "2 mins ago",
    balance: 45.20,
  },
  {
    id: "2",
    name: "GTM-Bot",
    framework: "LangGraph",
    status: "idle",
    lastRun: "1 hour ago",
    balance: 120.00,
  },
  {
    id: "3",
    name: "SecurityScanner",
    framework: "Craft",
    status: "failed",
    lastRun: "10 mins ago",
    balance: 12.50,
  },
];

export function AgentList() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>My Agents</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          {agents.map((agent) => (
            <div
              key={agent.id}
              className="flex items-center justify-between p-4 border rounded-lg"
            >
              <div className="space-y-1">
                <p className="text-sm font-medium leading-none">{agent.name}</p>
                <p className="text-xs text-muted-foreground">{agent.framework}</p>
              </div>
              <div className="flex items-center space-x-4">
                <div className="text-right space-y-1">
                  <p className="text-sm font-medium">${agent.balance.toFixed(2)}</p>
                  <p className="text-xs text-muted-foreground">Wallet Balance</p>
                </div>
                <Badge variant={agent.status === 'running' ? 'default' : agent.status === 'failed' ? 'destructive' : 'secondary'}>
                  {agent.status}
                </Badge>
              </div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
