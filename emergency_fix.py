import os

MAIN_PY = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'main.py')

print('=== Аварийное исправление: убираем value="" из ui.select ===')

with open(MAIN_PY, 'r', encoding='utf-8') as f:
    content = f.read()

# Находим проблемную строку
old_line = "model_select = ui.select([], label='Модель', value='')"
new_line = "model_select = ui.select([], label='Модель')"

if old_line in content:
    content = content.replace(old_line, new_line, 1)
    
    # Проверяем синтаксис
    try:
        compile(content, MAIN_PY, 'exec')
        print('✅ Синтаксис валиден')
        
        # Сохраняем
        with open(MAIN_PY, 'w', encoding='utf-8') as f:
            f.write(content)
        print('✅ Файл исправлен')
        print('🚀 Теперь запустите: python main.py')
    except SyntaxError as e:
        print(f'❌ Ошибка синтаксиса: {e}')
else:
    print('⚠️ Проблемная строка не найдена. Возможно, уже исправлено.')