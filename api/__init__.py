# -*- coding: utf-8 -*-
"""api — REST-слой drmAIcu.

Маршруты разнесены по доменам; main.py собирает приложение.
Точка входа приложения по-прежнему main.py (тесты используют TestClient(main.app)).
"""
from .routes_system import router as system_router
from .routes_agents import router as agents_router
from .routes_providers import router as providers_router
from .routes_patches import router as patches_router
from .routes_project import router as project_router
from .routes_updates import router as updates_router

ALL_ROUTERS = (system_router, agents_router, providers_router, patches_router, project_router, updates_router)
