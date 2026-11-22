import json
import os
import re
import sys

BASE = os.path.dirname(os.path.abspath(__file__))

def read(path):
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()

def extract_function(src, func_name):
    """Извлекает полную функцию из исходного кода."""
    pattern = re.compile(r'^(\s*)(async\s+)?def\s+' + re.escape(func_name) + r'\s*\(', re.MULTILINE)
    m = pattern.search(src)
    if not m:
        return None, None, None
    indent = m.group(1)
    start = m.start()
    lines = src[start:].split('\n')
    end_offset = 0
    for i, line in enumerate(lines[1:], 1):
        if not line.strip():
            continue
        line_indent = line[:len(line) - len(line.lstrip())]
        if len(line_indent) <= len(indent) and line.strip():
            end_offset = sum(len(l) + 1 for l in lines[:i])
            break
    else:
        end_offset = len(src) - start
    return start, src[start:start + end_offset].rstrip(), indent

def main():
    print('=== make103_full.py: надёжная версия с full_replace ===\n')

    ae_path = os.path.join(BASE, 'agent_engine.py')
    main_path = os.path.join(BASE, 'main.py')
    api_path = os.path.join(BASE, 'src', 'services', 'api.ts')
    console_hook_path = os.path.join(BASE, 'src', 'hooks', 'useConsole.ts')
    console_tab_path = os.path.join(BASE, 'src', 'components', 'tabs', 'ConsoleTab.tsx')
    app_path = os.path.join(BASE, 'src', 'App.tsx')

    for p in (ae_path, main_path, api_path, console_hook_path, console_tab_path, app_path):
        if not os.path.exists(p):
            print('ERROR: файл не найден:', p)
            sys.exit(1)

    main_src = read(main_path)
    ae_src = read(ae_path)
    api_src = read(api_path)
    hook_src = read(console_hook_path)
    tab_src = read(console_tab_path)
    app_src = read(app_path)

    operations = []

    # === Операция 1: main.py — full_replace функции s_task ===
    start, s_task_body, indent = extract_function(main_src, 's_task')
    if not s_task_body:
        print('ERROR: функция s_task не найдена в main.py')
        sys.exit(1)
    print(f'OK: извлечена s_task из main.py (строка {main_src[:start].count(chr(10)) + 1})')

    new_s_task = (
        "@app.post('/api/task')\n"
        "async def s_task(payload: dict):\n"
        "    e = get_engine()\n"
        "    if not e:\n"
        "        return JSONResponse({'success': False, 'error': 'Engine not loaded'})\n"
        "    try:\n"
        "        prompt = payload.get('prompt', '')\n"
        "        mode = payload.get('mode', 'fast')\n"
        "        model = payload.get('model', '')\n"
        "        provider = payload.get('provider', 'ollama')\n"
        "        r = await e.run_task(prompt, mode=mode, model=model, provider=provider)\n"
        "        return JSONResponse({'success': True, 'result': r})\n"
        "    except Exception as ex:\n"
        "        return JSONResponse({'success': False, 'error': str(ex)})"
    )
    operations.append({
        'type': 'full_replace',
        'target_file': 'main.py',
        'old_content': s_task_body,
        'new_content': new_s_task,
        'description': 'Замена функции s_task с поддержкой model и provider'
    })

    # === Операция 2: agent_engine.py — full_replace функции run_task ===
    start, run_task_body, indent = extract_function(ae_src, 'run_task')
    if not run_task_body:
        print('ERROR: функция run_task не найдена в agent_engine.py')
        sys.exit(1)
    print(f'OK: извлечена run_task из agent_engine.py (строка {ae_src[:start].count(chr(10)) + 1})')

    # Заменяем сигнатуру и блок candidates
    new_run_task = run_task_body.replace(
        'async def run_task(self, prompt: str, status_callback=None, mode: str = "full") -> str:',
        'async def run_task(self, prompt: str, status_callback=None, mode: str = "full", model: str = None, provider: str = None) -> str:'
    ).replace(
        'candidates = self._get_candidates()',
        'if model and provider:\n' + indent + '    self.log(f"TARGET: {provider} / {model}", "INFO")\n' + indent + '    candidates = [{"provider": provider, "model": model, "name": f"{provider}: {model}"}]\n' + indent + 'else:\n' + indent + '    candidates = self._get_candidates()'
    )
    
    operations.append({
        'type': 'full_replace',
        'target_file': 'agent_engine.py',
        'old_content': run_task_body,
        'new_content': new_run_task,
        'description': 'Замена функции run_task с поддержкой model и provider'
    })

    # === Операция 3: api.ts — search_and_replace ===
    old_api = (
        "export async function runAiTask(prompt: string, mode: string): Promise<{ success: boolean; result?: string; error?: string }> {\n"
        "  try {\n"
        "    const res = await fetch('/api/task', {\n"
        "      method: 'POST',\n"
        "      headers: { 'Content-Type': 'application/json' },\n"
        "      body: JSON.stringify({ prompt, mode }),\n"
        "    });\n"
        "    return await res.json();\n"
        "  } catch {\n"
        "    return { success: false, error: 'Ошибка сети' };\n"
        "  }\n"
        "}"
    )
    new_api = (
        "export async function runAiTask(prompt: string, provider: string, model: string): Promise<{ success: boolean; result?: string; error?: string }> {\n"
        "  try {\n"
        "    const res = await fetch('/api/task', {\n"
        "      method: 'POST',\n"
        "      headers: { 'Content-Type': 'application/json' },\n"
        "      body: JSON.stringify({ prompt, provider, model, mode: 'fast' }),\n"
        "    });\n"
        "    return await res.json();\n"
        "  } catch {\n"
        "    return { success: false, error: 'Ошибка сети' };\n"
        "  }\n"
        "}"
    )
    if old_api in api_src:
        print('OK: найден runAiTask в api.ts (search_and_replace)')
        operations.append({
            'type': 'search_and_replace',
            'target_file': 'src/services/api.ts',
            'find': old_api,
            'replace': new_api
        })
    else:
        print('WARN: runAiTask не найден в api.ts, пропускаем')

    # === Операция 4-6: useConsole.ts — search_and_replace ===
    replacements_hook = [
        (
            "const [providerMode, setProviderMode] = useState<'ollama' | 'groq' | 'all'>('all');",
            "const [providerMode, setProviderMode] = useState<'ollama' | 'groq' | 'all'>('ollama');\n  const [selectedModel, setSelectedModel] = useState('qwen2.5-coder:1.5b');",
            "useState providerMode"
        ),
        (
            "const data = await runAiTaskApi(consolePrompt, providerMode);",
            "const data = await runAiTaskApi(consolePrompt, providerMode, selectedModel);",
            "вызов runAiTaskApi"
        ),
        (
            "  return {\n    consolePrompt, setConsolePrompt,\n    consoleLoading, providerMode, setProviderMode,\n    runAiTask,\n  };\n}",
            "  return {\n    consolePrompt, setConsolePrompt,\n    consoleLoading, providerMode, setProviderMode,\n    selectedModel, setSelectedModel,\n    runAiTask,\n  };\n}",
            "return statement"
        )
    ]
    
    for old, new, desc in replacements_hook:
        if old in hook_src:
            print(f'OK: найден {desc} в useConsole.ts')
            operations.append({
                'type': 'search_and_replace',
                'target_file': 'src/hooks/useConsole.ts',
                'find': old,
                'replace': new
            })
        else:
            print(f'WARN: {desc} не найден в useConsole.ts, пропускаем')

    # === Операция 7-9: ConsoleTab.tsx ===
    replacements_tab = [
        (
            "interface ConsoleTabProps {\n  consolePrompt: string;\n  setConsolePrompt: (value: string) => void;\n  consoleLoading: boolean;\n  providerMode: 'ollama' | 'groq' | 'all';\n  setProviderMode: (mode: 'ollama' | 'groq' | 'all') => void;\n  ollamaUrl: string;\n  setOllamaUrl: (url: string) => void;\n  runAiTask: () => void;\n}",
            "interface ConsoleTabProps {\n  consolePrompt: string;\n  setConsolePrompt: (value: string) => void;\n  consoleLoading: boolean;\n  providerMode: 'ollama' | 'groq' | 'all';\n  setProviderMode: (mode: 'ollama' | 'groq' | 'all') => void;\n  selectedModel: string;\n  setSelectedModel: (model: string) => void;\n  ollamaModels: string[];\n  ollamaUrl: string;\n  setOllamaUrl: (url: string) => void;\n  runAiTask: () => void;\n}",
            "интерфейс ConsoleTabProps"
        ),
        (
            "  const {\n    consolePrompt, setConsolePrompt, consoleLoading,\n    providerMode, setProviderMode, ollamaUrl, setOllamaUrl, runAiTask,\n  } = props;",
            "  const {\n    consolePrompt, setConsolePrompt, consoleLoading,\n    providerMode, setProviderMode,\n    selectedModel, setSelectedModel, ollamaModels,\n    ollamaUrl, setOllamaUrl, runAiTask,\n  } = props;",
            "деструктуризация пропсов"
        ),
        (
            '        <div className="flex gap-3 mb-4">\n          <button onClick={() => setProviderMode(\'ollama\')} className={`flex-1 px-4 py-3 rounded-lg text-sm font-medium transition-all border-2 ${providerMode === \'ollama\' ? \'bg-emerald-500/20 border-emerald-500/50 text-emerald-400\' : \'bg-gray-800/50 border-gray-700 text-gray-400\'}`}>🏠 Ollama</button>\n          <button onClick={() => setProviderMode(\'groq\')} className={`flex-1 px-4 py-3 rounded-lg text-sm font-medium transition-all border-2 ${providerMode === \'groq\' ? \'bg-cyan-500/20 border-cyan-500/50 text-cyan-400\' : \'bg-gray-800/50 border-gray-700 text-gray-400\'}`}>☁️ Groq</button>\n          <button onClick={() => setProviderMode(\'all\')} className={`flex-1 px-4 py-3 rounded-lg text-sm font-medium transition-all border-2 ${providerMode === \'all\' ? \'bg-purple-500/20 border-purple-500/50 text-purple-400\' : \'bg-gray-800/50 border-gray-700 text-gray-400\'}`}>⚡ Все</button>\n        </div>',
            '        <div className="flex gap-3 mb-4">\n          <button onClick={() => setProviderMode(\'ollama\')} className={`flex-1 px-4 py-3 rounded-lg text-sm font-medium transition-all border-2 ${providerMode === \'ollama\' ? \'bg-emerald-500/20 border-emerald-500/50 text-emerald-400\' : \'bg-gray-800/50 border-gray-700 text-gray-400\'}`}>🏠 Ollama</button>\n          <button onClick={() => setProviderMode(\'groq\')} className={`flex-1 px-4 py-3 rounded-lg text-sm font-medium transition-all border-2 ${providerMode === \'groq\' ? \'bg-cyan-500/20 border-cyan-500/50 text-cyan-400\' : \'bg-gray-800/50 border-gray-700 text-gray-400\'}`}>☁️ Groq</button>\n        </div>\n        {providerMode === \'ollama\' && ollamaModels.length > 0 && (\n          <div className="mb-4">\n            <label className="text-xs text-gray-400 mb-1 block">Модель:</label>\n            <select\n              value={selectedModel}\n              onChange={(e) => setSelectedModel(e.target.value)}\n              className="w-full px-4 py-3 rounded-lg bg-gray-800 border border-gray-700 text-white text-sm focus:border-emerald-500 focus:outline-none"\n            >\n              {ollamaModels.map(m => (\n                <option key={m} value={m}>{m}</option>\n              ))}\n            </select>\n          </div>\n        )}',
            "блок кнопок провайдеров"
        )
    ]
    
    for old, new, desc in replacements_tab:
        if old in tab_src:
            print(f'OK: найден {desc} в ConsoleTab.tsx')
            operations.append({
                'type': 'search_and_replace',
                'target_file': 'src/components/tabs/ConsoleTab.tsx',
                'find': old,
                'replace': new
            })
        else:
            print(f'WARN: {desc} не найден в ConsoleTab.tsx, пропускаем')

    # === Операция 10: App.tsx ===
    old_app = (
        "        {activeTab === 'console' && (\n"
        "          <ConsoleTab\n"
        "            consolePrompt={consolePrompt}\n"
        "            setConsolePrompt={setConsolePrompt}\n"
        "            consoleLoading={consoleLoading}\n"
        "            providerMode={providerMode}\n"
        "            setProviderMode={setProviderMode}\n"
        "            ollamaUrl={ollamaUrl}\n"
        "            setOllamaUrl={setOllamaUrl}\n"
        "            runAiTask={runAiTask}\n"
        "          />\n"
        "        )}"
    )
    new_app = (
        "        {activeTab === 'console' && (\n"
        "          <ConsoleTab\n"
        "            consolePrompt={consolePrompt}\n"
        "            setConsolePrompt={setConsolePrompt}\n"
        "            consoleLoading={consoleLoading}\n"
        "            providerMode={providerMode}\n"
        "            setProviderMode={setProviderMode}\n"
        "            selectedModel={selectedModel}\n"
        "            setSelectedModel={setSelectedModel}\n"
        "            ollamaModels={ollamaModels}\n"
        "            ollamaUrl={ollamaUrl}\n"
        "            setOllamaUrl={setOllamaUrl}\n"
        "            runAiTask={runAiTask}\n"
        "          />\n"
        "        )}"
    )
    if old_app in app_src:
        print('OK: найден ConsoleTab в App.tsx')
        operations.append({
            'type': 'search_and_replace',
            'target_file': 'src/App.tsx',
            'find': old_app,
            'replace': new_app
        })
    else:
        print('WARN: ConsoleTab не найден в App.tsx, пропускаем')

    # === ПРОВЕРКА ВАЛИДНОСТИ ОПЕРАЦИЙ (симуляция превью) ===
    print('\n=== ПРОВЕРКА ВАЛИДНОСТИ ОПЕРАЦИЙ ===')
    files = {
        'main.py': main_src,
        'agent_engine.py': ae_src,
        'src/services/api.ts': api_src,
        'src/hooks/useConsole.ts': hook_src,
        'src/components/tabs/ConsoleTab.tsx': tab_src,
        'src/App.tsx': app_src,
    }
    
    valid_ops = []
    for i, op in enumerate(operations):
        target = op['target_file']
        content = files[target]
        
        if op['type'] == 'full_replace':
            # Для full_replace проверяем, что old_content существует в файле
            if op['old_content'] in content:
                print(f'✅ Операция {i+1} ({target}): full_replace валидна')
                valid_ops.append(op)
            else:
                print(f'❌ Операция {i+1} ({target}): old_content не найден в файле!')
        elif op['type'] == 'search_and_replace':
            # Для search_and_replace проверяем, что find существует ровно 1 раз
            count = content.count(op['find'])
            if count == 1:
                print(f'✅ Операция {i+1} ({target}): search_and_replace валидна')
                valid_ops.append(op)
            elif count == 0:
                print(f'❌ Операция {i+1} ({target}): подстрока не найдена!')
            else:
                print(f'⚠️ Операция {i+1} ({target}): найдено {count} вхождений (ожидалось 1)')
    
    if not valid_ops:
        print('\nERROR: ни одна операция не валидна!')
        sys.exit(1)
    
    print(f'\n✅ Валидных операций: {len(valid_ops)} из {len(operations)}')

    # === Сохраняем патч ===
    patch = {
        'patch_id': '103',
        'version': '1.0',
        'type': 'multi',
        'description': 'Console: explicit model selection passed from UI to agent_engine',
        'author': 'review',
        'created_at': '2026-11-20T00:00:00',
        'operations': valid_ops
    }
    out_path = os.path.join(BASE, 'patch', '103.json')
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(patch, f, indent=2, ensure_ascii=False)
    print(f'\n✅ DONE: {out_path} создан с {len(valid_ops)} валидными операциями')
    print('Можете применять через панель!')

if __name__ == '__main__':
    main()