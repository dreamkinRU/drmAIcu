import os
import sys

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

BASE = os.path.dirname(os.path.abspath(__file__))
MAIN_PY = os.path.join(BASE, 'main.py')

print('=' * 70)
print('АКТУАЛЬНОЕ СОДЕРЖИМОЕ ФУНКЦИИ s_task В main.py')
print('=' * 70)

if not os.path.exists(MAIN_PY):
    print('ERROR: main.py не найден')
    sys.exit(1)

with open(MAIN_PY, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Ищем функцию s_task
start_line = None
for i, line in enumerate(lines):
    if 'def s_task(' in line:
        start_line = i
        break

if start_line is None:
    print('ERROR: функция s_task не найдена в main.py')
    sys.exit(1)

# Находим конец функции (следующая функция с тем же или меньшим отступом)
indent = len(lines[start_line]) - len(lines[start_line].lstrip())
end_line = start_line + 1
while end_line < len(lines):
    line = lines[end_line]
    if line.strip() and not line.startswith(' ' * (indent + 1)) and not line.startswith('\t' * (indent + 1)):
        if line.strip().startswith('def ') or line.strip().startswith('@') or line.strip().startswith('async def'):
            break
    end_line += 1

# Показываем функцию с номерами строк и repr() для каждого символа
print(f'\nФункция s_task: строки {start_line + 1} - {end_line}')
print(f'Всего строк: {end_line - start_line}\n')

for i in range(start_line, min(end_line, start_line + 20)):
    line = lines[i]
    print(f'Строка {i + 1}: {line.rstrip()}')
    print(f'  repr: {repr(line.rstrip())}')
    print()

if end_line - start_line > 20:
    print(f'... [ещё {end_line - start_line - 20} строк]')

print('\n' + '=' * 70)
print('ГОТОВО')
print('=' * 70)