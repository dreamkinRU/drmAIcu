import { useState } from 'react';
import { Agent, AgentPipeline, AgentPipelineStep, AgentProviderId, TabId } from '../../types';
import StatusBadge from '../ui/StatusBadge';
import Modal from '../ui/Modal';

interface AgentStoreItem {
  id: string;
  name: string;
  description: string;
  stack: string[];
  category: string;
  provider?: AgentProviderId;
  model?: string;
  systemPrompt?: string;
}

interface AgentsTabProps {
  agents: Agent[];
  pipelines?: AgentPipeline[];
  addPipeline?: (data: { name: string; description: string; steps: AgentPipelineStep[] }) => void;
  deletePipeline?: (id: string) => void;
  activeAgentId?: number | null;
  setActiveAgentId?: (id: number | null) => void;
  activePipelineId?: string | null;
  setActivePipelineId?: (id: string | null) => void;
  setActiveTab?: (tab: TabId) => void;
  showAgentStore: boolean;
  setShowAgentStore: (value: boolean) => void;
  toggleAgent: (id: number) => void;
  setJudgeAgent?: (id: number) => void;
  updateAgent?: (id: number, patch: Partial<Agent>) => void;
  addAgent?: (data: {
    name: string;
    description: string;
    task: string;
    stack: string[];
    provider: AgentProviderId;
    model: string;
    systemPrompt: string;
  }) => void;
  deleteAgent?: (id: number) => void;
  importAgent: (agentId: string) => void;
  agentStore: AgentStoreItem[];
  installedModels?: any[];
  bionicModels?: any[];
  lmstudioModels?: any[];
  strataModels?: any[];
}

const PROVIDER_OPTIONS: Array<{ value: AgentProviderId; label: string }> = [
  { value: 'ollama', label: '🏠 Ollama' },
  { value: 'strata', label: '🪨 Strata' },
  { value: 'lmstudio', label: '💻 LM Studio' },
  { value: 'bionic', label: '🧬 Bionic AI' },
  { value: 'groq', label: '☁️ Groq' },
  { value: 'openrouter', label: '🌐 OpenRouter' },
  { value: 'together', label: '⚡ Together AI' },
  { value: 'huggingface', label: '🤗 Hugging Face' },
  { value: 'gemini', label: '✨ Gemini' },
];

