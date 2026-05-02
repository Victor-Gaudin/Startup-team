
import { Suspense } from 'react';
import { AgentList } from '@/components/AgentList';
import { StatsCards } from '@/components/StatsCards';
import { ActivityFeed } from '@/components/ActivityFeed';
import { Button } from '@/components/ui/Button';
import { Plus } from 'lucide-react';

export default function Dashboard() {
  return (
    <div className="flex-1 space-y-4 p-8 pt-6">
      <div className="flex items-center justify-between space-y-2">
        <h2 className="text-3xl font-bold tracking-tight">Agent Dashboard</h2>
        <div className="flex items-center space-x-2">
          <Button>
            <Plus className="mr-2 h-4 w-4" />
            New Agent
          </Button>
        </div>
      </div>
      <StatsCards />
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-7">
        <div className="col-span-4">
          <Suspense fallback={<div>Loading agents...</div>}>
            <AgentList />
          </Suspense>
        </div>
        <div className="col-span-3">
          <Suspense fallback={<div>Loading activity...</div>}>
            <ActivityFeed />
          </Suspense>
        </div>
      </div>
    </div>
  );
}
