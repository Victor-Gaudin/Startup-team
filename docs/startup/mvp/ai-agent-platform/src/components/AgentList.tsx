import { createClient } from '@supabase/supabase-js';

const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
);

export async function AgentList() {
  const { data: agents } = await supabase.from('agents').select('*');

  if (!agents || agents.length === 0) {
    return (
      <div className="p-4 text-gray-400 text-sm">
        No agents yet. Create your first one.
      </div>
    );
  }

  return (
    <ul className="space-y-2">
      {agents.map((agent) => (
        >
          <p className="font-semibold text-white">{agent.name}</p>
          <p className="text-sm text-gray-400">Balance: ${agent.balance}</p>
          <p className="text-xs text-gray-500">{agent.framework || 'No framework set'}</p>
        </li>
      ))}
    </ul>
  );
}
