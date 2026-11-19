import json

# Читаем main.py
with open('main.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Ищем функцию validate
start_marker = "def validate(name, code):"
start_idx = content.find(start_marker)
if start_idx == -1:
    print("ERROR: функция validate не найдена")
    exit(1)

# Находим конец функции (следующая функция верхнего уровня или конец файла)
lines = content[start_idx:].split('\n')
end_idx = start_idx
for i, line in enumerate(lines[1:], 1):
    if line and not line.startswith(' ') and not line.startswith('\t'):
        end_idx = start_idx + sum(len(l) + 1 for l in lines[:i])
        break
else:
    end_idx = len(content)

validate_func = content[start_idx:end_idx].strip()
print("Найдена функция validate:")
print("=" * 60)
print(validate_func)
print("=" * 60)

# Создаём патч 092
patch_092 = {
    "patch_id": "092",
    "version": "1.0",
    "description": "Add TS/TSX validation with tsc --noEmit in validate() function",
    "author": "review",
    "created_at": "2026-11-19T17:10:00",
    "operations": [
        {
            "type": "search_and_replace",
            "target_file": "main.py",
            "find": validate_func,
            "replace": validate_func.replace(
                "    return True, None",
                """    elif ext in ('.ts', '.tsx', '.js', '.jsx', '.mjs', '.cjs'):
        err = check_ts(name, code)
        if err:
            return False, 'TS/JS: ' + err
        # Полная типовая проверка (только для TS/TSX, не JS)
        if ext in ('.ts', '.tsx'):
            err = check_ts_full()
            if err:
                return False, err
    return True, None"""
            )
        }
    ]
}

# Сохраняем патч
with open('patch/092.json', 'w', encoding='utf-8') as f:
    json.dump(patch_092, f, indent=2, ensure_ascii=False)

print("\nПатч 092 создан: patch/092.json")