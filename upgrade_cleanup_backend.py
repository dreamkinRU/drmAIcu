# upgrade_cleanup_backend.py
import re
import os
from datetime import datetime, timedelta

file_path = "main.py"
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

print("🔍 Модернизирую анализатор проекта...")

# 1. Добавляем функцию умного анализа
smart_analysis_func = """
def get_cleanup_recommendation(f):
    \"\"\"Умный анализ файла на предмет удаления\"\"\"
    name = f['filename']
    rel = f['path']
    size = f['size']
    ext = f['extension']
    
    # 1. Пустые файлы
    if size == 0 and ext not in ('.gitkeep', '.keep'):
        return {'action': 'delete', 'reason': 'Файл абсолютно пустой (0 байт)'}
    
    # 2. Системный мусор ОС
    if name in ('.DS_Store', 'Thumbs.db', 'desktop.ini', 'ehthumbs.db', 'Icon\\r'):
        return {'action': 'delete', 'reason': 'Скрытый системный мусор операционной системы'}
    
    # 3. Временные файлы и кэш
    if ext in ('.tmp', '.pyc', '.pyo') or '__pycache__' in rel or '.vite' in rel:
        return {'action': 'delete', 'reason': 'Временный файл или кэш компиляции'}
    
    # 4. Устаревшие версии в корне (main_v1.py, App_old.tsx и т.д.)
    if re.search(r'_(old|backup|v\d+|copy)\.', name, re.IGNORECASE) and '/' not in rel and '\\' not in rel:
        return {'action': 'delete', 'reason': 'Устаревшая резервная копия в корне проекта'}
    
    # 5. Огромные логи (> 5 МБ)
    if ext in ('.log', '.txt') and size > 5 * 1024 * 1024:
        return {'action': 'review', 'reason': f'Очень большой файл ({f["size_human"]}). Возможно, старый лог.'}
    
    # 6. Дубликаты
    if f.get('is_duplicate') and f.get('duplicates'):
        # Оставляем тот, что в более "правильной" папке, остальные на удаление
        primary = f['duplicates'][0]
        if len(rel) > len(primary): # Если текущий путь длиннее, скорее всего это копия
            return {'action': 'delete', 'reason': f'Дубликат. Оригинал находится в: {primary}'}
        else:
            return {'action': 'review', 'reason': f'Имеет дубликат в: {", ".join(f["duplicates"][:2])}'}
    
    # 7. Файлы с подозрительными именами в корне
    if re.match(r'^(test|temp|tmp|untitled|new_file|copy)\..+', name, re.IGNORECASE):
        return {'action': 'review', 'reason': 'Подозрительное временное имя файла в корне проекта'}
    
    # По умолчанию
    return {'action': 'keep', 'reason': 'Файл выглядит корректно'}

"""

# Вставляем функцию перед def scan_project
if "def get_cleanup_recommendation(f):" not in content:
    content = content.replace("def scan_project():", smart_analysis_func + "\ndef scan_project():")
    print("✅ Добавлена функция get_cleanup_recommendation")

# 2. Модифицируем цикл в scan_project, чтобы добавить рекомендацию
old_loop_end = """                files.append({'path': rel, 'filename': n, 'size': st.st_size,
                              'size_human': human(st.st_size),
                              'modified': datetime.fromtimestamp(st.st_mtime).isoformat(),
                              'category': cat, 'hash': h,
                              'is_critical': cat == 'critical', 'is_important': rel in imp,
                              'extension': os.path.splitext(n)[1].lower(),
                              'icon': ICONS.get(os.path.splitext(n)[1].lower(), 'FILE'),
                              'is_duplicate': False, 'duplicates': []})"""

new_loop_end = """                rec = get_cleanup_recommendation({'filename': n, 'path': rel, 'size': st.st_size, 'extension': os.path.splitext(n)[1].lower()})
                files.append({'path': rel, 'filename': n, 'size': st.st_size,
                              'size_human': human(st.st_size),
                              'modified': datetime.fromtimestamp(st.st_mtime).isoformat(),
                              'category': cat, 'hash': h,
                              'is_critical': cat == 'critical', 'is_important': rel in imp,
                              'extension': os.path.splitext(n)[1].lower(),
                              'icon': ICONS.get(os.path.splitext(n)[1].lower(), 'FILE'),
                              'is_duplicate': False, 'duplicates': [],
                              'cleanup': rec})"""

if old_loop_end in content:
    content = content.replace(old_loop_end, new_loop_end)
    print("✅ Интегрирован вызов анализатора в цикл сканирования")
else:
    print("⚠️ Не нашел точный блок цикла. Проверьте main.py вручную.")

# Обновляем статистику, чтобы показать количество файлов на удаление
old_stats = """    st = {'total': len(files), 'total_size': total, 'total_size_human': human(total),
          'by_category': {}, 'by_extension': {},
          'duplicates_count': len([f for f in files if f['is_duplicate']]),
          'duplicates_groups': len([v for v in hashes.values() if len(v) > 1]),
          'critical_count': len([f for f in files if f['is_critical']]),
          'important_count': len([f for f in files if f['is_important']]),
          'trash_count': len([f for f in files if f['category'] == 'trash']),
          'backup_count': len([f for f in files if f['category'] == 'backup'])}"""

new_stats = """    st = {'total': len(files), 'total_size': total, 'total_size_human': human(total),
          'by_category': {}, 'by_extension': {},
          'duplicates_count': len([f for f in files if f['is_duplicate']]),
          'duplicates_groups': len([v for v in hashes.values() if len(v) > 1]),
          'critical_count': len([f for f in files if f['is_critical']]),
          'important_count': len([f for f in files if f['is_important']]),
          'trash_count': len([f for f in files if f['category'] == 'trash']),
          'backup_count': len([f for f in files if f['category'] == 'backup']),
          'cleanup_delete_count': len([f for f in files if f.get('cleanup', {}).get('action') == 'delete']),
          'cleanup_review_count': len([f for f in files if f.get('cleanup', {}).get('action') == 'review'])}"""

if old_stats in content:
    content = content.replace(old_stats, new_stats)
    print("✅ Обновлена статистика очистки")

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("🎉 Backend обновлен! Перезапусти лаунчер.")