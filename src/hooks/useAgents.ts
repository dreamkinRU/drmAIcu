import { useState } from 'react';
import { Agent } from '../types';
import { initialAgents, agentStore } from '../utils/constants';

export function useAgents() {
  const [agents, setAgents] = useState<Agent[]>(initialAgents);
  const [showAgentStore, setShowAgentStore] = useState(false);

  const toggleAgent = (id: number) => {
    setAgents(prev =>
      prev.map(a =>
        a.id === id
          ? { ...a, enabled: !a.enabled, status: !a.enabled ? 'active' : 'frozen' }
          : a
      )
    );
  };

  const importAgent = (agentId: string) => {
    const sa = agentStore.find(a => a.id === agentId);
    if (!sa) return;
    setAgents(prev => [
      ...prev,
      {
        id: prev.length + 1,
        name: sa.name,
        status: 'frozen',
        task: 'Готов к активации',
        stack: sa.stack,
        progress: 0,
        lastActivity: 'Только что',
        enabled: false,
        description: sa.description,
      },
    ]);
    setShowAgentStore(false);
  };

  return {
    agents, setAgents,
    showAgentStore, setShowAgentStore,
    toggleAgent, importAgent,
  };
}
