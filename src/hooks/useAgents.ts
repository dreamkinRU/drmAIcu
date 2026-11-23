import { useState, useEffect } from 'react';
import { Agent, AgentPipeline, AgentPipelineStep, AgentProviderId } from '../types';
import { initialAgents, agentStore } from '../utils/constants';
import { loadAgentsApi, saveAgentsApi, loadPipelinesApi, savePipelinesApi } from '../services/api';

const AGENTS_STORAGE_KEY = 'drmaicu_agents_v1';
const ACTIVE_AGENT_STORAGE_KEY = 'drmaicu_active_agent_id';
const PIPELINES_STORAGE_KEY = 'drmaicu_pipelines_v1';
const ACTIVE_PIPELINE_STORAGE_KEY = 'drmaicu_active_pipeline_id';

const DEFAULT_PIPELINES: AgentPipeline[] = [
  {
    id: 'pipe-fast-code-check',
    name: 'Быстрый код + проверка',
    description: 'Быстрая генерация самодостаточного кода и проверка на ошибки/заглушки',
    steps: [
      { agentId: 1, instruction: 'Напиши готовый самодостаточный код без внешних ссылок и заглушек.' },
      { agentId: 3, instruction: 'Проверь код на ошибки, незакрытые блоки и лишние зависимости; выдай исправленный итог.' },
    ],
  },
  {
    id: 'pipe-code-audit',
    name: 'Код → Аудит → Фикс',
    description: 'Генерация решения, проверка на баги/типы и выпуск финальной версии',
    steps: [
      { agentId: 1, instruction: 'Напиши рабочее решение задачи.' },
      { agentId: 3, instruction: 'Проверь код выше на ошибки, уязвимости и крайние случаи.' },
      { agentId: 1, instruction: 'Исправь найденные замечания и выдай финальный чистый код.' },
    ],
  },
  {
    id: 'pipe-arch-patch',
    name: 'Анализ → План реализации',
    description: 'Разбор требований и подготовка пошаговой архитектуры изменений',
    steps: [
      { agentId: 2, instruction: 'Разбери задачу на требования, риски и структуру данных.' },
      { agentId: 1, instruction: 'Реализуй решение по подготовленному плану.' },
    ],
  },
];

