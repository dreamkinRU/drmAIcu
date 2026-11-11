# backend/api.py — минимальный каркас
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import subprocess
import psutil  # для проверки процессов

app = FastAPI(title="drmAIcu API")

# Разрешаем запросы с фронтенда (порт 5173)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health():
    """Проверка что бэкенд жив"""
    return {"status": "ok"}

@app.get("/services")
def get_services():
    """Статус всех сервисов"""
    return {
        "ollama": check_ollama(),
        "frontend": check_port(5173),
        "agent": check_process("main.py"),
    }

def check_ollama():
    import requests
    try:
        r = requests.get("http://localhost:11434/api/tags", timeout=2)
        return {"status": "ok", "models": r.json().get("models", [])}
    except:
        return {"status": "down"}

def check_port(port):
    import socket
    s = socket.socket()
    try:
        s.connect(("127.0.0.1", port))
        return {"status": "ok"}
    except:
        return {"status": "down"}
    finally:
        s.close()

def check_process(name):
    for proc in psutil.process_iter(['name', 'cmdline']):
        if name in ' '.join(proc.info.get('cmdline') or []):
            return {"status": "ok", "pid": proc.pid}
    return {"status": "down"}