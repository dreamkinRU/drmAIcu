import json
import os

print("=== Запуск системы полной диагностики и авто-исправления ===")

# 1. Читаем реальный файл байт-в-байт
with open('main.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# 2. Ищем проблемную строку
target_line_idx = None
for i, line in enumerate(lines):
    if 'apply_patch_atomic(payload)' in line:
        target_line_idx = i
        break

if target_line_idx is not None:
    actual_line = lines[target_line_idx]
    
    print(f"\n[ДИАГНОСТИКА] Строка найдена на линии {target_line_idx + 1}")
    print(f"[ДИАГНОСТИКА] Точное содержимое (REPR): {repr(actual_line)}")
    print(f"[ДИАГНОСТИКА] HEX-код строки: {actual_line.encode('utf-8').hex()}")
    
    # 3. АВТОМАТИЧЕСКАЯ ГЕНЕРАЦИЯ ИСПРАВЛЕНИЯ
    # Мы заменяем только имя функции, сохраняя ВСЕ оригинальные пробелы и \n
    new_line = actual_line.replace('apply_patch_atomic(payload)', 'apply_patch(payload)')
    
    patch_data = {
        "patch_id": "134-auto-fix",
        "version": "1.0",
        "type": "multi",
        "description": "Автоматически сгенерированный патч на основе реальных байтов файла (без ручного подбора якорей)",
        "operations": [
            {
                "type": "search_and_replace",
                "target_file": "main.py",
                "find": actual_line,
                "replace": new_line
            }
        ]
    }
    
    os.makedirs('patch', exist_ok=True)
    with open('patch/134-auto-fix.json', 'w', encoding='utf-8') as f:
        json.dump(patch_data, f, ensure_ascii=False, indent=2)
        
    print("\n✅ УСПЕХ: Файл patch/134-auto-fix.json создан автоматически с точными байтами.")
    print("✅ Теперь просто выполните команду ниже. Больше ничего копировать не нужно.")
    print("\nКОМАНДА ДЛЯ ПРИМЕНЕНИЯ:")
    print('curl.exe -X POST http://127.0.0.1:8080/api/patches/apply -H "Content-Type: application/json; charset=utf-8" --data-binary "@patch\\134-auto-fix.json"')
    
else:
    print("\n✅ Строка с 'apply_patch_atomic(payload)' уже отсутствует или изменена. Проблема решена ранее.")