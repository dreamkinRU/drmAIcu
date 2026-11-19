import { useState, useEffect } from 'react';
import { ProjectFile, ProjectStats } from '../types';
import {
  scanProject as scanProjectApi,
  loadProjectFile,
  bulkProjectAction,
  restoreProjectFile,
  rollbackProjectAction,
  loadProjectHistory,
  loadArchiveList,
  ProjectHistoryEntry,
  ArchiveFile,
} from '../services/api';
import { storage, STORAGE_KEYS } from '../utils/storage';

export type SortField = 'name' | 'size' | 'date';
export type SortDir = 'asc' | 'desc';

export function useProject() {
  const [projectFiles, setProjectFiles] = useState<ProjectFile[]>([]);
  const [projectStats, setProjectStats] = useState<ProjectStats | null>(null);
  const [projectLoading, setProjectLoading] = useState(false);
  const [projectSearch, setProjectSearch] = useState('');
  const [projectDuplicatesOnly, setProjectDuplicatesOnly] = useState(false);
  const [projectImportantOnly, setProjectImportantOnly] = useState(false);
  const [projectFilters, setProjectFilters] = useState<Set<string>>(new Set());
  const [sortField, setSortField] = useState<SortField>('name');
  const [sortDir, setSortDir] = useState<SortDir>('asc');
  const [selectedFiles, setSelectedFiles] = useState<Set<string>>(new Set());
  const [cleanupMode, setCleanupMode] = useState(false);
  const [history, setHistory] = useState<ProjectHistoryEntry[]>([]);
  const [archiveFiles, setArchiveFiles] = useState<ArchiveFile[]>([]);
  const [showArchiveModal, setShowArchiveModal] = useState(false);
  const [selectedProjectFile, setSelectedProjectFile] = useState<ProjectFile | null>(null);
  const [projectFileContent, setProjectFileContent] = useState('');
  const [projectFileLoading, setProjectFileLoading] = useState(false);
  const [showPreviewModal, setShowPreviewModal] = useState(false);
  const [hasScanned, setHasScanned] = useState(false);

  const scanProject = async () => {
    setProjectLoading(true);
    try {
      const data = await scanProjectApi();
      setProjectFiles(data.files);
      setProjectStats(data.stats);
      setHasScanned(true);
    } catch {
      // ignore
    } finally {
      setProjectLoading(false);
    }
  };

  useEffect(() => {
    if (!hasScanned) {
      scanProject();
    }
  }, [hasScanned]);

  const toggleFilter = (cat: string) => {
    setProjectFilters(prev => {
      const next = new Set(prev);
      if (next.has(cat)) next.delete(cat);
      else next.add(cat);
      return next;
    });
  };

  const clearFilters = () => setProjectFilters(new Set());

  const toggleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDir(prev => (prev === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortField(field);
      setSortDir('asc');
    }
  };

  const toggleFileSelection = (path: string) => {
    setSelectedFiles(prev => {
      const next = new Set(prev);
      if (next.has(path)) next.delete(path);
      else next.add(path);
      return next;
    });
  };

  const selectAll = () => {
    setSelectedFiles(new Set(filteredProjectFiles.map(f => f.path)));
  };

  const deselectAll = () => setSelectedFiles(new Set());

  const bulkAction = async (action: 'archive' | 'important' | 'delete') => {
    if (selectedFiles.size === 0) return;
    const paths = Array.from(selectedFiles);
    const data = await bulkProjectAction(action, paths);
    if (data.success) {
      await scanProject();
      await loadHistory();
      setSelectedFiles(new Set());
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

  const loadHistory = async () => {
    const h = await loadProjectHistory();
    setHistory(h);
  };

  const loadArchive = async () => {
    const files = await loadArchiveList();
    setArchiveFiles(files);
    setShowArchiveModal(true);
  };

  const restoreFile = async (archivePath: string) => {
    const data = await restoreProjectFile(archivePath);
    if (data.success) {
      await loadArchive();
      await scanProject();
    }
  };

  const rollbackLast = async () => {
    const data = await rollbackProjectAction();
    if (data.success) {
      await scanProject();
      await loadHistory();
    }
  };

  useEffect(() => {
    loadHistory();
  }, []);

  const filteredProjectFiles = projectFiles
    .filter(f => {
      if (projectSearch && !f.filename.toLowerCase().includes(projectSearch.toLowerCase()) && !f.path.toLowerCase().includes(projectSearch.toLowerCase())) return false;
      if (projectDuplicatesOnly && !f.is_duplicate) return false;
      if (projectImportantOnly && !f.is_important) return false;
      if (projectFilters.size > 0 && !projectFilters.has(f.category)) return false;
      return true;
    })
    .sort((a, b) => {
      let cmp = 0;
      if (sortField === 'name') cmp = a.filename.localeCompare(b.filename);
      else if (sortField === 'size') cmp = a.size - b.size;
      else if (sortField === 'date') cmp = new Date(a.modified).getTime() - new Date(b.modified).getTime();
      return sortDir === 'asc' ? cmp : -cmp;
    });

  return {
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
    selectedProjectFile, setSelectedProjectFile,
    projectFileContent, projectFileLoading,
    showPreviewModal, setShowPreviewModal,
    filteredProjectFiles,
    scanProject, openProjectFilePreview, bulkAction,
  };
}
