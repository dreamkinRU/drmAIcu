import { useState, useRef, useEffect } from 'react';
import { Agent, AgentPipeline, CodeIssue } from '../types';
import {
  runAiTaskStream, runCouncilTaskStream, runPipelineTaskStream,
  buildAgentContextApi, savePatchFromConsoleApi,
  CouncilAgentResult, PipelineStepPayload,
  StreamMetrics, loadBionicModels, loadLmStudioModels, loadStrataModels,
} from '../services/api';

function stripCodeFences(text: string): string {
  return text
    .replace(/```[a-zA-Z0-9_-]*\r?\n?/g, '')
    .replace(/```/g, '')
    .replace(/\r\n/g, '\n')
    .replace(/\n{2,}/g, '\n')
    .replace(/^\n+/, '');
}

const VALID_CONSOLE_MODES = ['ollama', 'groq', 'bionic', 'lmstudio', 'strata', 'all'] as const;
type ConsoleProviderMode = typeof VALID_CONSOLE_MODES[number];

export function useConsole(
  addLog: (entry: any) => void,
  activeAgent?: Agent | null,
  agents: Agent[] = [],
  activeAgentId: number | null = null,
  activePipeline?: AgentPipeline | null,
  codeIssues: CodeIssue[] = [],
  recordAgentStats?: (id: number, stats: { tps?: number; patchCreated?: boolean }) => void
) {
  const [consolePrompt, setConsolePrompt] = useState('');
  const [consoleLoading, setConsoleLoading] = useState(false);
  const [providerMode, setProviderMode] = useState<ConsoleProviderMode>(() => {
    try {
      const saved = localStorage.getItem('drmaicu_provider_mode');
      if (saved && (VALID_CONSOLE_MODES as readonly string[]).includes(saved)) {
        return saved as ConsoleProviderMode;
      }
    } catch {}
    return 'all';
  });
  const [strataUrl, setStrataUrl] = useState<string>(() => {
    try {
      const saved = localStorage.getItem('drmaicu_strata_url');
      return (!saved || saved === 'http://127.0.0.1:8081/v1') ? 'http://127.0.0.1:47831/v1' : saved;
    } catch {
      return 'http://127.0.0.1:47831/v1';
    }
  });
  const [strataModels, setStrataModels] = useState<any[]>([]);

  useEffect(() => {
    try {
      localStorage.setItem('drmaicu_strata_url', strataUrl);
    } catch {}
  }, [strataUrl]);

  useEffect(() => {
    let active = true;
    loadStrataModels(strataUrl).then((ms) => {
      if (active) setStrataModels(ms);
    });
    return () => { active = false; };
  }, [strataUrl, providerMode]);

  const [lmstudioUrl, setLmstudioUrl] = useState<string>(() => {
    try {
      return localStorage.getItem('drmaicu_lmstudio_url') || 'http://localhost:1234/v1';
    } catch {
      return 'http://localhost:1234/v1';
    }
  });
  const [lmstudioModels, setLmstudioModels] = useState<any[]>([]);

  useEffect(() => {
    try {
      localStorage.setItem('drmaicu_lmstudio_url', lmstudioUrl);
    } catch {}
  }, [lmstudioUrl]);

  useEffect(() => {
    let active = true;
    loadLmStudioModels(lmstudioUrl).then((ms) => {
      if (active) setLmstudioModels(ms);
    });
    return () => { active = false; };
  }, [lmstudioUrl, providerMode]);

  const [bionicUrl, setBionicUrl] = useState<string>(() => {
    try {
      return localStorage.getItem('drmaicu_bionic_url') || 'http://localhost:1235/v1';
    } catch {
      return 'http://localhost:1235/v1';
    }
  });
  const [bionicModels, setBionicModels] = useState<any[]>([]);

  useEffect(() => {
    try {
      localStorage.setItem('drmaicu_bionic_url', bionicUrl);
    } catch {}
  }, [bionicUrl]);

  useEffect(() => {
    let active = true;
    loadBionicModels(bionicUrl).then((ms) => {
      if (active) setBionicModels(ms);
    });
    return () => { active = false; };
  }, [bionicUrl, providerMode]);

  const [selectedModel, setSelectedModel] = useState<string>(() => {
    try {
      return localStorage.getItem('drmaicu_selected_model') || '';
    } catch {
      return '';
    }
  });

  const [contextFiles, setContextFiles] = useState<string[]>([]);
  const [includeLogs, setIncludeLogs] = useState(false);
  const [includeCodeIssues, setIncludeCodeIssues] = useState(false);
  const [exportingPatch, setExportingPatch] = useState(false);

  useEffect(() => {
    if (!activeAgent) return;
    if (activeAgent.provider && (VALID_CONSOLE_MODES as readonly string[]).includes(activeAgent.provider)) {
      setProviderMode(activeAgent.provider as ConsoleProviderMode);
    }
    if (typeof activeAgent.model === 'string') {
      setSelectedModel(activeAgent.model);
    }
    if (Array.isArray(activeAgent.contextFiles)) {
      setContextFiles(activeAgent.contextFiles);
    }
  }, [activeAgent?.id, activeAgent?.provider, activeAgent?.model]);

  useEffect(() => {
    try {
      localStorage.setItem('drmaicu_provider_mode', providerMode);
    } catch {}
  }, [providerMode]);

  useEffect(() => {
    try {
      localStorage.setItem('drmaicu_selected_model', selectedModel);
    } catch {}
  }, [selectedModel]);

  const [lastPrompt, setLastPrompt] = useState<string>('');
  const [consoleMetrics, setConsoleMetrics] = useState<StreamMetrics | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const lastEndRef = useRef<number>(0);

  const enrichPromptWithContext = async (userPrompt: string): Promise<string> => {
    const openIssues = includeCodeIssues ? codeIssues.filter((i) => !i.fixed) : [];
    if (contextFiles.length === 0 && !includeLogs && openIssues.length === 0) {
      return userPrompt;
    }
    const ctxRes = await buildAgentContextApi({
      files: contextFiles,
      include_logs: includeLogs,
      code_issues: openIssues,
    });
    if (!ctxRes.success || !ctxRes.context_text.trim()) {
      return userPrompt;
    }
    return `КОНТЕКСТ ПРОЕКТА:\n${ctxRes.context_text}\n\nЗАДАЧА ПОЛЬЗОВАТЕЛЯ:\n${userPrompt}`;
  };

  const executePipeline = async (promptToSend: string, pipeline: AgentPipeline) => {
    const resolvedSteps: PipelineStepPayload[] = [];
    for (const s of pipeline.steps) {
      const ag = agents.find((a) => a.id === s.agentId);
      if (ag) {
        resolvedSteps.push({
          name: ag.name,
          provider: ag.provider || 'ollama',
          model: ag.model || '',
          systemPrompt: ag.systemPrompt || '',
          instruction: s.instruction || '',
        });
      }
    }

    if (resolvedSteps.length === 0) {
      const warnText = consolePrompt.trimEnd() + '\n\n--- ⚠️ ЦЕПОЧКА ---\nАгенты из шагов цепочки не найдены.\n\n';
      lastEndRef.current = warnText.length;
      setConsolePrompt(warnText);
      return;
    }

    setLastPrompt(promptToSend);
    setConsoleLoading(true);
    setConsoleMetrics(null);

    const enrichedPrompt = await enrichPromptWithContext(promptToSend);
    const controller = new AbortController();
    abortRef.current = controller;

    addLog({
      time: new Date().toLocaleTimeString('ru-RU'),
      level: 'info',
      message: `Запуск цепочки «${pipeline.name}» (${resolvedSteps.length} шагов)...`,
      source: 'Pipeline',
    });

    const baseText = consolePrompt.trimEnd() + '\n';
    const stepHeaders: Record<number, string> = {};
    const stepRawTexts: Record<number, string> = {};
    const stepOrder: number[] = [];

    const renderPipelineText = () => {
      const blocks = stepOrder.map((num) => `${stepHeaders[num]}\n${stripCodeFences(stepRawTexts[num] || '')}`);
      return baseText + blocks.join('\n\n');
    };

    try {
      const res = await runPipelineTaskStream(enrichedPrompt, resolvedSteps, {
        signal: controller.signal,
        onStepStart: (info) => {
          if (!stepOrder.includes(info.step)) stepOrder.push(info.step);
          stepHeaders[info.step] = `=== ⛓️ [Шаг ${info.step}/${info.total}] ${info.name} (${info.provider}/${info.model}) ===`;
          stepRawTexts[info.step] = '';
          setConsolePrompt(renderPipelineText());
        },
        onStepChunk: (step, chunk) => {
          stepRawTexts[step] = (stepRawTexts[step] || '') + chunk;
          setConsolePrompt(renderPipelineText());
        },
        onStepDone: (info) => {
          stepHeaders[info.step] = `=== ✅ [Шаг ${info.step}/${info.total}] ${info.name} (${info.elapsed_sec}s) ===`;
          setConsolePrompt(renderPipelineText());
        },
        onMeta: (meta) => {
          setConsoleMetrics(meta);
        },
      });

      if (res.aborted) {
        const finalText = renderPipelineText().trimEnd() + '\n\n[⏹ Цепочка остановлена пользователем]\n\n';
        lastEndRef.current = finalText.length;
        setConsolePrompt(finalText);
      } else if (res.success) {
        const finalText = renderPipelineText().trimEnd() + '\n\n';
        lastEndRef.current = finalText.length;
        setConsolePrompt(finalText);
        addLog({
          time: new Date().toLocaleTimeString('ru-RU'),
          level: 'success',
          message: `Цепочка «${pipeline.name}» выполнена`,
          source: 'Pipeline',
        });
      } else {
        const finalText = renderPipelineText().trimEnd() + `\n\n--- ❌ ОШИБКА ЦЕПОЧКИ ---\n${res.error || 'Неизвестная ошибка'}\n\n`;
        lastEndRef.current = finalText.length;
        setConsolePrompt(finalText);
        addLog({
          time: new Date().toLocaleTimeString('ru-RU'),
          level: 'error',
          message: 'Ошибка цепочки: ' + (res.error || 'Неизвестная ошибка'),
          source: 'Pipeline',
        });
      }
    } finally {
      abortRef.current = null;
      setConsoleLoading(false);
    }
  };

  const executeCouncil = async (promptToSend: string) => {
    const enabledAgents = agents.filter((a) => a.enabled);
    if (enabledAgents.length === 0) {
      const warnText = consolePrompt.trimEnd() + '\n\n--- ⚠️ КОНСИЛИУМ ---\nНет активных агентов. Включите хотя бы одного агента во вкладке «Агенты».\n\n';
      lastEndRef.current = warnText.length;
      setConsolePrompt(warnText);
      return;
    }

    const judge = agents.find((a) => a.isJudge) || null;
    setLastPrompt(promptToSend);
    setConsoleLoading(true);
    setConsoleMetrics(null);

    const enrichedPrompt = await enrichPromptWithContext(promptToSend);
    const controller = new AbortController();
    abortRef.current = controller;

    addLog({
      time: new Date().toLocaleTimeString('ru-RU'),
      level: 'info',
      message: `Запуск консилиума (${enabledAgents.length} агентов${judge ? `, судья: ${judge.name}` : ''})...`,
      source: 'Council',
    });

    const baseText = consolePrompt.trimEnd() + '\n';
    const agentBlocks: string[] = [];
    let statusLine = '⏳ Консилиум: подготовка...';
    let judgeHeader = '';
    let rawJudgeText = '';

    const renderCouncilText = () => {
      const parts: string[] = [];
      if (agentBlocks.length > 0) parts.push(agentBlocks.join('\n\n'));
      if (statusLine) parts.push(statusLine);
      if (judgeHeader) {
        parts.push(`${judgeHeader}\n${stripCodeFences(rawJudgeText)}`);
      }
      return baseText + parts.join('\n\n');
    };

    setConsolePrompt(renderCouncilText());

    try {
      const res = await runCouncilTaskStream(enrichedPrompt, enabledAgents, judge, {
        signal: controller.signal,
        onStatus: (msg) => {
          statusLine = msg;
          setConsolePrompt(renderCouncilText());
        },
        onAgentDone: (r: CouncilAgentResult) => {
          if (r.content) {
            const clean = stripCodeFences(r.content).trim();
            agentBlocks.push(`[✓ ${r.name} • ${r.provider}/${r.model} • ${r.elapsed_sec}s]\n${clean}`);
          } else {
            agentBlocks.push(`[✕ ${r.name} • ${r.provider}/${r.model}] Ошибка: ${r.error || 'нет ответа'}`);
          }
          setConsolePrompt(renderCouncilText());
        },
        onSingleWinner: (winnerName) => {
          statusLine = `✅ Ответил единственный активный агент: ${winnerName}`;
          setConsolePrompt(renderCouncilText());
        },
        onJudgeChunk: (judgeName, chunk) => {
          statusLine = '';
          if (!judgeHeader) {
            judgeHeader = `=== ⚖️ ВЕРДИКТ СУДЬИ (${judgeName}) ===`;
          }
          rawJudgeText += chunk;
          setConsolePrompt(renderCouncilText());
        },
        onMeta: (meta) => {
          setConsoleMetrics(meta);
        },
      });

      if (res.aborted) {
        statusLine = '[⏹ Консилиум остановлен пользователем]';
        const finalText = renderCouncilText().trimEnd() + '\n\n';
        lastEndRef.current = finalText.length;
        setConsolePrompt(finalText);
      } else if (res.success) {
        if (judgeHeader) statusLine = '';
        const finalText = renderCouncilText().trimEnd() + '\n\n';
        lastEndRef.current = finalText.length;
        setConsolePrompt(finalText);
        addLog({
          time: new Date().toLocaleTimeString('ru-RU'),
          level: 'success',
          message: 'Консилиум завершил работу',
          source: 'Council',
        });
      } else {
        statusLine = `--- ❌ ОШИБКА КОНСИЛИУМА ---\n${res.error || 'Неизвестная ошибка'}`;
        const finalText = renderCouncilText().trimEnd() + '\n\n';
        lastEndRef.current = finalText.length;
        setConsolePrompt(finalText);
        addLog({
          time: new Date().toLocaleTimeString('ru-RU'),
          level: 'error',
          message: 'Ошибка консилиума: ' + (res.error || 'Неизвестная ошибка'),
          source: 'Council',
        });
      }
    } finally {
      abortRef.current = null;
      setConsoleLoading(false);
    }
  };

  const executePrompt = async (promptToSend: string) => {
    if (!promptToSend.trim() || consoleLoading) return;
    if (activePipeline) {
      await executePipeline(promptToSend, activePipeline);
      return;
    }
    if (activeAgentId === -1) {
      await executeCouncil(promptToSend);
      return;
    }

    setLastPrompt(promptToSend);
    setConsoleLoading(true);
    setConsoleMetrics(null);

    const enrichedPrompt = await enrichPromptWithContext(promptToSend);
    const controller = new AbortController();
    abortRef.current = controller;

    const agentLabel = activeAgent ? ` [Агент: ${activeAgent.name}]` : '';
    addLog({
      time: new Date().toLocaleTimeString('ru-RU'),
      level: 'info',
      message: `Стриминг задачи${agentLabel} (провайдер: ${providerMode}${selectedModel ? `, модель: ${selectedModel}` : ''})...`,
      source: 'Console',
    });

    const baseText = consolePrompt.trimEnd() + '\n> ';
    let rawStreamed = '';
    let latestTps = 0;
    setConsolePrompt(baseText);

    try {
      const res = await runAiTaskStream(enrichedPrompt, providerMode, selectedModel, {
        signal: controller.signal,
        systemPrompt: activeAgent?.systemPrompt || '',
        onChunk: (chunk) => {
          rawStreamed += chunk;
          setConsolePrompt(baseText + stripCodeFences(rawStreamed));
        },
        onMeta: (meta) => {
          latestTps = meta.tps || 0;
          setConsoleMetrics(meta);
        },
      });

      if (res.aborted) {
        const finalText = (baseText + stripCodeFences(rawStreamed)).trimEnd() + '\n\n[⏹ Генерация остановлена]\n\n';
        lastEndRef.current = finalText.length;
        setConsolePrompt(finalText);
        addLog({
          time: new Date().toLocaleTimeString('ru-RU'),
          level: 'warn',
          message: 'Генерация остановлена пользователем',
          source: 'Console',
        });
      } else if (res.success) {
        const finalText = baseText + stripCodeFences(rawStreamed).trimEnd() + '\n\n';
        lastEndRef.current = finalText.length;
        setConsolePrompt(finalText);
        if (activeAgent && recordAgentStats) {
          recordAgentStats(activeAgent.id, { tps: latestTps });
        }
        addLog({
          time: new Date().toLocaleTimeString('ru-RU'),
          level: 'success',
          message: 'Задача выполнена',
          source: 'Python Core',
        });
      } else {
        const finalText = (baseText + stripCodeFences(rawStreamed)).trimEnd() + '\n\n--- ❌ ОШИБКА ---\n' + (res.error || 'Неизвестная ошибка') + '\n\n';
        lastEndRef.current = finalText.length;
        setConsolePrompt(finalText);
        addLog({
          time: new Date().toLocaleTimeString('ru-RU'),
          level: 'error',
          message: 'Ошибка ИИ: ' + (res.error || 'Неизвестная ошибка'),
          source: 'Python Core',
        });
      }
    } finally {
      abortRef.current = null;
      setConsoleLoading(false);
    }
  };

  const runAiTask = () => {
    const startIdx = lastEndRef.current <= consolePrompt.length ? lastEndRef.current : 0;
    const freshPrompt = consolePrompt.slice(startIdx).trim() || consolePrompt.trim();
    executePrompt(freshPrompt);
  };

  const stopAiTask = () => {
    if (abortRef.current) {
      abortRef.current.abort();
    }
  };

  const retryLastTask = () => {
    if (lastPrompt.trim()) {
      executePrompt(lastPrompt);
    }
  };

  const exportPatchToPatches = async () => {
    if (!consolePrompt.trim() || exportingPatch) return;
    setExportingPatch(true);
    try {
      const res = await savePatchFromConsoleApi(consolePrompt);
      if (res.success && res.filename) {
        const okPreflight = Boolean(res.preview?.success);
        const statusMsg = okPreflight
          ? `✅ Патч ${res.filename} сохранён в patch/ и прошёл preflight-проверку!`
          : `⚠️ Патч ${res.filename} сохранён в patch/, но preflight вернул предупреждение: ${res.preview?.error || 'проверьте во вкладке Патчи'}`;
        const nextText = consolePrompt.trimEnd() + `\n\n[📦 PATCHMASTER] ${statusMsg}\n\n`;
        lastEndRef.current = nextText.length;
        setConsolePrompt(nextText);
        if (activeAgent && recordAgentStats) {
          recordAgentStats(activeAgent.id, { patchCreated: true });
        }
        addLog({
          time: new Date().toLocaleTimeString('ru-RU'),
          level: okPreflight ? 'success' : 'warn',
          message: statusMsg,
          source: 'PATCHMASTER',
        });
      } else {
        const errText = consolePrompt.trimEnd() + `\n\n[📦 PATCHMASTER ❌] ${res.error || 'Не удалось извлечь JSON-патч'}\n\n`;
        lastEndRef.current = errText.length;
        setConsolePrompt(errText);
      }
    } finally {
      setExportingPatch(false);
    }
  };

  const hasPatchCandidate =
    consolePrompt.includes('"operations"') || consolePrompt.includes('"target_file"');

  return {
    consolePrompt, setConsolePrompt,
    consoleLoading, providerMode, setProviderMode,
    selectedModel, setSelectedModel,
    bionicUrl, setBionicUrl, bionicModels,
    lmstudioUrl, setLmstudioUrl, lmstudioModels,
    strataUrl, setStrataUrl, strataModels,
    contextFiles, setContextFiles,
    includeLogs, setIncludeLogs,
    includeCodeIssues, setIncludeCodeIssues,
    exportingPatch, hasPatchCandidate, exportPatchToPatches,
    lastPrompt, consoleMetrics,
    runAiTask, stopAiTask, retryLastTask,
  };
}
