import { useState, useEffect } from 'react';
import { Provider } from '../types';
import { initialProviders, POLL_INTERVALS } from '../utils/constants';
import { checkOllama as checkOllamaApi, loadInstalledModels as loadInstalledModelsApi, pullModel as pullModelApi } from '../services/api';
import { OllamaModel } from '../types';

export function useOllama() {
  const [ollamaUrl, setOllamaUrl] = useState('http://localhost:11434');
  const [providers, setProviders] = useState<Provider[]>(initialProviders);
  const [ollamaStatus, setOllamaStatus] = useState<'checking' | 'online' | 'offline'>('checking');
  const [ollamaModels, setOllamaModels] = useState<string[]>([]);
  const [ollamaProcesses, setOllamaProcesses] = useState<Array<{ name: string; size: number; vram: number }>>([]);
  const [installedModels, setInstalledModels] = useState<OllamaModel[]>([]);
  const [newModelName, setNewModelName] = useState('');
  const [isPulling, setIsPulling] = useState(false);

  // ANTI-JITTER: setState только при реальном изменении данных — иначе каждый
  // опрос создаёт новый массив и перерисовывает страницу без причины.
  const sameJson = (a: unknown, b: unknown) => JSON.stringify(a) === JSON.stringify(b);

  const checkOllama = async () => {
    const result = await checkOllamaApi(ollamaUrl);
    if (result.online) {
      setOllamaStatus(prev => (prev === 'online' ? prev : 'online'));
      setOllamaModels(prev => (sameJson(prev, result.models) ? prev : result.models));
      setOllamaProcesses(prev => (sameJson(prev, result.processes) ? prev : result.processes));
      setProviders(prev =>
        prev.map(p =>
          p.name === 'Ollama'
            ? { ...p, status: 'online', models: result.models.length }
            : p
        )
      );
    } else {
      setOllamaStatus(prev => (prev === 'offline' ? prev : 'offline'));
      setOllamaModels(prev => (prev.length === 0 ? prev : []));
      setOllamaProcesses(prev => (prev.length === 0 ? prev : []));
      setProviders(prev =>
        prev.map(p => (p.name === 'Ollama' ? { ...p, status: 'offline', models: 0 } : p))
      );
    }
  };

  const loadInstalledModels = async () => {
    const models = await loadInstalledModelsApi();
    setInstalledModels(prev => (sameJson(prev, models) ? prev : models));
  };

  const pullModel = async () => {
    if (!newModelName.trim()) return;
    setIsPulling(true);
    try {
      const data = await pullModelApi(newModelName);
      if (data.success) {
        alert(data.message);
        setNewModelName('');
        loadInstalledModels();
        checkOllama();
      } else {
        alert('Ошибка: ' + data.error);
      }
    } catch {
      alert('Ошибка сети');
    } finally {
      setIsPulling(false);
    }
  };

  useEffect(() => {
    checkOllama();
    loadInstalledModels();
    const ollamaInterval = setInterval(checkOllama, POLL_INTERVALS.OLLAMA);
    const modelsInterval = setInterval(loadInstalledModels, POLL_INTERVALS.MODELS);
    return () => {
      clearInterval(ollamaInterval);
      clearInterval(modelsInterval);
    };
  }, [ollamaUrl]);

  const totalRam = ollamaProcesses.reduce((s, m) => s + m.size, 0);
  const totalVram = ollamaProcesses.reduce((s, m) => s + m.vram, 0);

  return {
    ollamaUrl, setOllamaUrl,
    providers, setProviders,
    ollamaStatus, ollamaModels, ollamaProcesses,
    installedModels, newModelName, setNewModelName, isPulling,
    checkOllama, loadInstalledModels, pullModel,
    totalRam, totalVram,
  };
}
