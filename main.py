# main.py — точка сборки drmAIcu Core (v3.14.0 refactor)
# UI + сборка приложения; REST-маршруты разнесены по api/routes_*.py,
# движок патчей — patch_engine.py, движок агентов — agent_engine.py.
# Версия — единый источник version.py.
from version import VERSION as _VER
from nicegui import ui, app
import json
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

try:
    app.add_middleware(CORSMiddleware, allow_origins=['http://127.0.0.1:5173', 'http://localhost:5173', 'http://127.0.0.1:8080', 'http://localhost:8080'], allow_credentials=True, allow_methods=['*'], allow_headers=['*'])
except RuntimeError:
    pass

import patch_engine as _pe
from api import ALL_ROUTERS
from api.shared import log, load_cfg, get_engine
from core.plugins.routes import plugin_router, startup_plugins

# Лог ядра переезжает в api.shared; движок патчей и агентный движок получают ту же функцию лога.
_pe.log = log

# Монтаж маршрутов: плагины (как раньше) + доменные роутеры API-слоя.
app.include_router(plugin_router)
for _router in ALL_ROUTERS:
    app.include_router(_router)
startup_plugins()


def create_ui():
    ui.dark_mode().enable()

    # Шапка
    with ui.header().classes('bg-gray-900 text-white p-4'):
        ui.label('drmAIcu Core v' + _VER + ' HARDENED').classes('text-xl font-bold')

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

                label='Модель'

            ).classes('w-64 mb-4')

            # Промпт
            prompt_input = ui.textarea(
                label='Промпт',
                placeholder='Опишите задачу... (Ctrl+Enter для отправки)'
            ).classes('w-full mb-4').props('rows=4')

            # Ответ
            response_display = ui.markdown('*Ожидание запроса...*').classes('w-full')

            # Функция загрузки моделей
            def load_models():
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
                            payload = result.get('result', '')
                            if isinstance(payload, dict):
                                payload = payload.get('result') or ''
                            response_display.content = payload or '*Нет ответа*'
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
            prompt_input.on('keydown.enter', send_task)


if __name__ in {'__main__', '__mp_main__'}:
    log('Starting drmAIcu Core v' + _VER + ' HARDENED...')
    # B51 FIX (P1-04): crash-восстановление незавершённой транзакции после перезапуска
    rec_j = _pe.recover_journal()
    if rec_j:
        try:
            log('CRASH RECOVERY: ' + json.dumps(rec_j, ensure_ascii=False), 'WARNING')
        except Exception:
            pass
    get_engine()
    create_ui()
    ui.run(title='drmAIcu Core', port=8080, reload=False, show=False)
