import os

print("=== Исправление логики бэкенда для полной совместимости с UI ===\n")

with open('main.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Ищем блок авто-определения типа операции
target_found = False
for i in range(len(lines)):
    if "elif o.get('full_file_content'):" in lines[i] and "pt = 'full_replace'" in lines[i+1]:
        # Вставляем авто-определение search_and_replace ПЕРЕД full_replace
        indent = "        " # 8 пробелов, как в оригинале
        new_lines = [
            f"{indent}elif 'find' in o or o.get('find') is not None:\n",
            f"{indent}    pt = 'search_and_replace'\n"
        ]
        lines = lines[:i] + new_lines + lines[i:]
        target_found = True
        print(f"✅ Логика исправлена! Вставлено авто-определение 'search_and_replace' на строке {i+1}.")
        break

if not target_found:
    print("❌ Не удалось найти целевой блок кода. Возможно, он уже исправлен или изменен.")
else:
    # Сохраняем исправленный файл
    with open('main.py', 'w', encoding='utf-8') as f:
        f.writelines(lines)
    print("✅ Файл main.py успешно обновлен.")
    print("\nТеперь панель управления сможет применять search_and_replace патчи без ошибки 'Нет full_file_content'.")