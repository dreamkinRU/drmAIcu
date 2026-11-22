import json
import os
import subprocess
import sys

print("=== Комплексное исправление всех критических дыр системы патчинга ===\n")

with open('main.py', 'r', encoding='utf-8') as f:
    content = f.read()
    lines = content.splitlines(True)

operations = []

# Проблема 1: compute_ops обходит safe_path (строка 500)
# Ищем уникальный маркер: "path = os.path.normpath(os.path.join(BASE, tgt))" внутри compute_ops
found = False
for i, line in enumerate(lines):
    if "path = os.path.normpath(os.path.join(BASE, tgt))" in line and i > 490 and i < 510:
        # Нашли строку 500. Нужно заменить блок 499-508
        # Строка 499: pt = o.get('type', '') or ...
        # Строки 500-504: path = ... + commonpath проверка
        # Строки 505-508: if not tgt or not inside: ...
        
        # Находим начало блока (строка с pt = ...)
        start_idx = i - 1  # строка 499
        # Находим конец блока (строка с continue)
        end_idx = i
        for j in range(i, min(i + 10, len(lines))):
            if "continue" in lines[j]:
                end_idx = j
                break
        
        # Формируем замену
        old_block = ''.join(lines[start_idx:end_idx + 1])
        
        # Новая версия с safe_path и правильной проверкой типа
        new_block = (
            "        pt = o.get('type', '')\n"
            "        if not pt:\n"
            "            if o.get('diff'):\n"
            "                pt = 'unified_diff'\n"
            "            elif 'find' in o or o.get('find') is not None:\n"
            "                pt = 'search_and_replace'\n"
            "            elif o.get('full_file_content'):\n"
            "                pt = 'full_replace'\n"
            "        path = safe_path(tgt)\n"
            "        if path is None:\n"
            "            res.append({'target_file': tgt, 'type': pt, 'path': None, 'new': None,\n"
            "                        'err': 'Bad target_file (security): ' + str(tgt)})\n"
            "            continue\n"
        )
        
        operations.append({
            "type": "search_and_replace",
            "target_file": "main.py",
            "find": old_block,
            "replace": new_block
        })
        print(f"✅ Проблема 1: compute_ops path security — найдена на строке {i + 1}")
        found = True
        break

if not found:
    print("ℹ️ Проблема 1: уже исправлена или не найдена")

# Проблема 2: Потеря файла при сбое backup (строки 626-636)
# Ищем блок отката в apply_patch
found = False
for i, line in enumerate(lines):
    if "elif os.path.exists(pl['path']):" in line and i > 620 and i < 640:
        # Нашли строку 632. Нужно добавить проверку existed перед удалением
        # Строка 632: elif os.path.exists(pl['path']):
        # Строка 633: try:
        # Строка 634: os.remove(pl['path'])
        
        # Заменяем на проверку existed
        old_block = ''.join(lines[i:i + 4])  # 4 строки: elif, try, os.remove, except
        new_block = (
            "            elif pl.get('existed') and not pl['backs']:\n"
            "                # Файл существовал, бэкапа нет — удалять НЕЛЬЗЯ (A-01 fix)\n"
            "                pass\n"
            "            elif not pl.get('existed') and os.path.exists(pl['path']):\n"
            "                # Новый файл (create) — можно удалить при откате\n"
            "                try:\n"
            "                    os.remove(pl['path'])\n"
            "                except Exception:\n"
            "                    pass\n"
        )
        
        operations.append({
            "type": "search_and_replace",
            "target_file": "main.py",
            "find": old_block,
            "replace": new_block
        })
        print(f"✅ Проблема 2: потеря файла при сбое backup — найдена на строке {i + 1}")
        found = True
        break

if not found:
    print("ℹ️ Проблема 2: уже исправлена или не найдена")

# Проблема 3: API вызывает apply_patch_atomic (строка 1005)
found = False
for i, line in enumerate(lines):
    if "return JSONResponse(apply_patch_atomic(payload))" in line:
        old_line = line
        new_line = line.replace("apply_patch_atomic(payload)", "apply_patch(payload)")
        operations.append({
            "type": "search_and_replace",
            "target_file": "main.py",
            "find": old_line,
            "replace": new_line
        })
        print(f"✅ Проблема 3: API endpoint — найдена на строке {i + 1}")
        found = True
        break

if not found:
    print("ℹ️ Проблема 3: уже исправлена")

