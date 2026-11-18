import re

file_path = "main.py"

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

print(f"📄 Читаю {file_path} ({len(content)} байт)")

# 1. Добавляем эндпоинт test-apply перед apply
old_apply_endpoint = """@app.post('/api/patches/apply')
def s_papply(payload: dict):
    return JSONResponse(apply_patch(payload))"""

new_apply_endpoint = """@app.post('/api/patches/test-apply')
def s_ptest(payload: dict):
    \"\"\"Тестовое применение патча без записи файла\"\"\"
    data = resolve(payload)
    pid = str(data.get('patch_id', 'unknown'))
    tgt = data.get('target_file', '')
    path, new, err = compute_new(data)
    if err:
        return JSONResponse({'success': False, 'error': err})
    
    old_content = ''
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            old_content = f.read()
    
    old_lines = len(old_content.split('\\n'))
    new_lines = len(new.split('\\n'))
    
    return JSONResponse({
        'success': True,
        'patch_id': pid,
        'target_file': tgt,
        'old_size': len(old_content),
        'new_size': len(new),
        'old_lines': old_lines,
        'new_lines': new_lines,
        'lines_added': max(0, new_lines - old_lines),
        'lines_removed': max(0, old_lines - new_lines),
        'message': f'Тест пройден: {old_lines} -> {new_lines} строк'
    })

@app.post('/api/patches/apply')
def s_papply(payload: dict):
    return JSONResponse(apply_patch(payload))"""

if old_apply_endpoint in content:
    content = content.replace(old_apply_endpoint, new_apply_endpoint)
    print("✅ Добавлен эндпоинт /api/patches/test-apply")
else:
    print("⚠️ Не нашёл эндпоинт apply. Проверяю альтернативный формат...")
    # Альтернативный поиск
    alt_pattern = r"@app\.post\('/api/patches/apply'\)"
    if re.search(alt_pattern, content):
        print("   Нашёл альтернативный формат, но не могу заменить автоматически.")
        print("   Нужна ручная проверка.")
    else:
        print("❌ Эндпоинт apply не найден вообще.")

# Записываем файл
with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("\n🎉 Готово! Перезапусти лаунчер.")
print("   Проверка: открой http://127.0.0.1:8080/docs (если есть Swagger) или")
print("   выполни: Invoke-RestMethod -Uri 'http://127.0.0.1:8080/api/patches/test-apply' -Method Post -Body '{}' -ContentType 'application/json'")