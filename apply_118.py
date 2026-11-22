import json
import urllib.request
import os

os.makedirs("patch", exist_ok=True)

patch_data = {
    "patch_id": "118",
    "version": "1.0",
    "type": "multi",
    "description": "Добавить выбор модели в Консоль (React UI)",
    "author": "review",
    "created_at": "2026-11-21T14:00:00",
    "operations": [
        {
            "type": "search_and_replace",
            "target_file": "src/services/api.ts",
            "find": "export async function runAiTask(prompt: string, mode: string): Promise<{ success: boolean; result?: string; error?: string }> {\n  try {\n    const res = await fetch('/api/task', {\n      method: 'POST',\n      headers: { 'Content-Type': 'application/json' },\n      body: JSON.stringify({ prompt, mode }),\n    });",
            "replace": "export async function runAiTask(prompt: string, mode: string, model?: string): Promise<{ success: boolean; result?: string; error?: string }> {\n  try {\n    const res = await fetch('/api/task', {\n      method: 'POST',\n      headers: { 'Content-Type': 'application/json' },\n      body: JSON.stringify({ prompt, mode, model: model || '' }),\n    });"
        },
        {
            "type": "search_and_replace",
            "target_file": "src/hooks/useConsole.ts",
            "find": "export function useConsole(addLog: (entry: any) => void) {\n  const [consolePrompt, setConsolePrompt] = useState('');\n  const [consoleLoading, setConsoleLoading] = useState(false);\n  const [providerMode, setProviderMode] = useState<'ollama' | 'groq' | 'all'>('all');\n\n  const runAiTask = async () => {",
            "replace": "export function useConsole(addLog: (entry: any) => void) {\n  const [consolePrompt, setConsolePrompt] = useState('');\n  const [consoleLoading, setConsoleLoading] = useState(false);\n  const [providerMode, setProviderMode] = useState<'ollama' | 'groq' | 'all'>('all');\n  const [selectedModel, setSelectedModel] = useState<string>('');\n\n  const runAiTask = async () => {"
        },
        {
            "type": "search_and_replace",
            "target_file": "src/hooks/useConsole.ts",
            "find": "    try {\n      const data = await runAiTaskApi(consolePrompt, providerMode);",
            "replace": "    try {\n      const data = await runAiTaskApi(consolePrompt, providerMode, selectedModel);"
        },
        {
            "type": "search_and_replace",
            "target_file": "src/hooks/useConsole.ts",
            "find": "  return {\n    consolePrompt, setConsolePrompt,\n    consoleLoading, providerMode, setProviderMode,\n    runAiTask,\n  };",
            "replace": "  return {\n    consolePrompt, setConsolePrompt,\n    consoleLoading, providerMode, setProviderMode,\n    selectedModel, setSelectedModel,\n    runAiTask,\n  };"
        },
        {
            "type": "search_and_replace",
            "target_file": "src/App.tsx",
            "find": "  const {\n    consolePrompt, setConsolePrompt, consoleLoading,\n    providerMode, setProviderMode, runAiTask,\n  } = useConsole(addLog);",
            "replace": "  const {\n    consolePrompt, setConsolePrompt, consoleLoading,\n    providerMode, setProviderMode, selectedModel, setSelectedModel, runAiTask,\n  } = useConsole(addLog);"
        },
        {
            "type": "search_and_replace",
            "target_file": "src/App.tsx",
            "find": "        {activeTab === 'console' && (\n          <ConsoleTab\n            consolePrompt={consolePrompt}\n            setConsolePrompt={setConsolePrompt}\n            consoleLoading={consoleLoading}\n            providerMode={providerMode}\n            setProviderMode={setProviderMode}\n            ollamaUrl={ollamaUrl}\n            setOllamaUrl={setOllamaUrl}\n            runAiTask={runAiTask}\n          />\n        )}",
            "replace": "        {activeTab === 'console' && (\n          <ConsoleTab\n            consolePrompt={consolePrompt}\n            setConsolePrompt={setConsolePrompt}\n            consoleLoading={consoleLoading}\n            providerMode={providerMode}\n            setProviderMode={setProviderMode}\n            selectedModel={selectedModel}\n            setSelectedModel={setSelectedModel}\n            installedModels={installedModels}\n            ollamaUrl={ollamaUrl}\n            setOllamaUrl={setOllamaUrl}\n            runAiTask={runAiTask}\n          />\n        )}"
        },
        {
            "type": "search_and_replace",
            "target_file": "src/components/tabs/ConsoleTab.tsx",
            "find": "interface ConsoleTabProps {\n  consolePrompt: string;\n  setConsolePrompt: (value: string) => void;\n  consoleLoading: boolean;\n  providerMode: 'ollama' | 'groq' | 'all';\n  setProviderMode: (mode: 'ollama' | 'groq' | 'all') => void;\n  ollamaUrl: string;\n  setOllamaUrl: (url: string) => void;\n  runAiTask: () => void;\n}\n\nexport default function ConsoleTab(props: ConsoleTabProps) {\n  const {\n    consolePrompt, setConsolePrompt, consoleLoading,\n    providerMode, setProviderMode, ollamaUrl, setOllamaUrl, runAiTask,\n  } = props;",
            "replace": "interface ConsoleTabProps {\n  consolePrompt: string;\n  setConsolePrompt: (value: string) => void;\n  consoleLoading: boolean;\n  providerMode: 'ollama' | 'groq' | 'all';\n  setProviderMode: (mode: 'ollama' | 'groq' | 'all') => void;\n  selectedModel: string;\n  setSelectedModel: (value: string) => void;\n  installedModels: any[];\n  ollamaUrl: string;\n  setOllamaUrl: (url: string) => void;\n  runAiTask: () => void;\n}\n\nexport default function ConsoleTab(props: ConsoleTabProps) {\n  const {\n    consolePrompt, setConsolePrompt, consoleLoading,\n    providerMode, setProviderMode, selectedModel, setSelectedModel, installedModels,\n    ollamaUrl, setOllamaUrl, runAiTask,\n  } = props;"
        },
        {
            "type": "search_and_replace",
            "target_file": "src/components/tabs/ConsoleTab.tsx",
            "find": "        {(providerMode === 'ollama' || providerMode === 'all') && (\n          <input\n            type=\"text\"\n            value={ollamaUrl}\n            onChange={(e) => setOllamaUrl(e.target.value)}\n            className=\"w-full px-4 py-3 rounded-lg bg-gray-800 border border-gray-700 text-white text-sm font-mono focus:border-emerald-500 focus:outline-none\"\n          />\n        )}\n      </div>",
            "replace": "        {(providerMode === 'ollama' || providerMode === 'all') && (\n          <div className=\"space-y-3\">\n            <input\n              type=\"text\"\n              value={ollamaUrl}\n              onChange={(e) => setOllamaUrl(e.target.value)}\n              className=\"w-full px-4 py-3 rounded-lg bg-gray-800 border border-gray-700 text-white text-sm font-mono focus:border-emerald-500 focus:outline-none\"\n              placeholder=\"http://localhost:11434\"\n            />\n            <select\n              value={selectedModel}\n              onChange={(e) => setSelectedModel(e.target.value)}\n              className=\"w-full px-4 py-3 rounded-lg bg-gray-800 border border-gray-700 text-white text-sm focus:border-emerald-500 focus:outline-none appearance-none cursor-pointer\"\n            >\n              <option value=\"\">🤖 Выбрать модель...</option>\n              {installedModels.map((m: any) => (\n                <option key={m.name || m} value={m.name || m}>\n                  {m.name || m}\n                </option>\n              ))}\n            </select>\n          </div>\n        )}\n      </div>"
        }
    ]
}

file_path = "patch/118.json"
with open(file_path, "w", encoding="utf-8") as f:
    json.dump(patch_data, f, indent=2, ensure_ascii=False)
print(f"✅ Файл {file_path} сохранён корректно (UTF-8).")

req = urllib.request.Request(
    "http://127.0.0.1:8080/api/patches/apply",
    data=json.dumps(patch_data).encode("utf-8"),
    headers={"Content-Type": "application/json; charset=utf-8"}
)
try:
    with urllib.request.urlopen(req) as response:
        print("🚀 Результат применения:")
        print(response.read().decode("utf-8"))
except urllib.error.HTTPError as e:
    print(f"❌ HTTP Ошибка {e.code}: {e.read().decode('utf-8')}")
except Exception as e:
    print(f"❌ Ошибка: {e}")