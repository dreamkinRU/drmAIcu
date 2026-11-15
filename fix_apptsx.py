import os

file_path = "src/App.tsx"
backup_path = "backups/App.tsx_LATEST.bak"

# Восстанавливаем из бэкапа
if os.path.exists(backup_path):
    with open(backup_path, 'r', encoding='utf-8') as f:
        content = f.read()
    print("✅ Восстановлено из бэкапа")
else:
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    print("⚠️ Бэкап не найден, работаем с текущим файлом")

# 1. Добавляем состояние restarting
old_state = "const [projectDuplicatesOnly, setProjectDuplicatesOnly] = useState(false);"
new_state = old_state + "\n  const [restarting, setRestarting] = useState(false);"
content = content.replace(old_state, new_state)
print("✅ Добавлено состояние restarting")

# 2. Добавляем функцию restartSystem
func_code = """
  const restartSystem = async () => {
    if (!confirm('Перезапустить всю систему?\\n\\nPython и React будут перезапущены автоматически.')) return;
    setRestarting(true);
    try {
      const res = await fetch('/api/system/restart', { method: 'POST' });
      const data = await res.json();
      if (data.success) { alert(data.message); setTimeout(() => window.location.reload(), 8000); }
      else { alert('Ошибка: ' + data.error); }
    } catch (e) { alert('Ошибка сети. Система, возможно, перезапускается...'); setTimeout(() => window.location.reload(), 8000); }
    finally { setRestarting(false); }
  };
"""
old_func_anchor = "const scanProject = async () => {"
content = content.replace(old_func_anchor, func_code + "\n  " + old_func_anchor)
print("✅ Добавлена функция restartSystem")

# 3. Вставляем кнопку в шапку (после часов)
old_header = """              <div className="px-4 py-2 rounded-lg bg-gray-800/50 border-2 border-emerald-500/30">
                <span className="font-mono text-lg text-emerald-400 tabular-nums font-bold">{currentTime.toLocaleTimeString('ru-RU')}</span>
              </div>
            </div>
          </div>
        </div>"""

new_header = """              <div className="px-4 py-2 rounded-lg bg-gray-800/50 border-2 border-emerald-500/30">
                <span className="font-mono text-lg text-emerald-400 tabular-nums font-bold">{currentTime.toLocaleTimeString('ru-RU')}</span>
              </div>
              <Tooltip text="Перезапустить Python и React" position="bottom">
                <button onClick={restartSystem} disabled={restarting} className={`px-4 py-2 rounded-lg text-sm font-bold transition-all ${restarting ? 'bg-gray-700 text-gray-500 cursor-not-allowed' : 'bg-orange-500/20 border border-orange-500/50 text-orange-400 hover:bg-orange-500/30'}`}>
                  {restarting ? '⏳ Перезапуск...' : '🔄 Перезапуск'}
                </button>
              </Tooltip>
            </div>
          </div>
        </div>"""

content = content.replace(old_header, new_header)
print("✅ Вставлена кнопка в шапку")

# Записываем файл
with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("✅ Файл сохранён. Обнови браузер (Ctrl+F5)")