# Архитектура drmAIcu

## Компоненты
1. **main.py** (v3.0.6 FORTRESS): Ядро на NiceGUI/FastAPI. Управляет UI, валидацией и резервным копированием.
2. **agent_engine.py** (v2.3): Движок ИИ. Поддерживает Ollama (локально) + Groq, OpenRouter, Gemini, HF, Together (облако).
3. **src/App.tsx**: Единая React-панель управления (v3.2.0).
4. **launcher.bat**: Supervisor-скрипт для автоперезапуска при сбоях.

## Поток данных
React (порт 5173) ↔ FastAPI endpoints в main.py (порт 8080) ↔ agent_engine.py ↔ Ollama/API