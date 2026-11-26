import { useState, useEffect } from 'react';
import { TabId } from '../../types';
import Tooltip from '../ui/Tooltip';
import { fetchSystemResources, SystemResources } from '../../services/api';
import { POLL_INTERVALS } from '../../utils/constants';

interface FooterProps {
  setActiveTab: (tab: TabId) => void;
  ollamaProcesses: Array<{ name: string; size: number; vram: number }>;
  restarting: boolean;
  onRestart: () => void;
}

export default function Footer({ setActiveTab, ollamaProcesses, restarting, onRestart }: FooterProps) {
  const [sysRes, setSysRes] = useState<SystemResources | null>(null);

  useEffect(() => {
    let active = true;
    const load = async () => {
      const data = await fetchSystemResources();
      if (active && data) {
        // ANTI-JITTER: обновляем счётчики памяти только при реальном изменении —
        // иначе каждое обновление перерисовывает индикаторы и они «прыгают».
        setSysRes(prev =>
          prev && prev.ram_used_gb === data.ram_used_gb && prev.ram_total_gb === data.ram_total_gb &&
          prev.vram_used_gb === data.vram_used_gb && prev.vram_total_gb === data.vram_total_gb
            ? prev
            : data
        );
      }
    };
    load();
    const id = setInterval(load, POLL_INTERVALS.RESOURCES);
    return () => {
      active = false;
      clearInterval(id);
    };
  }, []);

  const fmtGb = (v: number) => String(Math.round(v));
  const ramPct = sysRes && sysRes.ram_total_gb > 0
    ? Math.min(100, Math.max(0, (sysRes.ram_used_gb / sysRes.ram_total_gb) * 100))
    : 0;
  const vramPct = sysRes && sysRes.vram_total_gb > 0
    ? Math.min(100, Math.max(0, (sysRes.vram_used_gb / sysRes.vram_total_gb) * 100))
    : 0;

  const memoryTooltip = sysRes
    ? `RAM: ${fmtGb(sysRes.ram_used_gb)} / ${Math.round(sysRes.ram_total_gb)} ГБ (${Math.round(ramPct)}%) • VRAM: ${fmtGb(sysRes.vram_used_gb)} / ${Math.round(sysRes.vram_total_gb)} ГБ (${Math.round(vramPct)}%)` +
      (ollamaProcesses.length > 0 ? '\n' + ollamaProcesses.map(m => `${m.name}: ${m.vram}MB VRAM`).join('\n') : '')
    : 'Загрузка метрик памяти...';

  return (
    <footer className="fixed bottom-0 left-0 right-0 border-t border-gray-800 bg-gray-900/95 backdrop-blur-sm py-2 px-4 z-50">
      <div className="max-w-7xl mx-auto flex items-center justify-between text-xs text-gray-500">
        <div className="flex items-center gap-4">
          <button onClick={() => setActiveTab('logs')} className="hover:text-emerald-400 transition-colors flex items-center gap-1">
            <span>▤</span> Логи
          </button>
        </div>

        <div className="flex items-center gap-2.5">
          <Tooltip text={memoryTooltip} position="top">
            <div className="flex items-center gap-2">
              <div className="relative overflow-hidden px-3 py-1.5 rounded-lg bg-[#103828] border border-emerald-600/50 font-mono text-xs font-bold text-white whitespace-nowrap select-none">
                <div
                  className="absolute inset-y-0 left-0 bg-[#1f6e4c] transition-all duration-500"
                  style={{ width: `${ramPct}%` }}
                />
                <span className="relative z-10">
                  RAM: {sysRes && sysRes.ram_total_gb > 0 ? `${fmtGb(sysRes.ram_used_gb)} / ${Math.round(sysRes.ram_total_gb)} GB` : '—'}
                </span>
              </div>

              <div className="relative overflow-hidden px-3 py-1.5 rounded-lg bg-[#123842] border border-cyan-600/50 font-mono text-xs font-bold text-white whitespace-nowrap select-none">
                <div
                  className="absolute inset-y-0 left-0 bg-[#157485] transition-all duration-500"
                  style={{ width: `${vramPct}%` }}
                />
                <span className="relative z-10">
                  VRAM: {sysRes && sysRes.vram_total_gb > 0 ? `${fmtGb(sysRes.vram_used_gb)} / ${Math.round(sysRes.vram_total_gb)} GB` : '—'}
                </span>
              </div>
            </div>
          </Tooltip>

          <Tooltip text="Перезапустить Python и React" position="top">
            <button
              type="button"
              onClick={onRestart}
              disabled={restarting}
              className={`flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-bold transition-all whitespace-nowrap border ${
                restarting
                  ? 'bg-gray-800 border-gray-700 text-gray-500 cursor-not-allowed'
                  : 'bg-[#151d28] border-[#b87e4d]/80 text-[#d8935a] hover:bg-[#1e2938] hover:border-[#d8935a]'
              }`}
            >
              <svg
                className={`w-3.5 h-3.5 ${restarting ? 'animate-spin' : ''}`}
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2.2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <path d="M21 12a9 9 0 0 0-9-9 9.75 9.75 0 0 0-6.74 2.74L3 8" />
                <path d="M3 3v5h5" />
                <path d="M3 12a9 9 0 0 0 9 9 9.75 9.75 0 0 0 6.74-2.74L21 16" />
                <path d="M16 16h5v5" />
              </svg>
              <span>{restarting ? 'Рестарт...' : 'Перезапуск'}</span>
            </button>
          </Tooltip>
        </div>
      </div>
    </footer>
  );
}
