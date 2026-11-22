import re

MAIN_PY = 'main.py'
print('=== Убираем async из load_models ===')

with open(MAIN_PY, 'r', encoding='utf-8') as f:
    content = f.read()

# Заменяем async def load_models(): на def load_models():
new_content = re.sub(r'async def load_models\(\):', 'def load_models():', content)

if new_content != content:
    try:
        compile(new_content, MAIN_PY, 'exec')
        with open(MAIN_PY, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print('✅ Функция load_models() теперь синхронная (как и должно быть для requests.get)')
        print('🔄 Теперь нажмите Ctrl+C в окне терминала и запустите: python main.py')
    except SyntaxError as e:
        print(f'❌ Ошибка синтаксиса: {e}')
else:
    print('ℹ️ Изменений не требуется (функция уже синхронная)')