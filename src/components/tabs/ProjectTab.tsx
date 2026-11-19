import { ProjectFile, ProjectStats } from '../../types';
import { getCategoryColor, getCategoryLabel } from '../../utils/categories';
import Modal from '../ui/Modal';
import { SortField } from '../../hooks/useProject';
import { ArchiveFile, ProjectHistoryEntry } from '../../services/api';

interface ProjectTabProps {
  projectFiles: ProjectFile[];
  projectStats: ProjectStats | null;
  projectLoading: boolean;
  projectSearch: string;
  setProjectSearch: (search: string) => void;
  projectDuplicatesOnly: boolean;
  setProjectDuplicatesOnly: (value: boolean) => void;
  projectImportantOnly: boolean;
  setProjectImportantOnly: (value: boolean) => void;
  projectFilters: Set<string>;
  toggleFilter: (cat: string) => void;
  clearFilters: () => void;
  sortField: SortField;
  sortDir: 'asc' | 'desc';
  toggleSort: (field: SortField) => void;
  selectedFiles: Set<string>;
  toggleFileSelection: (path: string) => void;
  selectAll: () => void;
  deselectAll: () => void;
  cleanupMode: boolean;
  setCleanupMode: (value: boolean) => void;
  history: ProjectHistoryEntry[];
  rollbackLast: () => void;
  archiveFiles: ArchiveFile[];
  showArchiveModal: boolean;
  setShowArchiveModal: (value: boolean) => void;
  loadArchive: () => void;
  restoreFile: (archivePath: string) => void;
  selectedProjectFile: ProjectFile | null;
  projectFileContent: string;
  projectFileLoading: boolean;
  showPreviewModal: boolean;
  setShowPreviewModal: (value: boolean) => void;
  filteredProjectFiles: ProjectFile[];
  scanProject: () => void;
  openProjectFilePreview: (file: ProjectFile) => void;
  bulkAction: (action: 'archive' | 'important' | 'delete') => void;
}

