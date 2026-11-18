import { useState, useEffect } from 'react';

interface Agent { id: number; name: string; status: 'active' | 'frozen' | 'offline'; task: string; stack: string[]; progress: number; lastActivity: string; enabled: boolean; description: string; }
interface Provider { name: string; status: 'online' | 'offline' | 'error'; latency: number; models: number; description: string; url: string; enabled: boolean; apiKey?: string; getKeyUrl?: string; }
interface LogEntry { time: string; level: 'info' | 'warn' | 'error' | 'success'; message: string; source: string; details?: string; }
interface CodeIssue { id: number; severity: 'critical' | 'warning' | 'info'; line: string; title: string; description: string; fix: string; before: string; after: string; file: string; fixed: boolean; fixLog?: string[]; }
interface Task { id: number; text: string; done: boolean; priority: 'high' | 'medium' | 'low'; category: 'code' | 'general'; }
interface MDFile { name: string; description: string; }
interface OllamaModel { name: string; size_gb: number; }
interface PatchInfo { filename: string; filepath: string; patch_id: string; target_file: string; description: string; author: string; created_at: string; is_applied: boolean; file_exists: boolean; checksum_ok: boolean | null; content_length: number; has_content: boolean; error?: string; full_file_content?: string; }
interface ProjectFile { path: string; filename: string; size: number; size_human: string; modified: string; category: string; hash: string; preview: string; is_critical: boolean; is_important: boolean; extension: string; icon: string; is_duplicate: boolean; duplicates: string[]; error?: string; }
interface ProjectStats { total: number; total_size: number; total_size_human: string; by_category: Record<string, number>; by_extension: Record<string, number>; duplicates_count: number; duplicates_groups: number; critical_count: number; important_count: number; trash_count: number; backup_count: number; }

const initialAgents: Agent[] = [
  { id: 1, name: 'Агент №1 — Развитие системы', status: 'active', task: 'Исправление ошибок компиляции', stack: ['Java', 'Python', 'VBA/Excel'], progress: 45, lastActivity: '2 мин назад', enabled: true, description: 'Основной агент для развития инфраструктуры drmAIcu.' },
  { id: 2, name: 'Агент №2 — Аналитика данных', status: 'frozen', task: 'На паузе', stack: ['Python', 'Pandas', 'SQL'], progress: 0, lastActivity: '—', enabled: false, description: 'Агент для анализа данных и построения отчётов.' },
  { id: 3, name: 'Агент №3 — Автоматизация отчётов', status: 'frozen', task: 'На паузе', stack: ['Python', 'Excel VBA', 'TTS'], progress: 0, lastActivity: '—', enabled: false, description: 'Агент для автоматизации создания отчётов.' },
];
const agentStore = [
  { id: 'agent-ml', name: 'Агент ML', description: 'Машинное обучение, нейронные сети.', stack: ['Python', 'TensorFlow'], category: 'AI/ML' },
  { id: 'agent-web', name: 'Агент Web', description: 'Full-stack веб-разработчик.', stack: ['JavaScript', 'React'], category: 'Web' },
  { id: 'agent-devops', name: 'Агент DevOps', description: 'CI/CD, контейнеризация.', stack: ['Docker', 'Kubernetes'], category: 'DevOps' },
];
const initialProviders: Provider[] = [
  { name: 'Ollama', status: 'offline', latency: 0, models: 0, description: 'Локальные модели', url: 'http://localhost:11434', enabled: true },
  { name: 'Groq', status: 'online', latency: 23, models: 8, description: 'Быстрые облачные модели', url: 'https://console.groq.com', enabled: true, apiKey: '', getKeyUrl: 'https://console.groq.com/keys' },
  { name: 'HuggingFace', status: 'online', latency: 120, models: 150, description: 'Библиотека моделей', url: 'https://huggingface.co', enabled: true, apiKey: '', getKeyUrl: 'https://huggingface.co/settings/tokens' },
  { name: 'OpenRouter', status: 'online', latency: 89, models: 45, description: 'Агрегатор моделей', url: 'https://openrouter.ai', enabled: true, apiKey: '', getKeyUrl: 'https://openrouter.ai/workspaces/default/keys' },
  { name: 'Gemini', status: 'offline', latency: 0, models: 0, description: 'Google Gemini', url: 'https://aistudio.google.com', enabled: false, apiKey: '', getKeyUrl: 'https://aistudio.google.com/api-keys' },
  { name: 'Together', status: 'error', latency: 0, models: 0, description: 'Together AI', url: 'https://api.together.xyz', enabled: false, apiKey: '' },
];
const initialLogs: LogEntry[] = [{ time: '14:32:01', level: 'info', message: 'ЦУ v.3.4.3 TOGGLES запущена', source: 'main.py' }];
const initialCodeIssues: CodeIssue[] = [
  { id: 1, severity: 'critical', line: '113', file: 'agent_engine.py', title: 'asyncio.get_event_loop() — deprecated', description: 'В Python 3.10+ вызывает DeprecationWarning', fix: 'Заменить на asyncio.get_running_loop()', before: 'loop = asyncio.get_event_loop()', after: 'loop = asyncio.get_running_loop()', fixed: false, fixLog: [] },
  { id: 2, severity: 'critical', line: '126', file: 'agent_engine.py', title: 'Gemini: потеря контекста', description: 'Берётся только messages[-1]', fix: 'Конвертировать все messages', before: 'prompt_text = messages[-1]', after: 'contents = messages.map(...)', fixed: false, fixLog: [] },
  { id: 3, severity: 'warning', line: '83', file: 'agent_engine.py', title: 'HuggingFace: нет метода запроса', description: 'Клиент есть, метода нет', fix: 'Добавить _query_huggingface', before: '// Нет метода', after: 'async _query_huggingface(...)', fixed: false, fixLog: [] },
];
const initialTasks: Task[] = [
  { id: 1, text: 'Исправить py_compile ошибку в main.py', done: false, priority: 'high', category: 'code' },
  { id: 2, text: 'Исправить импорт VBA-модулей', done: false, priority: 'high', category: 'code' },
  { id: 3, text: 'Реализовать модуль TTS', done: false, priority: 'medium', category: 'general' },
  { id: 4, text: 'Тестирование мульти-провайдеров', done: true, priority: 'low', category: 'general' },
];
const mdFiles: MDFile[] = [
  { name: 'CHANGELOG.md', description: 'Полная история изменений' },
  { name: 'USER_GUIDE.md', description: 'Руководство пользователя' },
  { name: 'NEW_FEATURES.md', description: 'Описание новых функций' },
  { name: 'ARCHITECTURE.md', description: 'Архитектура системы' },
];

function Tooltip({ children, text, position = 'bottom' }: { children: React.ReactNode; text: string; position?: 'top' | 'bottom' | 'left' | 'right' }) {
  const posClasses = { top: 'bottom-full left-1/2 -translate-x-1/2 mb-2', bottom: 'top-full left-1/2 -translate-x-1/2 mt-2', left: 'right-full top-1/2 -translate-y-1/2 mr-2', right: 'left-full top-1/2 -translate-y-1/2 ml-2' };
  const arrowClasses = { top: 'top-full left-1/2 -translate-x-1/2 border-t-gray-900', bottom: 'bottom-full left-1/2 -translate-x-1/2 border-b-gray-900', left: 'left-full top-1/2 -translate-y-1/2 border-l-gray-900', right: 'right-full top-1/2 -translate-y-1/2 border-r-gray-900' };
  return (<div className="relative group">{children}<div className={`absolute ${posClasses[position]} px-3 py-2 bg-gray-900 border border-gray-700 rounded-lg text-xs text-gray-300 whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-[100] shadow-xl`}>{text}<div className={`absolute ${arrowClasses[position]} border-4 border-transparent`}></div></div></div>);
}
function StatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = { active: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30', frozen: 'bg-blue-500/20 text-blue-400 border-blue-500/30', offline: 'bg-gray-500/20 text-gray-400 border-gray-500/30', online: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30', error: 'bg-red-500/20 text-red-400 border-red-500/30' };
  const labels: Record<string, string> = { active: 'АКТИВЕН', frozen: 'ЗАМОРОЖЕН', offline: 'ОФФЛАЙН', online: 'ОНЛАЙН', error: 'ОШИБКА' };
  return <span className={`px-2 py-0.5 rounded text-[10px] font-bold border ${colors[status] || colors.offline}`}>{labels[status] || status}</span>;
}

