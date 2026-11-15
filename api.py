# api.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import main  # Импортируем твои существующие функции из main.py
import json
import os

app = FastAPI(title="drmAIcu API Bridge")

# Разрешаем запросы с React (порт 3000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/status")
def get_status():
    """Возвращает общий статус системы для дашборда"""
    config = main.load_config()
    ollama_online = False
    try:
        import urllib.request
        urllib.request.urlopen(f"{config.get('ollama_url', 'http://localhost:11434')}/api/tags", timeout=2)
        ollama_online = True
    except:
        pass

    return {
        "version": "3.2.0",
        "fortress_core": "3.0.6",
        "ollama": {"status": "online" if ollama_online else "offline"},
        "guardian": "ACTIVE",
        "agents_active": 1 # Заглушка, можно доработать подсчет из agent_engine
    }

@app.get("/api/logs")
def get_logs(lines: int = 50):
    """Возвращает последние логи из DEBUG_LOG в main.py"""
    # Берем последние N записей из списка DEBUG_LOG
    recent_logs = main.DEBUG_LOG[-lines:] if hasattr(main, 'DEBUG_LOG') else []
    return {"logs": recent_logs}

@app.post("/api/restart")
def trigger_restart():
    """Создает флаг перезапуска, который поймает launcher.bat"""
    try:
        with open("restart.flag", "w") as f:
            f.write("restart")
        return {"status": "success", "message": "Restart flag created"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/api/apply-patch")
async def apply_patch(payload: dict):
    """Вызывает UniversalAIGuardian для применения изменений в коде"""
    filename = payload.get("filename")
    content = payload.get("content")
    description = payload.get("description", "Manual patch from UI")
    
    if not filename or not content:
        return {"success": False, "error": "Missing filename or content"}
        
    # Инициализируем гардиана (если он еще не создан в main)
    engine = main.get_engine()
    if not engine:
        return {"success": False, "error": "Engine not loaded"}
        
    guardian = main.UniversalAIGuardian(engine, main.log_debug)
    
    # Запускаем 4-уровневую валидацию и применение
    validation = await guardian.validate_and_apply_patch(filename, content, description)
    if validation.get("approved"):
        success = await guardian.apply_patch(filename, content, validation)
        return {"success": success, "validation": validation}
    else:
        return {"success": False, "validation": validation}