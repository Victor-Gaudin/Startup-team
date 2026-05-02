
export type AgentStatus = 'idle' | 'running' | 'failed' | 'completed';

export interface Agent {
  id: string;
  name: string;
  framework: string;
  status: AgentStatus;
  lastRun?: string;
  balance: number;
}

export interface AgentSession {
  id: string;
  agentId: string;
  startedAt: string;
  endedAt?: string;
  status: AgentStatus;
}

export interface LogEntry {
  id: string;
  sessionId: string;
  timestamp: string;
  level: 'info' | 'warn' | 'error' | 'debug';
  message: string;
  metadata?: any;
}
