import { useState } from 'react';
import { runAiTask as runAiTaskApi } from '../services/api';

export function useConsole(addLog: (entry: any) => void) {
  const [consolePrompt, setConsolePrompt] = useState('');
  const [consoleLoading, setConsoleLoading] = useState(false);
  const [providerMode, setProviderMode] = useState<'ollama' | 'groq' | 'all'>('all');
  const [selectedModel, setSelectedModel] = useState<string>('');

  const runAiTask = async () => {
    if (!consolePrompt.trim()) return;
    setConsoleLoading(true);
    addLog({
      time: new Date().toLocaleTimeString('ru-RU'),
      level: 'info',
      message: 'Отправка задачи (режим: ' + providerMode + (selectedModel ? `, модель: ${selectedModel}` : '') + ')...',
      source: 'Console',
    });
    try {
      const data = await runAiTaskApi(consolePrompt, providerMode, selectedModel);
      if (data.success) {
        setConsolePrompt(prev => prev + '\n\n--- ✅ РЕЗУЛЬТАТ ---\n' + data.result);
        addLog({
          time: new Date().toLocaleTimeString('ru-RU'),
          level: 'success',
          message: 'Задача выполнена',
          source: 'Python Core',
        });
      } else {
        setConsolePrompt(prev => prev + '\n\n--- ❌ ОШИБКА ---\n' + (data.error || 'Неизвестная ошибка'));
        addLog({
          time: new Date().toLocaleTimeString('ru-RU'),
          level: 'error',
          message: 'Ошибка ИИ: ' + data.error,
          source: 'Python Core',
        });
      }
    } catch {
      setConsolePrompt(prev => prev + '\n\n--- ❌ ОШИБКА СЕТИ ---');
      addLog({
        time: new Date().toLocaleTimeString('ru-RU'),
        level: 'error',
        message: 'Ошибка сети',
        source: 'React',
      });
    } finally {
      setConsoleLoading(false);
    }
  };

  return {
    consolePrompt, setConsolePrompt,
    consoleLoading, providerMode, setProviderMode,
    selectedModel, setSelectedModel,
    runAiTask,
  };
}
