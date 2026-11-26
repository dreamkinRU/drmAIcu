import { useState, useEffect } from 'react';
import { LogEntry } from '../types';
import { initialLogs, POLL_INTERVALS } from '../utils/constants';
import { clearBackendLogIssues, fetchBackendLogs, postBackendLog } from '../services/api';

export function useLogs() {
  const [logs, setLogs] = useState<LogEntry[]>(initialLogs);

  const refreshLogs = async () => {
    const newLogs = await fetchBackendLogs();
    if (newLogs.length > 0) {
      setLogs(prev => {
        const unique = newLogs.filter(
          bl => !prev.some(pl => pl.time === bl.time && pl.message === bl.message)
        );
        return [...prev, ...unique];
      });
    }
  };

  // Ошибка/событие UI: сразу в локальный список (дедуп по time+message,
  // чтобы не задублировать при совпадении с ответом бэкенда) + POST /api/logs,
  // чтобы запись пережила перезагрузку страницы (раньше ошибки плагинов и синхронизации
  // вообще не попадали во вкладку «Логи»).
  const addLog = (entry: LogEntry) => {
    setLogs(prev => (
      prev.some(pl => pl.time === entry.time && pl.message === entry.message)
        ? prev
        : [...prev, entry]
    ));
    void postBackendLog(entry);
  };

  useEffect(() => {
    refreshLogs();
    const interval = setInterval(refreshLogs, POLL_INTERVALS.LOGS);
    return () => clearInterval(interval);
  }, []);

  // Кнопка «Очистить ошибки»: убирает из локального журнала (и с бэкенда через
  // DELETE /api/logs/issues) все записи error/warn — старые уже исправленные ошибки
  // перестают мозолить глаза, info/действия остаются. После очистки ротация
  // (refreshLogs) их не вернёт, потому что на бэкенде их больше нет.
  const clearIssues = async () => {
    await clearBackendLogIssues();
    setLogs(prev => prev.filter(l => l.level !== 'error' && l.level !== 'warn'));
  };

  return { logs, setLogs, addLog, refreshLogs, clearIssues };
}
