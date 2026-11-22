import os
import re
import sys

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

BASE = os.path.dirname(os.path.abspath(__file__))
AE_PATH = os.path.join(BASE, 'agent_engine.py')

print('=' * 70)
print('ВОССТАНОВЛЕНИЕ функции run_task в agent_engine.py')
print('=' * 70)

if not os.path.exists(AE_PATH):
    print('ERROR: agent_engine.py не найден')
    sys.exit(1)

with open(AE_PATH, 'r', encoding='utf-8') as f:
    content = f.read()

# Проверяем, есть ли уже run_task
if 'def run_task(' in content:
    print('WARNING: run_task уже существует в файле')
    print('Продолжаю поиск для проверки корректности...')

# Находим функцию _query_ollama — она точно есть и не была затронута
pattern_ollama = re.compile(r'^\s*async def _query_ollama\(', re.MULTILINE)
match_ollama = pattern_ollama.search(content)

if not match_ollama:
    print('ERROR: функция _query_ollama не найдена')
    print('Файл agent_engine.py сильно повреждён')
    sys.exit(1)

print(f'OK: найдена _query_ollama на позиции {match_ollama.start()}')

# Находим конец _query_ollama (следующая функция с тем же или меньшим отступом)
start_pos = match_ollama.start()
indent = len(content[start_pos:start_pos + content[start_pos:].index('async')])

# Ищем следующую строку с отступом <= indent, начинающуюся с def/async def/class
lines_after = content[match_ollama.end():].split('\n')
end_offset = 0
for i, line in enumerate(lines_after):
    if not line.strip():
        continue
    line_indent = len(line) - len(line.lstrip())
    if line_indent <= indent and (line.strip().startswith('def ') or 
                                    line.strip().startswith('async def ') or
                                    line.strip().startswith('class ')):
        end_offset = sum(len(l) + 1 for l in lines_after[:i])
        break
else:
    end_offset = len(content) - match_ollama.end()

ollama_end = match_ollama.end() + end_offset
print(f'Конец _query_ollama: позиция {ollama_end}')

# Новая функция run_task с поддержкой model и provider
new_run_task = '''

    async def run_task(self, prompt: str, status_callback=None, mode: str = "full", model: str = None, provider: str = None) -> str:
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

# Вставляем новую функцию после _query_ollama
new_content = content[:ollama_end] + new_run_task + content[ollama_end:]

# Проверяем синтаксис
try:
    compile(new_content, AE_PATH, 'exec')
    print('OK: синтаксис валиден')
except SyntaxError as e:
    print(f'ERROR: синтаксическая ошибка: {e}')
    # Сохраняем бэкап
    backup_path = AE_PATH + '.before_restore'
    with open(backup_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f'Бэкап сохранён: {backup_path}')
    sys.exit(1)

# Сохраняем
with open(AE_PATH, 'w', encoding='utf-8') as f:
    f.write(new_content)

print('✅ Функция run_task восстановлена с поддержкой model и provider')
print('Теперь нажмите 🔄 Перезапуск в панели управления')