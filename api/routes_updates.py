# -*- coding: utf-8 -*-
"""REST API для трёхэтапного Update Wizard."""
import ipaddress
from urllib.parse import urlparse

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from core.updater.manager import UpdateError, manager

router = APIRouter()


def _check_local_browser_request(request: Request, require_origin=True):
    """CSRF/browser-origin барьер для изменяющих состояние endpoint-ов.

    Это защита от cross-site запросов из браузера, не аутентификация против
    другого локального процесса под той же учётной записью ОС.
    """
    origin = request.headers.get("origin")
    if not origin and require_origin:
        raise UpdateError("Для операции обновления требуется заголовок Origin.", "origin_required", 403)
    if origin:
        try:
            parsed = urlparse(origin)
            host = parsed.hostname
            origin_ip = ipaddress.ip_address(host) if host else None
        except (ValueError, TypeError):
            raise UpdateError("Некорректный Origin.", "origin_rejected", 403)
        allowed_name = host in ("localhost", "127.0.0.1", "::1")
        allowed_ip = bool(origin_ip and origin_ip.is_loopback)
        if parsed.scheme != "http" or not (allowed_name or allowed_ip):
            raise UpdateError("Операции обновления доступны только из локального браузера.", "origin_rejected", 403)
    host_header = request.headers.get("host", "")
    try:
        request_host = urlparse("//" + host_header).hostname
        host_ip = ipaddress.ip_address(request_host) if request_host else None
    except ValueError:
        host_ip = None
    if not (request_host in ("localhost", "127.0.0.1", "::1") or (host_ip and host_ip.is_loopback)):
        raise UpdateError("Host header не относится к локальному интерфейсу.", "host_rejected", 403)
    fetch_site = request.headers.get("sec-fetch-site", "").lower()
    if fetch_site == "cross-site":
        raise UpdateError("Cross-site запрос отклонён.", "cross_site_rejected", 403)
    client_host = request.client.host if request.client else ""
    try:
        if not ipaddress.ip_address(client_host).is_loopback:
            raise UpdateError("Запрос должен поступать с локального компьютера.", "client_rejected", 403)
    except ValueError:
        if client_host != "localhost":
            raise UpdateError("Запрос должен поступать с локального компьютера.", "client_rejected", 403)


def _error(exc):
    if isinstance(exc, UpdateError):
        return JSONResponse(
            {"success": False, "error": str(exc), "code": exc.code},
            status_code=exc.status,
        )
    return JSONResponse(
        {"success": False, "error": "Внутренняя ошибка Update Manager.", "code": "internal_error"},
        status_code=500,
    )


@router.get("/api/updates/state")
def update_state(request: Request):
    try:
        _check_local_browser_request(request, require_origin=False)
        return JSONResponse(manager.state())
    except Exception as exc:
        return _error(exc)


@router.post("/api/updates/check")
def update_check(request: Request):
    try:
        _check_local_browser_request(request)
        return JSONResponse(manager.check())
    except Exception as exc:
        return _error(exc)


@router.post("/api/updates/apply")
async def update_apply(request: Request):
    try:
        _check_local_browser_request(request)
        body = await request.json()
        operation_id = body.get("operation_id") if isinstance(body, dict) else None
        if not isinstance(operation_id, str) or len(operation_id) != 32:
            raise UpdateError("Некорректный идентификатор плана.", "invalid_operation_id", 422)
        return JSONResponse(await run_in_threadpool(manager.apply, operation_id))
    except Exception as exc:
        return _error(exc)


@router.post("/api/updates/prepare")
async def update_prepare(request: Request):
    try:
        _check_local_browser_request(request)
        body = await request.json()
        operation_id = body.get("operation_id") if isinstance(body, dict) else None
        if not isinstance(operation_id, str) or len(operation_id) != 32:
            raise UpdateError("Некорректный идентификатор плана.", "invalid_operation_id", 422)
        return JSONResponse(await run_in_threadpool(manager.prepare, operation_id))
    except Exception as exc:
        return _error(exc)


@router.post("/api/updates/recover")
async def update_recover(request: Request):
    try:
        _check_local_browser_request(request)
        body = await request.json()
        operation_id = body.get("operation_id") if isinstance(body, dict) else None
        manual_confirmation = body.get("manual_confirmation", False) if isinstance(body, dict) else False
        if not isinstance(operation_id, str) or len(operation_id) != 32:
            raise UpdateError("Некорректный идентификатор операции.", "invalid_operation_id", 422)
        if not isinstance(manual_confirmation, bool):
            raise UpdateError("manual_confirmation должен быть логическим значением.", "invalid_manual_confirmation", 422)
        return JSONResponse(await run_in_threadpool(
            manager.recover, operation_id, manual_confirmation=manual_confirmation
        ))
    except Exception as exc:
        return _error(exc)
