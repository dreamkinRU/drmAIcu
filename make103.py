import json
import os
import re
import sys

BASE = os.path.dirname(os.path.abspath(__file__))

def read(path):
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()

def main():
    print('=== make103.py v5: финальная версия ===\n')

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

    ae_src = read(ae_path)
    main_src = read(main_path)
    api_src = read(api_path)
    hook_src = read(console_hook_path)
    tab_src = read(console_tab_path)
    app_src = read(app_path)

    operations = []

    # === Операция 1: main.py ===
    old_s_task = (
        "@app.post('/api/task')\n"
        "async def s_task(payload: dict):\n"
        "    e = get_engine()\n"
        "    if not e:\n"
        "        return JSONResponse({'success': False, 'error': 'Engine not loaded'})\n"
        "    try:\n"
        "        r = await e.run_task(payload.get('prompt', ''), mode=payload.get('mode', 'full'))\n"
        "        return JSONResponse({'success': True, 'result': r})\n"
        "    except Exception as ex:\n"
        "        return JSONResponse({'success': False, 'error': str(ex)})"
    )
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
    if old_s_task not in main_src:
        print('ERROR: функция s_task не найдена в main.py')
        sys.exit(1)
    print('OK: найден s_task в main.py')
    operations.append({'type': 'search_and_replace', 'target_file': 'main.py', 'find': old_s_task, 'replace': new_s_task})

    # === Операция 2: agent_engine.py — сигнатура run_task ===
    old_sig = 'async def run_task(self, prompt: str, status_callback=None, mode: str = "full") -> str:'
    new_sig = 'async def run_task(self, prompt: str, status_callback=None, mode: str = "full", model: str = None, provider: str = None) -> str:'
    if old_sig not in ae_src:
        print('ERROR: сигнатура run_task не найдена в agent_engine.py')
        sys.exit(1)
    print('OK: найдена сигнатура run_task в agent_engine.py')
    operations.append({'type': 'search_and_replace', 'target_file': 'agent_engine.py', 'find': old_sig, 'replace': new_sig})

    # === Операция 3: agent_engine.py — блок candidates (УМНЫЙ ПОИСК ЧЕРЕЗ REGEX) ===
    # Ищем строку "candidates = self._get_candidates()" и определяем её отступ
    pattern = re.compile(r'^([ \t]*)candidates = self\._get_candidates\(\)', re.MULTILINE)
    match = pattern.search(ae_src)
    if not match:
        print('ERROR: строка "candidates = self._get_candidates()" не найдена в agent_engine.py')
        sys.exit(1)
    
    indent = match.group(1)  # Реальный отступ (пробелы или табы)
    old_candidates_line = match.group(0)
    
    new_candidates_block = (
        f'{indent}if model and provider:\n'
        f'{indent}    self.log(f"TARGET: {{provider}} / {{model}}", "INFO")\n'
        f'{indent}    candidates = [{{"provider": provider, "model": model, "name": f"{{provider}}: {{model}}"}}]\n'
        f'{indent}else:\n'
        f'{indent}    candidates = self._get_candidates()'
    )
    
    print(f'OK: найден candidates в agent_engine.py (отступ: {repr(indent)})')
    operations.append({
        'type': 'search_and_replace',
        'target_file': 'agent_engine.py',
        'find': old_candidates_line,
        'replace': new_candidates_block
    })

    # === Операция 4: api.ts ===
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
    if old_api not in api_src:
        print('ERROR: старый runAiTask не найден в api.ts')
        sys.exit(1)
    print('OK: найден runAiTask в api.ts')
    operations.append({'type': 'search_and_replace', 'target_file': 'src/services/api.ts', 'find': old_api, 'replace': new_api})

    # === Операция 5: useConsole.ts — useState ===
    old_hook_sig = "const [providerMode, setProviderMode] = useState<'ollama' | 'groq' | 'all'>('all');"
    new_hook_sig = "const [providerMode, setProviderMode] = useState<'ollama' | 'groq' | 'all'>('ollama');\n  const [selectedModel, setSelectedModel] = useState('qwen2.5-coder:1.5b');"
    if old_hook_sig not in hook_src:
        print('ERROR: useState providerMode не найден в useConsole.ts')
        sys.exit(1)
    print('OK: найден useState providerMode в useConsole.ts')
    operations.append({'type': 'search_and_replace', 'target_file': 'src/hooks/useConsole.ts', 'find': old_hook_sig, 'replace': new_hook_sig})

    # === Операция 6: useConsole.ts — вызов runAiTaskApi ===
    old_call = "const data = await runAiTaskApi(consolePrompt, providerMode);"
    new_call = "const data = await runAiTaskApi(consolePrompt, providerMode, selectedModel);"
    if old_call not in hook_src:
        print('ERROR: вызов runAiTaskApi не найден в useConsole.ts')
        sys.exit(1)
    print('OK: найден вызов runAiTaskApi в useConsole.ts')
    operations.append({'type': 'search_and_replace', 'target_file': 'src/hooks/useConsole.ts', 'find': old_call, 'replace': new_call})

    # === Операция 7: useConsole.ts — return ===
    old_return = (
        "  return {\n"
        "    consolePrompt, setConsolePrompt,\n"
        "    consoleLoading, providerMode, setProviderMode,\n"
        "    runAiTask,\n"
        "  };\n"
        "}"
    )
    new_return = (
        "  return {\n"
        "    consolePrompt, setConsolePrompt,\n"
        "    consoleLoading, providerMode, setProviderMode,\n"
        "    selectedModel, setSelectedModel,\n"
        "    runAiTask,\n"
        "  };\n"
        "}"
    )
    if old_return not in hook_src:
        print('ERROR: return statement не найден в useConsole.ts')
        sys.exit(1)
    print('OK: найден return statement в useConsole.ts')
    operations.append({'type': 'search_and_replace', 'target_file': 'src/hooks/useConsole.ts', 'find': old_return, 'replace': new_return})

    # === Операция 8: ConsoleTab.tsx — интерфейс пропсов ===
    old_props = (
        "interface ConsoleTabProps {\n"
        "  consolePrompt: string;\n"
        "  setConsolePrompt: (value: string) => void;\n"
        "  consoleLoading: boolean;\n"
        "  providerMode: 'ollama' | 'groq' | 'all';\n"
        "  setProviderMode: (mode: 'ollama' | 'groq' | 'all') => void;\n"
        "  ollamaUrl: string;\n"
        "  setOllamaUrl: (url: string) => void;\n"
        "  runAiTask: () => void;\n"
        "}"
    )
    new_props = (
        "interface ConsoleTabProps {\n"
        "  consolePrompt: string;\n"
        "  setConsolePrompt: (value: string) => void;\n"
        "  consoleLoading: boolean;\n"
        "  providerMode: 'ollama' | 'groq' | 'all';\n"
        "  setProviderMode: (mode: 'ollama' | 'groq' | 'all') => void;\n"
        "  selectedModel: string;\n"
        "  setSelectedModel: (model: string) => void;\n"
        "  ollamaModels: string[];\n"
        "  ollamaUrl: string;\n"
        "  setOllamaUrl: (url: string) => void;\n"
        "  runAiTask: () => void;\n"
        "}"
    )
    if old_props not in tab_src:
        print('ERROR: интерфейс ConsoleTabProps не найден в ConsoleTab.tsx')
        sys.exit(1)
    print('OK: найден интерфейс ConsoleTabProps в ConsoleTab.tsx')
    operations.append({'type': 'search_and_replace', 'target_file': 'src/components/tabs/ConsoleTab.tsx', 'find': old_props, 'replace': new_props})

    # === Операция 9: ConsoleTab.tsx — деструктуризация ===
    old_destruct = (
        "  const {\n"
        "    consolePrompt, setConsolePrompt, consoleLoading,\n"
        "    providerMode, setProviderMode, ollamaUrl, setOllamaUrl, runAiTask,\n"
        "  } = props;"
    )
    new_destruct = (
        "  const {\n"
        "    consolePrompt, setConsolePrompt, consoleLoading,\n"
        "    providerMode, setProviderMode,\n"
        "    selectedModel, setSelectedModel, ollamaModels,\n"
        "    ollamaUrl, setOllamaUrl, runAiTask,\n"
        "  } = props;"
    )
    if old_destruct not in tab_src:
        print('ERROR: деструктуризация пропсов не найдена в ConsoleTab.tsx')
        sys.exit(1)
    print('OK: найдена деструктуризация пропсов в ConsoleTab.tsx')
    operations.append({'type': 'search_and_replace', 'target_file': 'src/components/tabs/ConsoleTab.tsx', 'find': old_destruct, 'replace': new_destruct})

    # === Операция 10: ConsoleTab.tsx — кнопки провайдеров ===
    old_buttons = (
        "        <div className=\"flex gap-3 mb-4\">\n"
        "          <button onClick={() => setProviderMode('ollama')} className={`flex-1 px-4 py-3 rounded-lg text-sm font-medium transition-all border-2 ${providerMode === 'ollama' ? 'bg-emerald-500/20 border-emerald-500/50 text-emerald-400' : 'bg-gray-800/50 border-gray-700 text-gray-400'}`}>🏠 Ollama</button>\n"
        "          <button onClick={() => setProviderMode('groq')} className={`flex-1 px-4 py-3 rounded-lg text-sm font-medium transition-all border-2 ${providerMode === 'groq' ? 'bg-cyan-500/20 border-cyan-500/50 text-cyan-400' : 'bg-gray-800/50 border-gray-700 text-gray-400'}`}>☁️ Groq</button>\n"
        "          <button onClick={() => setProviderMode('all')} className={`flex-1 px-4 py-3 rounded-lg text-sm font-medium transition-all border-2 ${providerMode === 'all' ? 'bg-purple-500/20 border-purple-500/50 text-purple-400' : 'bg-gray-800/50 border-gray-700 text-gray-400'}`}>⚡ Все</button>\n"
        "        </div>"
    )
    new_buttons = (
        "        <div className=\"flex gap-3 mb-4\">\n"
        "          <button onClick={() => setProviderMode('ollama')} className={`flex-1 px-4 py-3 rounded-lg text-sm font-medium transition-all border-2 ${providerMode === 'ollama' ? 'bg-emerald-500/20 border-emerald-500/50 text-emerald-400' : 'bg-gray-800/50 border-gray-700 text-gray-400'}`}>🏠 Ollama</button>\n"
        "          <button onClick={() => setProviderMode('groq')} className={`flex-1 px-4 py-3 rounded-lg text-sm font-medium transition-all border-2 ${providerMode === 'groq' ? 'bg-cyan-500/20 border-cyan-500/50 text-cyan-400' : 'bg-gray-800/50 border-gray-700 text-gray-400'}`}>☁️ Groq</button>\n"
        "        </div>\n"
        "        {providerMode === 'ollama' && ollamaModels.length > 0 && (\n"
        "          <div className=\"mb-4\">\n"
        "            <label className=\"text-xs text-gray-400 mb-1 block\">Модель:</label>\n"
        "            <select\n"
        "              value={selectedModel}\n"
        "              onChange={(e) => setSelectedModel(e.target.value)}\n"
        "              className=\"w-full px-4 py-3 rounded-lg bg-gray-800 border border-gray-700 text-white text-sm focus:border-emerald-500 focus:outline-none\"\n"
        "            >\n"
        "              {ollamaModels.map(m => (\n"
        "                <option key={m} value={m}>{m}</option>\n"
        "              ))}\n"
        "            </select>\n"
        "          </div>\n"
        "        )}"
    )
    if old_buttons not in tab_src:
        print('ERROR: блок кнопок провайдеров не найден в ConsoleTab.tsx')
        sys.exit(1)
    print('OK: найден блок кнопок провайдеров в ConsoleTab.tsx')
    operations.append({'type': 'search_and_replace', 'target_file': 'src/components/tabs/ConsoleTab.tsx', 'find': old_buttons, 'replace': new_buttons})

    # === Операция 11: App.tsx ===
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
    if old_app not in app_src:
        print('ERROR: ConsoleTab в App.tsx не найден')
        sys.exit(1)
    print('OK: найден ConsoleTab в App.tsx')
    operations.append({'type': 'search_and_replace', 'target_file': 'src/App.tsx', 'find': old_app, 'replace': new_app})

    # === Проверка уникальности якорей ===
    files = {
        'main.py': main_src,
        'agent_engine.py': ae_src,
        'src/services/api.ts': api_src,
        'src/hooks/useConsole.ts': hook_src,
        'src/components/tabs/ConsoleTab.tsx': tab_src,
        'src/App.tsx': app_src,
    }
    for i, op in enumerate(operations):
        content = files[op['target_file']]
        count = content.count(op['find'])
        if count != 1:
            print(f'ERROR: операция {i+1} ({op["target_file"]}): найдено {count} вхождений якоря (ожидалось 1)')
            sys.exit(1)
    print(f'\nOK: все {len(operations)} якорей уникальны')

    # === Сохраняем патч ===
    patch = {
        'patch_id': '103',
        'version': '1.0',
        'type': 'multi',
        'description': 'Console: explicit model selection passed from UI to agent_engine',
        'author': 'review',
        'created_at': '2026-11-19T23:00:00',
        'operations': operations,
    }
    out_path = os.path.join(BASE, 'patch', '103.json')
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(patch, f, indent=2, ensure_ascii=False)
    print(f'\nDONE: {out_path} создан с {len(operations)} операциями')

if __name__ == '__main__':
    main()