import { useState } from 'react';
import { ProjectFile, ProjectStats } from '../types';
import {
  scanProject as scanProjectApi,
  loadProjectFile,
  archiveProjectFile as archiveProjectFileApi,
  deleteProjectFile as deleteProjectFileApi,
  toggleImportant as toggleImportantApi,
} from '../services/api';
import { storage, STORAGE_KEYS } from '../utils/storage';

export function useProject() {
  const [projectFiles, setProjectFiles] = useState<ProjectFile[]>([]);
  const [projectStats, setProjectStats] = useState<ProjectStats | null>(null);
  const [projectLoading, setProjectLoading] = useState(false);
  const [projectFilter, setProjectFilter] = useState<string>('all');
  const [projectSearch, setProjectSearch] = useState('');
  const [projectDuplicatesOnly, setProjectDuplicatesOnly] = useState(false);
  const [projectImportantOnly, setProjectImportantOnly] = useState(false);
  const [cleanupMode, setCleanupMode] = useState(false);
  const [showCritical, setShowCritical] = useState(false);
  const [showImportant, setShowImportant] = useState(true);
  const [showTrash, setShowTrash] = useState(true);
  const [showDuplicates, setShowDuplicates] = useState(true);
  const [selectedProjectFile, setSelectedProjectFile] = useState<ProjectFile | null>(null);
  const [projectFileContent, setProjectFileContent] = useState('');
  const [projectFileLoading, setProjectFileLoading] = useState(false);
  const [showPreviewModal, setShowPreviewModal] = useState(false);

  const scanProject = async () => {
    setProjectLoading(true);
    try {
      const data = await scanProjectApi();
      setProjectFiles(data.files);
      setProjectStats(data.stats);
    } catch {
      // ignore
    } finally {
      setProjectLoading(false);
    }
  };

  const openProjectFilePreview = async (file: ProjectFile) => {
    setSelectedProjectFile(file);
    setProjectFileContent('');
    setProjectFileLoading(true);
    setShowPreviewModal(true);
    const data = await loadProjectFile(file.path);
    if (data.success) {
      setProjectFileContent(data.content);
    } else {
      setProjectFileContent('[Ошибка: ' + data.error + ']');
    }
    setProjectFileLoading(false);
  };

  const archiveProjectFile = async (file: ProjectFile) => {
    if (file.is_critical) {
      alert('Нельзя архивировать критичный файл!');
      return;
    }
    const data = await archiveProjectFileApi(file.path);
    if (data.success) {
      storage.set(STORAGE_KEYS.SCROLL_PROJECT, window.scrollY.toString());
      setProjectFiles(prev => prev.filter(f => f.path !== file.path));
    }
  };

  const deleteProjectFile = async (file: ProjectFile) => {
    if (file.is_critical) {
      alert('Нельзя удалять критичный файл!');
      return;
    }
    if (!confirm('УДАЛИТЬ ' + file.path + '?')) return;
    const data = await deleteProjectFileApi(file.path);
    if (data.success) {
      storage.set(STORAGE_KEYS.SCROLL_PROJECT, window.scrollY.toString());
      setProjectFiles(prev => prev.filter(f => f.path !== file.path));
    } else {
      alert('Ошибка: ' + data.error);
    }
  };

  const toggleImportant = async (file: ProjectFile) => {
    const data = await toggleImportantApi(file.path);
    if (data.success) {
      setProjectFiles(prev =>
        prev.map(f => (f.path === file.path ? { ...f, is_important: !f.is_important } : f))
      );
    }
  };

  const applyCleanup = async () => {
    const toDelete = projectFiles.filter(f => f.cleanup?.action === 'delete');
    if (toDelete.length === 0) {
      alert('Нечего очищать');
      return;
    }
    if (!confirm('Переместить ' + toDelete.length + ' файлов в архив?')) return;
    let successCount = 0;
    for (const file of toDelete) {
      const data = await archiveProjectFileApi(file.path);
      if (data.success) successCount++;
    }
    alert('Очищено: ' + successCount + ' из ' + toDelete.length + ' файлов');
    setCleanupMode(false);
    storage.set(STORAGE_KEYS.SCROLL_PROJECT, window.scrollY.toString());
    setProjectFiles(prev => prev.filter(f => f.cleanup?.action !== 'delete'));
  };

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

  return {
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
    selectedProjectFile, setSelectedProjectFile,
    projectFileContent, projectFileLoading,
    showPreviewModal, setShowPreviewModal,
    filteredProjectFiles,
    scanProject, openProjectFilePreview,
    archiveProjectFile, deleteProjectFile, toggleImportant, applyCleanup,
  };
}