export default function ProjectTab(props: ProjectTabProps) {
  const {
    projectFiles, projectStats, projectLoading,
    projectSearch, setProjectSearch,
    projectDuplicatesOnly, setProjectDuplicatesOnly,
    projectImportantOnly, setProjectImportantOnly,
    projectFilters, toggleFilter, clearFilters,
    sortField, sortDir, toggleSort,
    selectedFiles, toggleFileSelection, selectAll, deselectAll,
    cleanupMode, setCleanupMode,
    history, rollbackLast,
    archiveFiles, showArchiveModal, setShowArchiveModal, loadArchive, restoreFile,
    selectedProjectFile, projectFileContent, projectFileLoading,
    showPreviewModal, setShowPreviewModal,
    filteredProjectFiles,
    scanProject, openProjectFilePreview, bulkAction,
  } = props;

  const categories = ['critical', 'code', 'config', 'docs', 'backup', 'trash', 'other'];

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h2 className="text-2xl font-bold">🗂 Управление проектом</h2>
        <div className="flex gap-2">
          <button onClick={() => setCleanupMode(!cleanupMode)} className={`px-4 py-2 rounded-lg text-sm font-bold transition-all ${cleanupMode ? 'bg-red-500 text-white' : 'bg-gray-700 text-gray-300 hover:bg-gray-600'}`}>
            {cleanupMode ? '❌ Отмена' : '🧹 Режим очистки'}
          </button>
          <button onClick={scanProject} disabled={projectLoading} className="px-4 py-2 rounded-lg bg-gradient-to-r from-emerald-500 to-cyan-500 text-white text-sm font-bold disabled:opacity-50">
            {projectLoading ? '⏳ Сканирование...' : '🔄 Пересканировать'}
          </button>
        </div>
      </div>

      <div className="rounded-xl border border-gray-700 bg-gray-900/50 p-4 space-y-3">
        <input
          type="text"
          value={projectSearch}
          onChange={(e) => setProjectSearch(e.target.value)}
          placeholder="🔍 Поиск по имени..."
          className="w-full px-4 py-2 rounded-lg bg-gray-800 border border-gray-700 text-white text-sm focus:border-emerald-500 focus:outline-none"
        />
        <div className="flex flex-wrap gap-2">
          {categories.map(cat => (
            <button
              key={cat}
              onClick={() => toggleFilter(cat)}
              className={`px-3 py-2 rounded-lg text-xs font-bold transition-all ${
                projectFilters.has(cat)
                  ? 'bg-emerald-500/20 text-emerald-400 border-2 border-emerald-500/50'
                  : 'bg-gray-800 text-gray-400 border border-gray-700 hover:border-gray-600'
              }`}
            >
              {getCategoryLabel(cat)}
            </button>
          ))}
          <button
            onClick={clearFilters}
            className="px-3 py-2 rounded-lg text-xs font-bold bg-gray-800 text-gray-400 border border-gray-700 hover:border-emerald-500/50"
          >
            📋 Все
          </button>
        </div>
        <div className="flex flex-wrap gap-4 items-center">
          <label className="flex items-center gap-2 text-sm text-gray-400 cursor-pointer">
            <input type="checkbox" checked={projectDuplicatesOnly} onChange={(e) => setProjectDuplicatesOnly(e.target.checked)} className="rounded" />
            👯 Только дубликаты
          </label>
          <label className="flex items-center gap-2 text-sm text-gray-400 cursor-pointer">
            <input type="checkbox" checked={projectImportantOnly} onChange={(e) => setProjectImportantOnly(e.target.checked)} className="rounded" />
            ⭐ Только важные
          </label>
          <div className="flex gap-2 ml-auto">
            <span className="text-xs text-gray-500 self-center">Сортировка:</span>
            {(['name', 'size', 'date'] as const).map(field => (
              <button
                key={field}
                onClick={() => toggleSort(field)}
                className={`px-2 py-1 rounded text-xs font-bold ${
                  sortField === field ? 'bg-emerald-500/20 text-emerald-400' : 'bg-gray-800 text-gray-400'
                }`}
              >
                {field === 'name' ? 'Имя' : field === 'size' ? 'Размер' : 'Дата'} {sortField === field && (sortDir === 'asc' ? '▲' : '▼')}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="text-xs text-gray-500 px-2">
        📊 Всего: {projectStats?.total || 0} файлов ({projectStats?.total_size_human || '0 Б'}) | Показано: {filteredProjectFiles.length} | Выбрано: {selectedFiles.size}
      </div>

      <div className="space-y-2">
        {filteredProjectFiles.length > 0 && (
          <div className="flex gap-2 items-center px-2">
            <button onClick={selectedFiles.size === filteredProjectFiles.length ? deselectAll : selectAll} className="text-xs text-emerald-400 hover:text-emerald-300">
              {selectedFiles.size === filteredProjectFiles.length ? '☑ Снять все' : '☐ Выбрать все'}
            </button>
          </div>
        )}
        {filteredProjectFiles.map((file, idx) => (
          <div key={idx} className={`rounded-xl border p-4 transition-all ${file.is_critical ? 'border-red-500/30 bg-red-500/5' : file.is_duplicate ? 'border-purple-500/30 bg-purple-500/5' : file.category === 'trash' ? 'border-orange-500/30 bg-orange-500/5' : 'border-gray-700 bg-gray-900/50 hover:border-gray-600'}`}>
            <div className="flex items-start gap-3">
              <input
                type="checkbox"
                checked={selectedFiles.has(file.path)}
                onChange={() => toggleFileSelection(file.path)}
                className="mt-1 rounded"
              />
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
                <button onClick={() => openProjectFilePreview(file)} className="px-3 py-1.5 rounded bg-gray-700 hover:bg-gray-600 text-gray-300 text-xs font-bold">👁</button>
                {!file.is_critical && (
                  <>
                    <button onClick={() => bulkAction('archive')} className="px-3 py-1.5 rounded bg-blue-500/20 hover:bg-blue-500/30 text-blue-400 text-xs font-bold" disabled={!selectedFiles.has(file.path)}>📦</button>
                    <button onClick={() => bulkAction('delete')} className="px-3 py-1.5 rounded bg-red-500/20 hover:bg-red-500/30 text-red-400 text-xs font-bold" disabled={!selectedFiles.has(file.path)}>🗑</button>
                  </>
                )}
              </div>
            </div>
          </div>
        ))}
        {filteredProjectFiles.length === 0 && (
          <div className="text-center py-12 text-gray-500 border-2 border-dashed border-gray-700 rounded-xl">
            <p className="text-lg mb-2">🔍 Ничего не найдено</p>
            <p className="text-sm">Измени фильтры или включи переключатели выше</p>
          </div>
        )}
      </div>

      {selectedFiles.size > 0 && (
        <div className="fixed bottom-20 left-1/2 -translate-x-1/2 bg-gray-900 border border-emerald-500/50 rounded-xl p-4 shadow-2xl flex gap-3 z-40">
          <span className="text-sm text-gray-400 self-center">Выбрано: {selectedFiles.size}</span>
          <button onClick={() => bulkAction('archive')} className="px-4 py-2 rounded-lg bg-blue-500/20 hover:bg-blue-500/30 text-blue-400 text-sm font-bold">📦 Архивировать</button>
          <button onClick={() => bulkAction('important')} className="px-4 py-2 rounded-lg bg-yellow-500/20 hover:bg-yellow-500/30 text-yellow-400 text-sm font-bold">⭐ Пометить важными</button>
          <button onClick={() => bulkAction('delete')} className="px-4 py-2 rounded-lg bg-red-500/20 hover:bg-red-500/30 text-red-400 text-sm font-bold">🗑 Удалить</button>
          <button onClick={deselectAll} className="px-4 py-2 rounded-lg bg-gray-700 hover:bg-gray-600 text-gray-300 text-sm font-bold">✕ Снять</button>
        </div>
      )}

      {history.length > 0 && (
        <div className="rounded-xl border border-gray-700 bg-gray-900/50 p-4">
          <div className="flex justify-between items-center mb-3">
            <h3 className="text-sm font-bold text-gray-300">📜 История действий</h3>
            <button onClick={rollbackLast} className="px-3 py-1.5 rounded bg-orange-500/20 hover:bg-orange-500/30 text-orange-400 text-xs font-bold">↩ Откатить последнее</button>
          </div>
          <div className="space-y-2 max-h-48 overflow-y-auto">
            {history.slice().reverse().map((entry, idx) => (
              <div key={idx} className="flex items-center gap-3 text-xs text-gray-400 py-1 border-b border-gray-800/30 last:border-0">
                <span className="text-gray-600">[{new Date(entry.timestamp).toLocaleTimeString('ru-RU')}]</span>
                <span>{entry.action === 'archive' ? '📦 Архивировано' : entry.action === 'important' ? '⭐ Помечено важными' : '🗑 Удалено'} {entry.paths.length} файлов</span>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="flex gap-2">
        <button onClick={loadArchive} className="px-4 py-2 rounded-lg bg-gray-700 hover:bg-gray-600 text-gray-300 text-sm font-bold">📂 Показать архив</button>
      </div>

      <Modal isOpen={showArchiveModal} onClose={() => setShowArchiveModal(false)} title="📂 Архив проекта" maxWidth="max-w-3xl">
        <div className="space-y-2">
          {archiveFiles.length === 0 ? (
            <p className="text-gray-500 text-center py-8">Архив пуст</p>
          ) : (
            archiveFiles.map((file, idx) => (
              <div key={idx} className="flex items-center justify-between p-3 rounded-lg bg-gray-800/50 border border-gray-700">
                <div>
                  <span className="font-mono text-sm text-white">{file.filename}</span>
                  <div className="text-xs text-gray-500 mt-1">
                    <span>📏 {(file.size / 1024).toFixed(1)} KB</span> | <span>🕐 {new Date(file.modified).toLocaleString('ru-RU')}</span>
                  </div>
                </div>
                <button onClick={() => restoreFile(file.path)} className="px-3 py-1.5 rounded bg-emerald-500/20 hover:bg-emerald-500/30 text-emerald-400 text-xs font-bold">↩ Восстановить</button>
              </div>
            ))
          )}
        </div>
      </Modal>

      <Modal
        isOpen={showPreviewModal && !!selectedProjectFile}
        onClose={() => setShowPreviewModal(false)}
        title={selectedProjectFile ? `${selectedProjectFile.icon} ${selectedProjectFile.path}` : ''}
      >
        {selectedProjectFile && (
          <>
            <div className="flex gap-3 mt-2 text-xs text-gray-400 mb-4">
              <span>{selectedProjectFile.size_human}</span>
              <span>{getCategoryLabel(selectedProjectFile.category)}</span>
              <span>{projectFileContent.split('\n').length} строк</span>
            </div>
            <div className="flex-1 overflow-y-auto bg-gray-950 rounded-lg p-4 font-mono text-xs text-gray-300 border border-gray-800">
              {projectFileLoading ? (
                <div className="text-center py-10 text-gray-500">⏳ Загрузка...</div>
              ) : (
                <pre className="whitespace-pre-wrap break-all">{projectFileContent || '[Пустой файл]'}</pre>
              )}
            </div>
          </>
        )}
      </Modal>
    </div>
  );
}
