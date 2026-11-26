# -*- coding: utf-8 -*-
"""api.routes_providers — модели и конфигурация провайдеров (ollama/strata/lmstudio/bionic/облачные)."""
import asyncio
import json
import os
import time

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from guards import validate_url
from .shared import CONFIG, log, load_cfg, rebuild_engine

router = APIRouter()


@router.get('/api/bionic/models')
def s_bionic_models(url: str = ''):
    try:
        import requests
        base = (url or load_cfg().get('bionic_url', 'http://localhost:1235/v1')).rstrip('/')
        r = requests.get(base + '/models', timeout=4)
        if r.status_code != 200:
            return JSONResponse({'success': False, 'error': f'HTTP {r.status_code}', 'models': []})
        ms = r.json().get('data', [])
        out = [{'name': m.get('id', ''), 'size_gb': 0} for m in ms if m.get('id') and 'embed' not in m.get('id', '').lower()]
        return JSONResponse({'success': True, 'models': out})
    except Exception as e:
        return JSONResponse({'success': False, 'error': str(e), 'models': []})


@router.get('/api/lmstudio/models')
def s_lmstudio_models(url: str = ''):
    try:
        import requests
        base = (url or load_cfg().get('lmstudio_url', 'http://localhost:1234/v1')).rstrip('/')
        ok, why = validate_url(base)
        if not ok:
            return JSONResponse({'success': False, 'error': 'URL отклонён: ' + why, 'models': []})
        r = requests.get(base + '/models', timeout=4)
        if r.status_code != 200:
            return JSONResponse({'success': False, 'error': f'HTTP {r.status_code}', 'models': []})
        ms = r.json().get('data', [])
        out = [{'name': m.get('id', ''), 'size_gb': 0} for m in ms if m.get('id') and 'embed' not in m.get('id', '').lower()]
        return JSONResponse({'success': True, 'models': out})
    except Exception as e:
        return JSONResponse({'success': False, 'error': str(e), 'models': []})


@router.get('/api/strata/models')
def s_strata_models(url: str = ''):
    try:
        import requests
        base = (url or load_cfg().get('strata_url', 'http://127.0.0.1:47831/v1')).rstrip('/')
        ok, why = validate_url(base)
        if not ok:
            return JSONResponse({'success': False, 'error': 'URL отклонён: ' + why, 'models': []})
        r = requests.get(base + '/models', timeout=4)
        if r.status_code != 200:
            return JSONResponse({'success': False, 'error': f'HTTP {r.status_code}', 'models': []})
        ms = r.json().get('data', [])
        out = [{'name': m.get('id', ''), 'size_gb': 0} for m in ms if m.get('id') and 'embed' not in m.get('id', '').lower()]
        return JSONResponse({'success': True, 'models': out})
    except Exception as e:
        return JSONResponse({'success': False, 'error': str(e), 'models': []})


