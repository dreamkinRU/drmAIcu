import Tooltip from '../ui/Tooltip';
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
  setActiveTab: (tab: TabId) => void;
}

export default function Header(props: HeaderProps) {
  const {
    activeTab, agents, providers, patchStats, codeIssues,
    completedTasks, taskList, projectStats, ollamaStatus, ollamaModels,
    setActiveTab,
  } = props;

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
                <p className="text-[10px] text-gray-500 leading-tight mt-0.5">v.3.6.1 Model</p>
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
