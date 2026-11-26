import { useState, useEffect } from 'react';
import { LogEntry } from '../types';
import { initialLogs, POLL_INTERVALS } from '../utils/constants';
import { fetchBackendLogs, postBackendLog } from '../services/api';

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

  return { logs, setLogs, addLog, refreshLogs };
}