export function useAgents() {
  const [agents, setAgents] = useState<Agent[]>(() => {
    try {
      const raw = localStorage.getItem(AGENTS_STORAGE_KEY);
      if (raw) {
        const parsed = JSON.parse(raw);
        if (Array.isArray(parsed) && parsed.length > 0) return parsed;
      }
    } catch {}
    return initialAgents;
  });

  const [pipelines, setPipelines] = useState<AgentPipeline[]>(() => {
    try {
      const raw = localStorage.getItem(PIPELINES_STORAGE_KEY);
      if (raw) {
        const parsed = JSON.parse(raw);
        if (Array.isArray(parsed) && parsed.length > 0) return parsed;
      }
    } catch {}
    return DEFAULT_PIPELINES;
  });

  const [activeAgentId, setActiveAgentIdState] = useState<number | null>(() => {
    try {
      const raw = localStorage.getItem(ACTIVE_AGENT_STORAGE_KEY);
      if (raw) {
        const num = Number(raw);
        if (num === -1 || (Number.isFinite(num) && num > 0)) return num;
      }
    } catch {}
    return null;
  });

  const [activePipelineId, setActivePipelineIdState] = useState<string | null>(() => {
    try {
      return localStorage.getItem(ACTIVE_PIPELINE_STORAGE_KEY) || null;
    } catch {
      return null;
    }
  });

  const [showAgentStore, setShowAgentStore] = useState(false);

  useEffect(() => {
    let active = true;
    loadAgentsApi().then((remote) => {
      if (active && remote && remote.length > 0) {
        setAgents(remote);
        try {
          localStorage.setItem(AGENTS_STORAGE_KEY, JSON.stringify(remote));
        } catch {}
      }
    });
    loadPipelinesApi().then((remotePipes) => {
      if (active && remotePipes && remotePipes.length > 0) {
        setPipelines(remotePipes);
        try {
          localStorage.setItem(PIPELINES_STORAGE_KEY, JSON.stringify(remotePipes));
        } catch {}
      }
    });
    return () => {
      active = false;
    };
  }, []);

  const setActiveAgentId = (id: number | null) => {
    setActiveAgentIdState(id);
    try {
      if (id !== null) {
        localStorage.setItem(ACTIVE_AGENT_STORAGE_KEY, String(id));
        setActivePipelineIdState(null);
        localStorage.removeItem(ACTIVE_PIPELINE_STORAGE_KEY);
      } else {
        localStorage.removeItem(ACTIVE_AGENT_STORAGE_KEY);
      }
    } catch {}
  };

  const setActivePipelineId = (id: string | null) => {
    setActivePipelineIdState(id);
    try {
      if (id) {
        localStorage.setItem(ACTIVE_PIPELINE_STORAGE_KEY, id);
        setActiveAgentIdState(null);
        localStorage.removeItem(ACTIVE_AGENT_STORAGE_KEY);
      } else {
        localStorage.removeItem(ACTIVE_PIPELINE_STORAGE_KEY);
      }
    } catch {}
  };

  const persistAgents = (next: Agent[]) => {
    try {
      localStorage.setItem(AGENTS_STORAGE_KEY, JSON.stringify(next));
    } catch {}
    saveAgentsApi(next);
  };

  const persistPipelines = (next: AgentPipeline[]) => {
    try {
      localStorage.setItem(PIPELINES_STORAGE_KEY, JSON.stringify(next));
    } catch {}
    savePipelinesApi(next);
  };

  const toggleAgent = (id: number) => {
    setAgents((prev) => {
      const next = prev.map((a) =>
        a.id === id
          ? { ...a, enabled: !a.enabled, status: (!a.enabled ? 'active' : 'frozen') as Agent['status'] }
          : a
      );
      persistAgents(next);
      return next;
    });
  };

  const setJudgeAgent = (id: number) => {
    setAgents((prev) => {
      const target = prev.find((a) => a.id === id);
      const nextJudgeState = !target?.isJudge;
      const next = prev.map((a) => ({
        ...a,
        isJudge: a.id === id ? nextJudgeState : false,
      }));
      persistAgents(next);
      return next;
    });
  };

  const updateAgent = (id: number, patch: Partial<Agent>) => {
    setAgents((prev) => {
      const next = prev.map((a) => (a.id === id ? { ...a, ...patch } : a));
      persistAgents(next);
      return next;
    });
  };

  const recordAgentStats = (id: number, stats: { tps?: number; patchCreated?: boolean }) => {
    if (!id || id <= 0) return;
    setAgents((prev) => {
      const next = prev.map((a) => {
        if (a.id !== id) return a;
        const prevTasks = a.tasksCompleted || 0;
        const nextTasks = stats.tps !== undefined ? prevTasks + 1 : prevTasks;
        const nextAvgTps =
          stats.tps !== undefined && stats.tps > 0
            ? prevTasks > 0 && a.avgTps
              ? Math.round(((a.avgTps * prevTasks + stats.tps) / nextTasks) * 10) / 10
              : Math.round(stats.tps * 10) / 10
            : a.avgTps;
        const nextPatches = (a.patchesCreated || 0) + (stats.patchCreated ? 1 : 0);
        return {
          ...a,
          tasksCompleted: nextTasks,
          avgTps: nextAvgTps,
          patchesCreated: nextPatches,
          lastActivity: new Date().toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' }),
        };
      });
      persistAgents(next);
      return next;
    });
  };

  const addAgent = (data: {
    name: string;
    description: string;
    task: string;
    stack: string[];
    provider: AgentProviderId;
    model: string;
    systemPrompt: string;
    contextFiles?: string[];
  }) => {
    setAgents((prev) => {
      const maxId = prev.reduce((m, a) => Math.max(m, a.id), 0);
      const created: Agent = {
        id: maxId + 1,
        name: data.name.trim() || `Агент #${maxId + 1}`,
        status: 'active',
        task: data.task.trim() || 'Готов к работе',
        stack: data.stack.length > 0 ? data.stack : ['AI'],
        progress: 0,
        lastActivity: 'Только что',
        enabled: true,
        description: data.description.trim() || 'Пользовательский агент',
        provider: data.provider || 'ollama',
        model: data.model.trim(),
        systemPrompt: data.systemPrompt.trim(),
        isJudge: false,
        tasksCompleted: 0,
        avgTps: 0,
        patchesCreated: 0,
        contextFiles: data.contextFiles || [],
      };
      const next = [...prev, created];
      persistAgents(next);
      return next;
    });
  };

  const deleteAgent = (id: number) => {
    setAgents((prev) => {
      const next = prev.filter((a) => a.id !== id);
      persistAgents(next);
      return next;
    });
    if (activeAgentId === id) {
      setActiveAgentId(null);
    }
  };

  const importAgent = (agentId: string) => {
    const sa = agentStore.find((a) => a.id === agentId);
    if (!sa) return;
    setAgents((prev) => {
      const maxId = prev.reduce((m, a) => Math.max(m, a.id), 0);
      const next: Agent[] = [
        ...prev,
        {
          id: maxId + 1,
          name: sa.name,
          status: 'active',
          task: 'Готов к работе',
          stack: sa.stack,
          progress: 0,
          lastActivity: 'Только что',
          enabled: true,
          description: sa.description,
          provider: sa.provider || 'ollama',
          model: sa.model || '',
          systemPrompt: sa.systemPrompt || '',
          isJudge: false,
          tasksCompleted: 0,
          avgTps: 0,
          patchesCreated: 0,
          contextFiles: [],
        },
      ];
      persistAgents(next);
      return next;
    });
    setShowAgentStore(false);
  };

  const addPipeline = (data: { name: string; description: string; steps: AgentPipelineStep[] }) => {
    if (data.steps.length === 0) return;
    setPipelines((prev) => {
      const created: AgentPipeline = {
        id: `pipe-${Date.now()}`,
        name: data.name.trim() || `Цепочка #${prev.length + 1}`,
        description: data.description.trim() || 'Последовательный конвейер агентов',
        steps: data.steps,
      };
      const next = [...prev, created];
      persistPipelines(next);
      return next;
    });
  };

  const deletePipeline = (id: string) => {
    setPipelines((prev) => {
      const next = prev.filter((p) => p.id !== id);
      persistPipelines(next);
      return next;
    });
    if (activePipelineId === id) {
      setActivePipelineId(null);
    }
  };

  const activeAgent = activeAgentId && activeAgentId > 0 ? (agents.find((a) => a.id === activeAgentId) || null) : null;
  const judgeAgent = agents.find((a) => a.isJudge) || null;
  const activePipeline = activePipelineId ? (pipelines.find((p) => p.id === activePipelineId) || null) : null;

  return {
    agents, setAgents,
    pipelines, addPipeline, deletePipeline,
    activeAgentId, setActiveAgentId, activeAgent, judgeAgent,
    activePipelineId, setActivePipelineId, activePipeline,
    showAgentStore, setShowAgentStore,
    toggleAgent, setJudgeAgent, updateAgent, recordAgentStats, addAgent, deleteAgent, importAgent,
  };
}
