import os
import re
import sys

# Принудительно UTF-8 для вывода
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

BASE = os.path.dirname(os.path.abspath(__file__))

def main():
    print('=' * 70)
    print('ПОИСК ФАЙЛА С ЛОГИКОЙ ПАТЧИНГА')
    print('=' * 70)
    
    # 1. Ищем все Python-файлы в корне проекта
    py_files = []
    for f in os.listdir(BASE):
        if f.endswith('.py') and f not in ('diag_patching.py', 'diag_ollama.py', 'make103.py', 'make103_full.py', 'fix_slow.py', 'find_patching.py'):
            py_files.append(f)
    
    print(f'\nНайдено Python-файлов в корне: {len(py_files)}')
    for f in sorted(py_files):
        size = os.path.getsize(os.path.join(BASE, f))
        print(f'  {f} ({size} байт)')
    
    # 2. Ищем файлы, содержащие ключевые слова патчинга
    keywords = ['search_and_replace', 'full_replace', 'full_file_content', 
                'patch_manifest', 'is_applied', 'apply_patch', 'preview_patch',
                'manifest.json', 'backup', 'check_ts']
    
    print('\n=== Файлы с логикой патчинга ===\n')
    candidates = []
    for f in py_files:
        path = os.path.join(BASE, f)
        try:
            with open(path, 'r', encoding='utf-8') as fh:
                content = fh.read()
        except:
            continue
        
        found_kw = [kw for kw in keywords if kw in content]
        if found_kw:
            candidates.append((f, found_kw, content))
            print(f'  [OK] {f} — найдены ключи: {", ".join(found_kw[:5])}')
    
    if not candidates:
        print('\n[ERR] Файл с логикой патчинга не найден!')
        print('Проверьте, не находится ли он в подпапке (например, backend/, core/, engine/)')
        
        # Ищем в подпапках
        for root, dirs, files in os.walk(BASE):
            if any(skip in root for skip in ('node_modules', '.git', '__pycache__', '.venv')):
                continue
            for f in files:
                if f.endswith('.py'):
                    path = os.path.join(root, f)
                    try:
                        with open(path, 'r', encoding='utf-8') as fh:
                            content = fh.read()
                    except:
                        continue
                    found_kw = [kw for kw in keywords if kw in content]
                    if found_kw:
                        rel = os.path.relpath(path, BASE)
                        print(f'  [OK] {rel} — найдены ключи: {", ".join(found_kw[:5])}')
        return
    
    # 3. Для каждого кандидата извлекаем ключевые функции
    for fname, kws, content in candidates:
        print(f'\n{"=" * 70}')
        print(f'ФАЙЛ: {fname} ({len(content)} символов)')
        print(f'{"=" * 70}')
        
        # Находим все функции
        func_pattern = re.compile(r'^(\s*)(async\s+)?def\s+(\w+)\s*\(', re.MULTILINE)
        functions = []
        for m in func_pattern.finditer(content):
            indent = m.group(1)
            func_name = m.group(3)
            start = m.start()
            lines = content[start:].split('\n')
            end_offset = 0
            for i, line in enumerate(lines[1:], 1):
                if not line.strip():
                    continue
                line_indent = line[:len(line) - len(line.lstrip())]
                if len(line_indent) <= len(indent) and line.strip():
                    end_offset = sum(len(l) + 1 for l in lines[:i])
                    break
            else:
                end_offset = len(content) - start
            body = content[start:start + end_offset].rstrip()
            functions.append((func_name, start, body, indent))
        
        print(f'\nВсего функций: {len(functions)}')
        
        # Фильтруем интересные функции
        interesting = ['apply', 'preview', 'validate', 'backup', 'manifest', 
                       'patch', 'search', 'replace', 'create', 'delete', 'check']
        
        for func_name, start, body, indent in functions:
            if any(kw in func_name.lower() for kw in interesting) or func_name.startswith('s_'):
                line_num = content[:start].count('\n') + 1
                print(f'\n--- {func_name} (строка {line_num}, {len(body)} символов, отступ={repr(indent)}) ---')
                # Показываем первые 30 строк
                body_lines = body.split('\n')
                for line in body_lines[:30]:
                    print(line)
                if len(body_lines) > 30:
                    print(f'... [ещё {len(body_lines) - 30} строк]')
    
    # 4. Ищем структуру манифеста
    print(f'\n{"=" * 70}')
    print('СТРУКТУРА МАНИФЕСТА')
    print(f'{"=" * 70}')
    for fname, kws, content in candidates:
        if 'manifest' in content.lower():
            for i, line in enumerate(content.split('\n'), 1):
                if 'is_applied' in line or 'patch_id' in line or 'operations' in line:
                    print(f'  {fname}:{i}: {line.strip()}')
    
    print('\n' + '=' * 70)
    print('ПОИСК ЗАВЕРШЁН')
    print('=' * 70)

if __name__ == '__main__':
    main()