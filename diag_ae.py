import re

with open('agent_engine.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

print("=== Контекст вокруг 'run_task' и 'candidates' в agent_engine.py ===")
for i, line in enumerate(lines):
    if 'run_task' in line or 'candidates' in line or '_get_candidates' in line:
        # Выводим 3 строки до и 5 строк после для полного контекста
        start = max(0, i - 3)
        end = min(len(lines), i + 6)
        print(f"\n--- Блок вокруг строки {i+1} ---")
        for j in range(start, end):
            print(f"{j+1:4d}: {repr(lines[j])}")