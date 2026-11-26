# -*- coding: utf-8 -*-
"""api.routes_system — статус, версия, логи, ресурсы, документация, рестарт."""
import os
import subprocess
import sys
import threading
import time
from datetime import datetime

from fastapi import APIRouter
from fastapi.responses import FileResponse, JSONResponse

from patch_engine import safe_path, read_text
from guards import is_doc_rel
from version import VERSION as _VER
from .shared import BASE, RESTART_FLAG, LOG, log, load_cfg

router = APIRouter()


@router.get('/rollback')
def rollback_page():
    """Аварийная страница отката"""
    rollback_html = os.path.join(BASE, 'rollback.html')
    if os.path.exists(rollback_html):
        return FileResponse(rollback_html)
    return {'error': 'rollback.html not found'}


@router.get('/api/status')
def s_status():
    cfg = load_cfg()
    ok = False
    try:
        import requests
        r = requests.get(cfg.get('ollama_url', 'http://localhost:11434') + '/api/tags', timeout=2)
        ok = r.status_code == 200
    except Exception:
        pass
    return JSONResponse({'ollama': 'online' if ok else 'offline', 'guardian': 'active',
                         'version': _VER + ' MULTI-ATOMIC HARDENED',
                         'providers': {'groq': bool(cfg.get('groq_api_key')),
                                       'openrouter': bool(cfg.get('openrouter_api_key')),
                                       'gemini': bool(cfg.get('gemini_api_key'))}})


@router.get('/api/version')
def s_version():
    # Оболочка (Header) берёт версию отсюда — единый источник version.py (B68), без хардкода в UI.
    return JSONResponse({'success': True, 'version': _VER})


@router.get('/api/logs')
def s_logs():
    # Вкладка «Логи»: ядро (LOG) + ошибки/предупреждения плагинов из журналов
    # активности (manager.recent_issues) — раньше ошибки плагинов туда не попадали.
    from core.plugins.routes import get_manager
    merged = list(LOG[-100:])
    try:
        mgr = get_manager()
        if mgr is not None:
            merged.extend(mgr.recent_issues(limit=60))
    except Exception:
        pass  # логи ядра всё равно отдаём
    return JSONResponse({'logs': merged})


@router.delete('/api/logs/issues')
def s_logs_clear_issues():
    """Кнопка «Очистить ошибки» во вкладке «Логи».

    Честное поведение: удаляем из журнала только записи уровня error/warn —
    как из ядра (LOG), так и из журналов активности плагинов
    (manager.clear_issues → data/plugins/activity/*.jsonl). Info/action записи
    остаются. Без этого пользователь не может убрать старые уже исправленные ошибки.
    """
    from core.plugins.routes import get_manager
    before = len(LOG)
    LOG[:] = [e for e in LOG if e.get('level') not in ('error', 'warn')]
    removed = before - len(LOG)
    try:
        mgr = get_manager()
        if mgr is not None:
            removed += mgr.clear_issues()
    except Exception:
        pass  # логи ядра мы уже очистили — не отдаём 500 из-за плагинов
    return JSONResponse({'success': True, 'removed': removed})


@router.post('/api/logs')
async def s_log_add(payload: dict):
    """Принять ошибку/событие от UI и сохранить в общий LOG.

    Нужно, чтобы ошибки, увиденные на фронтенде (плашка «Репозитории/Плагины»),
    остались во вкладке «Логи» даже после перезагрузки страницы.
    Поле time приходит от клиента (dedupe по time+message на фронтенде).
    """
    msg = str(payload.get('message') or '')[:2000]
    lvl = str(payload.get('level') or 'info').lower()
    if lvl not in ('info', 'warn', 'error', 'success'):
        lvl = 'info'
    if not msg:
        return JSONResponse({'success': False, 'error': 'пустое сообщение (message)'})
    src = str(payload.get('source') or 'UI')[:60]
    t = str(payload.get('time') or datetime.now().strftime('%H:%M:%S'))[:12]
    LOG.append({'time': t, 'level': lvl, 'message': msg, 'source': src})
    if len(LOG) > 500:
        LOG.pop(0)
    return JSONResponse({'success': True})


_RES_CACHE = {'ts': 0.0, 'data': None}
_RES_LOCK = threading.Lock()


