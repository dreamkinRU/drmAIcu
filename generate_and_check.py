import json
import os

print("=== 1. Создание идеального патча на основе diag_pipeline.txt ===")

# Якоря взяты байт-в-байт из предоставленного вами diag_pipeline.txt (строки 1005 и 1029-1030)
patch_data = {
    "patch_id": "136",
    "version": "1.0",
    "type": "multi",
    "description": "Финальная нейтрализация apply_patch_atomic на основе точных строк из diag_pipeline.txt",
    "operations": [
        {
            "type": "search_and_replace",
            "target_file": "main.py",
            "find": "    return JSONResponse(apply_patch_atomic(payload))",
            "replace": "    return JSONResponse(apply_patch(payload))"
        },
        {
            "type": "search_and_replace",
            "target_file": "main.py",
            "find": "def apply_patch_atomic(data):\n    \"\"\"Атомарное применение: все операции или ни одной.\"\"\"",
            "replace": "def _apply_patch_atomic_DEPRECATED(data):\n    \"\"\"DEPRECATED: Dead code. Delegated to apply_patch.\"\"\"\n    return apply_patch(data)"
        }
    ]
}

os.makedirs('patch', exist_ok=True)
with open('patch/136.json', 'w', encoding='utf-8') as f:
    json.dump(patch_data, f, ensure_ascii=False, indent=2)
print("✅ Файл patch/136.json успешно создан.")

print("\n=== 2. Запуск DRY-RUN проверки против реального main.py ===")
with open('main.py', 'r', encoding='utf-8') as f:
    content = f.read()

all_ok = True
for i, op in enumerate(patch_data['operations'], 1):
    tgt = op['target_file']
    find = op.get('find', '')
    if find in content:
        cnt = content.count(find)
        print(f"  Операция {i}: ✅ НАЙДЕНО ({cnt}x) в {tgt}")
        if cnt > 1:
            print(f"          ⚠️ ВНИМАНИЕ: Найдено более 1 раза, движок отклонит!")
            all_ok = False
    else:
        print(f"  Операция {i}: ❌ НЕ НАЙДЕНО в {tgt}")
        print(f"          Искомая строка (repr): {repr(find[:100])}")
        all_ok = False

if all_ok:
    print("\n🎉 DRY-RUN ПРОЙДЕН! Патч 136 гарантированно применится.")
    print("Скопируйте и выполните эту команду:")
    print('curl.exe -X POST http://127.0.0.1:8080/api/patches/apply -H "Content-Type: application/json; charset=utf-8" --data-binary "@patch\\136.json"')
else:
    print("\n❌ DRY-RUN ПРОВАЛЕН. Не применяйте патч, якоря не совпадают.")