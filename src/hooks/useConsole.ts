import { useState, useRef, useEffect } from 'react';
import { runAiTaskStream, StreamMetrics, loadBionicModels, loadLmStudioModels, loadStrataModels } from '../services/api';

function stripCodeFences(text: string): string {
  return text
    .replace(/```[a-zA-Z0-9_-]*\r?\n?/g, '')
    .replace(/```/g, '')
    .replace(/\r\n/g, '\n')
    .replace(/\n{2,}/g, '\n')
    .replace(/^\n+/, '');
}

export function useConsole(addLog: (entry: any) => void) {
  const [consolePrompt, setConsolePrompt] = useState('');
  const [consoleLoading, setConsoleLoading] = useState(false);
  const [providerMode, setProviderMode] = useState<'ollama' | 'groq' | 'bionic' | 'lmstudio' | 'strata' | 'all'>(() => {
    try {
      const saved = localStorage.getItem('drmaicu_provider_mode');
      if (saved === 'ollama' || saved === 'groq' || saved === 'bionic' || saved === 'lmstudio' || saved === 'strata' || saved === 'all') return saved;
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

  const executePrompt = async (promptToSend: string) => {
    if (!promptToSend.trim() || consoleLoading) return;
    setLastPrompt(promptToSend);
    setConsoleLoading(true);
    setConsoleMetrics(null);

    const controller = new AbortController();
    abortRef.current = controller;

    addLog({
      time: new Date().toLocaleTimeString('ru-RU'),
      level: 'info',
      message: 'Стриминг задачи (провайдер: ' + providerMode + (selectedModel ? `, модель: ${selectedModel}` : '') + ')...',
      source: 'Console',
    });

    const baseText = consolePrompt.trimEnd() + '\n> ';
    let rawStreamed = '';
    setConsolePrompt(baseText);

    try {
      const res = await runAiTaskStream(promptToSend, providerMode, selectedModel, {
        signal: controller.signal,
        onChunk: (chunk) => {
          rawStreamed += chunk;
          setConsolePrompt(baseText + stripCodeFences(rawStreamed));
        },
        onMeta: (meta) => {
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

  return {
    consolePrompt, setConsolePrompt,
    consoleLoading, providerMode, setProviderMode,
    selectedModel, setSelectedModel,
    bionicUrl, setBionicUrl, bionicModels,
    lmstudioUrl, setLmstudioUrl, lmstudioModels,
    strataUrl, setStrataUrl, strataModels,
    lastPrompt, consoleMetrics,
    runAiTask, stopAiTask, retryLastTask,
  };
}