def _get_ram_gb():
    try:
        if sys.platform == 'win32':
            import ctypes
            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ('dwLength', ctypes.c_ulong),
                    ('dwMemoryLoad', ctypes.c_ulong),
                    ('ullTotalPhys', ctypes.c_ulonglong),
                    ('ullAvailPhys', ctypes.c_ulonglong),
                    ('ullTotalPageFile', ctypes.c_ulonglong),
                    ('ullAvailPageFile', ctypes.c_ulonglong),
                    ('ullTotalVirtual', ctypes.c_ulonglong),
                    ('ullAvailVirtual', ctypes.c_ulonglong),
                    ('ullAvailExtendedVirtual', ctypes.c_ulonglong),
                ]
            st = MEMORYSTATUSEX()
            st.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(st))
            total = st.ullTotalPhys / (1024 ** 3)
            used = (st.ullTotalPhys - st.ullAvailPhys) / (1024 ** 3)
            return round(used, 1), round(total, 1)
    except Exception:
        pass
    return 0.0, 0.0


def _get_vram_total_gb():
    if sys.platform != 'win32':
        return 0.0
    max_bytes = 0
    try:
        import winreg
        base_key = r'SYSTEM\ControlSet001\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}'
        for i in range(16):
            sub = rf'{base_key}\{i:04d}'
            try:
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, sub) as k:
                    val, _ = winreg.QueryValueEx(k, 'HardwareInformation.qwMemorySize')
                    if isinstance(val, bytes):
                        val = int.from_bytes(val, 'little')
                    if isinstance(val, int) and val > max_bytes:
                        max_bytes = val
            except OSError:
                continue
    except Exception:
        pass
    return round(max_bytes / (1024 ** 3), 1) if max_bytes > 0 else 0.0


def _get_vram_used_gb():
    if sys.platform != 'win32':
        return 0.0
    try:
        cmd = [
            'powershell', '-NoProfile', '-Command',
            '(Get-CimInstance Win32_PerfFormattedData_GPUPerformanceCounters_GPUAdapterMemory | Measure-Object -Property DedicatedUsage -Sum).Sum'
        ]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=4, creationflags=0x08000000)
        out = (r.stdout or '').strip().replace(',', '.')
        if out:
            val = float(out)
            return round(val / (1024 ** 3), 1)
    except Exception:
        pass
    return 0.0


@router.get('/api/system/resources')
def s_sys_resources():
    now = time.time()
    with _RES_LOCK:
        if _RES_CACHE['data'] is not None and (now - _RES_CACHE['ts']) < 2.5:
            return JSONResponse(_RES_CACHE['data'])
        ram_used, ram_total = _get_ram_gb()
        vram_total = _get_vram_total_gb()
        vram_used = _get_vram_used_gb()
        data = {
            'ram_used_gb': ram_used,
            'ram_total_gb': ram_total,
            'vram_used_gb': vram_used,
            'vram_total_gb': vram_total,
        }
        _RES_CACHE['data'] = data
        _RES_CACHE['ts'] = now
        return JSONResponse(data)


@router.get('/api/md/{name:path}')
def s_md_get(name):
    if not is_doc_rel(name):
        return JSONResponse({'content': '', 'name': name, 'error': 'Разрешены только Markdown-файлы документации (*.md)'})
    p = safe_path(name)
    if p is None:
        return JSONResponse({'content': '', 'name': name, 'error': 'forbidden'})
    if os.path.exists(p):
        return JSONResponse({'content': read_text(p), 'name': name})
    return JSONResponse({'content': '', 'name': name, 'error': 'not found'})


@router.post('/api/md/{name:path}')
def s_md_post(name, payload: dict):
    if not is_doc_rel(name):
        return JSONResponse({'success': False, 'error': 'Разрешены только Markdown-файлы документации (*.md)'})
    p = safe_path(name)
    if p is None:
        return JSONResponse({'success': False, 'error': 'forbidden'})
    try:
        with open(p, 'w', encoding='utf-8') as f:
            f.write(payload.get('content', ''))
        return JSONResponse({'success': True})
    except Exception as e:
        return JSONResponse({'success': False, 'error': str(e)})


@router.post('/api/system/restart')
def s_restart():
    log('RESTART via panel', 'WARNING')
    with open(RESTART_FLAG, 'w') as f:
        f.write('restart')
    for title in ('drmAIcu Core', 'drmAIcu UI'):
        try:
            subprocess.run(['taskkill', '/F', '/FI', 'WINDOWTITLE eq ' + title], capture_output=True)
        except Exception:
            pass

    def bye():
        time.sleep(1.5)
        os._exit(0)
    threading.Thread(target=bye, daemon=True).start()
    return JSONResponse({'success': True, 'message': 'Перезапуск инициирован'})
