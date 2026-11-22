import os

AE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'agent_engine.py')

print('=== Очистка мусорного дубликата в agent_engine.py ===')

with open(AE_PATH, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Ищем строку с неиндентированным async def run_task (признак мусорного дубликата)
target_line = 'async def run_task(self, prompt: str, status_callback=None, mode: str = "full", model: str = None, provider: str = None) -> str:\n'

for i, line in enumerate(lines):
    if line == target_line:
        # Нашли дубликат! Обрезаем всё, начиная с этой строки.
        # Предыдущие строки (включая return judge) останутся нетронутыми.
        clean_lines = lines[:i]
        with open(AE_PATH, 'w', encoding='utf-8') as f:
            f.writelines(clean_lines)
        print(f'✅ Найдён и удалён мусорный дубликат, начинающийся со строки {i+1}.')
        print('✅ Файл успешно очищен и готов к работе.')
        break
else:
    print('ℹ️ Мусорный дубликат не найден. Файл уже чист.')