@router.post('/api/providers/ping')
def s_providers_ping(payload: dict):
    import requests
    from concurrent.futures import ThreadPoolExecutor

    items = payload.get('providers') or []

    KNOWN_PROVIDER_BASE = {
        'groq': 'https://api.groq.com/openai/v1',
        'openrouter': 'https://openrouter.ai/api/v1',
        'together': 'https://api.together.xyz/v1',
    }

    def guarded_get(u, **kw):
        ok, why = validate_url(u)
        if not ok:
            raise ValueError('URL отклонён: ' + why)
        return requests.get(u, **kw)

    def check_one(item):
        pid = str(item.get('id', ''))
        url = str(item.get('url', '')).strip().rstrip('/')
        api_key = str(item.get('api_key', '')).strip()
        t0 = time.perf_counter()
        try:
            if pid == 'ollama':
                base = url or 'http://localhost:11434'
                r = guarded_get(base + '/api/tags', timeout=2.5)
                ms = int((time.perf_counter() - t0) * 1000)
                if r.status_code == 200:
                    models = [m.get('name', '') for m in r.json().get('models', []) if m.get('name')]
                    return pid, {'online': True, 'latency': ms, 'models': models}
                return pid, {'online': False, 'latency': 0, 'models': [], 'error': f'HTTP {r.status_code}'}
            elif pid == 'gemini':
                if not api_key:
                    return pid, {'online': False, 'latency': 0, 'models': [], 'error': 'Нет ключа'}
                r = requests.get('https://generativelanguage.googleapis.com/v1beta/models', headers={'x-goog-api-key': api_key}, timeout=3.0)
                ms = int((time.perf_counter() - t0) * 1000)
                if r.status_code == 200:
                    return pid, {'online': True, 'latency': ms, 'models': ['gemini-1.5-flash', 'gemini-2.0-flash']}
                return pid, {'online': False, 'latency': 0, 'models': [], 'error': f'HTTP {r.status_code}'}
            elif pid == 'huggingface':
                if not api_key:
                    return pid, {'online': False, 'latency': 0, 'models': [], 'error': 'Нет ключа'}
                r = requests.get('https://huggingface.co/api/whoami-v2', headers={'Authorization': f'Bearer {api_key}'}, timeout=3.0)
                ms = int((time.perf_counter() - t0) * 1000)
                if r.status_code == 200:
                    return pid, {'online': True, 'latency': ms, 'models': ['meta-llama/Llama-3.1-8B-Instruct', 'Qwen/Qwen2.5-Coder-32B-Instruct']}
                return pid, {'online': False, 'latency': 0, 'models': [], 'error': f'HTTP {r.status_code}'}
            else:
                base = KNOWN_PROVIDER_BASE.get(pid)
                if base is not None:
                    if not api_key:
                        return pid, {'online': False, 'latency': 0, 'models': [], 'error': 'Нет API-ключа'}
                    headers = {'Authorization': f'Bearer {api_key}'}
                else:
                    if not url:
                        return pid, {'online': False, 'latency': 0, 'models': [], 'error': 'Нет URL'}
                    base = url
                    headers = {}
                r = guarded_get(base + '/models', headers=headers, timeout=2.5)
                ms = int((time.perf_counter() - t0) * 1000)
                if r.status_code == 200:
                    data = r.json().get('data', [])
                    models = [m.get('id', '') for m in data if m.get('id') and 'embed' not in m.get('id', '').lower()]
                    return pid, {'online': True, 'latency': ms, 'models': models}
                return pid, {'online': False, 'latency': 0, 'models': [], 'error': f'HTTP {r.status_code}'}
        except Exception as e:
            return pid, {'online': False, 'latency': 0, 'models': [], 'error': str(e)[:80]}

    statuses = {}
    if items:
        with ThreadPoolExecutor(max_workers=min(8, len(items))) as ex:
            for pid, st in ex.map(check_one, items):
                statuses[pid] = st
    return JSONResponse({'success': True, 'statuses': statuses})


@router.post('/api/providers/config')
def s_providers_config(payload: dict):
    try:
        cfg = load_cfg()
        if not isinstance(cfg, dict):
            cfg = {}
        updates = payload.get('config') or {}
        if isinstance(updates, dict):
            for k, v in updates.items():
                if isinstance(k, str) and isinstance(v, (str, int, float, bool, dict)):
                    cfg[k] = v
        tmp = CONFIG + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
        os.replace(tmp, CONFIG)

        rebuild_engine()
        return JSONResponse({'success': True, 'file': 'settings.json'})
    except Exception as e:
        return JSONResponse({'success': False, 'error': str(e)})


@router.get('/api/ollama/models')
def s_models():
    try:
        import requests
        r = requests.get(load_cfg().get('ollama_url', 'http://localhost:11434') + '/api/tags', timeout=5)
        ms = r.json().get('models', [])
        out = [{'name': m['name'], 'size_gb': round(m.get('size', 0) / 1073741824, 2)} for m in ms]
        return JSONResponse({'success': True, 'models': out})
    except Exception as e:
        return JSONResponse({'success': False, 'error': str(e), 'models': []})


@router.post('/api/ollama/pull')
async def s_pull(payload: dict):
    n = payload.get('name', '').strip()
    if not n:
        return JSONResponse({'success': False, 'error': 'no name'})
    try:
        import ollama
        await asyncio.to_thread(ollama.pull, n)
        return JSONResponse({'success': True, 'message': n + ' ready'})
    except Exception as e:
        return JSONResponse({'success': False, 'error': str(e)})
