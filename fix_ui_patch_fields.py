import re

file_path = "src/App.tsx"

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

print(f"📄 Читаю {file_path} ({len(content)} байт)")

# Старый формат body (короткий, без type и diff)
old_body_pattern = r"body:\s*JSON\.stringify\(\{\s*target_file:\s*patch\.target_file,\s*full_file_content:\s*\(patch\s+as\s+any\)\.full_file_content\s*\|\|\s*'',\s*patch_id:\s*patch\.patch_id\s*\}\)"

# Новый формат body (полный, со всеми полями)
new_body = """body: JSON.stringify({
          patch_id: patch.patch_id,
          type: patch.patch_type,
          target_file: patch.target_file,
          full_file_content: (patch as any).full_file_content || '',
          diff: (patch as any).diff || '',
          filename: patch.filename
        })"""

# Находим все вхождения
matches = re.findall(old_body_pattern, content)
print(f"🔍 Найдено {len(matches)} вхождений старого формата body")

if len(matches) == 0:
    print("⚠️ Не нашёл старый формат. Возможно, UI уже исправлен или структура другая.")
    print("   Проверяю наличие нового формата...")
    if 'type: patch.patch_type' in content:
        print("✅ Новый формат уже присутствует!")
    else:
        print("❌ Ни старый, ни новый формат не найдены. Нужна ручная проверка.")
else:
    # Заменяем все вхождения
    new_content = re.sub(old_body_pattern, new_body, content)
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(new_content)
    
    print(f"✅ Заменил {len(matches)} вхождений на новый формат")
    print("   Теперь UI передаёт: patch_id, type, target_file, full_file_content, diff, filename")

# Проверка результата
if 'type: patch.patch_type' in content or 'type: patch.patch_type' in new_content:
    print("\n✅ Проверка: поле type присутствует в запросах")
else:
    print("\n⚠️ Проверка: поле type НЕ найдено")

if 'diff: (patch as any).diff' in content or 'diff: (patch as any).diff' in new_content:
    print("✅ Проверка: поле diff присутствует в запросах")
else:
    print("⚠️ Проверка: поле diff НЕ найдено")

print("\n🎉 Готово! Обнови браузер (Ctrl+F5)")