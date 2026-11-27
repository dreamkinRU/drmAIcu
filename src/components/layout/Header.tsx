import Tooltip from '../ui/Tooltip';
import { useEffect, useState } from 'react';
import type { PatchProgress } from '../../services/api';

function statusLabel(state: string, step?: string) {
  const labels: Record<string,string> = {
    idle: 'Готов', running: 'Выполняется', success: 'Применён', warning: 'Внимание',
    failed: 'Ошибка', recovery_required: 'Восстановление', IDLE: 'Готов',
    CHECKED: 'Проверен', APPLYING: 'Обновление', CODE_UPDATED: 'Код получен',
    RESTORING: 'Восстановление', PREPARING: 'Подготовка', RESTART_REQUIRED: 'Перезапуск',
    COMPLETED: 'Завершено', FAILED: 'Ошибка', RECOVERY_REQUIRED: 'Восстановление',
    UPDATE_NEEDS_REPAIR: 'Требуется ремонт',
  };
  const stages: Record<string,string> = {validation:'Проверка',backup:'Бэкап',write:'Запись',manifest:'Манифест',archive:'Архив',merge:'Git',restore:'Восстановление',environment:'Окружение',python:'Python',npm:'npm',frontend_build:'Сборка'};
  return (step && stages[step]) || labels[state] || state;
}
function statusColor(state: string) {
  if (['success','COMPLETED'].includes(state)) return 'text-emerald-300';
  if (['failed','FAILED','RECOVERY_REQUIRED','recovery_required','UPDATE_NEEDS_REPAIR'].includes(state)) return 'text-red-300';
  if (['running','APPLYING','RESTORING','PREPARING'].includes(state)) return 'text-cyan-300';
  return 'text-amber-300';
}
import { TabId } from '../../types';

interface HeaderProps {
  activeTab?: TabId;
  agents: any[];
  providers: any[];
  patchStats: any;
  codeIssues: any[];
  completedTasks: number;
  taskList: any[];
  projectStats: any;
  ollamaStatus: 'checking' | 'online' | 'offline';
  ollamaModels: string[];
  version: string | null;
  setActiveTab: (tab: TabId) => void;
  onIncomingUpdate: () => void;
  incomingBusy: boolean;
  applyingPatch: boolean;
}

