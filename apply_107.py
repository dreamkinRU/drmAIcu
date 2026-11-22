import json
import urllib.request
import os

# Убеждаемся, что папка patch существует
os.makedirs("patch", exist_ok=True)

patch_data = {
    "patch_id": "107",
    "version": "1.0",
    "type": "multi",
    "description": "Исправление agent_engine.py: run_task теперь использует model и provider из UI",
    "author": "review",
    "created_at": "2026-11-21T10:00:00",
    "operations": [
        {
            "type": "search_and_replace",
            "target_file": "agent_engine.py",
            "find": "async def run_task(self, prompt: str, status_callback=None, mode: str = \"full\") -> str:",
            "replace": "async def run_task(self, prompt: str, status_callback=None, mode: str = \"full\", model: str = None, provider: str = None) -> str:"
        },
        {
            "type": "search_and_replace",
            "target_file": "agent_engine.py",
            "find": "candidates = self._get_candidates()",
            "replace": "if model and provider:\n            self.log(f\"TARGET: {provider} / {model}\", \"INFO\")\n            candidates = [{\"provider\": provider, \"model\": model, \"name\": f\"{provider}: {model}\"}]\n        else:\n            candidates = self._get_candidates()"
        }
    ]
}

# 1. Сохраняем файл корректно (UTF-8 без BOM)
file_path = "patch/107.json"
with open(file_path, "w", encoding="utf-8") as f:
    json.dump(patch_data, f, indent=2, ensure_ascii=False)
print(f"✅ Файл {file_path} сохранён корректно (UTF-8).")

# 2. Применяем через API (атомарно, с бэкапом)
req = urllib.request.Request(
    "http://127.0.0.1:8080/api/patches/apply",
    data=json.dumps(patch_data).encode("utf-8"),
    headers={"Content-Type": "application/json; charset=utf-8"}
)
try:
    with urllib.request.urlopen(req) as response:
        result = response.read().decode("utf-8")
        print("🚀 Результат применения:")
        print(result)
except urllib.error.HTTPError as e:
    print(f"❌ HTTP Ошибка {e.code}: {e.read().decode('utf-8')}")
except Exception as e:
    print(f"❌ Ошибка: {e}")