import re

MAIN_PY = 'main.py'

print('=== Аварийное исправление model_select ===')

with open(MAIN_PY, 'r', encoding='utf-8') as f:
    content = f.read()

# Ищем блок model_select = ui.select(...) с любым содержимым внутри
# Regex находит от "model_select = ui.select(" до закрывающей ")" с учётом вложенных скобок
pattern = re.compile(
    r"(\s*)model_select\s*=\s*ui\.select\(\s*\[\s*\],\s*label\s*=\s*['\"]Модель['\"](?:\s*,\s*value\s*=\s*['\"][^'\"]*['\"])?\s*\)(?:\.classes\([^)]*\))?",
    re.MULTILINE
)

match = pattern.search(content)
if not match:
    print('❌ Блок model_select не найден. Показываю контекст строки 1274:')
    lines = content.split('\n')
    if len(lines) > 1274:
        for i in range(1270, min(1285, len(lines))):
            print(f'  {i+1}: {repr(lines[i])}')
    input('Нажмите Enter для выхода...')
    exit(1)

# Получаем отступ из найденного блока
indent = match.group(1)

# Новая корректная версия (без value='', с безопасной инициализацией)
replacement = (
    f"{indent}model_select = ui.select(\n"
    f"{indent}    [],\n"
    f"{indent}    label='Модель'\n"
    f"{indent}).classes('w-64 mb-4')"
)

new_content = content[:match.start()] + replacement + content[match.end():]

# Проверка синтаксиса
try:
    compile(new_content, MAIN_PY, 'exec')
    print('✅ Синтаксис валиден')
except SyntaxError as e:
    print(f'❌ Ошибка синтаксиса после замены: {e}')
    print('Сохраняю бэкап текущего состояния...')
    with open(MAIN_PY + '.broken_backup', 'w', encoding='utf-8') as f:
        f.write(content)
    print(f'Бэкап: {MAIN_PY}.broken_backup')
    input('Нажмите Enter для выхода...')
    exit(1)

# Сохраняем
with open(MAIN_PY, 'w', encoding='utf-8') as f:
    f.write(new_content)

print('✅ Файл main.py исправлен')
print('🚀 Запустите: python main.py')