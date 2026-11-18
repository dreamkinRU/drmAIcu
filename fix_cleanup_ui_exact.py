import os

file_path = "src/App.tsx"
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

print("🔧 Исправляю отображение бейджа очистки в App.tsx...")

# 1. ТОЧНАЯ замена блока карточки (используем реальный код из твоего вывода)
old_block = """                      <div className="flex gap-4 mt-1 text-xs text-gray-500 flex-wrap">
                        <span>📏 {file.size_human}</span>
                        <span>🕐 {new Date(file.modified).toLocaleString('ru-RU')}</span>
                        {file.is_duplicate && file.duplicates.length > 0 && <span className="text-purple-400">Дубли: {file.duplicates.join(', ')}</span>}
                      </div>"""

new_block = """                      <div className="flex gap-4 mt-1 text-xs text-gray-500 flex-wrap">
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
                      )}"""

if old_block in content:
    content = content.replace(old_block, new_block)
    print("✅ Бейдж очистки успешно добавлен в карточку файла!")
else:
    print("⚠️ Не удалось найти точный блок. Возможно, он уже добавлен.")

# 2. Добавляем состояние cleanupMode, если его нет
if "const [cleanupMode, setCleanupMode]" not in content:
    content = content.replace(
        "const [projectDuplicatesOnly, setProjectDuplicatesOnly] = useState(false);",
        "const [projectDuplicatesOnly, setProjectDuplicatesOnly] = useState(false);\n  const [cleanupMode, setCleanupMode] = useState(false);"
    )
    print("✅ Добавлено состояние cleanupMode")

# 3. Добавляем функцию applyCleanup, если её нет
if "const applyCleanup = async ()" not in content:
    cleanup_func = """  const applyCleanup = async () => {
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

"""
    content = content.replace("const scanProject = async () => {", cleanup_func + "  const scanProject = async () => {")
    print("✅ Добавлена функция applyCleanup")

# 4. Добавляем кнопку "Режим очистки", если её нет
if "Режим очистки" not in content:
    old_btn = """              <button onClick={scanProject} disabled={projectLoading} className="px-4 py-2 rounded-lg bg-gradient-to-r from-emerald-500 to-cyan-500 text-white text-sm font-bold disabled:opacity-50">
                {projectLoading ? '⏳ Сканирование...' : '🔄 Пересканировать'}
              </button>"""
              
    new_btn = """              <div className="flex gap-2">
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
              </div>"""
              
    if old_btn in content:
        content = content.replace(old_btn, new_btn)
        print("✅ Добавлена кнопка 'Режим очистки'")

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("\n🎉 UI обновлен! Обнови браузер (Ctrl+F5).")