import os
import shutil
import py_compile

print("=== Прямое безопасное обновление main.py (Умная очистка проекта) ===\n")

# 1. Бэкап
shutil.copy2('main.py', 'main.py.backup_before_project_fix')
print("✅ Создан бэкап: main.py.backup_before_project_fix")

with open('main.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 2. Точный якорь из diag_pipeline.txt (строки 698-719)
old_category = """def category(name, rel, size):
    if name in CRIT_FILES or rel.replace('\\\\', '/').startswith(CRIT_DIRS):
        return 'critical'
    if name.endswith('.bak'):
        return 'backup'
    if size == 0 or name.endswith(('.tmp', '.pyc')):
        return 'trash'
    if name in ('.DS_Store', 'Thumbs.db', 'desktop.ini'):
        return 'trash'
    if name.endswith('.md'):
        return 'docs'
    if name.endswith(('.py', '.tsx', '.ts', '.jsx', '.js')):
        return 'code'
    if name.endswith(('.json', '.yaml', '.yml', '.ini', '.cfg')):
        return 'config'
    if name.endswith(('.bat', '.cmd', '.sh')):
        return 'scripts'
    if name.endswith(('.html', '.css')):
        return 'web'
    if name.endswith(('.log', '.txt')):
        return 'logs'
    return 'other'"""

new_functions = """def classify_file(name, rel, size):
    r = rel.replace('\\\\', '/').lower()
    n = name.lower()
    # Критическое ядро
    if name in CRIT_FILES or r.startswith(CRIT_DIRS):
        return {'category': 'critical', 'risk': 'critical', 'icon': 'lock',
                'reason': 'Критическое ядро системы. Удаление сломает приложение.', 'action': 'keep'}
    # Одноразовые скрипты миграции/фиксов — мусор
    import re as _re
    if _re.match(r'^(apply|fix|emergency|clean|restore|patch)_.*\\\\.py$', n):
        return {'category': 'trash', 'risk': 'low', 'icon': 'trash',
                'reason': 'Одноразовый скрипт миграции/фикса. Безопасно к удалению.', 'action': 'delete'}
    if n.startswith('diag_') or n.startswith('auto_fix') or n.startswith('final_') or n.startswith('make_perfect') or n.startswith('fix_all') or n.startswith('fix_backend') or n.startswith('create_audit') or n.startswith('generate_and_check') or n.startswith('patch_dryrun'):
        return {'category': 'trash', 'risk': 'low', 'icon': 'trash',
                'reason': 'Вспомогательный скрипт диагностики. Безопасно к удалению.', 'action': 'delete'}
    # Резервные копии
    if n.endswith('.bak'):
        return {'category': 'backup', 'risk': 'medium', 'icon': 'archive',
                'reason': 'Резервная копия. Можно архивировать.', 'action': 'archive'}
    # Мусор по размеру/расширению
    if size == 0 or n.endswith(('.tmp', '.pyc')) or n in ('.ds_store', 'thumbs.db', 'desktop.ini'):
        return {'category': 'trash', 'risk': 'low', 'icon': 'trash',
                'reason': 'Пустой файл или временный артефакт. Безопасно к удалению.', 'action': 'delete'}
    # Логи
    if n.endswith(('.log', '.txt')) and not n.endswith('requirements.txt'):
        return {'category': 'logs', 'risk': 'low', 'icon': 'file',
                'reason': 'Лог/текстовый артефакт.', 'action': 'archive'}
    # Документация
    if n.endswith('.md'):
        return {'category': 'docs', 'risk': 'low', 'icon': 'book',
                'reason': 'Документация.', 'action': 'keep'}
    # Код
    if n.endswith(('.py', '.tsx', '.ts', '.jsx', '.js')):
        return {'category': 'code', 'risk': 'medium', 'icon': 'code',
                'reason': 'Исходный код. Проверить перед удалением.', 'action': 'keep'}
    # Конфиг
    if n.endswith(('.json', '.yaml', '.yml', '.ini', '.cfg')):
        return {'category': 'config', 'risk': 'medium', 'icon': 'gear',
                'reason': 'Конфигурация. Проверить перед удалением.', 'action': 'keep'}
    # Скрипты запуска
    if n.endswith(('.bat', '.cmd', '.sh')):
        return {'category': 'scripts', 'risk': 'medium', 'icon': 'terminal',
                'reason': 'Скрипт запуска.', 'action': 'keep'}
    if n.endswith(('.html', '.css')):
        return {'category': 'web', 'risk': 'low', 'icon': 'globe',
                'reason': 'Веб-ресурс.', 'action': 'keep'}
    return {'category': 'other', 'risk': 'low', 'icon': 'file',
            'reason': 'Неизвестный тип файла.', 'action': 'keep'}

def category(name, rel, size):
    return classify_file(name, rel, size)['category']

def load_important():
    if os.path.exists(IMPORTANT):
        try:
            with open(IMPORTANT, 'r', encoding='utf-8') as f:
                return set(json.load(f).get('important', []))
        except Exception:
            pass
    return set()

def save_important(items):
    try:
        with open(IMPORTANT, 'w', encoding='utf-8') as f:
            json.dump({'important': sorted(list(items))}, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False

def smart_cleanup_scan():
    important = important_set()
    result = []
    for root, dirs, files in os.walk(BASE):
        dirs[:] = [d for d in dirs if d not in ('node_modules', '.git', '__pycache__', 'backups', 'project_archive')]
        for fn in files:
            fp = os.path.join(root, fn)
            rel = os.path.relpath(fp, BASE).replace('\\\\', '/')
            if rel in important:
                continue
            try:
                size = os.path.getsize(fp)
            except Exception:
                size = 0
            info = classify_file(fn, rel, size)
            if info['action'] == 'delete':
                result.append({'target_file': rel, 'size': size, **info})
    return result
"""

if old_category in content:
    content = content.replace(old_category, new_functions)
    print("✅ Функция category расширена до classify_file + добавлены load/save_important и smart_cleanup_scan")
else:
    print("⚠️ Функция category уже изменена или не найдена в точности. Пропускаем замену.")

# 3. Добавление эндпоинта smart-cleanup
if "@app.post('/api/project/smart-cleanup')" not in content:
    insert_marker = "def important_set():"
    if insert_marker in content:
        new_endpoint = """
@app.post('/api/project/smart-cleanup')
def s_smart_cleanup():
    \"\"\"Возвращает список файлов, которые безопасно удалить (мусор), исключая важные.\"\"\"
    try:
        files = smart_cleanup_scan()
        return {'success': True, 'files': files, 'count': len(files)}
    except Exception as e:
        return {'success': False, 'error': str(e)}

"""
        content = content.replace(insert_marker, new_endpoint + insert_marker)
        print("✅ Добавлен эндпоинт /api/project/smart-cleanup")

# 4. Сохранение и проверка синтаксиса
with open('main.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("💾 Сохраняю main.py...")

try:
    py_compile.compile('main.py', doraise=True)
    print("\n🎉 СИНТАКСИС main.py ВАЛИДЕН! Обновление прошло успешно.")
    print("👉 ТЕПЕРЬ НАЖМИ '🔄 Перезапуск' в панели управления.")
    print("👉 После перезапуска API /api/project/smart-cleanup начнет отдавать умный список мусора с причинами.")
except py_compile.PyCompileError as e:
    print("\n❌ ОШИБКА СИНТАКСИСА! Восстанавливаю из бэкапа...")
    shutil.copy2('main.py.backup_before_project_fix', 'main.py')
    print("✅ Бэкап восстановлен. Ошибка:", e)