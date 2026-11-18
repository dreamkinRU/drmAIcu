import os

def upgrade_main():
    file_path = "main.py"
    if not os.path.exists(file_path):
        print("❌ main.py не найден")
        return False

    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    if "def get_cleanup_recommendation(f):" in content:
        print("✅ main.py уже содержит умный анализатор")
        return True

    print("🔧 Модернизирую main.py...")
    
    # 1. Вставляем функцию анализа перед scan_project
    analysis_func = """
def get_cleanup_recommendation(f):
    name = f['filename']
    rel = f['path']
    size = f['size']
    ext = f['extension']
    
    if size == 0 and ext not in ('.gitkeep', '.keep'):
        return {'action': 'delete', 'reason': 'Файл абсолютно пустой (0 байт)'}
    if name in ('.DS_Store', 'Thumbs.db', 'desktop.ini', 'ehthumbs.db'):
        return {'action': 'delete', 'reason': 'Скрытый системный мусор ОС'}
    if ext in ('.tmp', '.pyc', '.pyo') or '__pycache__' in rel or '.vite' in rel:
        return {'action': 'delete', 'reason': 'Временный файл или кэш компиляции'}
    if __import__('re').search(r'_(old|backup|v\\d+|copy)\\.', name, __import__('re').IGNORECASE) and '/' not in rel and '\\\\' not in rel:
        return {'action': 'delete', 'reason': 'Устаревшая резервная копия в корне проекта'}
    if ext in ('.log', '.txt') and size > 5 * 1024 * 1024:
        return {'action': 'review', 'reason': f'Очень большой файл ({f["size_human"]}). Возможно, старый лог.'}
    if f.get('is_duplicate') and f.get('duplicates'):
        primary = f['duplicates'][0]
        if len(rel) > len(primary):
            return {'action': 'delete', 'reason': f'Дубликат. Оригинал: {primary}'}
        else:
            return {'action': 'review', 'reason': f'Имеет дубликат в: {", ".join(f["duplicates"][:2])}'}
    if __import__('re').match(r'^(test|temp|tmp|untitled|new_file|copy)\\..+', name, __import__('re').IGNORECASE):
        return {'action': 'review', 'reason': 'Подозрительное временное имя файла в корне'}
    
    return {'action': 'keep', 'reason': 'Файл выглядит корректно'}

"""
    content = content.replace("def scan_project():", analysis_func + "def scan_project():")

    # 2. Модифицируем создание словаря файла
    old_append = """                files.append({'path': rel, 'filename': n, 'size': st.st_size,
                              'size_human': human(st.st_size),
                              'modified': datetime.fromtimestamp(st.st_mtime).isoformat(),
                              'category': cat, 'hash': h,
                              'is_critical': cat == 'critical', 'is_important': rel in imp,
                              'extension': os.path.splitext(n)[1].lower(),
                              'icon': ICONS.get(os.path.splitext(n)[1].lower(), 'FILE'),
                              'is_duplicate': False, 'duplicates': []})"""
    
    new_append = """                rec = get_cleanup_recommendation({'filename': n, 'path': rel, 'size': st.st_size, 'extension': os.path.splitext(n)[1].lower(), 'is_duplicate': False, 'duplicates': []})
                files.append({'path': rel, 'filename': n, 'size': st.st_size,
                              'size_human': human(st.st_size),
                              'modified': datetime.fromtimestamp(st.st_mtime).isoformat(),
                              'category': cat, 'hash': h,
                              'is_critical': cat == 'critical', 'is_important': rel in imp,
                              'extension': os.path.splitext(n)[1].lower(),
                              'icon': ICONS.get(os.path.splitext(n)[1].lower(), 'FILE'),
                              'is_duplicate': False, 'duplicates': [],
                              'cleanup': rec})"""
    
    if old_append in content:
        content = content.replace(old_append, new_append)

    # 3. Обновляем статистику
    old_stats = """          'trash_count': len([f for f in files if f['category'] == 'trash']),
          'backup_count': len([f for f in files if f['category'] == 'backup'])}"""
    
    new_stats = """          'trash_count': len([f for f in files if f['category'] == 'trash']),
          'backup_count': len([f for f in files if f['category'] == 'backup']),
          'cleanup_delete_count': len([f for f in files if f.get('cleanup', {}).get('action') == 'delete']),
          'cleanup_review_count': len([f for f in files if f.get('cleanup', {}).get('action') == 'review'])}"""
          
    if old_stats in content:
        content = content.replace(old_stats, new_stats)

    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("✅ main.py успешно обновлен!")
    return True

def upgrade_ui():
    file_path = "src/App.tsx"
    if not os.path.exists(file_path):
        print("❌ src/App.tsx не найден")
        return False

    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    if "cleanupMode" in content:
        print("✅ App.tsx уже содержит элементы умной очистки")
        return True

    print("🔧 Модернизирую src/App.tsx...")

    # 1. Добавляем состояние
    content = content.replace(
        "const [projectDuplicatesOnly, setProjectDuplicatesOnly] = useState(false);",
        "const [projectDuplicatesOnly, setProjectDuplicatesOnly] = useState(false);\n  const [cleanupMode, setCleanupMode] = useState(false);"
    )

    # 2. Добавляем функцию очистки перед scanProject
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

    # 3. Добавляем бейдж рекомендации в карточку файла
    old_card = """                      <div className="flex gap-4 mt-1 text-xs text-gray-500">
                        <span>📏 {file.size_human}</span>
                        <span>🕐 {new Date(file.modified).toLocaleString('ru-RU')}</span>
                      </div>"""
    
    new_card = """                      <div className="flex gap-4 mt-1 text-xs text-gray-500">
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
    
    if old_card in content:
        content = content.replace(old_card, new_card)

    # 4. Добавляем кнопку режима очистки
    old_header_btn = """              <button onClick={scanProject} disabled={projectLoading} className="px-4 py-2 rounded-lg bg-gradient-to-r from-emerald-500 to-cyan-500 text-white text-sm font-bold disabled:opacity-50">
                {projectLoading ? '⏳ Сканирование...' : '🔄 Пересканировать'}
              </button>"""
              
    new_header_btn = """              <div className="flex gap-2">
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
              
    if old_header_btn in content:
        content = content.replace(old_header_btn, new_header_btn)

    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("✅ src/App.tsx успешно обновлен!")
    return True

if __name__ == "__main__":
    print("🚀 Запуск умной модернизации системы очистки...\n")
    ok1 = upgrade_main()
    ok2 = upgrade_ui()
    if ok1 and ok2:
        print("\n🎉 ГОТОВО! Перезапусти лаунчер и обнови браузер (Ctrl+F5).")
        print("   Перейди во вкладку '🗂 Проект' и нажми '🧹 Режим очистки'.")
    else:
        print("\n⚠️ Возникли проблемы при обновлении. Проверь вывод выше.")