export default function Header(props: HeaderProps) {
  const {
    activeTab, agents, providers, patchStats, codeIssues,
    completedTasks, taskList, projectStats, ollamaStatus, ollamaModels,
    version, setActiveTab, onIncomingUpdate, incomingBusy, applyingPatch,
  } = props;

  const [patchProgress, setPatchProgress] = useState<PatchProgress | null>(null);
  const [updateProgress, setUpdateProgress] = useState<{state?: string; active_step?: string; behind?: number; ahead?: number} | null>(null);
  useEffect(() => {
    let stopped = false;
    let timer: number;
    async function poll() {
      const read = async (url: string) => {
        const response = await fetch(url, { cache: 'no-store', signal: AbortSignal.timeout(4000) });
        if (!response.ok) throw new Error('status unavailable');
        const data = await response.json();
        if (!data.success) throw new Error('status unavailable');
        return data.progress;
      };
      const [patch, update] = await Promise.allSettled([read('/api/patches/progress'), read('/api/updates/progress')]);
      if (stopped) return;
      setPatchProgress(patch.status === 'fulfilled' ? patch.value : null);
      setUpdateProgress(update.status === 'fulfilled' ? update.value : null);
      timer = window.setTimeout(poll, applyingPatch || incomingBusy ? 1200 : 5000);
    }
    void poll();
    return () => { stopped = true; window.clearTimeout(timer); };
  }, [applyingPatch, incomingBusy]);
  const patchState = applyingPatch ? 'running' : patchProgress?.state || '';
  const updateState = updateProgress?.state || '';
  const updateActive = incomingBusy || ['APPLYING','RESTORING','PREPARING'].includes(updateState);
  const onlineProviders = providers.filter(p => p.status === 'online').length;
  const activeAgents = agents.filter(a => a.enabled).length;
  const openIssues = codeIssues.filter(i => !i.fixed).length;

  const navBtnClass = (tab: TabId) =>
    `flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold border transition-all whitespace-nowrap ${
      activeTab === tab
        ? 'bg-cyan-500/15 border-cyan-400/70 text-cyan-300 shadow-[0_0_12px_rgba(34,211,238,0.22)]'
        : 'bg-gray-800/50 border-gray-700/60 text-gray-300 hover:border-gray-600 hover:text-white'
    }`;

  return (
    <header className="bg-gray-900/95 backdrop-blur-md border-b border-gray-800 sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 py-2.5">
        <div className="flex items-center justify-between gap-4">
          <Tooltip text={ollamaStatus === 'online' ? `✅ Ollama онлайн • ${ollamaModels.length} моделей` : '❌ Ollama не запущен'} position="bottom">
            <div className="flex items-center gap-2.5 cursor-pointer shrink-0" onClick={() => setActiveTab('console')}>
              <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-emerald-500 via-cyan-500 to-blue-500 flex items-center justify-center font-bold text-xs shadow-lg shadow-emerald-500/25">
                AI
              </div>
              <div>
                <h1 className="text-base font-bold gradient-text leading-none">drmAIcu</h1>
                <p className="text-[10px] text-gray-500 leading-tight mt-0.5">{version ? `v.${version} Model` : '\u2026'}</p>
              </div>
            </div>
          </Tooltip>

          <nav className="flex items-center gap-2 flex-1 justify-end overflow-x-auto">
            <Tooltip text={`${activeAgents} из ${agents.length} агентов`} position="bottom">
              <button onClick={() => setActiveTab('agents')} className={navBtnClass('agents')}>
                <span>🤖</span>
                <span>Агенты</span>
                <span className="text-[11px] text-emerald-400 font-mono">{activeAgents}/{agents.length}</span>
              </button>
            </Tooltip>

            <Tooltip text={`${onlineProviders} из ${providers.length} провайдеров онлайн`} position="bottom">
              <button onClick={() => setActiveTab('providers')} className={navBtnClass('providers')}>
                <span>🌐</span>
                <span>Провайдеры</span>
                <span className="text-[11px] text-cyan-400 font-mono">{onlineProviders}/{providers.length}</span>
              </button>
            </Tooltip>

            <Tooltip text={`${projectStats?.total || 0} файлов проекта`} position="bottom">
              <button onClick={() => setActiveTab('project')} className={navBtnClass('project')}>
                <span>🗂</span>
                <span>Файлы</span>
                <span className="text-[11px] text-orange-400 font-mono">{projectStats?.total || 0}</span>
              </button>
            </Tooltip>

            <Tooltip text={`${patchStats.pending || 0} ожидающих патчей`} position="bottom">
              <button onClick={() => setActiveTab('patches')} className={navBtnClass('patches')}>
                <span>🔄</span>
                <span>Патчи</span>
                <span className="text-[11px] text-yellow-400 font-mono">{patchStats.pending || 0}</span>
                <span role="status" className={statusColor(patchState)}>{patchState ? statusLabel(patchState, patchState === 'running' && patchProgress?.state === 'running' ? patchProgress.stage : undefined) : 'Нет связи'}{patchProgress?.state === 'running' && patchProgress.patch_id ? ' #' + patchProgress.patch_id : ''}</span>
              </button>
            </Tooltip>

            <Tooltip text={`${openIssues} замечаний в коде`} position="bottom">
              <button onClick={() => setActiveTab('code')} className={navBtnClass('code')}>
                <span>⟨⟩</span>
                <span>Код</span>
                <span className="text-[11px] text-red-400 font-mono">{openIssues}</span>
              </button>
            </Tooltip>

            <Tooltip text={`${completedTasks}/${taskList.length} задач`} position="bottom">
              <button onClick={() => setActiveTab('tasks')} className={navBtnClass('tasks')}>
                <span>☑</span>
                <span>Задачи</span>
                <span className="text-[11px] text-amber-400 font-mono">{completedTasks}/{taskList.length}</span>
              </button>
            </Tooltip>

            <Tooltip text="Плагины: интеграции, разрешения, журнал" position="bottom">
              <button onClick={() => setActiveTab('plugins')} className={navBtnClass('plugins')}>
                <span>🔌</span>
                <span>Плагины</span>
              </button>
            </Tooltip>

            <Tooltip text="Репозитории: локальный git и синхронизация с GitHub (замена sync.bat)" position="bottom">
              <button onClick={() => setActiveTab('repositories')} className={navBtnClass('repositories')}>
                <span>🗂</span>
                <span>Репозитории</span>
              </button>
            </Tooltip>

            <div className="flex items-center gap-1 shrink-0">
              <Tooltip text="Открыть мастер обновления" position="bottom">
                <button onClick={() => setActiveTab('updates')} className={navBtnClass('updates')}>
                  <span>Обновление</span>
                  <span role="status" className={statusColor(updateActive ? 'running' : updateState)}>{updateActive ? (['APPLYING','RESTORING','PREPARING'].includes(updateState) ? statusLabel(updateState, updateProgress?.active_step) : 'Выполняется') : updateState ? statusLabel(updateState) : 'Нет данных'}</span>
                </button>
              </Tooltip>
              <button type="button" onClick={onIncomingUpdate} disabled={incomingBusy || updateActive || applyingPatch || patchProgress?.state === 'running'}
                title="Входящая синхронизация: получить изменения GitHub, выполнить три этапа и перезапуск при необходимости"
                aria-label="Входящая синхронизация из GitHub"
                className="rounded-lg border border-emerald-400/60 bg-emerald-500/15 px-2 py-1.5 text-emerald-300 hover:bg-emerald-500/25 disabled:opacity-40">
                <svg aria-hidden="true" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 3v12m-5-5 5 5 5-5M4 16v5h16v-5"/></svg>
              </button>
            </div>

            <Tooltip text="Документация и заметки Markdown" position="bottom">
              <button onClick={() => setActiveTab('md')} className={navBtnClass('md')}>
                <span>📝</span>
                <span>MD</span>
              </button>
            </Tooltip>
          </nav>
        </div>
      </div>
    </header>
  );
}