export default function App() {
  const [agents, setAgents] = useState<Agent[]>(initialAgents);
  const [providers, setProviders] = useState<Provider[]>(initialProviders);
  const [logs, setLogs] = useState<LogEntry[]>(initialLogs);
  const [codeIssues, setCodeIssues] = useState<CodeIssue[]>(initialCodeIssues);
  const [taskList, setTaskList] = useState<Task[]>(initialTasks);
  const [currentTime, setCurrentTime] = useState(new Date());
  const [activeTab, setActiveTab] = useState<'console' | 'panel' | 'agents' | 'providers' | 'models' | 'md' | 'code' | 'logs' | 'tasks' | 'patches' | 'project'>(() => {
    const saved = localStorage.getItem('drmActiveTab') as 'console' | 'panel' | 'agents' | 'providers' | 'models' | 'md' | 'code' | 'logs' | 'tasks' | 'patches' | 'project' | null;
    return saved || 'console';
  });
  useEffect(() => { localStorage.setItem('drmActiveTab', activeTab); }, [activeTab]);
  const [ollamaUrl, setOllamaUrl] = useState('http://localhost:11434');
  const [providerMode, setProviderMode] = useState<'ollama' | 'groq' | 'all'>('all');
  const [consolePrompt, setConsolePrompt] = useState('');
  const [consoleLoading, setConsoleLoading] = useState(false);
  const [showAgentStore, setShowAgentStore] = useState(false);
  const [providerFilter, setProviderFilter] = useState<'all' | 'online' | 'offline'>('all');
  const [ollamaStatus, setOllamaStatus] = useState<'checking' | 'online' | 'offline'>('checking');
  const [ollamaModels, setOllamaModels] = useState<string[]>([]);
  const [ollamaProcesses, setOllamaProcesses] = useState<Array<{name: string; size: number; vram: number}>>([]);
  const [selectedMDFile, setSelectedMDFile] = useState<MDFile | null>(null);
  const [mdContent, setMdContent] = useState('');
  const [mdFileExists, setMdFileExists] = useState(true);
  const [newTaskText, setNewTaskText] = useState('');
  const [newTaskPriority, setNewTaskPriority] = useState<'high' | 'medium' | 'low'>('medium');
  const [newTaskCategory, setNewTaskCategory] = useState<'code' | 'general'>('general');
  const [installedModels, setInstalledModels] = useState<OllamaModel[]>([]);
  const [newModelName, setNewModelName] = useState('');
  const [isPulling, setIsPulling] = useState(false);
  const [patches, setPatches] = useState<PatchInfo[]>([]);
  const [patchStats, setPatchStats] = useState<any>({total: 0, applied: 0, pending: 0, errors: 0, backups_count: 0});
  const [selectedPatch, setSelectedPatch] = useState<PatchInfo | null>(null);
  const [patchPreview, setPatchPreview] = useState<any>(null);
  const [applyingPatch, setApplyingPatch] = useState(false);
  const [patchFilter, setPatchFilter] = useState<'all' | 'pending' | 'applied' | 'errors'>('all');
  const [patchLog, setPatchLog] = useState<string[]>([]);
  const [projectFiles, setProjectFiles] = useState<ProjectFile[]>([]);
  const [projectStats, setProjectStats] = useState<ProjectStats | null>(null);
  const [projectLoading, setProjectLoading] = useState(false);
  const [projectFilter, setProjectFilter] = useState<string>('all');
  const [projectSearch, setProjectSearch] = useState('');
  const [projectDuplicatesOnly, setProjectDuplicatesOnly] = useState(false);
  const [cleanupMode, setCleanupMode] = useState(false);
  const [restarting, setRestarting] = useState(false);
  const [projectImportantOnly, setProjectImportantOnly] = useState(false);
  const [selectedProjectFile, setSelectedProjectFile] = useState<ProjectFile | null>(null);
  const [projectFileContent, setProjectFileContent] = useState('');
  const [projectFileLoading, setProjectFileLoading] = useState(false);
  const [showPreviewModal, setShowPreviewModal] = useState(false);
  
  // ===== НОВОЕ: Переключатели видимости категорий =====
  const [showCritical, setShowCritical] = useState(false);
  const [showImportant, setShowImportant] = useState(true);
  const [showTrash, setShowTrash] = useState(true);
  const [showDuplicates, setShowDuplicates] = useState(true);

  useEffect(() => { const timer = setInterval(() => setCurrentTime(new Date()), 1000); return () => clearInterval(timer); }, []);

  const checkOllama = async () => {
    try {
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 3000);
      const res = await fetch(`${ollamaUrl}/api/tags`, { signal: controller.signal });
      clearTimeout(timeout);
      if (res.ok) {
        const data = await res.json();
        setOllamaStatus('online');
        setOllamaModels(data.models?.map((m: any) => m.name) || []);
        setProviders(prev => prev.map(p => p.name === 'Ollama' ? { ...p, status: 'online', models: data.models?.length || 0 } : p));
      } else { throw new Error('Not OK'); }
    } catch {
      setOllamaStatus('offline');
      setOllamaModels([]);
      setOllamaProcesses([]);
      setProviders(prev => prev.map(p => p.name === 'Ollama' ? { ...p, status: 'offline', models: 0 } : p));
      return;
    }
    try {
      const res = await fetch(`${ollamaUrl}/api/ps`);
      if (res.ok) {
        const data = await res.json();
        const processes = (data.models || []).map((m: any) => ({ name: m.name || m.model || 'unknown', size: Math.round((m.size || 0) / 1024 / 1024), vram: Math.round((m.size_vram || 0) / 1024 / 1024) }));
        setOllamaProcesses(processes);
      }
    } catch { setOllamaProcesses([]); }
  };

  const loadInstalledModels = async () => { try { const res = await fetch('/api/ollama/models'); const data = await res.json(); if (data.success) setInstalledModels(data.models); } catch (e) { console.error(e); } };
  const runAiTask = async () => {
    if (!consolePrompt.trim()) return;
    setConsoleLoading(true);
    setLogs(prev => [...prev, { time: new Date().toLocaleTimeString('ru-RU'), level: 'info', message: `Отправка задачи (режим: ${providerMode})...`, source: 'Console' }]);
    try {
      const res = await fetch('/api/task', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ prompt: consolePrompt, mode: providerMode }) });
      const data = await res.json();
      if (data.success) { setConsolePrompt(prev => prev + '\n\n--- ✅ РЕЗУЛЬТАТ ---\n' + data.result); setLogs(prev => [...prev, { time: new Date().toLocaleTimeString('ru-RU'), level: 'success', message: 'Задача выполнена', source: 'Python Core' }]); }
      else { setConsolePrompt(prev => prev + '\n\n--- ❌ ОШИБКА ---\n' + (data.error || 'Неизвестная ошибка')); setLogs(prev => [...prev, { time: new Date().toLocaleTimeString('ru-RU'), level: 'error', message: `Ошибка ИИ: ${data.error}`, source: 'Python Core' }]); }
    } catch (e) { setConsolePrompt(prev => prev + '\n\n--- ❌ ОШИБКА СЕТИ ---'); setLogs(prev => [...prev, { time: new Date().toLocaleTimeString('ru-RU'), level: 'error', message: 'Ошибка сети', source: 'React' }]); }
    finally { setConsoleLoading(false); }
  };
  const pullModel = async () => {
    if (!newModelName.trim()) return;
    setIsPulling(true);
    try {
      const res = await fetch('/api/ollama/pull', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name: newModelName }) });
      const data = await res.json();
      if (data.success) { alert(data.message); setNewModelName(''); loadInstalledModels(); checkOllama(); } else { alert('Ошибка: ' + data.error); }
    } catch (e) { alert('Ошибка сети'); } finally { setIsPulling(false); }
  };
  const fetchBackendLogs = async () => {
    try {
      const res = await fetch('/api/logs');
      if (res.ok) {
        const data = await res.json();
        if (data.logs && data.logs.length > 0) {
          setLogs(prev => {
            const newLogs = data.logs.map((bl: any) => ({ time: bl.time, level: (bl.level === 'success' ? 'success' : bl.level === 'error' ? 'error' : bl.level === 'warn' ? 'warn' : 'info') as LogEntry['level'], message: bl.message, source: bl.source || 'Core' })).filter((backendLog: LogEntry) => !prev.some(localLog => localLog.time === backendLog.time && localLog.message === backendLog.message));
            return [...prev, ...newLogs];
          });
        }
      }
    } catch (e) {}
  };
  const loadRealMDFile = async (file: MDFile) => {
    setSelectedMDFile(file);
    setMdFileExists(true);
    try {
      const res = await fetch(`/api/md/${encodeURIComponent(file.name)}`);
      const data = await res.json();
      if (data.error) { setMdFileExists(false); setMdContent(''); } else { setMdContent(data.content || ''); }
    } catch (e) { setMdFileExists(false); setMdContent(''); }
  };
  const saveRealMDFile = async () => {
    if (!selectedMDFile) return;
    try {
      const res = await fetch(`/api/md/${encodeURIComponent(selectedMDFile.name)}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ content: mdContent }) });
      const data = await res.json();
      if (data.success) { setMdFileExists(true); alert('Файл сохранён!'); } else { alert('Ошибка: ' + data.error); }
    } catch (e) { alert('Ошибка сети'); }
  };
  const loadPatches = async () => { try { const [listRes, statsRes] = await Promise.all([fetch('/api/patches/list'), fetch('/api/patches/stats')]); const listData = await listRes.json(); const statsData = await statsRes.json(); if (listData.success) setPatches(listData.patches); if (statsData.success) setPatchStats(statsData.stats); } catch (e) { console.error(e); } };
  const previewPatch = async (patch: PatchInfo) => {
    setSelectedPatch(patch);
    setPatchPreview(null);
    try {
      const res = await fetch('/api/patches/preview', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({
          patch_id: patch.patch_id,
          type: patch.patch_type,
          target_file: patch.target_file,
          full_file_content: (patch as any).full_file_content || '',
          diff: (patch as any).diff || '',
          filename: patch.filename
        }) });
      const data = await res.json();
      setPatchPreview(data);
    } catch (e) { setPatchPreview({success: false, error: 'Ошибка сети'}); }
  };
  const applyPatch = async (patch: PatchInfo) => {
    if (!confirm(`Применить патч ${patch.patch_id}?`)) return;
    setApplyingPatch(true);
    try {
      const res = await fetch('/api/patches/apply', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({
          patch_id: patch.patch_id,
          type: patch.patch_type,
          target_file: patch.target_file,
          full_file_content: (patch as any).full_file_content || '',
          diff: (patch as any).diff || '',
          filename: patch.filename
        }) });
      const data = await res.json();
      if (data.success) { setPatchLog(prev => [...prev, `[${new Date().toLocaleTimeString()}] ✅ ${data.message}`]); alert(data.message + '\nСписок патчей обновлен.'); loadPatches(); } else { alert('Ошибка: ' + data.error); }
    } catch (e) { alert('Ошибка сети'); } finally { setApplyingPatch(false); }
  };
  const rollbackLastPatch = async () => {
    if (!confirm('Откатить последний патч?')) return;
    try {
      const res = await fetch('/api/patches/rollback', {method: 'POST'});
      const data = await res.json();
      if (data.success) { alert(data.message + '\nСписок патчей обновлен.'); loadPatches(); } else { alert('Ошибка: ' + data.error); }
    } catch (e) { alert('Ошибка сети'); }
  };
  const archivePatch = async (filename: string) => { try { const res = await fetch('/api/patches/archive', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({filename}) }); const data = await res.json(); if (data.success) { loadPatches(); setPatchLog(prev => [...prev, `[${new Date().toLocaleTimeString()}] 📦 ${data.message}`]); } } catch (e) { alert('Ошибка сети'); } };
  const deletePatch = async (filename: string) => { if (!confirm(`Удалить ${filename}?`)) return; try { const res = await fetch('/api/patches/delete', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({filename}) }); const data = await res.json(); if (data.success) { loadPatches(); setPatchLog(prev => [...prev, `[${new Date().toLocaleTimeString()}] 🗑 ${data.message}`]); } } catch (e) { alert('Ошибка сети'); } };
  const applyAllPending = async () => { if (!confirm(`Применить все патчи (${patchStats.pending} шт.)?`)) return; setApplyingPatch(true); try { const res = await fetch('/api/patches/apply-all', {method: 'POST'}); const data = await res.json(); if (data.success) { alert(`Применено: ${data.results.filter((r: any) => r.success).length}\nСписок патчей обновлен.`); loadPatches(); } } catch (e) { alert('Ошибка сети'); } finally { setApplyingPatch(false); } };

  
  const restartSystem = async () => {
    if (!confirm('Перезапустить всю систему?\n\nPython и React будут перезапущены автоматически.')) return;
    setRestarting(true);
    try {
      const res = await fetch('/api/system/restart', { method: 'POST' });
      const data = await res.json();
      if (data.success) { alert(data.message); setTimeout(() => window.location.reload(), 8000); }
      else { alert('Ошибка: ' + data.error); }
    } catch (e) { alert('Ошибка сети. Система, возможно, перезапускается...'); setTimeout(() => window.location.reload(), 8000); }
    finally { setRestarting(false); }
  };

  
  const applyCleanup = async () => {
    const toDelete = projectFiles.filter(f => f.cleanup?.action === 'delete');
    if (toDelete.length === 0) { alert('Нечего очищать'); return; }
    if (!confirm(`Переместить ${toDelete.length} файлов в архив?`)) return;
    
    let successCount = 0;
    for (const file of toDelete) {
      try {
        const res = await fetch('/api/project/archive', { 
          method: 'POST', 
          headers: { 'Content-Type': 'application/json' }, 
          body: JSON.stringify({ path: file.path }) 
        });
        const data = await res.json();
        if (data.success) successCount++;
      } catch (e) { console.error(e); }
    }
    alert(`Очищено: ${successCount} из ${toDelete.length} файлов`);
    setCleanupMode(false);
    scanProject();
  };

  const scanProject = async () => {
    setProjectLoading(true);
    try {
      const res = await fetch('/api/project/scan');
      const data = await res.json();
      if (data.files) { setProjectFiles(data.files); setProjectStats(data.stats); }
    } catch (e) { console.error(e); } finally { setProjectLoading(false); }
  };
  const openProjectFilePreview = async (file: ProjectFile) => {
    setSelectedProjectFile(file);
    setProjectFileContent('');
    setProjectFileLoading(true);
    setShowPreviewModal(true);
    try {
      const res = await fetch(`/api/project/file?path=${encodeURIComponent(file.path)}`);
      const data = await res.json();
      if (data.success) { setProjectFileContent(data.content); } else { setProjectFileContent(`[Ошибка: ${data.error}]`); }
    } catch (e) { setProjectFileContent('[Ошибка сети]'); } finally { setProjectFileLoading(false); }
  };
  const archiveProjectFile = async (file: ProjectFile) => {
    if (file.is_critical) { alert('Нельзя архивировать критичный файл!'); return; }
    if (!confirm(`Архивировать ${file.path}?`)) return;
    try {
      const res = await fetch('/api/project/archive', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({path: file.path}) });
      const data = await res.json();
      if (data.success) { alert(data.message); scanProject(); } else { alert('Ошибка: ' + data.error); }
    } catch (e) { alert('Ошибка сети'); }
  };
  const deleteProjectFile = async (file: ProjectFile) => {
    if (file.is_critical) { alert('Нельзя удалять критичный файл!'); return; }
    if (!confirm(`УДАЛИТЬ ${file.path}?`)) return;
    try {
      const res = await fetch('/api/project/delete', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({path: file.path}) });
      const data = await res.json();
      if (data.success) { alert(data.message); scanProject(); } else { alert('Ошибка: ' + data.error); }
    } catch (e) { alert('Ошибка сети'); }
  };
  const toggleImportant = async (file: ProjectFile) => { try { const res = await fetch('/api/project/important', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({path: file.path, action: 'toggle'}) }); const data = await res.json(); if (data.success) { scanProject(); } } catch (e) { console.error(e); } };

  const getCategoryColor = (cat: string) => {
    const colors: Record<string, string> = { critical: 'bg-red-500/20 text-red-400 border-red-500/30', code: 'bg-blue-500/20 text-blue-400 border-blue-500/30', config: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30', docs: 'bg-purple-500/20 text-purple-400 border-purple-500/30', backup: 'bg-gray-500/20 text-gray-400 border-gray-500/30', archive: 'bg-indigo-500/20 text-indigo-400 border-indigo-500/30', trash: 'bg-orange-500/20 text-orange-400 border-orange-500/30', logs: 'bg-cyan-500/20 text-cyan-400 border-cyan-500/30', scripts: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30', web: 'bg-pink-500/20 text-pink-400 border-pink-500/30', other: 'bg-gray-700/20 text-gray-400 border-gray-600', error: 'bg-red-500/20 text-red-400 border-red-500/30' };
    return colors[cat] || colors.other;
  };
  const getCategoryLabel = (cat: string) => {
    const labels: Record<string, string> = { critical: '🔴 Критичный', code: '💻 Код', config: '⚙️ Конфиг', docs: '📝 Документация', backup: '💾 Бэкап', archive: '📦 Архив', trash: '🗑 Мусор', logs: '📃 Логи', scripts: '⚙️ Скрипт', web: '🌐 Web', other: '📄 Другое', error: '❌ Ошибка' };
    return labels[cat] || cat;
  };

  useEffect(() => {
    checkOllama();
    loadInstalledModels();
    fetchBackendLogs();
    loadPatches();
    scanProject();
    const ollamaInterval = setInterval(checkOllama, 5000);
    const logInterval = setInterval(fetchBackendLogs, 3000);
    const modelsInterval = setInterval(loadInstalledModels, 10000);
    const patchesInterval = setInterval(loadPatches, 5000);
    return () => { clearInterval(ollamaInterval); clearInterval(logInterval); clearInterval(modelsInterval); clearInterval(patchesInterval); };
  }, [ollamaUrl]);

  const totalRam = ollamaProcesses.reduce((s, m) => s + m.size, 0);
  const totalVram = ollamaProcesses.reduce((s, m) => s + m.vram, 0);
  const toggleTask = (id: number) => setTaskList(prev => prev.map(t => t.id === id ? { ...t, done: !t.done } : t));
  const toggleAgent = (id: number) => setAgents(prev => prev.map(a => a.id === id ? { ...a, enabled: !a.enabled, status: !a.enabled ? 'active' : 'frozen' } : a));
  const toggleProvider = (name: string) => setProviders(prev => prev.map(p => p.name === name ? { ...p, enabled: !p.enabled } : p));
  const addTask = () => { if (!newTaskText.trim()) return; setTaskList(prev => [...prev, { id: prev.length + 1, text: newTaskText, done: false, priority: newTaskPriority, category: newTaskCategory }]); setNewTaskText(''); };
  const deleteTask = (id: number) => setTaskList(prev => prev.filter(t => t.id !== id));
  const importAgent = (agentId: string) => { const sa = agentStore.find(a => a.id === agentId); if (sa) { setAgents(prev => [...prev, { id: prev.length + 1, name: sa.name, status: 'frozen', task: 'Готов к активации', stack: sa.stack, progress: 0, lastActivity: 'Только что', enabled: false, description: sa.description }]); setShowAgentStore(false); } };
  const fixCodeIssue = (issueId: number) => {
    const issue = codeIssues.find(i => i.id === issueId);
    if (!issue || issue.fixed) return;
    const fixLog = [`═══════════════════════════════════════`, `⚠️ Реальное исправление через PatchMaster`, `═══════════════════════════════════════`, ``, `1️⃣  Файл: ${issue.file}`, `2️⃣  Тройной бэкап`, `3️⃣  Замена в строке ${issue.line}`, `4️⃣  Валидация`, `5️⃣  Атомарная замена`, ``, `🔧 КАК ВЫПОЛНИТЬ:`, `Шаг 1: Попросите ИИ сгенерировать патч`, `Шаг 2: Сохраните JSON в patch/`, `Шаг 3: Откройте вкладку "🔄 Патчи"`, `Шаг 4: Нажмите "✅ Применить"`, ``, `═══════════════════════════════════════`];
    setCodeIssues(prev => prev.map(i => i.id === issueId ? { ...i, fixed: true, fixLog } : i));
  };
  const completedTasks = taskList.filter(t => t.done).length;
  const codeTasks = taskList.filter(t => t.category === 'code');
  const generalTasks = taskList.filter(t => t.category === 'general');

  const tabs = [
    { id: 'console' as const, label: 'Консоль', icon: '▶', tooltip: 'Отправка запросов к LLM' },
    { id: 'panel' as const, label: 'Панель', icon: '◈', tooltip: 'Общая статистика системы' },
    { id: 'project' as const, label: 'Проект', icon: '🗂', tooltip: 'Анализ и очистка файлов' },
    { id: 'agents' as const, label: 'Агенты', icon: '🤖', tooltip: 'Управление AI-агентами' },
    { id: 'providers' as const, label: 'Провайдеры', icon: '🌐', tooltip: 'Настройка LLM провайдеров' },
    { id: 'models' as const, label: 'Модели', icon: '🧠', tooltip: 'Управление моделями Ollama' },
    { id: 'md' as const, label: 'MD', icon: '📝', tooltip: 'Редактор документации' },
    { id: 'code' as const, label: 'Код', icon: '⟨⟩', badge: codeIssues.filter(i => !i.fixed).length, tooltip: 'Анализ и исправление ошибок' },
    { id: 'patches' as const, label: 'Патчи', icon: '🔄', badge: patchStats.pending, tooltip: 'Система автопатчей' },
    { id: 'logs' as const, label: 'Логи', icon: '▤', tooltip: 'Системные события' },
    { id: 'tasks' as const, label: 'Задачи', icon: '☑', tooltip: 'Список задач' },
  ];

  // ===== НОВОЕ: Фильтрация с учётом переключателей =====
  const filteredProjectFiles = projectFiles.filter(f => {
    if (projectFilter !== 'all' && f.category !== projectFilter) return false;
    if (projectSearch && !f.filename.toLowerCase().includes(projectSearch.toLowerCase()) && !f.path.toLowerCase().includes(projectSearch.toLowerCase())) return false;
    if (projectDuplicatesOnly && !f.is_duplicate) return false;
    if (projectImportantOnly && !f.is_important) return false;
    if (!showCritical && f.is_critical) return false;
    if (!showImportant && f.is_important) return false;
    if (!showTrash && f.category === 'trash') return false;
    if (!showDuplicates && f.is_duplicate) return false;
    return true;
  });

  return (
    <div className="min-h-screen bg-gray-950 text-white flex flex-col text-base">
      <header className="bg-gray-900/90 backdrop-blur-sm border-b border-gray-800 sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 py-3">
          <div className="flex items-center justify-between gap-4">
            <Tooltip text={ollamaStatus === 'online' ? `✅ Ollama онлайн • ${ollamaModels.length} моделей` : '❌ Ollama не запущен'} position="bottom">
              <div className="flex items-center gap-3 cursor-pointer">
                <div className="w-12 h-12 rounded-lg bg-gradient-to-br from-emerald-500 via-cyan-500 to-blue-500 flex items-center justify-center font-bold text-sm shadow-lg shadow-emerald-500/30">AI</div>
                <div>
                  <h1 className="text-lg font-bold gradient-text leading-tight">drmAIcu</h1>
                  <p className="text-xs text-gray-500 leading-tight">v.3.4.3 TOGGLES</p>
                </div>
              </div>
            </Tooltip>
            <div className="flex items-center gap-3 flex-1 justify-center">
              <Tooltip text={`${agents.filter(a => a.enabled).length} агентов`} position="bottom">
                <button onClick={() => setActiveTab('agents')} className="flex items-center gap-2 px-4 py-2 rounded-lg bg-gray-800/50 border border-gray-700/50 hover:border-emerald-500/50 transition-all">
                  <span className="text-xl">🤖</span>
                  <div className="text-left">
                    <div className="flex items-baseline gap-1"><span className="font-bold text-emerald-400 text-lg">{agents.filter(a => a.enabled).length}</span><span className="text-gray-500 text-sm">/{agents.length}</span></div>
                    <p className="text-[10px] text-gray-500">Агенты</p>
                  </div>
                </button>
              </Tooltip>
              <Tooltip text={`${providers.filter(p => p.status === 'online').length} провайдеров`} position="bottom">
                <button onClick={() => setActiveTab('providers')} className="flex items-center gap-2 px-4 py-2 rounded-lg bg-gray-800/50 border border-gray-700/50 hover:border-cyan-500/50 transition-all">
                  <span className="text-xl">🌐</span>
                  <div className="text-left">
                    <div className="flex items-baseline gap-1"><span className="font-bold text-cyan-400 text-lg">{providers.filter(p => p.status === 'online').length}</span><span className="text-gray-500 text-sm">/{providers.length}</span></div>
                    <p className="text-[10px] text-gray-500">Провайдеры</p>
                  </div>
                </button>
              </Tooltip>
              <Tooltip text={`${projectStats?.total || 0} файлов`} position="bottom">
                <button onClick={() => setActiveTab('project')} className="flex items-center gap-2 px-4 py-2 rounded-lg bg-gray-800/50 border border-gray-700/50 hover:border-orange-500/50 transition-all">
                  <span className="text-xl">🗂</span>
                  <div className="text-left">
                    <div className="flex items-baseline gap-1"><span className="font-bold text-orange-400 text-lg">{projectStats?.total || 0}</span></div>
                    <p className="text-[10px] text-gray-500">Файлов</p>
                  </div>
                </button>
              </Tooltip>
              <Tooltip text={`${installedModels.length} моделей`} position="bottom">
                <button onClick={() => setActiveTab('models')} className="flex items-center gap-2 px-4 py-2 rounded-lg bg-gray-800/50 border border-gray-700/50 hover:border-purple-500/50 transition-all">
                  <span className="text-xl">🧠</span>
                  <div className="text-left">
                    <div className="flex items-baseline gap-1"><span className="font-bold text-purple-400 text-lg">{installedModels.length}</span></div>
                    <p className="text-[10px] text-gray-500">Модели</p>
                  </div>
                </button>
              </Tooltip>
              <Tooltip text={`${patchStats.pending || 0} патчей`} position="bottom">
                <button onClick={() => setActiveTab('patches')} className="flex items-center gap-2 px-4 py-2 rounded-lg bg-gray-800/50 border border-gray-700/50 hover:border-yellow-500/50 transition-all">
                  <span className="text-xl">🔄</span>
                  <div className="text-left">
                    <div className="flex items-baseline gap-1"><span className="font-bold text-yellow-400 text-lg">{patchStats.pending || 0}</span></div>
                    <p className="text-[10px] text-gray-500">Патчи</p>
                  </div>
                </button>
              </Tooltip>
              <Tooltip text={`${codeIssues.filter(i => !i.fixed).length} ошибок`} position="bottom">
                <button onClick={() => setActiveTab('code')} className="flex items-center gap-2 px-4 py-2 rounded-lg bg-gray-800/50 border border-gray-700/50 hover:border-red-500/50 transition-all">
                  <span className="text-xl">⟨⟩</span>
                  <div className="text-left">
                    <span className="font-bold text-red-400 text-lg">{codeIssues.filter(i => !i.fixed).length}</span>
                    <p className="text-[10px] text-gray-500">Код</p>
                  </div>
                </button>
              </Tooltip>
              <Tooltip text={`${completedTasks}/${taskList.length} задач`} position="bottom">
                <button onClick={() => setActiveTab('tasks')} className="flex items-center gap-2 px-4 py-2 rounded-lg bg-gray-800/50 border border-gray-700/50 hover:border-yellow-500/50 transition-all">
                  <span className="text-xl">☑</span>
                  <div className="text-left">
                    <div className="flex items-baseline gap-1"><span className="font-bold text-yellow-400 text-lg">{completedTasks}</span><span className="text-gray-500 text-sm">/{taskList.length}</span></div>
                    <p className="text-[10px] text-gray-500">Задачи</p>
                  </div>
                </button>
              </Tooltip>
            </div>
            <div className="flex items-center gap-3">
              <Tooltip text={ollamaProcesses.length > 0 ? ollamaProcesses.map(m => `${m.name}: ${m.size}MB RAM`).join('\n') : 'Нет моделей'} position="bottom">
                <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-gray-800/50 border border-gray-700/50">
                  <span className="text-xs text-gray-500">RAM:</span>
                  <span className={`font-mono font-bold text-sm ${totalRam > 0 ? 'text-emerald-400' : 'text-gray-600'}`}>{totalRam}MB</span>
                  <span className="text-gray-600">|</span>
                  <span className="text-xs text-gray-500">VRAM:</span>
                  <span className={`font-mono font-bold text-sm ${totalVram > 0 ? 'text-cyan-400' : 'text-gray-600'}`}>{totalVram}MB</span>
                </div>
              </Tooltip>
              <div className="px-4 py-2 rounded-lg bg-gray-800/50 border-2 border-emerald-500/30">
                <span className="font-mono text-lg text-emerald-400 tabular-nums font-bold">{currentTime.toLocaleTimeString('ru-RU')}</span>
              </div>
              <Tooltip text="Перезапустить Python и React" position="bottom">
                <button onClick={restartSystem} disabled={restarting} className={`px-4 py-2 rounded-lg text-sm font-bold transition-all ${restarting ? 'bg-gray-700 text-gray-500 cursor-not-allowed' : 'bg-orange-500/20 border border-orange-500/50 text-orange-400 hover:bg-orange-500/30'}`}>
                  {restarting ? '⏳ Перезапуск...' : '🔄 Перезапуск'}
                </button>
              </Tooltip>
            </div>
          </div>
        </div>
        <div className="max-w-7xl mx-auto px-4 flex items-center gap-2 overflow-x-auto border-t border-gray-800">
          {tabs.map((tab) => (
            <Tooltip key={tab.id} text={tab.tooltip} position="bottom">
              <button onClick={() => setActiveTab(tab.id)} className={`px-4 py-3 text-sm font-medium border-b-2 transition-all whitespace-nowrap flex items-center gap-2 ${activeTab === tab.id ? 'border-emerald-500 text-emerald-400' : 'border-transparent text-gray-500 hover:text-gray-300'}`}>
                <span className="text-base">{tab.icon}</span>
                <span>{tab.label}</span>
                {tab.badge ? <span className="px-1.5 py-0.5 rounded-full bg-red-500/20 text-red-400 text-xs font-bold">{tab.badge}</span> : null}
              </button>
            </Tooltip>
          ))}
        </div>
      </header>

      <main className="flex-1 max-w-7xl mx-auto px-4 py-6 w-full">
        {activeTab === 'console' && (
          <div className="space-y-6">
            <div className="rounded-xl border border-gray-700 bg-gradient-to-br from-gray-900/80 to-gray-800/50 p-6">
              <label className="text-sm font-bold text-gray-300 uppercase tracking-wider mb-3 block">Провайдеры</label>
              <div className="flex gap-3 mb-4">
                <button onClick={() => setProviderMode('ollama')} className={`flex-1 px-4 py-3 rounded-lg text-sm font-medium transition-all border-2 ${providerMode === 'ollama' ? 'bg-emerald-500/20 border-emerald-500/50 text-emerald-400' : 'bg-gray-800/50 border-gray-700 text-gray-400'}`}>🏠 Ollama</button>
                <button onClick={() => setProviderMode('groq')} className={`flex-1 px-4 py-3 rounded-lg text-sm font-medium transition-all border-2 ${providerMode === 'groq' ? 'bg-cyan-500/20 border-cyan-500/50 text-cyan-400' : 'bg-gray-800/50 border-gray-700 text-gray-400'}`}>☁️ Groq</button>
                <button onClick={() => setProviderMode('all')} className={`flex-1 px-4 py-3 rounded-lg text-sm font-medium transition-all border-2 ${providerMode === 'all' ? 'bg-purple-500/20 border-purple-500/50 text-purple-400' : 'bg-gray-800/50 border-gray-700 text-gray-400'}`}>⚡ Все</button>
              </div>
              {(providerMode === 'ollama' || providerMode === 'all') && <input type="text" value={ollamaUrl} onChange={(e) => setOllamaUrl(e.target.value)} className="w-full px-4 py-3 rounded-lg bg-gray-800 border border-gray-700 text-white text-sm font-mono focus:border-emerald-500 focus:outline-none" />}
            </div>
            <div className="rounded-xl border border-gray-700 bg-gradient-to-br from-gray-900/80 to-gray-800/50 p-6">
              <textarea value={consolePrompt} onChange={(e) => setConsolePrompt(e.target.value)} onKeyDown={(e) => { if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) { e.preventDefault(); runAiTask(); } }} placeholder="Опиши задачу... (Ctrl+Enter)" rows={8} className="w-full px-4 py-3 rounded-lg bg-gray-800/80 border border-gray-700 text-white text-sm focus:border-emerald-500 focus:outline-none resize-none font-mono" />
              <div className="flex justify-end mt-4 gap-3">
                <button onClick={() => setConsolePrompt('')} className="px-4 py-3 rounded-lg font-bold text-sm bg-gray-700 hover:bg-gray-600 text-gray-300">🗑 Очистить</button>
                <button onClick={runAiTask} disabled={consoleLoading || !consolePrompt.trim()} className={`px-8 py-3 rounded-lg font-bold text-base transition-all ${consoleLoading ? 'bg-gray-700 text-gray-500 cursor-not-allowed' : 'bg-gradient-to-r from-emerald-500 to-cyan-500 hover:from-emerald-600 hover:to-cyan-600 text-white shadow-lg shadow-emerald-500/20'}`}>{consoleLoading ? '⏳ Отправка...' : '▶ Отправить (Ctrl+Enter)'}</button>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'panel' && (
          <div className="space-y-6">
            <h2 className="text-2xl font-bold">Панель управления</h2>
            <div className="grid md:grid-cols-2 gap-6">
              <div className="rounded-xl border border-gray-700 bg-gray-900/50 p-6">
                <h3 className="text-lg font-bold mb-4 flex items-center gap-2"><span>🤖</span> Агенты</h3>
                <div className="space-y-2">{agents.map(a => (<div key={a.id} className="flex justify-between items-center text-sm"><span className={a.enabled ? 'text-emerald-400' : 'text-gray-500'}>{a.name}</span><StatusBadge status={a.status} /></div>))}</div>
              </div>
              <div className="rounded-xl border border-gray-700 bg-gray-900/50 p-6">
                <h3 className="text-lg font-bold mb-4 flex items-center gap-2"><span>🌐</span> Провайдеры</h3>
                <div className="space-y-2">{providers.map(p => (<div key={p.name} className="flex justify-between items-center text-sm"><span className={p.enabled ? 'text-white' : 'text-gray-500'}>{p.name}</span><StatusBadge status={p.status} /></div>))}</div>
              </div>
            </div>
            <div className="grid md:grid-cols-2 gap-6">
              <div className="rounded-xl border border-gray-700 bg-gray-900/50 p-6">
                <h3 className="text-lg font-bold mb-4 flex items-center gap-2"><span>🧠</span> Модели Ollama</h3>
                <div className="space-y-2">{installedModels.length === 0 ? <p className="text-gray-500 text-sm">Нет моделей</p> : installedModels.map((m, idx) => (<div key={idx} className="flex justify-between items-center text-sm"><span className="font-mono text-emerald-400">{m.name}</span><span className="text-gray-500">{m.size_gb} GB</span></div>))}</div>
              </div>
              <div className="rounded-xl border border-gray-700 bg-gray-900/50 p-6">
                <h3 className="text-lg font-bold mb-4 flex items-center gap-2"><span>🔄</span> Патчи</h3>
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between"><span className="text-gray-400">Всего:</span><span className="font-bold text-white">{patchStats.total || 0}</span></div>
                  <div className="flex justify-between"><span className="text-gray-400">Применено:</span><span className="font-bold text-emerald-400">{patchStats.applied || 0}</span></div>
                  <div className="flex justify-between"><span className="text-gray-400">Ожидают:</span><span className="font-bold text-yellow-400">{patchStats.pending || 0}</span></div>
                  <div className="flex justify-between"><span className="text-gray-400">Бэкапов:</span><span className="font-bold text-blue-400">{patchStats.backups_count || 0}</span></div>
                </div>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'project' && (
          <div className="space-y-6">
            <div className="flex justify-between items-center">
              <div>
                <h2 className="text-2xl font-bold">🗂 Управление проектом</h2>
                <p className="text-sm text-gray-400 mt-1">Анализ файлов, поиск дубликатов, архивирование мусора</p>
              </div>
              <div className="flex gap-2">
                <button onClick={() => setCleanupMode(!cleanupMode)} className={`px-4 py-2 rounded-lg text-sm font-bold transition-all ${cleanupMode ? 'bg-red-500 text-white' : 'bg-gray-700 text-gray-300 hover:bg-gray-600'}`}>
                  {cleanupMode ? '❌ Отмена' : '🧹 Режим очистки'}
                </button>
                {cleanupMode && projectStats?.cleanup_delete_count > 0 && (
                  <button onClick={applyCleanup} className="px-4 py-2 rounded-lg bg-red-600 hover:bg-red-700 text-white text-sm font-bold animate-pulse">
                    🗑 Удалить {projectStats.cleanup_delete_count} файлов
                  </button>
                )}
                <button onClick={scanProject} disabled={projectLoading} className="px-4 py-2 rounded-lg bg-gradient-to-r from-emerald-500 to-cyan-500 text-white text-sm font-bold disabled:opacity-50">
                  {projectLoading ? '⏳ Сканирование...' : '🔄 Пересканировать'}
                </button>
              </div>
            </div>

            {projectStats && (
              <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
                <div className="rounded-xl border border-gray-700 bg-gray-900/50 p-4">
                  <div className="text-xs text-gray-500">Всего файлов</div>
                  <div className="text-2xl font-bold text-white">{projectStats.total}</div>
                  <div className="text-xs text-gray-500 mt-1">{projectStats.total_size_human}</div>
                </div>
                <div className={`rounded-xl border p-4 transition-all ${showCritical ? 'border-red-500/50 bg-red-500/10' : 'border-gray-700 bg-gray-900/50 opacity-60'}`}>
                  <div className="flex items-center justify-between mb-2">
                    <div className="text-xs text-red-400">🔴 Критичные</div>
                    <button onClick={() => setShowCritical(!showCritical)} className={`w-10 h-5 rounded-full transition-all relative ${showCritical ? 'bg-red-500' : 'bg-gray-700'}`}>
                      <div className="w-4 h-4 rounded-full bg-white absolute top-0.5 transition-all" style={{ left: showCritical ? '22px' : '2px' }} />
                    </button>
                  </div>
                  <div className="text-2xl font-bold text-red-400">{projectStats.critical_count}</div>
                  <div className="text-xs text-gray-500 mt-1">{showCritical ? 'Показаны' : 'Скрыты'}</div>
                </div>
                <div className={`rounded-xl border p-4 transition-all ${showImportant ? 'border-yellow-500/50 bg-yellow-500/10' : 'border-gray-700 bg-gray-900/50 opacity-60'}`}>
                  <div className="flex items-center justify-between mb-2">
                    <div className="text-xs text-yellow-400">⭐ Важные</div>
                    <button onClick={() => setShowImportant(!showImportant)} className={`w-10 h-5 rounded-full transition-all relative ${showImportant ? 'bg-yellow-500' : 'bg-gray-700'}`}>
                      <div className="w-4 h-4 rounded-full bg-white absolute top-0.5 transition-all" style={{ left: showImportant ? '22px' : '2px' }} />
                    </button>
                  </div>
                  <div className="text-2xl font-bold text-yellow-400">{projectStats.important_count}</div>
                  <div className="text-xs text-gray-500 mt-1">{showImportant ? 'Показаны' : 'Скрыты'}</div>
                </div>
                <div className={`rounded-xl border p-4 transition-all ${showTrash ? 'border-orange-500/50 bg-orange-500/10' : 'border-gray-700 bg-gray-900/50 opacity-60'}`}>
                  <div className="flex items-center justify-between mb-2">
                    <div className="text-xs text-orange-400">🗑 Мусор</div>
                    <button onClick={() => setShowTrash(!showTrash)} className={`w-10 h-5 rounded-full transition-all relative ${showTrash ? 'bg-orange-500' : 'bg-gray-700'}`}>
                      <div className="w-4 h-4 rounded-full bg-white absolute top-0.5 transition-all" style={{ left: showTrash ? '22px' : '2px' }} />
                    </button>
                  </div>
                  <div className="text-2xl font-bold text-orange-400">{projectStats.trash_count}</div>
                  <div className="text-xs text-gray-500 mt-1">{showTrash ? 'Показан' : 'Скрыт'}</div>
                </div>
                <div className={`rounded-xl border p-4 transition-all ${showDuplicates ? 'border-purple-500/50 bg-purple-500/10' : 'border-gray-700 bg-gray-900/50 opacity-60'}`}>
                  <div className="flex items-center justify-between mb-2">
                    <div className="text-xs text-purple-400">👯 Дубликаты</div>
                    <button onClick={() => setShowDuplicates(!showDuplicates)} className={`w-10 h-5 rounded-full transition-all relative ${showDuplicates ? 'bg-purple-500' : 'bg-gray-700'}`}>
                      <div className="w-4 h-4 rounded-full bg-white absolute top-0.5 transition-all" style={{ left: showDuplicates ? '22px' : '2px' }} />
                    </button>
                  </div>
                  <div className="text-2xl font-bold text-purple-400">{projectStats.duplicates_count}</div>
                  <div className="text-xs text-gray-500 mt-1">{showDuplicates ? 'Показаны' : 'Скрыты'}</div>
                </div>
              </div>
            )}

            <div className="rounded-xl border border-gray-700 bg-gray-900/50 p-4">
              <div className="flex flex-wrap gap-3 items-center">
                <input type="text" value={projectSearch} onChange={(e) => setProjectSearch(e.target.value)} placeholder="🔍 Поиск..." className="flex-1 min-w-[200px] px-4 py-2 rounded-lg bg-gray-800 border border-gray-700 text-white text-sm focus:border-emerald-500 focus:outline-none" />
                <div className="flex flex-wrap gap-2">
                  {(['all', 'critical', 'code', 'config', 'docs', 'backup', 'trash', 'other'] as const).map(f => (
                    <button key={f} onClick={() => setProjectFilter(f)} className={`px-3 py-2 rounded-lg text-xs font-bold transition-all ${projectFilter === f ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/50' : 'bg-gray-800 text-gray-400 border border-gray-700 hover:border-gray-600'}`}>
                      {f === 'all' ? '📋 Все' : getCategoryLabel(f)}
                    </button>
                  ))}
                </div>
                <label className="flex items-center gap-2 text-sm text-gray-400 cursor-pointer">
                  <input type="checkbox" checked={projectDuplicatesOnly} onChange={(e) => setProjectDuplicatesOnly(e.target.checked)} className="rounded" />
                  Только дубликаты
                </label>
                <label className="flex items-center gap-2 text-sm text-gray-400 cursor-pointer">
                  <input type="checkbox" checked={projectImportantOnly} onChange={(e) => setProjectImportantOnly(e.target.checked)} className="rounded" />
                  Только важные
                </label>
              </div>
              <div className="mt-3 text-xs text-gray-500">Показано: {filteredProjectFiles.length} из {projectFiles.length} файлов</div>
            </div>

            <div className="space-y-2">
              {filteredProjectFiles.map((file, idx) => (
                <div key={idx} className={`rounded-xl border p-4 transition-all ${file.is_critical ? 'border-red-500/30 bg-red-500/5' : file.is_duplicate ? 'border-purple-500/30 bg-purple-500/5' : file.category === 'trash' ? 'border-orange-500/30 bg-orange-500/5' : 'border-gray-700 bg-gray-900/50 hover:border-gray-600'}`}>
                  <div className="flex items-start gap-3">
                    <button onClick={() => openProjectFilePreview(file)} className="text-2xl hover:scale-110 transition-transform">{file.icon}</button>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="font-mono text-sm text-white font-bold truncate">{file.path}</span>
                        <span className={`px-2 py-0.5 rounded text-[10px] font-bold border ${getCategoryColor(file.category)}`}>{getCategoryLabel(file.category)}</span>
                        {file.is_critical && <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-red-500/20 text-red-400 border border-red-500/30">🔒 КРИТИЧНЫЙ</span>}
                        {file.is_important && <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-yellow-500/20 text-yellow-400 border border-yellow-500/30">⭐ ВАЖНЫЙ</span>}
                        {file.is_duplicate && <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-purple-500/20 text-purple-400 border border-purple-500/30">👯 ДУБЛИКАТ</span>}
                      </div>
                      <div className="flex gap-4 mt-1 text-xs text-gray-500 flex-wrap">
                        <span>📏 {file.size_human}</span>
                        <span>🕐 {new Date(file.modified).toLocaleString('ru-RU')}</span>
                        {file.is_duplicate && file.duplicates.length > 0 && <span className="text-purple-400">Дубли: {file.duplicates.join(', ')}</span>}
                      </div>
                      {file.cleanup && file.cleanup.action !== 'keep' && (
                        <div className={`mt-2 px-2 py-1 rounded text-[11px] font-bold flex items-center gap-1 ${
                          file.cleanup.action === 'delete' ? 'bg-red-500/20 text-red-400 border border-red-500/30' : 'bg-yellow-500/20 text-yellow-400 border border-yellow-500/30'
                        }`}>
                          <span>{file.cleanup.action === 'delete' ? '🗑 УДАЛИТЬ' : '⚠️ ПРОВЕРИТЬ'}</span>
                          <span className="font-normal opacity-80">— {file.cleanup.reason}</span>
                        </div>
                      )}
                    </div>
                    <div className="flex gap-2 shrink-0">
                      <button onClick={() => toggleImportant(file)} className={`px-3 py-1.5 rounded text-xs font-bold transition-all ${file.is_important ? 'bg-yellow-500/20 text-yellow-400 border border-yellow-500/50' : 'bg-gray-700 text-gray-400 border border-gray-600 hover:border-yellow-500/50'}`}>{file.is_important ? '⭐' : '☆'}</button>
                      <button onClick={() => openProjectFilePreview(file)} className="px-3 py-1.5 rounded bg-gray-700 hover:bg-gray-600 text-gray-300 text-xs font-bold">👁</button>
                      {!file.is_critical && (<><button onClick={() => archiveProjectFile(file)} className="px-3 py-1.5 rounded bg-blue-500/20 hover:bg-blue-500/30 text-blue-400 text-xs font-bold">📦</button><button onClick={() => deleteProjectFile(file)} className="px-3 py-1.5 rounded bg-red-500/20 hover:bg-red-500/30 text-red-400 text-xs font-bold">🗑</button></>)}
                    </div>
                  </div>
                </div>
              ))}
              {filteredProjectFiles.length === 0 && <div className="text-center py-12 text-gray-500 border-2 border-dashed border-gray-700 rounded-xl"><p className="text-lg mb-2">🔍 Ничего не найдено</p><p className="text-sm">Измени фильтры или включи переключатели выше</p></div>}
            </div>

            {showPreviewModal && selectedProjectFile && (
              <div className="fixed inset-0 bg-black/80 z-50 flex items-center justify-center p-4" onClick={() => setShowPreviewModal(false)}>
                <div className="bg-gray-900 border border-gray-700 rounded-xl p-6 max-w-5xl w-full max-h-[90vh] overflow-hidden flex flex-col" onClick={e => e.stopPropagation()}>
                  <div className="flex justify-between items-start mb-4">
                    <div>
                      <h3 className="text-xl font-bold flex items-center gap-2"><span>{selectedProjectFile.icon}</span><span className="font-mono">{selectedProjectFile.path}</span></h3>
                      <div className="flex gap-3 mt-2 text-xs text-gray-400"><span>{selectedProjectFile.size_human}</span><span>{getCategoryLabel(selectedProjectFile.category)}</span><span>{projectFileContent.split('\n').length} строк</span></div>
                    </div>
                    <div className="flex gap-2">
                      {!selectedProjectFile.is_critical && (<><button onClick={() => { archiveProjectFile(selectedProjectFile); setShowPreviewModal(false); }} className="px-3 py-1.5 rounded bg-blue-500/20 text-blue-400 text-xs font-bold hover:bg-blue-500/30">📦 Архив</button><button onClick={() => { deleteProjectFile(selectedProjectFile); setShowPreviewModal(false); }} className="px-3 py-1.5 rounded bg-red-500/20 text-red-400 text-xs font-bold hover:bg-red-500/30">🗑 Удалить</button></>)}
                      <button onClick={() => setShowPreviewModal(false)} className="text-gray-400 text-2xl hover:text-white">×</button>
                    </div>
                  </div>
                  <div className="flex-1 overflow-y-auto bg-gray-950 rounded-lg p-4 font-mono text-xs text-gray-300 border border-gray-800">
                    {projectFileLoading ? <div className="text-center py-10 text-gray-500">⏳ Загрузка...</div> : <pre className="whitespace-pre-wrap break-all">{projectFileContent || '[Пустой файл]'}</pre>}
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {activeTab === 'agents' && (
          <div className="space-y-6">
            <div className="flex justify-between items-center">
              <h2 className="text-2xl font-bold">Агенты</h2>
              <button onClick={() => setShowAgentStore(true)} className="px-4 py-2 rounded-lg bg-gradient-to-r from-purple-500 to-pink-500 text-white text-sm font-bold">🛒 Магазин</button>
            </div>
            {showAgentStore && (
              <div className="fixed inset-0 bg-black/80 z-50 flex items-center justify-center p-4" onClick={() => setShowAgentStore(false)}>
                <div className="bg-gray-900 border border-gray-700 rounded-xl p-6 max-w-3xl w-full max-h-[80vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
                  <div className="flex justify-between mb-4"><h3 className="text-xl font-bold">Магазин агентов</h3><button onClick={() => setShowAgentStore(false)} className="text-gray-400 text-2xl">×</button></div>
                  <div className="grid md:grid-cols-2 gap-4">{agentStore.map(a => (<div key={a.id} className="bg-gray-800/50 border border-gray-700 rounded-lg p-4"><h4 className="font-bold text-white mb-2">{a.name}</h4><p className="text-sm text-gray-400 mb-3">{a.description}</p><div className="flex justify-between items-center"><span className="text-xs text-gray-500">{a.category}</span><button onClick={() => importAgent(a.id)} className="px-3 py-1.5 rounded bg-emerald-500 text-white text-xs font-bold">➕ Импортировать</button></div></div>))}</div>
                </div>
              </div>
            )}
            {agents.map(agent => (
              <div key={agent.id} className={`rounded-xl border-2 p-6 transition-all ${agent.enabled ? 'border-emerald-500/30 bg-emerald-500/5' : 'border-gray-700 bg-gray-900/50 opacity-70'}`}>
                <div className="flex justify-between items-start mb-3">
                  <div>
                    <div className="flex items-center gap-3 mb-2"><h3 className="text-lg font-bold text-white">{agent.name}</h3><StatusBadge status={agent.status} /></div>
                    <p className="text-sm text-gray-400">{agent.task}</p>
                    <p className="text-xs text-gray-500 italic mt-2">{agent.description}</p>
                  </div>
                  <button onClick={() => toggleAgent(agent.id)} className={`px-4 py-2 rounded-lg text-sm font-bold ${agent.enabled ? 'bg-red-500/20 text-red-400 border border-red-500/50' : 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/50'}`}>{agent.enabled ? '⏸ Выключить' : '▶ Включить'}</button>
                </div>
                <div className="flex gap-2 mb-3">{agent.stack.map(s => <span key={s} className="px-2 py-1 bg-gray-700/50 rounded text-xs text-gray-300">{s}</span>)}</div>
                <div className="h-2 bg-gray-700 rounded-full"><div className={`h-full rounded-full ${agent.enabled ? 'bg-gradient-to-r from-emerald-500 to-cyan-500' : 'bg-gray-600'}`} style={{ width: `${agent.progress}%` }} /></div>
              </div>
            ))}
          </div>
        )}

        {activeTab === 'providers' && (
          <div className="space-y-6">
            <div className="flex justify-between items-center">
              <h2 className="text-2xl font-bold">Провайдеры</h2>
              <div className="flex gap-2">{(['all', 'online', 'offline'] as const).map(f => (<button key={f} onClick={() => setProviderFilter(f)} className={`px-3 py-2 rounded-lg text-sm font-bold ${providerFilter === f ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/50' : 'bg-gray-800 text-gray-400 border border-gray-700'}`}>{f === 'all' ? 'Все' : f === 'online' ? 'Онлайн' : 'Оффлайн'}</button>))}</div>
            </div>
            <div className={`rounded-xl border-2 p-6 transition-all ${ollamaStatus === 'online' ? 'border-emerald-500/30 bg-emerald-500/5' : 'border-red-500/20 bg-red-500/5'}`}>
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-3">
                  <div className={`w-4 h-4 rounded-full ${ollamaStatus === 'online' ? 'bg-emerald-400 animate-pulse' : 'bg-red-400'}`} />
                  <div><span className="text-lg font-bold text-white">Ollama</span><span className="text-sm text-gray-400 ml-3">— {providers.find(p => p.name === 'Ollama')?.description}</span></div>
                </div>
                <div className="flex gap-2">
                  <button onClick={() => { navigator.clipboard.writeText('ollama serve'); }} className="px-3 py-2 rounded-lg bg-emerald-500/20 border border-emerald-500/50 text-emerald-400 text-xs font-bold">▶ Запуск</button>
                  <button onClick={() => setActiveTab('models')} className="px-3 py-2 rounded-lg bg-purple-500/20 border border-purple-500/50 text-purple-400 text-xs font-bold">🧠 Модели</button>
                </div>
              </div>
              <input type="text" value={ollamaUrl} onChange={(e) => setOllamaUrl(e.target.value)} className="w-full px-4 py-3 rounded-lg bg-gray-800 border border-gray-700 text-white text-sm font-mono mb-3" />
              {ollamaProcesses.length > 0 && <div className="text-sm text-gray-400">Запущено: {ollamaProcesses.map(m => `${m.name} (${m.size}MB RAM, ${m.vram}MB VRAM)`).join(' • ')}</div>}
            </div>
            <div className="space-y-3">{providers.filter(p => p.name !== 'Ollama').filter(p => providerFilter === 'all' || (providerFilter === 'online' ? p.status === 'online' : p.status !== 'online')).map(provider => (
              <div key={provider.name} className={`rounded-xl border p-4 transition-all ${provider.enabled ? 'border-gray-700 bg-gray-900/50' : 'border-gray-800 bg-gray-900/30 opacity-60'}`}>
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-3 flex-1 min-w-0">
                    <div className={`w-3 h-3 rounded-full ${provider.status === 'online' ? 'bg-emerald-400 animate-pulse' : provider.status === 'error' ? 'bg-red-400' : 'bg-gray-600'}`} />
                    <div className="min-w-0 flex-1"><div className="flex items-center gap-3"><span className="font-bold text-white text-base">{provider.name}</span><span className="text-sm text-gray-400 truncate">{provider.description}</span></div></div>
                  </div>
                  <div className="flex items-center gap-4 shrink-0">
                    <span className="text-sm text-gray-400">{provider.latency > 0 ? `${provider.latency}ms` : '—'}</span>
                    <span className="text-sm text-gray-400">{provider.models > 0 ? provider.models : '—'} моделей</span>
                    <button onClick={() => toggleProvider(provider.name)} className={`w-12 h-6 rounded-full transition-all relative ${provider.enabled ? 'bg-emerald-500' : 'bg-gray-700'}`}><div className="w-5 h-5 rounded-full bg-white absolute top-0.5 transition-all" style={{ left: provider.enabled ? '26px' : '2px' }} /></button>
                  </div>
                </div>
                {provider.enabled && provider.apiKey !== undefined && (<div className="flex gap-3 items-center mt-3"><input type="password" placeholder="API Key" defaultValue={provider.apiKey} className="flex-1 max-w-xs px-3 py-2 rounded-lg bg-gray-800 border border-gray-700 text-white text-sm" />{provider.getKeyUrl && <a href={provider.getKeyUrl} target="_blank" className="text-sm text-cyan-400 hover:text-cyan-300 whitespace-nowrap">Получить ключ →</a>}</div>)}
              </div>
            ))}</div>
          </div>
        )}

        {activeTab === 'models' && (
          <div className="space-y-6">
            <h2 className="text-2xl font-bold">🧠 Управление моделями Ollama</h2>
            <div className="rounded-xl border border-gray-700 bg-gray-900/50 p-6">
              <h3 className="text-lg font-bold mb-4">📥 Скачать новую модель</h3>
              <div className="flex gap-3">
                <input type="text" value={newModelName} onChange={(e) => setNewModelName(e.target.value)} onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); pullModel(); } }} placeholder="Например: qwen2.5-coder:1.5b" className="flex-1 px-4 py-3 rounded-lg bg-gray-800 border border-gray-700 text-white text-sm focus:border-emerald-500 focus:outline-none font-mono" disabled={isPulling} />
                <button onClick={pullModel} disabled={isPulling || !newModelName.trim()} className={`px-6 py-3 rounded-lg font-bold text-sm transition-all whitespace-nowrap ${isPulling ? 'bg-gray-700 text-gray-500 cursor-not-allowed' : 'bg-emerald-500 hover:bg-emerald-600 text-white'}`}>{isPulling ? '⏳ Загрузка...' : '📥 Скачать'}</button>
              </div>
              <p className="text-xs text-gray-500 mt-2">💡 Популярные: qwen2.5-coder:1.5b, qwen2.5-coder:14b, llama3.2, mistral, phi3</p>
            </div>
            <div className="rounded-xl border border-gray-700 bg-gray-900/50 p-6">
              <h3 className="text-lg font-bold mb-4">📦 Установленные модели ({installedModels.length})</h3>
              {installedModels.length === 0 ? <p className="text-gray-500 text-center py-8">{ollamaStatus === 'online' ? 'Нет моделей' : 'Ollama не запущена'}</p> : (<div className="grid md:grid-cols-2 gap-3">{installedModels.map((m, idx) => (<div key={idx} className="flex justify-between items-center p-4 rounded-lg bg-gray-800/50 border border-gray-700"><div><span className="font-mono text-sm text-emerald-400 font-bold">{m.name}</span><p className="text-xs text-gray-500 mt-1">Размер: {m.size_gb} GB</p></div><button onClick={() => { setConsolePrompt(prev => prev + (prev ? '\n' : '') + `// Использую модель: ${m.name}`); setActiveTab('console'); }} className="px-3 py-1.5 rounded bg-gray-700 hover:bg-emerald-500/20 text-gray-300 hover:text-emerald-400 text-xs font-bold">▶ Использовать</button></div>))}</div>)}
            </div>
          </div>
        )}

        {activeTab === 'md' && (
          <div className="space-y-6">
            <h2 className="text-2xl font-bold">📝 Документация</h2>
            <div className="grid md:grid-cols-4 gap-4">{mdFiles.map(file => (<button key={file.name} onClick={() => loadRealMDFile(file)} className={`rounded-xl border-2 p-4 text-left transition-all ${selectedMDFile?.name === file.name ? 'border-emerald-500/50 bg-emerald-500/5' : 'border-gray-700 bg-gray-900/50 hover:border-gray-600'}`}><h3 className="font-bold text-white text-base mb-2">{file.name}</h3><p className="text-xs text-gray-400">{file.description}</p></button>))}</div>
            {selectedMDFile && (
              <div className="rounded-xl border border-gray-700 bg-gray-900/50 p-6">
                <div className="flex justify-between items-center mb-4">
                  <h3 className="text-lg font-bold text-gray-300">📝 {selectedMDFile.name}</h3>
                  <button onClick={saveRealMDFile} className="px-4 py-2 rounded-lg bg-emerald-500 hover:bg-emerald-600 text-white text-sm font-bold">💾 Сохранить</button>
                </div>
                {!mdFileExists && <div className="mb-4 p-3 rounded-lg bg-yellow-500/10 border border-yellow-500/30 text-yellow-400 text-sm">⚠️ Файл не существует. Напишите содержимое и нажмите "Сохранить".</div>}
                <textarea value={mdContent} onChange={(e) => setMdContent(e.target.value)} placeholder="Начните писать..." className="w-full h-96 px-4 py-3 rounded-lg bg-gray-800 border border-gray-700 text-white text-sm font-mono focus:border-emerald-500 focus:outline-none resize-none" />
                <div className="mt-2 text-xs text-gray-500">Символов: {mdContent.length} | Строк: {mdContent.split('\n').length}</div>
              </div>
            )}
          </div>
        )}

        {activeTab === 'code' && (
          <div className="space-y-6">
            <div className="flex justify-between items-center">
              <h2 className="text-2xl font-bold">Анализ кода</h2>
              <button onClick={() => codeIssues.filter(i => !i.fixed).forEach(i => fixCodeIssue(i.id))} className="px-4 py-2 rounded-lg bg-gradient-to-r from-red-500 to-orange-500 text-white text-sm font-bold">🔧 Исправить все</button>
            </div>
            {codeIssues.map(issue => (
              <div key={issue.id} className={`rounded-xl border p-6 ${issue.fixed ? 'border-emerald-500/30 bg-emerald-500/5' : issue.severity === 'critical' ? 'border-red-500/30 bg-red-500/5' : issue.severity === 'warning' ? 'border-yellow-500/30 bg-yellow-500/5' : 'border-blue-500/30 bg-blue-500/5'}`}>
                <div className="flex justify-between items-start mb-3">
                  <div>
                    <div className="flex items-center gap-3 mb-2">
                      <span className={`px-2 py-1 rounded text-xs font-bold ${issue.severity === 'critical' ? 'bg-red-500/20 text-red-400' : issue.severity === 'warning' ? 'bg-yellow-500/20 text-yellow-400' : 'bg-blue-500/20 text-blue-400'}`}>{issue.severity.toUpperCase()}</span>
                      <span className="text-xs text-gray-500 font-mono">{issue.file}:{issue.line}</span>
                      {issue.fixed && <span className="px-2 py-1 rounded text-xs font-bold bg-emerald-500/20 text-emerald-400">ИСПРАВЛЕНО</span>}
                    </div>
                    <h4 className="text-base font-bold text-white">{issue.title}</h4>
                    <p className="text-sm text-gray-400 mt-2">{issue.description}</p>
                  </div>
                  {!issue.fixed && <button onClick={() => fixCodeIssue(issue.id)} className="px-4 py-2 rounded-lg bg-emerald-500/20 border border-emerald-500/50 text-emerald-400 text-sm font-bold">🔧 Исправить</button>}
                </div>
                {issue.fixed && issue.fixLog && issue.fixLog.length > 0 && (<div className="mt-4 p-4 rounded-lg bg-gray-900/80 border border-gray-700"><div className="space-y-1 max-h-96 overflow-y-auto">{issue.fixLog.map((log, i) => <p key={i} className="text-xs text-gray-400 font-mono whitespace-pre-wrap">{log}</p>)}</div></div>)}
              </div>
            ))}
          </div>
        )}

        {activeTab === 'patches' && (
          <div className="space-y-6">
            <div className="flex justify-between items-center">
              <div><h2 className="text-2xl font-bold">🔄 Система автопатчей</h2><p className="text-sm text-gray-400 mt-1">Сканирование patch/ каждые 5 сек</p></div>
              <div className="flex gap-2">
                <button onClick={rollbackLastPatch} className="px-4 py-2 rounded-lg bg-red-500/20 border border-red-500/50 text-red-400 text-sm font-bold hover:bg-red-500/30">↩ Откатить</button>
                <button onClick={applyAllPending} disabled={applyingPatch || !patchStats.pending} className="px-4 py-2 rounded-lg bg-gradient-to-r from-emerald-500 to-cyan-500 text-white text-sm font-bold disabled:opacity-50">⚡ Применить все ({patchStats.pending || 0})</button>
              </div>
            </div>
            <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
              <div className="rounded-xl border border-gray-700 bg-gray-900/50 p-4"><div className="text-xs text-gray-500">Всего</div><div className="text-2xl font-bold text-white">{patchStats.total || 0}</div></div>
              <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/5 p-4"><div className="text-xs text-emerald-400">Применено</div><div className="text-2xl font-bold text-emerald-400">{patchStats.applied || 0}</div></div>
              <div className="rounded-xl border border-yellow-500/30 bg-yellow-500/5 p-4"><div className="text-xs text-yellow-400">Ожидают</div><div className="text-2xl font-bold text-yellow-400">{patchStats.pending || 0}</div></div>
              <div className="rounded-xl border border-red-500/30 bg-red-500/5 p-4"><div className="text-xs text-red-400">С ошибками</div><div className="text-2xl font-bold text-red-400">{patchStats.errors || 0}</div></div>
              <div className="rounded-xl border border-blue-500/30 bg-blue-500/5 p-4"><div className="text-xs text-blue-400">Бэкапов</div><div className="text-2xl font-bold text-blue-400">{patchStats.backups_count || 0}</div></div>
            </div>
            <div className="flex gap-2">{(['all', 'pending', 'applied', 'errors'] as const).map(f => (<button key={f} onClick={() => setPatchFilter(f)} className={`px-4 py-2 rounded-lg text-sm font-bold transition-all ${patchFilter === f ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/50' : 'bg-gray-800 text-gray-400 border border-gray-700'}`}>{f === 'all' ? '📋 Все' : f === 'pending' ? '⏳ Ожидают' : f === 'applied' ? '✅ Применены' : '❌ С ошибками'}</button>))}</div>
            <div className="space-y-3">{patches.filter(p => { if (patchFilter === 'pending') return !p.is_applied && !p.error; if (patchFilter === 'applied') return p.is_applied; if (patchFilter === 'errors') return p.error; return true; }).map(patch => (
              <div key={patch.filename} className={`rounded-xl border-2 p-4 transition-all ${patch.is_applied ? 'border-emerald-500/30 bg-emerald-500/5' : patch.error ? 'border-red-500/30 bg-red-500/5' : 'border-gray-700 bg-gray-900/50 hover:border-cyan-500/30'}`}>
                <div className="flex justify-between items-start gap-4">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-3 mb-2 flex-wrap">
                      <span className="px-2 py-1 rounded bg-gray-800 text-xs font-mono text-cyan-400">#{patch.patch_id}</span>
                      <span className="font-bold text-white truncate">{patch.target_file}</span>
                      {patch.is_applied && <span className="px-2 py-0.5 rounded text-xs bg-emerald-500/20 text-emerald-400">ПРИМЕНЕН</span>}
                      {patch.error && <span className="px-2 py-0.5 rounded text-xs bg-red-500/20 text-red-400">ОШИБКА</span>}
                    </div>
                    <p className="text-sm text-gray-400 mb-2">{patch.description}</p>
                    <div className="flex gap-4 flex-wrap text-xs text-gray-500"><span>👤 {patch.author}</span><span>📄 {patch.content_length} символов</span></div>
                  </div>
                  <div className="flex gap-2 shrink-0">
                    <button onClick={() => previewPatch(patch)} className="px-3 py-1.5 rounded bg-gray-700 hover:bg-gray-600 text-gray-300 text-xs font-bold">👁 Просмотр</button>
                    {!patch.is_applied && !patch.error && <button onClick={() => applyPatch(patch)} disabled={applyingPatch} className="px-3 py-1.5 rounded bg-emerald-500 hover:bg-emerald-600 text-white text-xs font-bold disabled:opacity-50">✅ Применить</button>}
                    <button onClick={() => archivePatch(patch.filename)} className="px-3 py-1.5 rounded bg-blue-500/20 hover:bg-blue-500/30 text-blue-400 text-xs font-bold">📦</button>
                    <button onClick={() => deletePatch(patch.filename)} className="px-3 py-1.5 rounded bg-red-500/20 hover:bg-red-500/30 text-red-400 text-xs font-bold">🗑</button>
                  </div>
                </div>
              </div>
            ))}{patches.length === 0 && <div className="text-center py-12 text-gray-500 border-2 border-dashed border-gray-700 rounded-xl"><p className="text-lg mb-2">📂 Папка patch/ пуста</p></div>}</div>
            {selectedPatch && patchPreview && (
              <div className="fixed inset-0 bg-black/80 z-50 flex items-center justify-center p-4" onClick={() => {setSelectedPatch(null); setPatchPreview(null);}}>
                <div className="bg-gray-900 border border-gray-700 rounded-xl p-6 max-w-4xl w-full max-h-[90vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
                  <div className="flex justify-between mb-4"><h3 className="text-xl font-bold">Превью патча #{selectedPatch.patch_id}</h3><button onClick={() => {setSelectedPatch(null); setPatchPreview(null);}} className="text-gray-400 text-2xl">×</button></div>
                  {patchPreview.success ? (<div className="space-y-4"><div className="p-4 rounded-lg bg-emerald-500/10 border border-emerald-500/30 text-emerald-400">✅ {patchPreview.message}</div><div className="grid grid-cols-2 gap-4 text-sm"><div className="p-3 rounded bg-gray-800"><div className="text-gray-500 text-xs">Старый размер</div><div className="font-bold">{patchPreview.old_size} байт / {patchPreview.old_lines} строк</div></div><div className="p-3 rounded bg-gray-800"><div className="text-gray-500 text-xs">Новый размер</div><div className="font-bold">{patchPreview.new_size} байт / {patchPreview.new_lines} строк</div></div></div><div className="flex gap-3"><button onClick={() => {setSelectedPatch(null); setPatchPreview(null);}} className="flex-1 py-3 rounded-lg bg-gray-700 hover:bg-gray-600 text-white font-bold">Отмена</button><button onClick={() => {applyPatch(selectedPatch); setSelectedPatch(null); setPatchPreview(null);}} disabled={applyingPatch} className="flex-1 py-3 rounded-lg bg-gradient-to-r from-emerald-500 to-cyan-500 text-white font-bold disabled:opacity-50">✅ Применить</button></div></div>) : (<div className="p-4 rounded-lg bg-red-500/10 border border-red-500/30 text-red-400">❌ {patchPreview.error}</div>)}
                </div>
              </div>
            )}
          </div>
        )}

        {activeTab === 'logs' && (
          <div className="space-y-6">
            <div className="flex justify-between items-center"><h2 className="text-2xl font-bold">Логи</h2><span className="text-xs text-gray-500">Обновление каждые 3 сек</span></div>
            <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-4 max-h-[70vh] overflow-y-auto">{logs.slice().reverse().map((entry, i) => (<div key={i} className="flex items-start gap-3 py-2 font-mono text-sm border-b border-gray-800/30 last:border-0"><span className="text-gray-600 shrink-0">[{entry.time}]</span><span className={entry.level === 'info' ? 'text-blue-400' : entry.level === 'warn' ? 'text-yellow-400' : entry.level === 'error' ? 'text-red-400' : 'text-emerald-400'}>{entry.level === 'info' ? 'ℹ' : entry.level === 'warn' ? '⚠' : entry.level === 'error' ? '✕' : '✓'}</span><div className="flex-1"><span className="text-gray-300">{entry.message}</span>{entry.details && <p className="text-xs text-gray-500 mt-1">{entry.details}</p>}</div><span className="text-gray-600 shrink-0">({entry.source})</span></div>))}</div>
          </div>
        )}

        {activeTab === 'tasks' && (
          <div className="space-y-6">
            <h2 className="text-2xl font-bold">Задачи</h2>
            <div className="rounded-xl border border-gray-700 bg-gray-900/50 p-6">
              <h3 className="text-lg font-bold mb-4">➕ Добавить задачу</h3>
              <div className="space-y-3">
                <input type="text" value={newTaskText} onChange={(e) => setNewTaskText(e.target.value)} placeholder="Описание задачи..." className="w-full px-4 py-3 rounded-lg bg-gray-800 border border-gray-700 text-white text-sm focus:border-emerald-500 focus:outline-none" />
                <div className="flex gap-3">
                  <select value={newTaskPriority} onChange={(e) => setNewTaskPriority(e.target.value as any)} className="px-4 py-2 rounded-lg bg-gray-800 border border-gray-700 text-white text-sm"><option value="high">🔴 Высокий</option><option value="medium">🟡 Средний</option><option value="low">🔵 Низкий</option></select>
                  <select value={newTaskCategory} onChange={(e) => setNewTaskCategory(e.target.value as any)} className="px-4 py-2 rounded-lg bg-gray-800 border border-gray-700 text-white text-sm"><option value="code">⟨⟩ Исправление кода</option><option value="general">📋 Общая задача</option></select>
                  <button onClick={addTask} className="px-6 py-2 rounded-lg bg-emerald-500 text-white text-sm font-bold">Добавить</button>
                </div>
              </div>
            </div>
            <div className="rounded-xl border border-red-500/30 bg-red-500/5 p-6">
              <h3 className="text-lg font-bold mb-4 flex items-center gap-2"><span>⟨⟩</span> Задачи по коду ({codeTasks.filter(t => !t.done).length})</h3>
              <div className="space-y-3">{codeTasks.map(task => (<div key={task.id} className="flex items-center gap-3 py-3 border-b border-gray-800/50 last:border-0"><button onClick={() => toggleTask(task.id)} className={`w-6 h-6 rounded border-2 flex items-center justify-center ${task.done ? 'bg-emerald-500 border-emerald-500 text-white' : 'border-gray-600'}`}>{task.done && '✓'}</button><span className={`text-sm flex-1 ${task.done ? 'text-gray-500 line-through' : 'text-gray-200'}`}>{task.text}</span><span className={`px-2 py-1 rounded text-xs font-bold ${task.priority === 'high' ? 'bg-red-500/20 text-red-400' : task.priority === 'medium' ? 'bg-yellow-500/20 text-yellow-400' : 'bg-gray-500/20 text-gray-400'}`}>{task.priority.toUpperCase()}</span><button onClick={() => deleteTask(task.id)} className="text-red-400 hover:text-red-300 text-sm">✕</button></div>))}</div>
            </div>
            <div className="rounded-xl border border-blue-500/30 bg-blue-500/5 p-6">
              <h3 className="text-lg font-bold mb-4 flex items-center gap-2"><span>📋</span> Общие задачи ({generalTasks.filter(t => !t.done).length})</h3>
              <div className="space-y-3">{generalTasks.map(task => (<div key={task.id} className="flex items-center gap-3 py-3 border-b border-gray-800/50 last:border-0"><button onClick={() => toggleTask(task.id)} className={`w-6 h-6 rounded border-2 flex items-center justify-center ${task.done ? 'bg-emerald-500 border-emerald-500 text-white' : 'border-gray-600'}`}>{task.done && '✓'}</button><span className={`text-sm flex-1 ${task.done ? 'text-gray-500 line-through' : 'text-gray-200'}`}>{task.text}</span><span className={`px-2 py-1 rounded text-xs font-bold ${task.priority === 'high' ? 'bg-red-500/20 text-red-400' : task.priority === 'medium' ? 'bg-yellow-500/20 text-yellow-400' : 'bg-gray-500/20 text-gray-400'}`}>{task.priority.toUpperCase()}</span><button onClick={() => deleteTask(task.id)} className="text-red-400 hover:text-red-300 text-sm">✕</button></div>))}</div>
            </div>
          </div>
        )}
      </main>

      <footer className="border-t border-gray-800 bg-gray-900/50 shrink-0">
        <div className="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between text-xs text-gray-600">
          <div className="flex items-center gap-4 flex-wrap">
            <span>🤖 {agents.filter(a => a.enabled).length} агентов</span>
            <span>•</span>
            <span>🌐 {providers.filter(p => p.status === 'online').length} провайдеров</span>
            <span>•</span>
            <span>🗂 {projectStats?.total || 0} файлов</span>
            <span>•</span>
            <span>🧠 {installedModels.length} моделей</span>
            <span>•</span>
            <span>🔄 {patchStats.pending || 0} патчей</span>
            <span>•</span>
            <span>☑ {completedTasks}/{taskList.length} задач</span>
          </div>
          <span>v.3.4.3 TOGGLES • dreamkin • 2026</span>
        </div>
      </footer>
    </div>
  );
}