import json
import urllib.request
import os

# Убеждаемся, что папка patch существует
os.makedirs("patch", exist_ok=True)

patch_data = {
    "patch_id": "117",
    "version": "1.0",
    "type": "multi",
    "description": "Добавить полноценную вкладку Консоль с выбором моделей на NiceGUI",
    "author": "review",
    "created_at": "2026-11-21T12:00:00",
    "operations": [
        {
            "type": "search_and_replace",
            "target_file": "main.py",
            "find": "def create_ui():\n    ui.dark_mode().enable()\n    with ui.header().classes('bg-gray-900 text-white p-4'):\n        ui.label('drmAIcu Core v3.5.0 MULTI-ATOMIC').classes('text-xl font-bold')",
            "replace": """def create_ui():
    ui.dark_mode().enable()
    
    # Шапка
    with ui.header().classes('bg-gray-900 text-white p-4'):
        ui.label('drmAIcu Core v3.5.2 NICEGUI').classes('text-xl font-bold')
    
    # Вкладки
    with ui.tabs().classes('w-full') as tabs:
        console_tab = ui.tab('🖥 Консоль')
    
    with ui.tab_panels(tabs, value=console_tab).classes('w-full'):
        with ui.tab_panel(console_tab):
            # Выбор провайдера
            provider_select = ui.select(
                ['Ollama', 'Groq', 'Все'],
                value='Ollama',
                label='Провайдер'
            ).classes('w-64 mb-4')
            
            # Выбор модели
            model_select = ui.select(
                [],
                label='Модель',
                value=''
            ).classes('w-64 mb-4')
            
            # Промпт
            prompt_input = ui.textarea(
                label='Промпт',
                placeholder='Опишите задачу... (Ctrl+Enter для отправки)'
            ).classes('w-full mb-4').props('rows=4')
            
            # Ответ
            response_display = ui.markdown('*Ожидание запроса...*').classes('w-full')
            
            # Функция загрузки моделей
            async def load_models():
                try:
                    import requests
                    cfg = load_cfg()
                    r = requests.get(cfg.get('ollama_url', 'http://localhost:11434') + '/api/tags', timeout=5)
                    if r.status_code == 200:
                        models_data = r.json().get('models', [])
                        model_names = [m['name'] for m in models_data]
                        model_select.options = model_names
                        if model_names and not model_select.value:
                            model_select.value = model_names[0]
                except Exception as e:
                    log(f'Ошибка загрузки моделей: {e}', 'ERROR')
            
            # Функция отправки задачи
            async def send_task():
                prompt = prompt_input.value
                if not prompt:
                    response_display.content = '**Ошибка:** Введите промпт'
                    return
                
                response_display.content = '*Обработка...*'
                
                try:
                    import requests
                    payload = {
                        'prompt': prompt,
                        'mode': 'fast',
                        'model': model_select.value or '',
                        'provider': 'ollama' if provider_select.value == 'Ollama' else 'groq' if provider_select.value == 'Groq' else 'all'
                    }
                    r = requests.post('http://127.0.0.1:8080/api/task', json=payload, timeout=120)
                    if r.status_code == 200:
                        result = r.json()
                        if result.get('success'):
                            response_display.content = result.get('result', '*Нет ответа*')
                        else:
                            response_display.content = f"**Ошибка:** {result.get('error', 'Неизвестная ошибка')}"
                    else:
                        response_display.content = f'**HTTP Ошибка:** {r.status_code}'
                except Exception as e:
                    response_display.content = f'**Исключение:** {str(e)}'
            
            # Кнопка отправки
            ui.button('▶ Отправить', on_click=send_task).classes('bg-green-500 text-white mb-4')
            
            # Автообновление списка моделей каждые 10 секунд
            ui.timer(10.0, load_models)
            
            # Загрузка моделей при старте
            load_models()
            
            # Обработка Enter
            prompt_input.on('keydown.enter', send_task)"""
        }
    ]
}

# 1. Сохраняем файл корректно (UTF-8 без BOM)
file_path = "patch/117.json"
with open(file_path, "w", encoding="utf-8") as f:
    json.dump(patch_data, f, indent=2, ensure_ascii=False)
print(f"✅ Файл {file_path} сохранён корректно (UTF-8).")

# 2. Применяем через API (атомарно, с бэкапом и проверкой синтаксиса)
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