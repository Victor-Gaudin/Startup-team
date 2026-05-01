
import { createClient } from '@supabase/supabase-js';
import { Agent, AgentSession, LogEntry } from '@/types';

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL!;
const supabaseKey = process.env.SUPABASE_SERVICE_ROLE_KEY!;
const supabase = createClient(supabaseUrl, supabaseKey);

export class AgentManager {
  async createAgent(name: string, framework?: string) {
    const { data, error } = await supabase
      .from('agents')
      .insert([{ name, framework }])
      .select()
      .single();

    if (error) throw error;
    return data as Agent;
  }

  async startSession(agentId: string) {
    const { data, error } = await supabase
      .from('sessions')
      .insert([{ agent_id: agentId, status: 'running' }])
      .select()
      .single();

    if (error) throw error;
    return data as AgentSession;
  }

  async endSession(sessionId: string, status: 'completed' | 'failed' = 'completed') {
    const { data, error } = await supabase
      .from('sessions')
      .update({ status, ended_at: new Date().toISOString() })
      .eq('id', sessionId)
      .select()
      .single();

    if (error) throw error;
    return data as AgentSession;
  }

  async log(sessionId: string, level: LogEntry['level'], message: string, metadata?: any) {
    const { error } = await supabase
      .from('logs')
      .insert([{ session_id: sessionId, level, message, metadata }]);

    if (error) console.error('Error logging:', error);
  }
}
