# Архитектура drmAIcu

## Компоненты
- **main.py** (v3.1.2): Ядро на NiceGUI/FastAPI, порт 8080
- **agent_engine.py** (v2.3): Движок ИИ
- **src/App.tsx** (v3.4.1): React-панель, порт 5173
- **launcher.bat**: Единый лаунчер

## Поток данных
React → Vite Proxy → FastAPI → agent_engine.py → Ollama/API

## Безопасность
- Universal AI-Guardian: валидация + бэкап
- PatchMaster: атомарная замена + откат