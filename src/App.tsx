import { useState, useEffect } from 'react';
import { TabId } from './types';
import { agentStore, POLL_INTERVALS } from './utils/constants';
import { storage, STORAGE_KEYS } from './utils/storage';
import { useLogs } from './hooks/useLogs';
import { useCodeIssues } from './hooks/useCodeIssues';
import { useTasks } from './hooks/useTasks';
import { useAgents } from './hooks/useAgents';
import { useConsole } from './hooks/useConsole';
import { useMD } from './hooks/useMD';
import { useOllama } from './hooks/useOllama';
import { usePatches } from './hooks/usePatches';
import { useProject } from './hooks/useProject';
import Header from './components/layout/Header';
import Footer from './components/layout/Footer';
import TabLayout from './components/layout/TabLayout';
import ConsoleTab from './components/tabs/ConsoleTab';
import PanelTab from './components/tabs/PanelTab';
import ProjectTab from './components/tabs/ProjectTab';
import AgentsTab from './components/tabs/AgentsTab';
import ProvidersTab from './components/tabs/ProvidersTab';
import ModelsTab from './components/tabs/ModelsTab';
import MDTab from './components/tabs/MDTab';
import CodeTab from './components/tabs/CodeTab';
import LogsTab from './components/tabs/LogsTab';
import TasksTab from './components/tabs/TasksTab';
import PatchesTab from './components/tabs/PatchesTab';
import { restartSystem as restartSystemApi } from './services/api';

