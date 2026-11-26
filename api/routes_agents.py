# -*- coding: utf-8 -*-
"""api.routes_agents — AI-задачи, SSE-стриминг, агенты, пайплайны, сборка контекста."""
import asyncio
import json
import os

from fastapi import APIRouter
from fastapi.responses import JSONResponse, StreamingResponse

from patch_engine import safe_path, read_text
from .shared import BASE, LOG, get_engine

router = APIRouter()


@router.post('/api/task')
async def s_task(payload: dict):
    e = get_engine()
    if not e:
        return JSONResponse({'success': False, 'error': 'Engine not loaded'})
    try:
        prompt = payload.get('prompt', '')
        mode = payload.get('mode', 'fast')
        model = payload.get('model', '')
        provider = payload.get('provider', 'ollama')
        r = await e.run_task(prompt, mode=mode, model=model, provider=provider)
        return JSONResponse(r)
    except Exception as ex:
        return JSONResponse({'success': False, 'result': '', 'error': str(ex), 'providers': []})


AGENTS_FILE = os.path.join(BASE, 'agents.json')


@router.get('/api/agents')
def s_agents_get():
    if os.path.exists(AGENTS_FILE):
        try:
            with open(AGENTS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if isinstance(data, list):
                return JSONResponse({'success': True, 'agents': data})
        except Exception as e:
            return JSONResponse({'success': False, 'error': str(e), 'agents': None})
    return JSONResponse({'success': True, 'agents': None})


@router.post('/api/agents')
def s_agents_post(payload: dict):
    try:
        items = payload.get('agents')
        if not isinstance(items, list):
            return JSONResponse({'success': False, 'error': 'agents must be a list'})
        tmp = AGENTS_FILE + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(items, f, indent=2, ensure_ascii=False)
        os.replace(tmp, AGENTS_FILE)
        return JSONResponse({'success': True})
    except Exception as e:
        return JSONResponse({'success': False, 'error': str(e)})


@router.post('/api/task/stream')
async def s_task_stream(payload: dict):
    e = get_engine()
    if not e:
        return JSONResponse({'success': False, 'error': 'Engine not loaded'}, status_code=503)
    prompt = payload.get('prompt', '')
    mode = payload.get('mode', 'fast')
    model = payload.get('model', '')
    provider = payload.get('provider', 'ollama')
    system_prompt = payload.get('system_prompt', '')

    async def event_gen():
        try:
            async for ev in e.stream_task(prompt, mode=mode, model=model, provider=provider, system_prompt=system_prompt):
                yield f"data: {json.dumps(ev, ensure_ascii=False)}\n\n"
        except asyncio.CancelledError:
            return
        except Exception as ex:
            yield f"data: {json.dumps({'type': 'error', 'error': str(ex)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_gen(), media_type='text/event-stream')


PIPELINES_FILE = os.path.join(BASE, 'pipelines.json')


@router.get('/api/pipelines')
def s_pipelines_get():
    if os.path.exists(PIPELINES_FILE):
        try:
            with open(PIPELINES_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if isinstance(data, list):
                return JSONResponse({'success': True, 'pipelines': data})
        except Exception as e:
            return JSONResponse({'success': False, 'error': str(e), 'pipelines': None})
    return JSONResponse({'success': True, 'pipelines': None})


@router.post('/api/pipelines')
def s_pipelines_post(payload: dict):
    try:
        items = payload.get('pipelines')
        if not isinstance(items, list):
            return JSONResponse({'success': False, 'error': 'pipelines must be a list'})
        tmp = PIPELINES_FILE + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(items, f, indent=2, ensure_ascii=False)
        os.replace(tmp, PIPELINES_FILE)
        return JSONResponse({'success': True})
    except Exception as e:
        return JSONResponse({'success': False, 'error': str(e)})


@router.post('/api/task/council')
async def s_task_council(payload: dict):
    e = get_engine()
    if not e:
        return JSONResponse({'success': False, 'error': 'Engine not loaded'}, status_code=503)
    prompt = payload.get('prompt', '')
    agents = payload.get('agents') or []
    judge = payload.get('judge')

    async def event_gen():
        try:
            async for ev in e.stream_council(prompt, agents=agents, judge=judge):
                yield f"data: {json.dumps(ev, ensure_ascii=False)}\n\n"
        except asyncio.CancelledError:
            return
        except Exception as ex:
            yield f"data: {json.dumps({'type': 'error', 'error': str(ex)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_gen(), media_type='text/event-stream')


@router.post('/api/task/pipeline')
async def s_task_pipeline(payload: dict):
    e = get_engine()
    if not e:
        return JSONResponse({'success': False, 'error': 'Engine not loaded'}, status_code=503)
    prompt = payload.get('prompt', '')
    steps = payload.get('steps') or []

    async def event_gen():
        try:
            async for ev in e.stream_pipeline(prompt, steps=steps):
                yield f"data: {json.dumps(ev, ensure_ascii=False)}\n\n"
        except asyncio.CancelledError:
            return
        except Exception as ex:
            yield f"data: {json.dumps({'type': 'error', 'error': str(ex)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_gen(), media_type='text/event-stream')


@router.post('/api/context/build')
def s_context_build(payload: dict):
    files = payload.get('files') or []
    include_logs = bool(payload.get('include_logs'))
    code_issues = payload.get('code_issues') or []
    blocks = []
    attached = []
    total_chars = 0
    max_total = 36000

    for rel in files[:10]:
        rel_str = str(rel).strip()
        if not rel_str:
            continue
        fp = safe_path(rel_str)
        if fp and os.path.isfile(fp):
            try:
                txt = read_text(fp)
                if len(txt) > 12000:
                    txt = txt[:12000] + '\n... [обрезано по лимиту 12000 символов]'
                if total_chars + len(txt) > max_total:
                    break
                total_chars += len(txt)
                blocks.append(f'--- ФАЙЛ ПРОЕКТА: {rel_str} ---\n{txt}')
                attached.append(rel_str)
            except Exception:
                continue

    if include_logs and LOG:
        tail = LOG[-25:]
        log_lines = [f"[{x.get('time', '')}] [{x.get('level', '')}] {x.get('message', '')}" for x in tail]
        blocks.append('--- ПОСЛЕДНИЕ ЛОГИ ЯДРА ---\n' + '\n'.join(log_lines))

    if isinstance(code_issues, list) and len(code_issues) > 0:
        issue_lines = [
            f"- {it.get('file', '?')}:{it.get('line', '?')} — {it.get('title', '')}: {it.get('description', '')}"
            for it in code_issues[:15] if isinstance(it, dict)
        ]
        if issue_lines:
            blocks.append('--- ОТКРЫТЫЕ ЗАМЕЧАНИЯ В КОДЕ ---\n' + '\n'.join(issue_lines))

    return JSONResponse({
        'success': True,
        'context_text': '\n\n'.join(blocks),
        'attached_files': attached,
    })
