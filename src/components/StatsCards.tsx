
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { CreditCard, Activity, Users, AlertCircle } from "lucide-react";

export function StatsCards() {
  const stats = [
    {
      title: "Total Agents",
      value: "12",
      description: "+2 from last week",
      icon: Users,
    },
    {
      title: "Active Sessions",
      value: "4",
      description: "Running now",
      icon: Activity,
    },
    {
      title: "Total Spent",
      value: "$1,284.50",
      description: "+12.5% from last month",
      icon: CreditCard,
    },
    {
      title: "Failed Runs",
      value: "2",
      description: "Requires attention",
      icon: AlertCircle,
    },
  ];

  return (
    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
      {stats.map((stat) => (
        <Card key={stat.title}>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">
              {stat.title}
            </CardTitle>
            <stat.icon className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stat.value}</div>
            <p className="text-xs text-muted-foreground">
              {stat.description}
            </p>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