export default function App() {
  // === Хуки состояния ===
  const { logs, addLog } = useLogs();
  const { codeIssues, fixCodeIssue, fixAll } = useCodeIssues();
  const {
    taskList, newTaskText, setNewTaskText,
    newTaskPriority, setNewTaskPriority,
    newTaskCategory, setNewTaskCategory,
    addTask, toggleTask, deleteTask,
    codeTasks, generalTasks, completedTasks,
  } = useTasks();
  const {
    agents, showAgentStore, setShowAgentStore,
    toggleAgent, importAgent,
  } = useAgents();
  const {
    consolePrompt, setConsolePrompt, consoleLoading,
    providerMode, setProviderMode, selectedModel, setSelectedModel, runAiTask,
  } = useConsole(addLog);
  const {
    selectedMDFile, mdContent, setMdContent, mdFileExists,
    loadRealMDFile, saveRealMDFile,
  } = useMD();
  const {
    ollamaUrl, setOllamaUrl, providers, setProviders,
    ollamaStatus, ollamaModels, ollamaProcesses,
    installedModels, newModelName, setNewModelName, isPulling, pullModel,
  } = useOllama();
  const {
    patches, patchStats, selectedPatch, patchPreview, applyingPatch,
    patchFilter, setPatchFilter, patchLog,
    previewPatch, applyPatch, rollbackLastPatch,
    archivePatch, deletePatch, applyAllPending,
    setSelectedPatch, setPatchPreview,
  } = usePatches(addLog);
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
    selectedProjectFile, setSelectedProjectFile,
    projectFileContent, projectFileLoading,
    showPreviewModal, setShowPreviewModal,
    filteredProjectFiles,
    scanProject, openProjectFilePreview, bulkAction,
  } = useProject();

  // === Локальное состояние ===
  const [activeTab, setActiveTab] = useState<TabId>(() => {
    const saved = storage.get(STORAGE_KEYS.ACTIVE_TAB) as TabId | null;
    return saved || 'console';
  });
  const [currentTime, setCurrentTime] = useState(new Date());
  const [restarting, setRestarting] = useState(false);
  const [providerFilter, setProviderFilter] = useState<'all' | 'online' | 'offline'>('all');

  // === Эффекты ===
  useEffect(() => {
    storage.set(STORAGE_KEYS.ACTIVE_TAB, activeTab);
  }, [activeTab]);

  useEffect(() => {
    const timer = setInterval(() => setCurrentTime(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    if ('scrollRestoration' in history) {
      history.scrollRestoration = 'manual';
    }
    if (activeTab === 'project' && projectFiles.length > 0) {
      const saved = storage.get(STORAGE_KEYS.SCROLL_PROJECT);
      if (saved) {
        window.scrollTo({ top: parseInt(saved, 10), behavior: 'auto' });
        storage.remove(STORAGE_KEYS.SCROLL_PROJECT);
      }
    }
    if (activeTab === 'patches' && patches.length > 0) {
      const saved = storage.get(STORAGE_KEYS.SCROLL_PATCHES);
      if (saved) {
        window.scrollTo({ top: parseInt(saved, 10), behavior: 'auto' });
        storage.remove(STORAGE_KEYS.SCROLL_PATCHES);
      }
    }
  }, [activeTab, projectFiles, patches]);

  // === Обработчики ===
  const toggleProvider = (name: string) => {
    setProviders(prev => prev.map(p => (p.name === name ? { ...p, enabled: !p.enabled } : p)));
  };

  const handleRestart = async () => {
    if (!confirm('Перезапустить всю систему?\n\nPython и React будут перезапущены автоматически.')) return;
    setRestarting(true);
    try {
      const data = await restartSystemApi();
      if (data.success) {
        alert(data.message);
        setTimeout(() => window.location.reload(), 8000);
      } else {
        alert('Ошибка: ' + data.error);
      }
    } catch {
      alert('Ошибка сети. Система, возможно, перезапускается...');
      setTimeout(() => window.location.reload(), 8000);
    } finally {
      setRestarting(false);
    }
  };

  // === Рендер ===
  return (
    <div className="min-h-screen bg-gray-950 text-white flex flex-col text-base">
      <Header
        agents={agents}
        providers={providers}
        installedModels={installedModels}
        patchStats={patchStats}
        codeIssues={codeIssues}
        completedTasks={completedTasks}
        taskList={taskList}
        projectStats={projectStats}
        ollamaStatus={ollamaStatus}
        ollamaModels={ollamaModels}
        ollamaProcesses={ollamaProcesses}
        restarting={restarting}
        onRestart={handleRestart}
        setActiveTab={setActiveTab}
      />

      <TabLayout activeTab={activeTab}>
        {activeTab === 'console' && (
          <ConsoleTab
            consolePrompt={consolePrompt}
            setConsolePrompt={setConsolePrompt}
            consoleLoading={consoleLoading}
            providerMode={providerMode}
            setProviderMode={setProviderMode}
            selectedModel={selectedModel}
            setSelectedModel={setSelectedModel}
            installedModels={installedModels}
            ollamaUrl={ollamaUrl}
            setOllamaUrl={setOllamaUrl}
            runAiTask={runAiTask}
          />
        )}

        {activeTab === 'panel' && (
          <PanelTab
            agents={agents}
            providers={providers}
            installedModels={installedModels}
            patchStats={patchStats}
          />
        )}

        {activeTab === 'project' && (
          <ProjectTab
            projectFiles={projectFiles}
            projectStats={projectStats}
            projectLoading={projectLoading}
            projectSearch={projectSearch}
            setProjectSearch={setProjectSearch}
            projectDuplicatesOnly={projectDuplicatesOnly}
            setProjectDuplicatesOnly={setProjectDuplicatesOnly}
            projectImportantOnly={projectImportantOnly}
            setProjectImportantOnly={setProjectImportantOnly}
            projectFilters={projectFilters}
            toggleFilter={toggleFilter}
            clearFilters={clearFilters}
            sortField={sortField}
            sortDir={sortDir}
            toggleSort={toggleSort}
            selectedFiles={selectedFiles}
            toggleFileSelection={toggleFileSelection}
            selectAll={selectAll}
            deselectAll={deselectAll}
            cleanupMode={cleanupMode}
            setCleanupMode={setCleanupMode}
            history={history}
            rollbackLast={rollbackLast}
            archiveFiles={archiveFiles}
            showArchiveModal={showArchiveModal}
            setShowArchiveModal={setShowArchiveModal}
            loadArchive={loadArchive}
            restoreFile={restoreFile}
            selectedProjectFile={selectedProjectFile}
            projectFileContent={projectFileContent}
            projectFileLoading={projectFileLoading}
            showPreviewModal={showPreviewModal}
            setShowPreviewModal={setShowPreviewModal}
            filteredProjectFiles={filteredProjectFiles}
            scanProject={scanProject}
            openProjectFilePreview={openProjectFilePreview}
            bulkAction={bulkAction}
          />
        )}

        {activeTab === 'agents' && (
          <AgentsTab
            agents={agents}
            showAgentStore={showAgentStore}
            setShowAgentStore={setShowAgentStore}
            toggleAgent={toggleAgent}
            importAgent={importAgent}
            agentStore={agentStore}
          />
        )}

        {activeTab === 'providers' && (
          <ProvidersTab
            providers={providers}
            providerFilter={providerFilter}
            setProviderFilter={setProviderFilter}
            ollamaStatus={ollamaStatus}
            ollamaUrl={ollamaUrl}
            setOllamaUrl={setOllamaUrl}
            ollamaProcesses={ollamaProcesses}
            toggleProvider={toggleProvider}
            setActiveTab={setActiveTab}
            installedModelsCount={installedModels.length}
          />
        )}

        {activeTab === 'models' && (
          <ModelsTab
            ollamaStatus={ollamaStatus}
            newModelName={newModelName}
            setNewModelName={setNewModelName}
            isPulling={isPulling}
            pullModel={pullModel}
            installedModels={installedModels}
            setConsolePrompt={setConsolePrompt}
            setActiveTab={setActiveTab}
          />
        )}

        {activeTab === 'md' && (
          <MDTab
            selectedMDFile={selectedMDFile}
            mdContent={mdContent}
            setMdContent={setMdContent}
            mdFileExists={mdFileExists}
            loadRealMDFile={loadRealMDFile}
            saveRealMDFile={saveRealMDFile}
          />
        )}

        {activeTab === 'code' && (
          <CodeTab
            codeIssues={codeIssues}
            fixCodeIssue={fixCodeIssue}
            fixAll={fixAll}
          />
        )}

        {activeTab === 'logs' && <LogsTab logs={logs} />}

        {activeTab === 'tasks' && (
          <TasksTab
            taskList={taskList}
            newTaskText={newTaskText}
            setNewTaskText={setNewTaskText}
            newTaskPriority={newTaskPriority}
            setNewTaskPriority={setNewTaskPriority}
            newTaskCategory={newTaskCategory}
            setNewTaskCategory={setNewTaskCategory}
            addTask={addTask}
            toggleTask={toggleTask}
            deleteTask={deleteTask}
            codeTasks={codeTasks}
            generalTasks={generalTasks}
          />
        )}

        {activeTab === 'patches' && (
          <PatchesTab
            patches={patches}
            patchStats={patchStats}
            selectedPatch={selectedPatch}
            patchPreview={patchPreview}
            applyingPatch={applyingPatch}
            patchFilter={patchFilter}
            setPatchFilter={setPatchFilter}
            patchLog={patchLog}
            previewPatch={previewPatch}
            applyPatch={applyPatch}
            rollbackLastPatch={rollbackLastPatch}
            archivePatch={archivePatch}
            deletePatch={deletePatch}
            applyAllPending={applyAllPending}
            setSelectedPatch={setSelectedPatch}
            setPatchPreview={setPatchPreview}
          />
        )}
      </TabLayout>

      <Footer setActiveTab={setActiveTab} />
    </div>
  );
}
