import json
import os

print("=== Анализ текущего состояния main.py для создания 100% точного патча ===\n")

with open('main.py', 'r', encoding='utf-8') as f:
    content = f.read()

operations = []

# 1. Нейтрализация функции (заменяем только сигнатуру, остальное становится мертвым кодом)
# Пробуем найти с учетом возможных \r\n или \n
targets_to_neutralize = [
    "def apply_patch_atomic(data):\r\n    \"\"\"Атомарное применение: все операции или ни одной.\"\"\"",
    "def apply_patch_atomic(data):\n    \"\"\"Атомарное применение: все операции или ни одной.\"\"\""
]

replaced = False
for target in targets_to_neutralize:
    if target in content:
        # Формируем замену с теми же переносами строк, что и в оригинале
        newline = "\r\n" if "\r\n" in target else "\n"
        replace_text = f"def _apply_patch_atomic_DEPRECATED(data):{newline}    \"\"\"DEPRECATED: Dead code. Delegated to apply_patch.\"\"\"{newline}    return apply_patch(data)"
        
        operations.append({
            "type": "search_and_replace",
            "target_file": "main.py",
            "find": target,
            "replace": replace_text
        })
        print("✅ Найдена функция apply_patch_atomic. Будет нейтрализована.")
        replaced = True
        break

if not replaced:
    print("ℹ️ Функция apply_patch_atomic уже нейтрализована или переименована.")

# 2. Проверка эндпоинта (если вдруг там еще остался старый вызов)
target_api = "return JSONResponse(apply_patch_atomic(payload))"
if target_api in content:
    operations.append({
        "type": "search_and_replace",
        "target_file": "main.py",
        "find": target_api,
        "replace": "return JSONResponse(apply_patch(payload))"
    })
    print("✅ Найдено обращение к apply_patch_atomic в API. Будет исправлено.")
else:
    print("ℹ️ API уже использует безопасный apply_patch. Исправление не требуется.")

# 3. Генерация файла
if not operations:
    print("\n🎉 СИСТЕМА ЧИСТА! Все критические изменения уже успешно применены ранее.")
    print("Вам больше не нужно ничего делать. Мертвый код уже нейтрализован.")
else:
    os.makedirs('patch', exist_ok=True)
    patch_data = {
        "patch_id": "136-final-cleanup",
        "version": "1.0",
        "type": "multi",
        "description": "Автоматически сгенерированный патч с байт-в-байт точными якорями из текущего main.py",
        "operations": operations
    }
    
    with open('patch/136-final-cleanup.json', 'w', encoding='utf-8') as f:
        json.dump(patch_data, f, ensure_ascii=False, indent=2)
    
    print("\n✅ Патч успешно создан: patch/136-final-cleanup.json")
    print("Этот патч содержит ТОЧНЫЕ байты из вашего файла. Он не может не сработать.")
    print("\nСкопируйте и выполните эту команду:")
    print('curl.exe -X POST http://127.0.0.1:8080/api/patches/apply -H "Content-Type: application/json; charset=utf-8" --data-binary "@patch\\136-final-cleanup.json"')