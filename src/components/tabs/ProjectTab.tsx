import { useState } from 'react';
import { ProjectFile, ProjectStats } from '../../types';
import { getCategoryColor, getCategoryLabel } from '../../utils/categories';
import Modal from '../ui/Modal';

interface ProjectTabProps {
  projectFiles: ProjectFile[];
  projectStats: ProjectStats | null;
  projectLoading: boolean;
  projectFilter: string;
  setProjectFilter: (filter: string) => void;
  projectSearch: string;
  setProjectSearch: (search: string) => void;
  projectDuplicatesOnly: boolean;
  setProjectDuplicatesOnly: (value: boolean) => void;
  projectImportantOnly: boolean;
  setProjectImportantOnly: (value: boolean) => void;
  cleanupMode: boolean;
  setCleanupMode: (value: boolean) => void;
  showCritical: boolean;
  setShowCritical: (value: boolean) => void;
  showImportant: boolean;
  setShowImportant: (value: boolean) => void;
  showTrash: boolean;
  setShowTrash: (value: boolean) => void;
  showDuplicates: boolean;
  setShowDuplicates: (value: boolean) => void;
  filteredProjectFiles: ProjectFile[];
  scanProject: () => void;
  openProjectFilePreview: (file: ProjectFile) => void;
  archiveProjectFile: (file: ProjectFile) => void;
  deleteProjectFile: (file: ProjectFile) => void;
  toggleImportant: (file: ProjectFile) => void;
  applyCleanup: () => void;
  selectedProjectFile: ProjectFile | null;
  projectFileContent: string;
  projectFileLoading: boolean;
  showPreviewModal: boolean;
  setShowPreviewModal: (value: boolean) => void;
}

export default function ProjectTab(props: ProjectTabProps) {
  const {
    projectFiles, projectStats, projectLoading,
    projectFilter, setProjectFilter,
    projectSearch, setProjectSearch,
    projectDuplicatesOnly, setProjectDuplicatesOnly,
    projectImportantOnly, setProjectImportantOnly,
    cleanupMode, setCleanupMode,
    showCritical, setShowCritical,
    showImportant, setShowImportant,
    showTrash, setShowTrash,
    showDuplicates, setShowDuplicates,
    filteredProjectFiles,
    scanProject, openProjectFilePreview,
    archiveProjectFile, deleteProjectFile, toggleImportant, applyCleanup,
    selectedProjectFile, projectFileContent, projectFileLoading,
    showPreviewModal, setShowPreviewModal,
  } = props;

  return (
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
          {cleanupMode && (projectStats?.cleanup_delete_count ?? 0) > 0 && (
            <button onClick={applyCleanup} className="px-4 py-2 rounded-lg bg-red-600 hover:bg-red-700 text-white text-sm font-bold animate-pulse">
              🗑 Удалить {projectStats?.cleanup_delete_count} файлов
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
          <input
            type="text"
            value={projectSearch}
            onChange={(e) => setProjectSearch(e.target.value)}
            placeholder="🔍 Поиск..."
            className="flex-1 min-w-[200px] px-4 py-2 rounded-lg bg-gray-800 border border-gray-700 text-white text-sm focus:border-emerald-500 focus:outline-none"
          />
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
                {!file.is_critical && (
                  <>
                    <button onClick={() => archiveProjectFile(file)} className="px-3 py-1.5 rounded bg-blue-500/20 hover:bg-blue-500/30 text-blue-400 text-xs font-bold">📦</button>
                    <button onClick={() => deleteProjectFile(file)} className="px-3 py-1.5 rounded bg-red-500/20 hover:bg-red-500/30 text-red-400 text-xs font-bold">🗑</button>
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
            <div className="flex gap-2 mb-4">
              {!selectedProjectFile.is_critical && (
                <>
                  <button onClick={() => { archiveProjectFile(selectedProjectFile); setShowPreviewModal(false); }} className="px-3 py-1.5 rounded bg-blue-500/20 text-blue-400 text-xs font-bold hover:bg-blue-500/30">📦 Архив</button>
                  <button onClick={() => { deleteProjectFile(selectedProjectFile); setShowPreviewModal(false); }} className="px-3 py-1.5 rounded bg-red-500/20 text-red-400 text-xs font-bold hover:bg-red-500/30">🗑 Удалить</button>
                </>
              )}
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
