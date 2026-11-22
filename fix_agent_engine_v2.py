import os
import re
import sys

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

BASE = os.path.dirname(os.path.abspath(__file__))
AE_PATH = os.path.join(BASE, 'agent_engine.py')

print('=' * 70)
print('ИСПРАВЛЕНИЕ agent_engine.py v2: поиск и замена run_task')
print('=' * 70)

if not os.path.exists(AE_PATH):
    print('ERROR: agent_engine.py не найден')
    sys.exit(1)

with open(AE_PATH, 'r', encoding='utf-8') as f:
    content = f.read()

# Проверяем синтаксис
try:
    compile(content, AE_PATH, 'exec')
    print('OK: файл компилируется')
except SyntaxError as e:
    print(f'WARNING: синтаксическая ошибка: {e}')
    print('Продолжаю поиск функции...')

# Ищем начало функции run_task (даже если она сломана)
pattern_start = re.compile(r'^\s*async def run_task\(', re.MULTILINE)
match_start = pattern_start.search(content)

if not match_start:
    print('ERROR: не найдено начало функции run_task')
    sys.exit(1)

print(f'Найдено начало функции на позиции {match_start.start()}')

# Ищем следующую функцию или класс после run_task
# Ищем по паттерну: строка с отступом <= 4 пробелов, начинающаяся с def или class
pattern_end = re.compile(r'^\n(?:    def |    async def |class |\Z)', re.MULTILINE)
match_end = pattern_end.search(content, match_start.end())

if match_end:
    end_pos = match_end.start()
else:
    end_pos = len(content)

print(f'Конец функции на позиции {end_pos}')

# Извлекаем старую функцию
old_func = content[match_start.start():end_pos]
print(f'Старая функция: {len(old_func)} символов, {old_func.count(chr(10))} строк')

# Новая правильная версия функции
new_func = '''async def run_task(self, prompt: str, status_callback=None, mode: str = "full", model: str = None, provider: str = None) -> str:
        self.log("=" * 70, "INFO")
        self.log(f"TASK: {prompt[:80]}", "INFO")
        self.log(f"MODE: {mode}", "INFO")
        if model and provider:
            self.log(f"TARGET: {provider} / {model}", "INFO")
            candidates = [{"provider": provider, "model": model, "name": f"{provider}: {model}"}]
        else:
            candidates = self._get_candidates()
        self.log("=" * 70, "INFO")
        active_providers = set(c['provider'].upper() for c in candidates)
        self.log(f"Active providers: {', '.join(sorted(active_providers))}", "INFO")
        self.log(f"Total models: {len(candidates)}", "INFO")
        if status_callback:
            status_callback(f"Sending to {len(candidates)} models...")
        tasks = [self.get_code_response(c, prompt) for c in candidates]
        self.log("Parallel query...", "INFO")
        results = await asyncio.gather(*tasks, return_exceptions=True)
        valid_responses = []
        for res in results:
            if isinstance(res, Exception):
                self.log(f"[ERR] Critical: {res}", "ERROR")
            elif isinstance(res, dict) and res.get("code"):
                valid_responses.append(res)
            elif isinstance(res, dict):
                self.log(f"[WARN] {res['candidate']['name']}: {res.get('error')}", "WARN")
        self.log(f"Success: {len(valid_responses)} of {len(candidates)}", "INFO")
        if valid_responses:
            answered = [r['candidate']['name'] for r in valid_responses]
            self.log(f"Answered: {', '.join(answered)}", "SUCCESS")
        if not valid_responses:
            if status_callback:
                status_callback("All models failed")
            self.log("All models failed", "ERROR")
            return "All models failed. Check Debug log."
        if mode == "fast":
            winner = valid_responses[0]['candidate']['name']
            if status_callback:
                status_callback(f"Fast: {winner}")
            self.log(f"Fast: {winner}", "SUCCESS")
            return valid_responses[0]["code"]
        if len(valid_responses) == 1:
            if status_callback:
                status_callback("1 response")
            self.log("Only 1 response", "INFO")
            return valid_responses[0]["code"]
        if status_callback:
            status_callback("Judge...")
        judge_result = await self.judge_responses(prompt, valid_responses)
        if judge_result.get("code"):
            if status_callback:
                status_callback("Judge selected")
            return judge_result["code"]
        else:
            self.log("Judge failed, taking first", "WARN")
            if status_callback:
                status_callback("Taking first")
            return valid_responses[0]["code"]
'''

# Заменяем функцию
new_content = content[:match_start.start()] + new_func + content[end_pos:]

# Проверяем синтаксис
try:
    compile(new_content, AE_PATH, 'exec')
    print('OK: новый файл компилируется')
except SyntaxError as e:
    print(f'ERROR: синтаксическая ошибка в новом файле: {e}')
    print('Сохраняю бэкап старого файла...')
    backup_path = AE_PATH + '.broken'
    with open(backup_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f'Бэкап сохранён: {backup_path}')
    sys.exit(1)

# Сохраняем
with open(AE_PATH, 'w', encoding='utf-8') as f:
    f.write(new_content)

print('✅ agent_engine.py исправлен')
print('Теперь нажмите 🔄 Перезапуск в панели управления')