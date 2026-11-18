# upgrade_cleanup_ui.py
import re

file_path = "src/App.tsx"
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

print("🔍 Модернизирую UI вкладки Проект...")

# 1. Добавляем состояние для режима очистки
old_state = "const [projectDuplicatesOnly, setProjectDuplicatesOnly] = useState(false);"
new_state = """const [projectDuplicatesOnly, setProjectDuplicatesOnly] = useState(false);
  const [cleanupMode, setCleanupMode] = useState(false);"""

if old_state in content and "cleanupMode" not in content:
    content = content.replace(old_state, new_state)
    print("✅ Добавлено состояние cleanupMode")

# 2. Добавляем функцию массовой очистки
cleanup_func = """
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
"""

if "const applyCleanup = async ()" not in content:
    content = content.replace("const scanProject = async () => {", cleanup_func + "\n  const scanProject = async () => {")
    print("✅ Добавлена функция applyCleanup")

# 3. Модифицируем отображение списка файлов (добавляем бейдж рекомендации)
# Ищем место, где рендерится карточка файла
old_card_render = """                      <div className="flex gap-4 mt-1 text-xs text-gray-500">
                        <span>📏 {file.size_human}</span>
                        <span>🕐 {new Date(file.modified).toLocaleString('ru-RU')}</span>
                      </div>"""

new_card_render = """                      <div className="flex gap-4 mt-1 text-xs text-gray-500">
                        <span>📏 {file.size_human}</span>
                        <span>🕐 {new Date(file.modified).toLocaleString('ru-RU')}</span>
                      </div>
                      {file.cleanup && file.cleanup.action !== 'keep' && (
                        <div className={`mt-2 px-2 py-1 rounded text-[11px] font-bold flex items-center gap-1 ${
                          file.cleanup.action === 'delete' ? 'bg-red-500/20 text-red-400 border border-red-500/30' : 'bg-yellow-500/20 text-yellow-400 border border-yellow-500/30'
                        }`}>
                          <span>{file.cleanup.action === 'delete' ? '🗑 УДАЛИТЬ' : '⚠️ ПРОВЕРИТЬ'}</span>
                          <span className="font-normal opacity-80">— {file.cleanup.reason}</span>
                        </div>
                      )}"""

if old_card_render in content and "file.cleanup.action" not in content:
    content = content.replace(old_card_render, new_card_render)
    print("✅ Добавлен визуальный бейдж рекомендации")

# 4. Добавляем кнопку "🧹 Применить очистку" в заголовок вкладки
old_header = """              <button onClick={scanProject} disabled={projectLoading} className="px-4 py-2 rounded-lg bg-gradient-to-r from-emerald-500 to-cyan-500 text-white text-sm font-bold disabled:opacity-50">
                {projectLoading ? '⏳ Сканирование...' : '🔄 Пересканировать'}
              </button>"""

new_header = """              <div className="flex gap-2">
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

if old_header in content and "Режим очистки" not in content:
    content = content.replace(old_header, new_header)
    print("✅ Добавлена кнопка управления режимом очистки")

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("🎉 UI обновлен! Обнови браузер (Ctrl+F5).")