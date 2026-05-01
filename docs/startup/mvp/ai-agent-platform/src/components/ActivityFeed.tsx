
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Avatar, AvatarFallback } from "@/components/ui/Avatar";

const activities = [
  {
    id: "1",
    agent: "CodeReviewer",
    action: "Authorized payment",
    amount: "$2.50",
    time: "2 mins ago",
    initials: "CR",
  },
  {
    id: "2",
    agent: "GTM-Bot",
    action: "Completed task",
    time: "1 hour ago",
    initials: "GB",
  },
  {
    id: "3",
    agent: "SecurityScanner",
    action: "Failed authorization",
    time: "10 mins ago",
    initials: "SS",
  },
];

export function ActivityFeed() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Recent Activity</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-8">
          {activities.map((activity) => (
            <div key={activity.id} className="flex items-center">
              <Avatar className="h-9 w-9">
                <AvatarFallback>{activity.initials}</AvatarFallback>
              </Avatar>
              <div className="ml-4 space-y-1">
                <p className="text-sm font-medium leading-none">
                  {activity.agent}
                </p>
                <p className="text-sm text-muted-foreground">
                  {activity.action} {activity.amount && <span className="font-bold text-foreground">{activity.amount}</span>}
                </p>
              </div>
              <div className="ml-auto text-xs text-muted-foreground">
                {activity.time}
              </div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
