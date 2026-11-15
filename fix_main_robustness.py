import re

file_path = "main.py"

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

print(f"📄 Читаю {file_path} ({len(content)} байт)")

# Улучшение 1: Добавляем проверку целостности после записи
old_write_block = """    backs = backup(path)
    tmp = path + '.tmp'
    try:
        with open(tmp, 'w', encoding='utf-8') as f:
            f.write(new)
        os.replace(tmp, path)
    except Exception as e:
        if os.path.exists(tmp):
            os.remove(tmp)
        return {'success': False, 'error': 'Запись: ' + str(e)}"""

new_write_block = """    backs = backup(path)
    tmp = path + '.tmp'
    expected_sha = sha(new)
    try:
        with open(tmp, 'w', encoding='utf-8') as f:
            f.write(new)
        os.replace(tmp, path)
        
        # Проверка целостности после записи
        with open(path, 'r', encoding='utf-8') as f:
            written_content = f.read()
        actual_sha = sha(written_content)
        
        if actual_sha != expected_sha:
            log('Checksum mismatch after write! Expected: ' + expected_sha[:16] + ', Got: ' + actual_sha[:16], 'ERROR')
            # Автооткат
            if backs:
                shutil.copy2(backs[-1], path)
                log('Auto-rollback from backup: ' + backs[-1], 'WARNING')
            return {'success': False, 'error': 'Целостность файла нарушена после записи (автооткат)'}
        
        log('File integrity verified: ' + expected_sha[:16], 'SUCCESS')
    except Exception as e:
        if os.path.exists(tmp):
            os.remove(tmp)
        return {'success': False, 'error': 'Запись: ' + str(e)}"""

if old_write_block in content:
    content = content.replace(old_write_block, new_write_block)
    print("✅ Добавлена проверка целостности после записи + автооткат")
else:
    print("⚠️ Не нашёл блок записи файла. Возможно, структура другая.")

# Улучшение 2: Детальное логирование перед применением
old_apply_start = """def apply_patch(raw):
    data = resolve(raw)
    pid = str(data.get('patch_id', 'unknown'))
    tgt = data.get('target_file', '')
    path, new, err = compute_new(data)"""

new_apply_start = """def apply_patch(raw):
    data = resolve(raw)
    pid = str(data.get('patch_id', 'unknown'))
    tgt = data.get('target_file', '')
    ptype = data.get('type', 'unknown')
    log('Applying patch ' + pid + ' to ' + tgt + ' (type: ' + ptype + ', size: ' + str(len(new if 'new' in dir() else '')) + ' bytes)', 'INFO')
    path, new, err = compute_new(data)"""

# Более точная замена
old_apply_start_v2 = """    pid = str(data.get('patch_id', 'unknown'))
    tgt = data.get('target_file', '')
    path, new, err = compute_new(data)"""

new_apply_start_v2 = """    pid = str(data.get('patch_id', 'unknown'))
    tgt = data.get('target_file', '')
    ptype = data.get('type', 'unknown')
    log('Applying patch ' + pid + ' to ' + tgt + ' (type: ' + ptype + ')', 'INFO')
    path, new, err = compute_new(data)"""

if old_apply_start_v2 in content:
    content = content.replace(old_apply_start_v2, new_apply_start_v2)
    print("✅ Добавлено детальное логирование перед применением")
else:
    print("⚠️ Не нашёл начало функции apply_patch")

# Записываем файл
with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("\n🎉 Готово! Перезапусти лаунчер для применения изменений")