export default function AgentsTab({
  agents, pipelines = [], addPipeline, deletePipeline,
  activeAgentId, setActiveAgentId, activePipelineId, setActivePipelineId, setActiveTab,
  showAgentStore, setShowAgentStore,
  toggleAgent, setJudgeAgent, updateAgent, addAgent, deleteAgent,
  importAgent, agentStore,
  installedModels = [], bionicModels = [], lmstudioModels = [], strataModels = [],
}: AgentsTabProps) {
  const [editingId, setEditingId] = useState<number | null>(null);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showPipelineModal, setShowPipelineModal] = useState(false);

  const [newName, setNewName] = useState('');
  const [newTask, setNewTask] = useState('');
  const [newDesc, setNewDesc] = useState('');
  const [newStack, setNewStack] = useState('Python, TypeScript');
  const [newProvider, setNewProvider] = useState<AgentProviderId>('ollama');
  const [newModel, setNewModel] = useState('');
  const [newPrompt, setNewPrompt] = useState('Ты полезный ИИ-ассистент. Отвечай чётко, кратко и по делу на русском языке.');

  const [pipeName, setPipeName] = useState('');
  const [pipeDesc, setPipeDesc] = useState('');
  const [pipeSteps, setPipeSteps] = useState<AgentPipelineStep[]>([
    { agentId: agents[0]?.id || 1, instruction: '' },
    { agentId: agents[2]?.id || agents[0]?.id || 1, instruction: 'Проверь и улучши результат предыдущего шага.' },
  ]);

  const enabledCount = agents.filter((a) => a.enabled).length;
  const currentJudge = agents.find((a) => a.isJudge);

  const getModelsForProvider = (prov?: AgentProviderId): string[] => {
    if (prov === 'strata') return strataModels.map((m: any) => m.name || String(m));
    if (prov === 'lmstudio') return lmstudioModels.map((m: any) => m.name || String(m));
    if (prov === 'bionic') return bionicModels.map((m: any) => m.name || String(m));
    if (prov === 'groq') return ['llama-3.1-8b-versatile', 'llama-3.1-70b-versatile', 'llama-3.3-70b-versatile'];
    if (prov === 'openrouter') return ['meta-llama/llama-3.1-8b-instruct:free', 'qwen/qwen-2.5-coder-32b-instruct:free'];
    if (prov === 'gemini') return ['gemini-1.5-flash', 'gemini-2.0-flash'];
    return installedModels.map((m: any) => m.name || String(m));
  };

  const handleCreate = () => {
    if (!addAgent || !newName.trim()) return;
    addAgent({
      name: newName,
      task: newTask || 'Готов к работе',
      description: newDesc || 'Пользовательский агент',
      stack: newStack.split(',').map((s) => s.trim()).filter(Boolean),
      provider: newProvider,
      model: newModel,
      systemPrompt: newPrompt,
    });
    setNewName('');
    setNewTask('');
    setNewDesc('');
    setNewModel('');
    setShowCreateModal(false);
  };

  const handleCreatePipeline = () => {
    if (!addPipeline || !pipeName.trim() || pipeSteps.length === 0) return;
    addPipeline({
      name: pipeName,
      description: pipeDesc,
      steps: pipeSteps,
    });
    setPipeName('');
    setPipeDesc('');
    setShowPipelineModal(false);
  };

  const handleLaunchInConsole = (agent: Agent) => {
    if (!agent.enabled) toggleAgent(agent.id);
    if (setActiveAgentId) setActiveAgentId(agent.id);
    if (setActiveTab) setActiveTab('console');
  };

  const handleLaunchCouncil = () => {
    if (setActiveAgentId) setActiveAgentId(-1);
    if (setActiveTab) setActiveTab('console');
  };

  const handleLaunchPipeline = (pipelineId: string) => {
    if (setActivePipelineId) setActivePipelineId(pipelineId);
    if (setActiveTab) setActiveTab('console');
  };

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap justify-between items-center gap-3">
        <div>
          <h2 className="text-2xl font-bold">Агенты</h2>
          <p className="text-xs text-gray-400 mt-0.5">
            Активных: <span className="text-emerald-400 font-bold">{enabledCount}</span> из {agents.length}
            {' • '}Судья консилиума:{' '}
            <span className="text-amber-300 font-bold">{currentJudge ? currentJudge.name : 'автовыбор'}</span>
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2.5">
          {setActiveAgentId && setActiveTab && (
            <button
              type="button"
              onClick={handleLaunchCouncil}
              disabled={enabledCount === 0}
              className="px-4 py-2 rounded-lg bg-amber-500/20 hover:bg-amber-500/30 border border-amber-500/50 text-amber-300 text-sm font-bold disabled:opacity-40"
              title="Запустить параллельный опрос всех включённых агентов с вердиктом Судьи"
            >
              👥 Консилиум ({enabledCount})
            </button>
          )}
          {addPipeline && (
            <button
              type="button"
              onClick={() => setShowPipelineModal(true)}
              className="px-4 py-2 rounded-lg bg-indigo-500/20 hover:bg-indigo-500/30 border border-indigo-500/50 text-indigo-300 text-sm font-bold"
            >
              ⛓️ Новая цепочка
            </button>
          )}
          {addAgent && (
            <button
              type="button"
              onClick={() => setShowCreateModal(true)}
              className="px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-bold shadow-lg shadow-emerald-500/20"
            >
              ➕ Создать агента
            </button>
          )}
          <button
            type="button"
            onClick={() => setShowAgentStore(true)}
            className="px-4 py-2 rounded-lg bg-gradient-to-r from-purple-500 to-pink-500 hover:opacity-90 text-white text-sm font-bold"
          >
            🛒 Магазин
          </button>
        </div>
      </div>

      {pipelines.length > 0 && (
        <div className="rounded-xl border border-indigo-500/30 bg-indigo-950/15 p-4 space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-xs font-bold uppercase tracking-wider text-indigo-300">
              ⛓️ Последовательные цепочки агентов ({pipelines.length})
            </h3>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {pipelines.map((pipe) => {
              const isPipeActive = activePipelineId === pipe.id;
              return (
                <div
                  key={pipe.id}
                  className={`rounded-lg border p-3.5 flex flex-col justify-between gap-2.5 transition-all ${
                    isPipeActive
                      ? 'border-indigo-400 bg-indigo-500/15 shadow-[0_0_16px_rgba(99,102,241,0.2)]'
                      : 'border-gray-800 bg-gray-900/70'
                  }`}
                >
                  <div>
                    <div className="flex items-center justify-between gap-2 mb-1">
                      <span className="font-bold text-sm text-white">{pipe.name}</span>
                      {isPipeActive && (
                        <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-indigo-500/30 text-indigo-200">
                          Активна в Консоли
                        </span>
                      )}
                    </div>
                    <p className="text-xs text-gray-400 mb-2">{pipe.description}</p>
                    <div className="flex flex-wrap items-center gap-1.5 text-[11px] font-mono">
                      {pipe.steps.map((st, idx) => {
                        const ag = agents.find((a) => a.id === st.agentId);
                        return (
                          <span key={idx} className="flex items-center gap-1.5">
                            <span className="px-2 py-0.5 rounded bg-gray-800 border border-gray-700 text-indigo-300">
                              {idx + 1}. {ag ? ag.name.split('—')[0].trim() : `Агент #${st.agentId}`}
                            </span>
                            {idx < pipe.steps.length - 1 && <span className="text-gray-500">→</span>}
                          </span>
                        );
                      })}
                    </div>
                  </div>
                  <div className="flex items-center justify-end gap-2 pt-1">
                    {setActivePipelineId && setActiveTab && (
                      <button
                        type="button"
                        onClick={() => handleLaunchPipeline(pipe.id)}
                        className="px-3 py-1.5 rounded-lg text-xs font-bold bg-indigo-600 hover:bg-indigo-500 text-white"
                      >
                        ▶ В консоль
                      </button>
                    )}
                    {deletePipeline && (
                      <button
                        type="button"
                        onClick={() => deletePipeline(pipe.id)}
                        className="px-2.5 py-1.5 rounded-lg text-xs font-bold bg-gray-800 hover:bg-red-500/20 border border-gray-700 text-gray-400 hover:text-red-300"
                        title="Удалить цепочку"
                      >
                        🗑
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      <Modal
        isOpen={showPipelineModal}
        onClose={() => setShowPipelineModal(false)}
        title="Новая цепочка агентов (Pipeline)"
        maxWidth="max-w-2xl"
        maxHeight="max-h-[85vh]"
      >
        <div className="space-y-3 text-sm">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-gray-400 mb-1">Название цепочки *</label>
              <input
                type="text"
                value={pipeName}
                onChange={(e) => setPipeName(e.target.value)}
                placeholder="Например: Код → Ревью → Оптимизация"
                className="w-full px-3 py-2 rounded-lg bg-gray-800 border border-gray-700 text-white focus:border-indigo-500 focus:outline-none"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-400 mb-1">Описание</label>
              <input
                type="text"
                value={pipeDesc}
                onChange={(e) => setPipeDesc(e.target.value)}
                placeholder="Кратко о назначении конвейера"
                className="w-full px-3 py-2 rounded-lg bg-gray-800 border border-gray-700 text-white focus:border-indigo-500 focus:outline-none"
              />
            </div>
          </div>

          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <label className="text-xs text-gray-400 font-bold">Шаги выполнения</label>
              <button
                type="button"
                onClick={() => setPipeSteps((prev) => [...prev, { agentId: agents[0]?.id || 1, instruction: '' }])}
                className="px-2.5 py-1 rounded bg-indigo-500/20 border border-indigo-500/50 text-indigo-300 text-xs font-bold"
              >
                ➕ Добавить шаг
              </button>
            </div>

            {pipeSteps.map((st, idx) => (
              <div key={idx} className="p-3 rounded-lg bg-gray-800/70 border border-gray-700 space-y-2">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-xs font-bold text-indigo-300">Шаг #{idx + 1}</span>
                  <select
                    value={st.agentId}
                    onChange={(e) => {
                      const id = Number(e.target.value);
                      setPipeSteps((prev) => prev.map((item, i) => (i === idx ? { ...item, agentId: id } : item)));
                    }}
                    className="flex-1 px-2.5 py-1.5 rounded bg-gray-900 border border-gray-700 text-white text-xs"
                  >
                    {agents.map((a) => (
                      <option key={a.id} value={a.id}>{a.name} ({a.provider || 'ollama'})</option>
                    ))}
                  </select>
                  {pipeSteps.length > 1 && (
                    <button
                      type="button"
                      onClick={() => setPipeSteps((prev) => prev.filter((_, i) => i !== idx))}
                      className="px-2 py-1 rounded bg-gray-900 text-red-400 text-xs"
                    >
                      ✕
                    </button>
                  )}
                </div>
                <input
                  type="text"
                  value={st.instruction || ''}
                  onChange={(e) => {
                    const val = e.target.value;
                    setPipeSteps((prev) => prev.map((item, i) => (i === idx ? { ...item, instruction: val } : item)));
                  }}
                  placeholder="Инструкция для этого шага (необязательно)..."
                  className="w-full px-2.5 py-1.5 rounded bg-gray-900 border border-gray-700 text-white text-xs font-mono"
                />
              </div>
            ))}
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={() => setShowPipelineModal(false)}
              className="px-4 py-2 rounded-lg bg-gray-700 hover:bg-gray-600 text-gray-300 text-xs font-bold"
            >
              Отмена
            </button>
            <button
              type="button"
              onClick={handleCreatePipeline}
              disabled={!pipeName.trim() || pipeSteps.length === 0}
              className="px-5 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-bold disabled:opacity-50"
            >
              ✅ Сохранить цепочку
            </button>
          </div>
        </div>
      </Modal>

      <Modal
        isOpen={showCreateModal}
        onClose={() => setShowCreateModal(false)}
        title="Новый агент"
        maxWidth="max-w-2xl"
        maxHeight="max-h-[85vh]"
      >
        <div className="space-y-3 text-sm">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-gray-400 mb-1">Название *</label>
              <input
                type="text"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                placeholder="Например: Агент-Архитектор"
                className="w-full px-3 py-2 rounded-lg bg-gray-800 border border-gray-700 text-white focus:border-emerald-500 focus:outline-none"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-400 mb-1">Специализация / задача</label>
              <input
                type="text"
                value={newTask}
                onChange={(e) => setNewTask(e.target.value)}
                placeholder="Проектирование патчей и API"
                className="w-full px-3 py-2 rounded-lg bg-gray-800 border border-gray-700 text-white focus:border-emerald-500 focus:outline-none"
              />
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-gray-400 mb-1">Провайдер</label>
              <select
                value={newProvider}
                onChange={(e) => {
                  setNewProvider(e.target.value as AgentProviderId);
                  setNewModel('');
                }}
                className="w-full px-3 py-2 rounded-lg bg-gray-800 border border-gray-700 text-white focus:border-emerald-500 focus:outline-none"
              >
                {PROVIDER_OPTIONS.map((p) => (
                  <option key={p.value} value={p.value}>{p.label}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs text-gray-400 mb-1">Модель</label>
              <input
                type="text"
                list="new-agent-models"
                value={newModel}
                onChange={(e) => setNewModel(e.target.value)}
                placeholder="По умолчанию или выберите из списка"
                className="w-full px-3 py-2 rounded-lg bg-gray-800 border border-gray-700 text-white font-mono text-xs focus:border-emerald-500 focus:outline-none"
              />
              <datalist id="new-agent-models">
                {getModelsForProvider(newProvider).map((m) => (
                  <option key={m} value={m} />
                ))}
              </datalist>
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-gray-400 mb-1">Описание</label>
              <input
                type="text"
                value={newDesc}
                onChange={(e) => setNewDesc(e.target.value)}
                placeholder="Кратко о роли агента"
                className="w-full px-3 py-2 rounded-lg bg-gray-800 border border-gray-700 text-white focus:border-emerald-500 focus:outline-none"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-400 mb-1">Стек (через запятую)</label>
              <input
                type="text"
                value={newStack}
                onChange={(e) => setNewStack(e.target.value)}
                className="w-full px-3 py-2 rounded-lg bg-gray-800 border border-gray-700 text-white focus:border-emerald-500 focus:outline-none"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs text-gray-400 mb-1">Системный промпт (инструкция роли)</label>
            <textarea
              rows={4}
              value={newPrompt}
              onChange={(e) => setNewPrompt(e.target.value)}
              className="w-full px-3 py-2 rounded-lg bg-gray-800 border border-gray-700 text-white font-mono text-xs focus:border-emerald-500 focus:outline-none"
            />
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={() => setShowCreateModal(false)}
              className="px-4 py-2 rounded-lg bg-gray-700 hover:bg-gray-600 text-gray-300 text-xs font-bold"
            >
              Отмена
            </button>
            <button
              type="button"
              onClick={handleCreate}
              disabled={!newName.trim()}
              className="px-5 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold disabled:opacity-50"
            >
              ✅ Создать
            </button>
          </div>
        </div>
      </Modal>

      <Modal
        isOpen={showAgentStore}
        onClose={() => setShowAgentStore(false)}
        title="Магазин агентов"
        maxWidth="max-w-3xl"
        maxHeight="max-h-[80vh]"
      >
        <div className="grid md:grid-cols-2 gap-4">
          {agentStore.map((a) => (
            <div key={a.id} className="bg-gray-800/50 border border-gray-700 rounded-lg p-4 flex flex-col justify-between">
              <div>
                <h4 className="font-bold text-white mb-1">{a.name}</h4>
                <p className="text-sm text-gray-400 mb-2">{a.description}</p>
                {a.systemPrompt && (
                  <p className="text-[11px] text-gray-500 font-mono bg-gray-900/70 p-2 rounded mb-3 line-clamp-2">
                    {a.systemPrompt}
                  </p>
                )}
              </div>
              <div className="flex justify-between items-center">
                <span className="text-xs text-gray-500">{a.category}</span>
                <button
                  type="button"
                  onClick={() => importAgent(a.id)}
                  className="px-3 py-1.5 rounded bg-emerald-500 hover:bg-emerald-400 text-white text-xs font-bold"
                >
                  ➕ Импортировать
                </button>
              </div>
            </div>
          ))}
        </div>
      </Modal>

      {agents.map((agent) => {
        const isEditing = editingId === agent.id;
        const isSelectedInConsole = activeAgentId === agent.id;
        const provModels = getModelsForProvider(agent.provider || 'ollama');

        return (
          <div
            key={agent.id}
            className={`rounded-xl border-2 p-5 transition-all ${
              isSelectedInConsole
                ? 'border-cyan-400/70 bg-cyan-950/15 shadow-[0_0_20px_rgba(34,211,238,0.12)]'
                : agent.isJudge
                ? 'border-amber-500/40 bg-amber-950/10'
                : agent.enabled
                ? 'border-emerald-500/30 bg-emerald-500/5'
                : 'border-gray-800 bg-gray-900/50 opacity-75'
            }`}
          >
            <div className="flex flex-wrap justify-between items-start gap-4 mb-3">
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2.5 mb-1.5">
                  <h3 className="text-lg font-bold text-white">{agent.name}</h3>
                  <StatusBadge status={agent.status} />
                  {agent.isJudge && (
                    <span className="px-2 py-0.5 rounded-md text-[11px] font-bold bg-amber-500/20 border border-amber-500/50 text-amber-300">
                      ⚖️ Судья
                    </span>
                  )}
                  {isSelectedInConsole && (
                    <span className="px-2 py-0.5 rounded-md text-[11px] font-bold bg-cyan-500/20 border border-cyan-500/50 text-cyan-300">
                      Активен в Консоли
                    </span>
                  )}
                  <span className="px-2 py-0.5 rounded-md text-[11px] font-mono bg-gray-800 border border-gray-700 text-emerald-300 uppercase">
                    {agent.provider || 'ollama'}
                  </span>
                  <span className="px-2 py-0.5 rounded-md text-[11px] font-mono bg-gray-800 border border-gray-700 text-cyan-300">
                    {agent.model || 'модель по умолчанию'}
                  </span>
                </div>
                <p className="text-sm text-gray-300">{agent.task}</p>
                <p className="text-xs text-gray-500 italic mt-1">{agent.description}</p>
                <div className="flex flex-wrap items-center gap-3 mt-2 text-[11px] font-mono text-gray-400">
                  <span>📊 Задач: <strong className="text-gray-200">{agent.tasksCompleted || 0}</strong></span>
                  <span>⚡ Скорость: <strong className="text-emerald-300">{agent.avgTps ? `${agent.avgTps} tok/s` : '—'}</strong></span>
                  <span>📦 Патчей: <strong className="text-amber-300">{agent.patchesCreated || 0}</strong></span>
                  {agent.contextFiles && agent.contextFiles.length > 0 && (
                    <span>📎 Контекст: <strong className="text-cyan-300">{agent.contextFiles.join(', ')}</strong></span>
                  )}
                </div>
              </div>

              <div className="flex flex-wrap items-center gap-2 shrink-0">
                {setJudgeAgent && (
                  <button
                    type="button"
                    onClick={() => setJudgeAgent(agent.id)}
                    className={`px-3 py-2 rounded-lg text-xs font-bold border ${
                      agent.isJudge
                        ? 'bg-amber-500/25 border-amber-400/70 text-amber-200'
                        : 'bg-gray-800 hover:bg-amber-500/15 border-gray-700 hover:border-amber-500/40 text-gray-300'
                    }`}
                    title="Назначить этого агента Судьёй для сравнения ответов консилиума"
                  >
                    {agent.isJudge ? '⚖️ Судья (активен)' : '⚖️ Судья'}
                  </button>
                )}
                {setActiveAgentId && setActiveTab && (
                  <button
                    type="button"
                    onClick={() => handleLaunchInConsole(agent)}
                    className="px-3 py-2 rounded-lg text-xs font-bold bg-cyan-500/20 hover:bg-cyan-500/30 border border-cyan-500/50 text-cyan-300"
                    title="Выбрать агента и перейти в Консоль"
                  >
                    💬 В консоль
                  </button>
                )}
                {updateAgent && (
                  <button
                    type="button"
                    onClick={() => setEditingId(isEditing ? null : agent.id)}
                    className={`px-3 py-2 rounded-lg text-xs font-bold border ${
                      isEditing
                        ? 'bg-amber-500/20 border-amber-500/50 text-amber-300'
                        : 'bg-gray-800 hover:bg-gray-700 border-gray-700 text-gray-200'
                    }`}
                  >
                    {isEditing ? '✓ Готово' : '✏️ Настроить'}
                  </button>
                )}
                <button
                  type="button"
                  onClick={() => toggleAgent(agent.id)}
                  className={`px-3.5 py-2 rounded-lg text-xs font-bold ${
                    agent.enabled
                      ? 'bg-red-500/20 text-red-400 border border-red-500/50'
                      : 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/50'
                  }`}
                >
                  {agent.enabled ? '⏸ Выключить' : '▶ Включить'}
                </button>
                {deleteAgent && (
                  <button
                    type="button"
                    onClick={() => deleteAgent(agent.id)}
                    className="px-2.5 py-2 rounded-lg text-xs font-bold bg-gray-800 hover:bg-red-500/20 border border-gray-700 hover:border-red-500/50 text-gray-400 hover:text-red-300"
                    title="Удалить агента"
                  >
                    🗑
                  </button>
                )}
              </div>
            </div>

            {agent.systemPrompt && !isEditing && (
              <div className="text-xs text-gray-400 font-mono bg-gray-950/60 border border-gray-800 rounded-lg px-3 py-2 mb-3 truncate">
                <span className="text-gray-500 mr-1.5">Промпт:</span>
                {agent.systemPrompt}
              </div>
            )}

            {isEditing && updateAgent && (
              <div className="mt-3 pt-3 border-t border-gray-800 space-y-3 text-xs">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  <div>
                    <label className="block text-gray-400 mb-1">Название агента</label>
                    <input
                      type="text"
                      value={agent.name}
                      onChange={(e) => updateAgent(agent.id, { name: e.target.value })}
                      className="w-full px-3 py-2 rounded-lg bg-gray-950/80 border border-gray-700 text-white focus:border-cyan-500 focus:outline-none"
                    />
                  </div>
                  <div>
                    <label className="block text-gray-400 mb-1">Текущая задача / роль</label>
                    <input
                      type="text"
                      value={agent.task}
                      onChange={(e) => updateAgent(agent.id, { task: e.target.value })}
                      className="w-full px-3 py-2 rounded-lg bg-gray-950/80 border border-gray-700 text-white focus:border-cyan-500 focus:outline-none"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                  <div>
                    <label className="block text-gray-400 mb-1">Провайдер</label>
                    <select
                      value={agent.provider || 'ollama'}
                      onChange={(e) => updateAgent(agent.id, { provider: e.target.value as AgentProviderId, model: '' })}
                      className="w-full px-3 py-2 rounded-lg bg-gray-950/80 border border-gray-700 text-white focus:border-cyan-500 focus:outline-none"
                    >
                      {PROVIDER_OPTIONS.map((p) => (
                        <option key={p.value} value={p.value}>{p.label}</option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="block text-gray-400 mb-1">Модель (из списка или своя)</label>
                    <input
                      type="text"
                      list={`agent-models-${agent.id}`}
                      value={agent.model || ''}
                      onChange={(e) => updateAgent(agent.id, { model: e.target.value })}
                      placeholder="по умолчанию"
                      className="w-full px-3 py-2 rounded-lg bg-gray-950/80 border border-gray-700 text-white font-mono focus:border-cyan-500 focus:outline-none"
                    />
                    <datalist id={`agent-models-${agent.id}`}>
                      {provModels.map((m) => (
                        <option key={m} value={m} />
                      ))}
                    </datalist>
                  </div>
                  <div>
                    <label className="block text-gray-400 mb-1">Стек (через запятую)</label>
                    <input
                      type="text"
                      value={agent.stack.join(', ')}
                      onChange={(e) =>
                        updateAgent(agent.id, {
                          stack: e.target.value.split(',').map((s) => s.trim()).filter(Boolean),
                        })
                      }
                      className="w-full px-3 py-2 rounded-lg bg-gray-950/80 border border-gray-700 text-white focus:border-cyan-500 focus:outline-none"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-gray-400 mb-1">Файлы контекста по умолчанию (относительные пути через запятую)</label>
                  <input
                    type="text"
                    value={(agent.contextFiles || []).join(', ')}
                    onChange={(e) =>
                      updateAgent(agent.id, {
                        contextFiles: e.target.value.split(',').map((s) => s.trim()).filter(Boolean),
                      })
                    }
                    placeholder="Например: main.py, agent_engine.py, src/App.tsx"
                    className="w-full px-3 py-2 rounded-lg bg-gray-950/80 border border-gray-700 text-white font-mono focus:border-cyan-500 focus:outline-none"
                  />
                </div>

                <div>
                  <label className="block text-gray-400 mb-1">Системный промпт (инструкция поведения агента)</label>
                  <textarea
                    rows={3}
                    value={agent.systemPrompt || ''}
                    onChange={(e) => updateAgent(agent.id, { systemPrompt: e.target.value })}
                    placeholder="Опишите роль, правила ответа, формат кода..."
                    className="w-full px-3 py-2 rounded-lg bg-gray-950/80 border border-gray-700 text-white font-mono focus:border-cyan-500 focus:outline-none"
                  />
                </div>
              </div>
            )}

            <div className="flex gap-2 mt-3">
              {agent.stack.map((s) => (
                <span key={s} className="px-2 py-0.5 bg-gray-800 border border-gray-700/70 rounded text-xs text-gray-300">
                  {s}
                </span>
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}
