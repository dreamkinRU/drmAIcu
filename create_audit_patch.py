import json
import os

print("=== Создание патча с аудит-логированием API-вызовов ===\n")

with open('main.py', 'r', encoding='utf-8') as f:
    content = f.read()
    lines = content.splitlines(True)

# Найти актуальную строку с s_papply
target_line = None
for i, line in enumerate(lines):
    if 'def s_papply(payload: dict):' in line:
        # Следующая строка должна быть return
        if i + 1 < len(lines) and 'return JSONResponse' in lines[i + 1]:
            target_line = lines[i + 1]
            print(f"✅ Найдена строка {i + 2}: {repr(target_line)}")
            break

if target_line is None:
    print("❌ Не удалось найти актуальную строку с return JSONResponse")
    print("Возможные варианты:")
    for i, line in enumerate(lines):
        if 's_papply' in line or 'apply_patch' in line:
            print(f"  Строка {i + 1}: {repr(line)}")
else:
    # Создать патч с аудит-логированием
    new_line = target_line.replace(
        'return JSONResponse(apply_patch(payload))',
        'log(\'API apply: \' + str(payload.get(\'patch_id\', \'unknown\')), \'INFO\')\n    return JSONResponse(apply_patch(payload))'
    )
    
    patch_data = {
        "patch_id": "137-audit-logging",
        "version": "1.0",
        "type": "multi",
        "description": "Добавление аудит-логирования всех API-вызовов применения патчей",
        "operations": [
            {
                "type": "search_and_replace",
                "target_file": "main.py",
                "find": target_line,
                "replace": new_line
            }
        ]
    }
    
    os.makedirs('patch', exist_ok=True)
    with open('patch/137.json', 'w', encoding='utf-8') as f:
        json.dump(patch_data, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ Патч создан: patch/137.json")
    print(f"   Якорь (find): {repr(target_line)}")
    print(f"   Замена (replace): {repr(new_line)}")
    
    # Dry-run проверка
    if target_line in content:
        print(f"\n🎉 DRY-RUN: Якорь найден в main.py. Патч применим.")
        print("\nКоманда для применения:")
        print('curl.exe -X POST http://127.0.0.1:8080/api/patches/apply -H "Content-Type: application/json; charset=utf-8" --data-binary "@patch\\137.json"')
    else:
        print(f"\n❌ DRY-RUN: Якорь НЕ найден в main.py. Патч не применим.")