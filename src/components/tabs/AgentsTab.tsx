import { Agent } from '../../types';
import StatusBadge from '../ui/StatusBadge';
import Modal from '../ui/Modal';

interface AgentStoreItem {
  id: string;
  name: string;
  description: string;
  stack: string[];
  category: string;
}

interface AgentsTabProps {
  agents: Agent[];
  showAgentStore: boolean;
  setShowAgentStore: (value: boolean) => void;
  toggleAgent: (id: number) => void;
  importAgent: (agentId: string) => void;
  agentStore: AgentStoreItem[];
}

export default function AgentsTab({
  agents, showAgentStore, setShowAgentStore,
  toggleAgent, importAgent, agentStore,
}: AgentsTabProps) {
  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h2 className="text-2xl font-bold">Агенты</h2>
        <button
          onClick={() => setShowAgentStore(true)}
          className="px-4 py-2 rounded-lg bg-gradient-to-r from-purple-500 to-pink-500 text-white text-sm font-bold"
        >
          🛒 Магазин
        </button>
      </div>

      <Modal
        isOpen={showAgentStore}
        onClose={() => setShowAgentStore(false)}
        title="Магазин агентов"
        maxWidth="max-w-3xl"
        maxHeight="max-h-[80vh]"
      >
        <div className="grid md:grid-cols-2 gap-4">
          {agentStore.map(a => (
            <div key={a.id} className="bg-gray-800/50 border border-gray-700 rounded-lg p-4">
              <h4 className="font-bold text-white mb-2">{a.name}</h4>
              <p className="text-sm text-gray-400 mb-3">{a.description}</p>
              <div className="flex justify-between items-center">
                <span className="text-xs text-gray-500">{a.category}</span>
                <button
                  onClick={() => importAgent(a.id)}
                  className="px-3 py-1.5 rounded bg-emerald-500 text-white text-xs font-bold"
                >
                  ➕ Импортировать
                </button>
              </div>
            </div>
          ))}
        </div>
      </Modal>

      {agents.map(agent => (
        <div
          key={agent.id}
          className={`rounded-xl border-2 p-6 transition-all ${
            agent.enabled
              ? 'border-emerald-500/30 bg-emerald-500/5'
              : 'border-gray-700 bg-gray-900/50 opacity-70'
          }`}
        >
          <div className="flex justify-between items-start mb-3">
            <div>
              <div className="flex items-center gap-3 mb-2">
                <h3 className="text-lg font-bold text-white">{agent.name}</h3>
                <StatusBadge status={agent.status} />
              </div>
              <p className="text-sm text-gray-400">{agent.task}</p>
              <p className="text-xs text-gray-500 italic mt-2">{agent.description}</p>
            </div>
            <button
              onClick={() => toggleAgent(agent.id)}
              className={`px-4 py-2 rounded-lg text-sm font-bold ${
                agent.enabled
                  ? 'bg-red-500/20 text-red-400 border border-red-500/50'
                  : 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/50'
              }`}
            >
              {agent.enabled ? '⏸ Выключить' : '▶ Включить'}
            </button>
          </div>
          <div className="flex gap-2 mb-3">
            {agent.stack.map(s => (
              <span key={s} className="px-2 py-1 bg-gray-700/50 rounded text-xs text-gray-300">
                {s}
              </span>
            ))}
          </div>
          <div className="h-2 bg-gray-700 rounded-full">
            <div
              className={`h-full rounded-full ${
                agent.enabled ? 'bg-gradient-to-r from-emerald-500 to-cyan-500' : 'bg-gray-600'
              }`}
              style={{ width: `${agent.progress}%` }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}