# Проблема 4: Некорректный rollback (строки 656-658)
# Используем конкретный backup из манифеста, не _LATEST
found = False
for i, line in enumerate(lines):
    if "shutil.copy2(b[-1], path)" in line and i > 650 and i < 670:
        old_line = line
        new_line = "                shutil.copy2(b[0], path)  # Используем первый backup (timestamp), не _LATEST\n"
        operations.append({
            "type": "search_and_replace",
            "target_file": "main.py",
            "find": old_line,
            "replace": new_line
        })
        print(f"✅ Проблема 4: rollback correctness — найдена на строке {i + 1}")
        found = True
        break

if not found:
    print("ℹ️ Проблема 4: уже исправлена или не найдена")

# Проблема 5: Ложь пользователю при откате (строка 644)
found = False
for i, line in enumerate(lines):
    if "Транзакция отменена, всё восстановлено:" in line:
        old_line = line
        new_line = line.replace("Транзакция отменена, всё восстановлено:", "Транзакция отменена, выполнен откат:")
        operations.append({
            "type": "search_and_replace",
            "target_file": "main.py",
            "find": old_line,
            "replace": new_line
        })
        print(f"✅ Проблема 5: честное сообщение при откате — найдена на строке {i + 1}")
        found = True
        break

if not found:
    print("ℹ️ Проблема 5: уже исправлена")

# Проблема 6: Добавить existed флаг в planned (строки 595-596)
found = False
for i, line in enumerate(lines):
    if "'tgt': o['target_file'], 'sha': sha_bytes(data)" in line:
        old_line = line
        new_line = line.replace(
            "'tgt': o['target_file'], 'sha': sha_bytes(data)",
            "'tgt': o['target_file'], 'sha': sha_bytes(data), 'existed': os.path.exists(o['path'])"
        )
        operations.append({
            "type": "search_and_replace",
            "target_file": "main.py",
            "find": old_line,
            "replace": new_line
        })
        print(f"✅ Проблема 6: existed флаг — найдена на строке {i + 1}")
        found = True
        break

if not found:
    print("ℹ️ Проблема 6: уже исправлена")

# Итог
if not operations:
    print("\n🎉 ВСЕ ПРОБЛЕМЫ УЖЕ ИСПРАВЛЕНЫ! Патч не требуется.")
    sys.exit(0)

# Создаём патч
patch_data = {
    "patch_id": "138-comprehensive-fix",
    "version": "1.0",
    "type": "multi",
    "description": "Комплексное исправление всех критических дыр: path security, backup loss, API routing, rollback",
    "operations": operations
}

os.makedirs('patch', exist_ok=True)
with open('patch/138.json', 'w', encoding='utf-8') as f:
    json.dump(patch_data, f, ensure_ascii=False, indent=2)

print(f"\n✅ Создан патч patch/138.json с {len(operations)} операциями")

# Dry-run проверка
print("\n=== DRY-RUN проверка ===")
all_ok = True
for i, op in enumerate(operations, 1):
    find = op['find']
    if find in content:
        cnt = content.count(find)
        print(f"  Операция {i}: ✅ НАЙДЕНО ({cnt}x)")
        if cnt > 1:
            print(f"          ⚠️ AMBIGUOUS!")
            all_ok = False
    else:
        print(f"  Операция {i}: ❌ НЕ НАЙДЕНО")
        print(f"          find = {repr(find[:80])}")
        all_ok = False

if not all_ok:
    print("\n❌ DRY-RUN ПРОВАЛЕН. Патч не будет применён.")
    sys.exit(1)

print("\n🎉 DRY-RUN ПРОЙДЕН! Применяю патч через API...")

# Применяем через curl
result = subprocess.run(
    ['curl.exe', '-X', 'POST', 'http://127.0.0.1:8080/api/patches/apply',
     '-H', 'Content-Type: application/json; charset=utf-8',
     '--data-binary', '@patch/138.json'],
    capture_output=True, text=True, encoding='utf-8'
)

print("\n=== Результат применения ===")
print(result.stdout)
if result.stderr:
    print("STDERR:", result.stderr)

if '"success": true' in result.stdout or '"success":true' in result.stdout:
    print("\n🏆 ПАТЧ УСПЕШНО ПРИМЕНЁН! Все критические дыры закрыты.")
else:
    print("\n❌ Патч не применился. Проверь вывод выше.")