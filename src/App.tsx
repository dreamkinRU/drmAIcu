import { useState, useEffect, useRef } from 'react';
import { TabId } from './types';
import { agentStore } from './utils/constants';
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
import MDTab from './components/tabs/MDTab';
import CodeTab from './components/tabs/CodeTab';
import LogsTab from './components/tabs/LogsTab';
import TasksTab from './components/tabs/TasksTab';
import PatchesTab from './components/tabs/PatchesTab';
import PluginsTab from './components/tabs/PluginsTab';
import RepositoriesTab from './components/tabs/RepositoriesTab';
import UpdateWizardTab from './components/tabs/UpdateWizardTab';
import { usePlugins } from './hooks/usePlugins';
import { restartSystem as restartSystemApi, loadAppVersionApi } from './services/api';

export default function App() {
  // === Хуки состояния ===
  const { logs, addLog, clearIssues } = useLogs();
  // Версия оболочки — из /api/version (единый источник version.py), без хардкода в UI.
  const [appVersion, setAppVersion] = useState<string | null>(null);
  const [incomingRequest, setIncomingRequest] = useState(0);
  const [incomingBusy, setIncomingBusy] = useState(false);
  useEffect(() => { void loadAppVersionApi().then(v => setAppVersion(v)); }, []);
  const pluginCtl = usePlugins();
  const { codeIssues, fixCodeIssue, fixAll } = useCodeIssues();
  const {
    taskList, newTaskText, setNewTaskText,
    newTaskPriority, setNewTaskPriority,
    newTaskCategory, setNewTaskCategory,
    addTask, toggleTask, deleteTask,
    codeTasks, generalTasks, completedTasks,
  } = useTasks();
  const {
    agents, pipelines, addPipeline, deletePipeline,
    activeAgentId, setActiveAgentId, activeAgent,
    activePipelineId, setActivePipelineId, activePipeline,
    showAgentStore, setShowAgentStore,
    toggleAgent, setJudgeAgent, updateAgent, recordAgentStats, addAgent, deleteAgent, importAgent,
  } = useAgents();
  const {
    consolePrompt, setConsolePrompt, consoleLoading,
    providerMode, setProviderMode, selectedModel, setSelectedModel,
    bionicUrl, setBionicUrl, bionicModels,
    lmstudioUrl, setLmstudioUrl, lmstudioModels,
    strataUrl, setStrataUrl, strataModels,
    contextFiles, setContextFiles,
    includeLogs, setIncludeLogs,
    includeCodeIssues, setIncludeCodeIssues,
    exportingPatch, hasPatchCandidate, exportPatchToPatches,
    lastPrompt, consoleMetrics, runAiTask, stopAiTask, retryLastTask,
  } = useConsole(addLog, activeAgent, agents, activeAgentId, activePipeline, codeIssues, recordAgentStats);
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
    if (!saved || saved === 'models') return 'console';
    return saved;
  });
  const [restarting, setRestarting] = useState(false);
  const [providerFilter, setProviderFilter] = useState<'all' | 'online' | 'offline'>('all');
  const [newPatchPopup, setNewPatchPopup] = useState<any | null>(null);
  const seenPatchFilesRef = useRef<Set<string>>(new Set());
  const returnTabRef = useRef<TabId | null>(null);

  // === Эффекты ===
  useEffect(() => {
    storage.set(STORAGE_KEYS.ACTIVE_TAB, activeTab);
  }, [activeTab]);

  useEffect(() => {
    if (!patches || patches.length === 0) return;
    const unseenPending = patches.find(
      (p: any) => !p.is_applied && !p.error && !seenPatchFilesRef.current.has(p.filename)
    );
    if (unseenPending && !newPatchPopup) {
      seenPatchFilesRef.current.add(unseenPending.filename);
      setNewPatchPopup(unseenPending);
    }
  }, [patches, newPatchPopup]);

  // ПРИМЕЧАНИЕ: секундный таймер часов удалён — он вызывал setstate раз в 1 c и
  // перерисовывал всё дерево приложения (дрожание элементов страницы).
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

  const triggerSilentRestart = async () => {
    setRestarting(true);
    try {
      await restartSystemApi();
    } catch {
      // сервер уже перезапускается
    }
    const waitAndReload = () => {
      setTimeout(async () => {
        try {
          const r = await fetch('/api/status');
          if (r.ok) {
            window.location.reload();
            return;
          }
        } catch {}
        waitAndReload();
      }, 2000);
    };
    setTimeout(waitAndReload, 4000);
  };

  const applyPatchWithAutoRestart = async (patch: any) => {
    await Promise.resolve(applyPatch(patch));
    const needsRestart =
      (typeof patch?.target_file === 'string' && patch.target_file.includes('.py')) ||
      (Array.isArray(patch?.operations) && patch.operations.some((o: any) => String(o?.target_file || '').endsWith('.py')));
    if (needsRestart) {
      triggerSilentRestart();
    }
  };

  const handleRestart = async () => {
    triggerSilentRestart();
  };

  // === Рендер ===
  return (
    <div className="min-h-screen bg-gray-950 text-white flex flex-col text-base">
      <Header
        activeTab={activeTab}
        agents={agents}
        providers={providers}
        patchStats={patchStats}
        codeIssues={codeIssues}
        completedTasks={completedTasks}
        taskList={taskList}
        projectStats={projectStats}
        ollamaStatus={ollamaStatus}
        ollamaModels={ollamaModels}
        version={appVersion}
        onIncomingUpdate={() => { setActiveTab('updates'); setIncomingRequest(n => n + 1); }}
        incomingBusy={incomingBusy}
        applyingPatch={applyingPatch}
        setActiveTab={setActiveTab}
      />

      <TabLayout activeTab={activeTab}>
        {activeTab === 'console' && (
          <ConsoleTab
            consolePrompt={consolePrompt}
            setConsolePrompt={setConsolePrompt}
            consoleLoading={consoleLoading}
            agents={agents}
            pipelines={pipelines}
            projectFiles={projectFiles}
            codeIssues={codeIssues}
            contextFiles={contextFiles}
            setContextFiles={setContextFiles}
            includeLogs={includeLogs}
            setIncludeLogs={setIncludeLogs}
            includeCodeIssues={includeCodeIssues}
            setIncludeCodeIssues={setIncludeCodeIssues}
            exportingPatch={exportingPatch}
            hasPatchCandidate={hasPatchCandidate}
            exportPatchToPatches={exportPatchToPatches}
            activeAgentId={activeAgentId}
            setActiveAgentId={setActiveAgentId}
            activePipelineId={activePipelineId}
            setActivePipelineId={setActivePipelineId}
            providerMode={providerMode}
            setProviderMode={setProviderMode}
            selectedModel={selectedModel}
            setSelectedModel={setSelectedModel}
            installedModels={installedModels}
            bionicModels={bionicModels}
            lmstudioModels={lmstudioModels}
            strataModels={strataModels}
            lastPrompt={lastPrompt}
            consoleMetrics={consoleMetrics}
            runAiTask={runAiTask}
            stopAiTask={stopAiTask}
            retryLastTask={retryLastTask}
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
            pipelines={pipelines}
            addPipeline={addPipeline}
            deletePipeline={deletePipeline}
            activeAgentId={activeAgentId}
            setActiveAgentId={setActiveAgentId}
            activePipelineId={activePipelineId}
            setActivePipelineId={setActivePipelineId}
            setActiveTab={setActiveTab}
            showAgentStore={showAgentStore}
            setShowAgentStore={setShowAgentStore}
            toggleAgent={toggleAgent}
            setJudgeAgent={setJudgeAgent}
            updateAgent={updateAgent}
            addAgent={addAgent}
            deleteAgent={deleteAgent}
            importAgent={importAgent}
            agentStore={agentStore}
            installedModels={installedModels}
            bionicModels={bionicModels}
            lmstudioModels={lmstudioModels}
            strataModels={strataModels}
          />
        )}

        {activeTab === 'providers' && (
          <ProvidersTab
            providers={providers}
            providerFilter={providerFilter}
            setProviderFilter={setProviderFilter}
            providerMode={providerMode}
            setProviderMode={setProviderMode}
            selectedModel={selectedModel}
            setSelectedModel={setSelectedModel}
            installedModels={installedModels}
            bionicUrl={bionicUrl}
            setBionicUrl={setBionicUrl}
            bionicModels={bionicModels}
            lmstudioUrl={lmstudioUrl}
            setLmstudioUrl={setLmstudioUrl}
            lmstudioModels={lmstudioModels}
            strataUrl={strataUrl}
            setStrataUrl={setStrataUrl}
            strataModels={strataModels}
            ollamaStatus={ollamaStatus}
            ollamaUrl={ollamaUrl}
            setOllamaUrl={setOllamaUrl}
            ollamaProcesses={ollamaProcesses}
            toggleProvider={toggleProvider}
            setActiveTab={setActiveTab}
            installedModelsCount={installedModels.length}
            newModelName={newModelName}
            setNewModelName={setNewModelName}
            isPulling={isPulling}
            pullModel={pullModel}
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

        {activeTab === 'logs' && <LogsTab logs={logs} onClearIssues={clearIssues} />}

        {activeTab === 'plugins' && (
          <PluginsTab
            dataWarnings={pluginCtl.dataWarnings}
            plugins={pluginCtl.plugins}
            catalog={pluginCtl.catalog}
            confirmations={pluginCtl.confirmations}
            activity={pluginCtl.activity}
            loading={pluginCtl.loading}
            notice={pluginCtl.notice}
            setNotice={pluginCtl.setNotice}
            refresh={pluginCtl.refresh}
            install={pluginCtl.install}
            enable={pluginCtl.enable}
            disable={pluginCtl.disable}
            uninstall={pluginCtl.uninstall}
            grantAll={pluginCtl.grantAll}
            decide={pluginCtl.decide}
            addLog={addLog}
          />
        )}

        {activeTab === 'repositories' && (
          <RepositoriesTab
            plugins={pluginCtl.plugins}
            refresh={pluginCtl.refresh}
            setActiveTab={setActiveTab}
            addLog={addLog}
          />
        )}

        <div hidden={activeTab !== 'updates'}>
          <UpdateWizardTab appVersion={appVersion} visible={activeTab === 'updates'} incomingRequest={incomingRequest} onBusyChange={setIncomingBusy} onOpenRepositories={() => setActiveTab('repositories')} />
        </div>

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
            applyPatch={applyPatchWithAutoRestart}
            rollbackLastPatch={rollbackLastPatch}
            archivePatch={archivePatch}
            deletePatch={deletePatch}
            applyAllPending={applyAllPending}
            setSelectedPatch={setSelectedPatch}
            setPatchPreview={setPatchPreview}
          />
        )}
      </TabLayout>

      {newPatchPopup && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
          <div className="w-full max-w-md rounded-xl border border-emerald-500/40 bg-gray-900 p-5 shadow-2xl space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-bold text-emerald-400 uppercase tracking-wider">
                🔄 Обнаружен новый патч #{newPatchPopup.patch_id}
              </h3>
              <button
                type="button"
                onClick={() => setNewPatchPopup(null)}
                className="text-gray-400 hover:text-white text-sm px-2 py-1 rounded hover:bg-gray-800"
              >
                ✕
              </button>
            </div>
            <div className="space-y-1 text-sm">
              <div className="font-bold text-white truncate">{newPatchPopup.target_file}</div>
              {newPatchPopup.description && (
                <p className="text-gray-400 text-xs">{newPatchPopup.description}</p>
              )}
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={() => setNewPatchPopup(null)}
                disabled={applyingPatch}
                className="px-4 py-2 rounded-lg text-xs font-bold bg-gray-700 hover:bg-gray-600 text-gray-300 disabled:opacity-50"
              >
                Позже
              </button>
              <button
                type="button"
                disabled={applyingPatch}
                onClick={async () => {
                  const targetPatch = newPatchPopup;
                  returnTabRef.current = activeTab;
                  setNewPatchPopup(null);
                  await applyPatchWithAutoRestart(targetPatch);
                  if (returnTabRef.current) {
                    setActiveTab(returnTabRef.current);
                    returnTabRef.current = null;
                  }
                }}
                className="px-4 py-2 rounded-lg text-xs font-bold bg-gradient-to-r from-emerald-500 to-cyan-500 hover:from-emerald-600 hover:to-cyan-600 text-white disabled:opacity-50"
              >
                {applyingPatch ? '⏳ Применение...' : '✅ Применить'}
              </button>
            </div>
          </div>
        </div>
      )}

      {restarting && (
        <div className="fixed bottom-16 right-5 z-50 flex items-center gap-2.5 px-4 py-2.5 rounded-xl bg-orange-500/20 border border-orange-500/50 text-orange-300 text-sm font-bold shadow-2xl backdrop-blur-md animate-pulse">
          <span>🔄</span>
          <span>Выполняется перезагрузка панели...</span>
        </div>
      )}

      <Footer
        setActiveTab={setActiveTab}
        ollamaProcesses={ollamaProcesses}
        restarting={restarting}
        onRestart={handleRestart}
      />
    </div>
  );
}
