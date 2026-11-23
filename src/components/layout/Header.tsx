import Tooltip from '../ui/Tooltip';
import { TabId } from '../../types';

interface HeaderProps {
  agents: any[];
  providers: any[];
  installedModels: any[];
  patchStats: any;
  codeIssues: any[];
  completedTasks: number;
  taskList: any[];
  projectStats: any;
  ollamaStatus: 'checking' | 'online' | 'offline';
  ollamaModels: string[];
  ollamaProcesses: Array<{ name: string; size: number; vram: number }>;
  restarting: boolean;
  onRestart: () => void;
  setActiveTab: (tab: TabId) => void;
}

export default function Header(props: HeaderProps) {
  const {
    agents, providers, installedModels, patchStats, codeIssues,
    completedTasks, taskList, projectStats, ollamaStatus, ollamaModels,
    ollamaProcesses, restarting, onRestart, setActiveTab,
  } = props;

  const totalRam = ollamaProcesses.reduce((s, m) => s + m.size, 0);
  const totalVram = ollamaProcesses.reduce((s, m) => s + m.vram, 0);

  return (
    <header className="bg-gray-900/90 backdrop-blur-sm border-b border-gray-800 sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 py-3">
        <div className="flex items-center justify-between gap-4">
          <Tooltip text={ollamaStatus === 'online' ? `✅ Ollama онлайн • ${ollamaModels.length} моделей` : '❌ Ollama не запущен'} position="bottom">
            <div className="flex items-center gap-3 cursor-pointer" onClick={() => setActiveTab('console')}>
              <div className="w-12 h-12 rounded-lg bg-gradient-to-br from-emerald-500 via-cyan-500 to-blue-500 flex items-center justify-center font-bold text-sm shadow-lg shadow-emerald-500/30">AI</div>
              <div>
                <h1 className="text-lg font-bold gradient-text leading-tight">drmAIcu</h1>
                <p className="text-xs text-gray-500 leading-tight">v.3.6.0 HARDENED</p>
              </div>
            </div>
          </Tooltip>

          <div className="flex items-center gap-3 flex-1 justify-center">
            <Tooltip text={`${agents.filter(a => a.enabled).length} агентов`} position="bottom">
              <button onClick={() => setActiveTab('agents')} className="flex items-center gap-2 px-2 py-2 rounded-lg bg-gray-800/50 border border-gray-700/50 hover:border-emerald-500/50 transition-all">
                <span className="text-xl">🤖</span>
                <div className="text-left">
                  <p className="text-[10px] text-gray-500">Агенты</p>
                  <div className="flex items-baseline gap-1">
                    <span className="font-bold text-emerald-400 text-lg">{agents.filter(a => a.enabled).length}</span>
                    <span className="text-gray-500 text-sm">/{agents.length}</span>
                  </div>
                </div>
              </button>
            </Tooltip>

            <Tooltip text={`${providers.filter(p => p.status === 'online').length} провайдеров`} position="bottom">
              <button onClick={() => setActiveTab('providers')} className="flex items-center gap-2 px-2 py-2 rounded-lg bg-gray-800/50 border border-gray-700/50 hover:border-cyan-500/50 transition-all">
                <span className="text-xl">🌐</span>
                <div className="text-left">
                  <p className="text-[10px] text-gray-500">Провайдеры</p>
                  <div className="flex items-baseline gap-1">
                    <span className="font-bold text-cyan-400 text-lg">{providers.filter(p => p.status === 'online').length}</span>
                    <span className="text-gray-500 text-sm">/{providers.length}</span>
                  </div>
                </div>
              </button>
            </Tooltip>

            <Tooltip text={`${projectStats?.total || 0} файлов`} position="bottom">
              <button onClick={() => setActiveTab('project')} className="flex items-center gap-2 px-2 py-2 rounded-lg bg-gray-800/50 border border-gray-700/50 hover:border-orange-500/50 transition-all">
                <span className="text-xl">🗂</span>
                <div className="text-left">
                  <p className="text-[10px] text-gray-500">Файлов</p>
                  <div className="flex items-baseline gap-1">
                    <span className="font-bold text-orange-400 text-lg">{projectStats?.total || 0}</span>
                  </div>
                </div>
              </button>
            </Tooltip>

            <Tooltip text={`${installedModels.length} моделей`} position="bottom">
              <button onClick={() => setActiveTab('models')} className="flex items-center gap-2 px-2 py-2 rounded-lg bg-gray-800/50 border border-gray-700/50 hover:border-purple-500/50 transition-all">
                <span className="text-xl">🧠</span>
                <div className="text-left">
                  <p className="text-[10px] text-gray-500">Модели</p>
                  <div className="flex items-baseline gap-1">
                    <span className="font-bold text-purple-400 text-lg">{installedModels.length}</span>
                  </div>
                </div>
              </button>
            </Tooltip>

            <Tooltip text={`${patchStats.pending || 0} патчей`} position="bottom">
              <button onClick={() => setActiveTab('patches')} className="flex items-center gap-2 px-2 py-2 rounded-lg bg-gray-800/50 border border-gray-700/50 hover:border-yellow-500/50 transition-all">
                <span className="text-xl">🔄</span>
                <div className="text-left">
                  <p className="text-[10px] text-gray-500">Патчи</p>
                  <div className="flex items-baseline gap-1">
                    <span className="font-bold text-yellow-400 text-lg">{patchStats.pending || 0}</span>
                  </div>
                </div>
              </button>
            </Tooltip>

            <Tooltip text={`${codeIssues.filter(i => !i.fixed).length} ошибок`} position="bottom">
              <button onClick={() => setActiveTab('code')} className="flex items-center gap-2 px-2 py-2 rounded-lg bg-gray-800/50 border border-gray-700/50 hover:border-red-500/50 transition-all">
                <span className="text-xl">⟨⟩</span>
                <div className="text-left">
                  <p className="text-[10px] text-gray-500">Код</p>
                  <span className="font-bold text-red-400 text-lg">{codeIssues.filter(i => !i.fixed).length}</span>
                </div>
              </button>
            </Tooltip>

            <Tooltip text={`${completedTasks}/${taskList.length} задач`} position="bottom">
              <button onClick={() => setActiveTab('tasks')} className="flex items-center gap-2 px-2 py-2 rounded-lg bg-gray-800/50 border border-gray-700/50 hover:border-yellow-500/50 transition-all">
                <span className="text-xl">☑</span>
                <div className="text-left">
                  <p className="text-[10px] text-gray-500">Задачи</p>
                  <div className="flex items-baseline gap-1">
                    <span className="font-bold text-yellow-400 text-lg">{completedTasks}</span>
                    <span className="text-gray-500 text-sm">/{taskList.length}</span>
                  </div>
                </div>
              </button>
            </Tooltip>
          </div>

          <div className="flex items-center gap-3">
            <Tooltip text={ollamaProcesses.length > 0 ? ollamaProcesses.map(m => `${m.name}: ${m.size}MB RAM`).join('\n') : 'Нет моделей'} position="bottom">
              <div className="flex flex-col items-center gap-1 px-3 py-2 rounded-lg bg-gray-800/50 border border-gray-700/50">
                <div className="flex items-center gap-2">
                  <span className="text-xs text-gray-500">RAM:</span>
                  <span className={`font-mono font-bold text-sm ${totalRam > 0 ? 'text-emerald-400' : 'text-gray-600'}`}>{totalRam}MB</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-xs text-gray-500">VRAM:</span>
                  <span className={`font-mono font-bold text-sm ${totalVram > 0 ? 'text-cyan-400' : 'text-gray-600'}`}>{totalVram}MB</span>
                </div>
              </div>
            </Tooltip>

            <Tooltip text="Перезапустить Python и React" position="bottom">
              <button onClick={onRestart} disabled={restarting} className={`px-4 py-2 rounded-lg text-sm font-bold transition-all ${restarting ? 'bg-gray-700 text-gray-500 cursor-not-allowed' : 'bg-orange-500/20 border border-orange-500/50 text-orange-400 hover:bg-orange-500/30'}`}>
                {restarting ? '⏳ Перезапуск...' : '🔄 Перезапуск'}
              </button>
            </Tooltip>
          </div>
        </div>
      </div>
    </header>
  );
}
