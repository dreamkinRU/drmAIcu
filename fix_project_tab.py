import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def main():
    print("=== Исправление вкладки Проект ===")
    
    # 1. Исправляем импорты в useProject.ts
    use_project_path = os.path.join(BASE_DIR, 'src', 'hooks', 'useProject.ts')
    if os.path.exists(use_project_path):
        with open(use_project_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Исправляем пути импорта на правильные (на один уровень вверх)
        content = content.replace("from '../../types'", "from '../types'")
        content = content.replace("from '../../services/api'", "from '../services/api'")
        content = content.replace("from '../../utils/storage'", "from '../utils/storage'")
        
        with open(use_project_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print("✅ Исправлены импорты в src/hooks/useProject.ts")
    else:
        print("⚠️ Файл src/hooks/useProject.ts не найден")

    # 2. Исправляем App.tsx
    app_tsx_path = os.path.join(BASE_DIR, 'src', 'App.tsx')
    if os.path.exists(app_tsx_path):
        with open(app_tsx_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Заменяем старую деструктуризацию useProject на новую
        old_destructure = """  const {
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
    selectedProjectFile, projectFileContent, projectFileLoading,
    showPreviewModal, setShowPreviewModal,
    filteredProjectFiles,
    scanProject, openProjectFilePreview,
    archiveProjectFile, deleteProjectFile, toggleImportant, applyCleanup,
  } = useProject();"""
        
        new_destructure = """  const {
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
  } = useProject();"""
        
        if old_destructure in content:
            content = content.replace(old_destructure, new_destructure)
            print("✅ Исправлена деструктуризация useProject в src/App.tsx")
        else:
            print("ℹ️ Старая деструктуризация useProject не найдена (возможно, уже исправлена)")

        # Заменяем пропсы ProjectTab на правильные
        old_props = """        {activeTab === 'project' && (
          <ProjectTab
            projectFiles={projectFiles}
            projectStats={projectStats}
            projectLoading={projectLoading}
            projectFilter={projectFilter}
            setProjectFilter={setProjectFilter}
            projectSearch={projectSearch}
            setProjectSearch={setProjectSearch}
            projectDuplicatesOnly={projectDuplicatesOnly}
            setProjectDuplicatesOnly={setProjectDuplicatesOnly}
            projectImportantOnly={projectImportantOnly}
            setProjectImportantOnly={setProjectImportantOnly}
            cleanupMode={cleanupMode}
            setCleanupMode={setCleanupMode}
            showCritical={showCritical}
            setShowCritical={setShowCritical}
            showImportant={showImportant}
            setShowImportant={setShowImportant}
            showTrash={showTrash}
            setShowTrash={setShowTrash}
            showDuplicates={showDuplicates}
            setShowDuplicates={setShowDuplicates}
            filteredProjectFiles={filteredProjectFiles}
            scanProject={scanProject}
            openProjectFilePreview={openProjectFilePreview}
            archiveProjectFile={archiveProjectFile}
            deleteProjectFile={deleteProjectFile}
            toggleImportant={toggleImportant}
            applyCleanup={applyCleanup}
            selectedProjectFile={selectedProjectFile}
            projectFileContent={projectFileContent}
            projectFileLoading={projectFileLoading}
            showPreviewModal={showPreviewModal}
            setShowPreviewModal={setShowPreviewModal}
          />
        )}"""
        
        new_props = """        {activeTab === 'project' && (
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
        )}"""
        
        if old_props in content:
            content = content.replace(old_props, new_props)
            print("✅ Исправлены пропсы <ProjectTab /> в src/App.tsx")
        else:
            print("ℹ️ Старые пропсы <ProjectTab /> не найдены (возможно, уже исправлены)")
            
        with open(app_tsx_path, 'w', encoding='utf-8') as f:
            f.write(content)
    else:
        print("⚠️ Файл src/App.tsx не найден")

    print("\n🎉 ГОТОВО! Вкладка Проект исправлена.")
    print("Теперь выполните `npm run typecheck` чтобы убедиться, что ошибок TypeScript больше нет.")

if __name__ == '__main__':
    main()