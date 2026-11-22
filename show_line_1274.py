import os

MAIN_PY = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'main.py')

with open(MAIN_PY, 'r', encoding='utf-8') as f:
    lines = f.readlines()

print('=== Строки 1270-1280 из main.py ===')
for i in range(1269, min(1280, len(lines))):
    print(f'{i+1:4d}: {repr(lines[i])}')