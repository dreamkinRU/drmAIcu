import re
import os

MAIN_PY = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'main.py')

print('=== Универсальное исправление ui.select для model_select ===')

with open(MAIN_PY, 'r', encoding='utf-8') as f:
    content = f.read()

# Ищем паттерн: model_select = ui.select(..., value='...' или value="...")
# и убираем value=... если options пустой список []
pattern = re.compile(r"(model_select\s*=\s*ui\.select\s*\(\s*\[\s*\][^)]*?)value\s*=\s*['\"][^'\"]*['\"]\s*,?", re.MULTILINE)

match = pattern.search(content)
if match:
    # Убираем value=... из строки
    fixed = match.group(1).rstrip(', ') + ')'
    # Заменяем всю найденную конструкцию
    content = content[:match.start()] + fixed + content[match.end():]
    
    # Проверяем синтаксис
    try:
        compile(content, MAIN_PY, 'exec')
        print('✅ Синтаксис валиден')
        
        with open(MAIN_PY, 'w', encoding='utf-8') as f:
            f.write(content)
        print('✅ Файл исправлен')
        print('🚀 Теперь запустите: python main.py')
    except SyntaxError as e:
        print(f'❌ Ошибка синтаксиса: {e}')
else:
    print('⚠️ Паттерн не найден. Пробуем альтернативный поиск...')
    
    # Альтернативный поиск: просто ищем ui.select с пустым списком и value
    alt_pattern = re.compile(r"ui\.select\s*\(\s*\[\s*\]", re.MULTILINE)
    matches = list(alt_pattern.finditer(content))
    print(f'Найдено {len(matches)} вхождений ui.select([])')
    
    for i, m in enumerate(matches):
        start = max(0, m.start() - 50)
        end = min(len(content), m.end() + 100)
        context = content[start:end]
        print(f'\nВхождение #{i+1}:')
        print(repr(context))