# -*- coding: utf-8 -*-
"""api.shared — общие зависимости API-слоя.

Единое место для путей, конфига, лога ядра и реестра движка.
Роутеры импортируют отсюда; main.py только собирает приложение.
"""
import json
import os
import sys
import threading
import importlib
from datetime import datetime

import patch_engine as _pe
from guards import is_critical_rel, is_doc_rel, validate_url  # noqa: F401 (реэкспорт для роутеров)

BASE = _pe.BASE
PATCH_DIR = _pe.PATCH_DIR
ARCHIVE_DIR = _pe.ARCHIVE_DIR
BACKUP_DIR = _pe.BACKUP_DIR
MANIFEST = _pe.MANIFEST
CONFIG = os.path.join(BASE, 'settings.json')
ENGINE = os.path.join(BASE, 'agent_engine.py')
RESTART_FLAG = os.path.join(BASE, 'restart.flag')
PROJ_ARCHIVE = os.path.join(BASE, 'project_archive')
IMPORTANT = os.path.join(BASE, '.project-important.json')
LOG = []
SKIP = {'node_modules', '.git', '__pycache__', '.venv', 'venv', '.vscode', '.idea', 'dist', 'project_archive', '.vite', '.pytest_cache'}

for d in (PATCH_DIR, ARCHIVE_DIR, BACKUP_DIR, PROJ_ARCHIVE):
    os.makedirs(d, exist_ok=True)


def log(msg, lvl='INFO'):
    t = datetime.now().strftime('%H:%M:%S')
    LOG.append({'time': t, 'level': lvl.lower(), 'message': str(msg), 'source': 'Core'})
    if len(LOG) > 500:
        LOG.pop(0)
    print('[' + t + '] [' + lvl + '] ' + str(msg))


def human(n):
    if n < 1024:
        return str(n) + ' B'
    if n < 1048576:
        return str(round(n / 1024, 1)) + ' KB'
    return str(round(n / 1048576, 1)) + ' MB'


def load_cfg():
    if os.path.exists(CONFIG):
        try:
            with open(CONFIG, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {'ollama_url': 'http://localhost:11434'}


# --- Реестр AI-движка (один на процесс, используется агентными и provider-роутерами) ---

engine_obj = None
lock = threading.Lock()


def get_engine():
    global engine_obj
    with lock:
        if engine_obj is not None:
            return engine_obj
        try:
            if 'agent_engine' in sys.modules:
                importlib.reload(sys.modules['agent_engine'])
            else:
                import agent_engine
            engine_obj = sys.modules['agent_engine'].AgentEngine(load_cfg(), log_callback=log)
            log('Engine loaded', 'SUCCESS')
        except Exception as e:
            log('Engine error: ' + str(e), 'ERROR')
        return engine_obj


def rebuild_engine():
    """Пересобрать движок после смены конфигурации провайдеров."""
    global engine_obj
    with lock:
        if engine_obj is not None:
            try:
                importlib.reload(sys.modules['agent_engine'])
                engine_obj = sys.modules['agent_engine'].AgentEngine(load_cfg(), log_callback=log)
            except Exception as e:
                log('Engine rebuild error: ' + str(e), 'ERROR')
