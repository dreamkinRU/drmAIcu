import os
import re
import sys

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

BASE = os.path.dirname(os.path.abspath(__file__))

def fix_file(filepath, pattern, replacement, name):
    if not os.path.exists(filepath):
        print(f"❌ {name} не найден: {filepath}")
        return False
    
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    match = pattern.search(content)
    if match:
        new_content = content[:match.start()] + replacement + content[match.end():]
        try:
            compile(new_content, filepath, 'exec')
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(new_content)
            print(f"✅ {name} успешно обновлён")
            return True
        except SyntaxError as e:
            print(f"❌ Ошибка синтаксиса в {name}: {e}")
            return False
    else:
        print(f"⚠️ Шаблон не найден в {name}. Возможно, уже обновлено или файл повреждён.")
        return False

print('=' * 70)
print('ИСПРАВЛЕНИЕ КОНСОЛИ OLLAMA (main.py + agent_engine.py)')
print('=' * 70)

# 1. Fix main.py
main_py = os.path.join(BASE, 'main.py')
main_pattern = re.compile(r'(@app\.post\([\'"]\/api\/task[\'"]\)\s*\nasync def s_task\(payload: dict\):.*?)(?=\n@app\.get|\n@app\.post|\nasync def s_models|\ndef s_models|\Z)', re.DOTALL)
main_replacement = """@app.post('/api/task')
async def s_task(payload: dict):
    e = get_engine()
    if not e:
        return JSONResponse({'success': False, 'error': 'Engine not loaded'})
    try:
        prompt = payload.get('prompt', '')
        mode = payload.get('mode', 'fast')
        model = payload.get('model', '')
        provider = payload.get('provider', 'ollama')
        r = await e.run_task(prompt, mode=mode, model=model, provider=provider)
        return JSONResponse({'success': True, 'result': r})
    except Exception as ex:
        return JSONResponse({'success': False, 'error': str(ex)})"""

fix_file(main_py, main_pattern, main_replacement, 'main.py (s_task)')

# 2. Fix agent_engine.py
ae_py = os.path.join(BASE, 'agent_engine.py')
ae_pattern = re.compile(r'(    async def run_task\(self, prompt: str.*?)(?=\n    async def |\n    def |\nclass |\Z)', re.DOTALL)
ae_replacement = """    async def run_task(self, prompt: str, status_callback=None, mode: str = "full", model: str = None, provider: str = None) -> str:
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
            return valid_responses[0]["code"]"""

if not fix_file(ae_py, ae_pattern, ae_replacement, 'agent_engine.py (run_task)'):
    print("⚠️ Попытка аварийного восстановления через вставку после _query_ollama...")
    with open(ae_py, 'r', encoding='utf-8') as f:
        content = f.read()
    
    ollama_match = re.search(r'(    async def _query_ollama\(self.*?\n        return response\[\'message\'\]\[\'content\'\])', content, re.DOTALL)
    if ollama_match:
        new_content = content[:ollama_match.end()] + '\n' + ae_replacement + content[ollama_match.end():]
        try:
            compile(new_content, ae_py, 'exec')
            with open(ae_py, 'w', encoding='utf-8') as f:
                f.write(new_content)
            print("✅ agent_engine.py восстановлен через fallback")
        except SyntaxError as e:
            print(f"❌ Критическая ошибка синтаксиса: {e}")
    else:
        print("❌ Не удалось найти _query_ollama для fallback")

print('\n' + '=' * 70)
print('🚀 ГОТОВО! Теперь нажмите 🔄 Перезапуск в панели управления.')
print('=' * 70)