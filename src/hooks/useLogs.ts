import { useState, useEffect } from 'react';
import { LogEntry } from '../types';
import { initialLogs, POLL_INTERVALS } from '../utils/constants';
import { fetchBackendLogs } from '../services/api';

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

  const addLog = (entry: LogEntry) => {
    setLogs(prev => [...prev, entry]);
  };

  useEffect(() => {
    refreshLogs();
    const interval = setInterval(refreshLogs, POLL_INTERVALS.LOGS);
    return () => clearInterval(interval);
  }, []);

  return { logs, setLogs, addLog, refreshLogs };
}
