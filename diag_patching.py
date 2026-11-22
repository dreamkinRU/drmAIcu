import os
import re
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
MAIN_PY = os.path.join(BASE, 'main.py')

def extract_function(src, func_name):
    """Извлекает функцию по имени с точным содержимым."""
    pattern = re.compile(r'^(\s*)(async\s+)?def\s+' + re.escape(func_name) + r'\s*\(', re.MULTILINE)
    m = pattern.search(src)
    if not m:
        return None, None
    indent = m.group(1)
    start = m.start()
    lines = src[start:].split('\n')
    end_offset = 0
    for i, line in enumerate(lines[1:], 1):
        if not line.strip():
            continue
        line_indent = line[:len(line) - len(line.lstrip())]
        if len(line_indent) <= len(indent) and line.strip():
            end_offset = sum(len(l) + 1 for l in lines[:i])
            break
    else:
        end_offset = len(src) - start
    return start, src[start:start + end_offset].rstrip()

def main():
    print('=' * 70)
    print('ДИАГНОСТИКА СИСТЕМЫ ПАТЧИНГА')
    print('=' * 70)
    
    if not os.path.exists(MAIN_PY):
        print('ERROR: main.py не найден')
        sys.exit(1)
    
    with open(MAIN_PY, 'r', encoding='utf-8') as f:
        src = f.read()
    
    # Функции, связанные с патчингом
    target_funcs = [
        'apply_patch', 'preview_patch', 'validate', 'check_ts', 
        'check_ts_full', 'backup', 's_patches_apply', 's_patches_preview',
        's_patches_rollback', 'load_manifest', 'save_manifest',
        's_patches_validate_all'
    ]
    
    print('\n=== Функции системы патчинга ===\n')
    
    for func_name in target_funcs:
        start, body = extract_function(src, func_name)
        if body:
            line_num = src[:start].count('\n') + 1
            print(f'--- {func_name} (строка {line_num}, {len(body)} символов) ---')
            print(body)
            print()
        else:
            print(f'--- {func_name}: НЕ НАЙДЕНА ---\n')
    
    # Ищем, где ставится статус "ПРИМЕНЕН"
    print('\n=== Места, где ставится статус "ПРИМЕНЕН" ===\n')
    for i, line in enumerate(src.split('\n'), 1):
        if 'is_applied' in line and 'True' in line:
            print(f'Строка {i}: {line.strip()}')
    
    # Ищем, где записывается манифест
    print('\n=== Места записи манифеста ===\n')
    for i, line in enumerate(src.split('\n'), 1):
        if 'save_manifest' in line or 'manifest.json' in line:
            print(f'Строка {i}: {line.strip()}')
    
    # Ищем структуру операций патча
    print('\n=== Обработка операций патча ===\n')
    for i, line in enumerate(src.split('\n'), 1):
        if any(kw in line for kw in ['search_and_replace', 'full_replace', 'create', 'delete']):
            if 'operation' in line.lower() or 'op' in line.lower():
                print(f'Строка {i}: {line.strip()}')
    
    # Ищем бэкапы
    print('\n=== Работа с бэкапами ===\n')
    for i, line in enumerate(src.split('\n'), 1):
        if 'backup' in line.lower() and ('create' in line.lower() or 'restore' in line.lower() or 'save' in line.lower()):
            print(f'Строка {i}: {line.strip()}')
    
    print('\n' + '=' * 70)
    print('ДИАГНОСТИКА ЗАВЕРШЕНА')
    print('=' * 70)

if __name__ == '__main__':
    main()