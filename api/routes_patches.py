# -*- coding: utf-8 -*-
"""api.routes_patches — REST-обёртка над PATCHMASTER (patch_engine.py).

Единственный путь применения AI-правок исходников — через apply_patch.
"""
import json
import os
import re
import shutil
from datetime import datetime

from fastapi import APIRouter
from fastapi.responses import JSONResponse

import patch_engine as _pe
from patch_engine import (
    apply_patch, find_patch_file, list_patches, load_manifest,
    preview_patch, read_text, rollback, safe_path, stats, test_apply,
)
from .shared import BASE, PATCH_DIR, ARCHIVE_DIR, RESTART_FLAG, log

router = APIRouter()


@router.get('/api/patches/dump')
def s_dump():
    with open(os.path.join(BASE, 'patch_engine.py'), 'r', encoding='utf-8') as f:
        content = f.read()

    def extract(name):
        pat = re.compile(r'^\s*(?:async\s+)?def\s+' + re.escape(name) + r'\s*\(', re.MULTILINE)
        m = pat.search(content)
        if not m:
            return None
        start = m.start()
        indent_str = content[start:content.index('def', start)]
        indent = len(indent_str)
        lines = content[start:].split('\n')
        end = 0
        for i in range(1, len(lines)):
            ln = lines[i]
            if not ln.strip():
                continue
            li = len(ln) - len(ln.lstrip())
            if li <= indent and (ln.strip().startswith('def ') or ln.strip().startswith('async def ') or ln.strip().startswith('@')):
                end = sum(len(l) + 1 for l in lines[:i])
                break
        else:
            end = len(content) - start
        return content[start:start + end].rstrip()

    return JSONResponse({
        'success': True,
        'apply_patch': extract('apply_patch'),
        'apply_patch_atomic': extract('apply_patch_atomic'),
        'apply_search_replace': extract('apply_search_replace'),
        'preview_patch': extract('preview_patch'),
        'validate': extract('validate')
    })


@router.get('/api/patches/list')
def s_plist():
    return JSONResponse({'success': True, 'patches': list_patches()})


@router.get('/api/patches/validate-all')
def s_pvalidate_all():
    """Проверить валидность всех патчей без применения."""
    if not os.path.isdir(PATCH_DIR):
        return JSONResponse({'patches': []})
    results = []
    man = load_manifest()
    done = set(str(a.get('patch_id')) for a in man.get('applied', []))
    for f in sorted(os.listdir(PATCH_DIR)):
        if not _pe.is_patch_filename(f):
            continue
        fp = os.path.join(PATCH_DIR, f)
        try:
            with open(fp, 'r', encoding='utf-8') as fh:
                data = json.load(fh)
            ops = data.get('operations', [])
            errors = []
            for i, op in enumerate(ops):
                tgt = op.get('target_file', '')
                full_path = safe_path(tgt)
                # B64 FIX (P2-17): путь через safe_path — как в Patch Engine, иначе подозрительный целевой файл
                if full_path is None:
                    errors.append(f'Операция {i+1}: подозрительный target_file (за пределами проекта): {tgt}')
                    continue
                if not os.path.exists(full_path):
                    errors.append(f'Операция {i+1}: файл {tgt} не существует')
                    continue
                with open(full_path, 'r', encoding='utf-8') as fh:
                    content = fh.read()
                if op.get('type') == 'search_and_replace':
                    find_txt = op.get('find', '')
                    if find_txt not in content:
                        errors.append(f'Операция {i+1}: подстрока не найдена в {tgt}')
                    elif content.count(find_txt) > 1:
                        errors.append(f'Операция {i+1}: найдено {content.count(find_txt)} вхождений в {tgt}')
                elif op.get('type') == 'full_replace':
                    if 'full_file_content' not in op:
                        errors.append(f'Операция {i+1}: отсутствует full_file_content')
            results.append({
                'filename': f,
                'patch_id': str(data.get('patch_id', f[:-5])),
                'valid': len(errors) == 0,
                'errors': errors,
                'operations_count': len(ops),
                'is_applied': str(data.get('patch_id', f[:-5])) in done
            })
        except Exception as e:
            results.append({'filename': f, 'patch_id': '?', 'valid': False, 'errors': [f'Ошибка: {str(e)}'], 'operations_count': 0, 'is_applied': False})
    return JSONResponse({'patches': results})


@router.get('/api/patches/progress')
def s_pprogress():
    return JSONResponse({'success': True, 'progress': _pe.patch_progress()}, headers={'Cache-Control': 'no-store'})


@router.get('/api/patches/stats')
def s_pstats():
    return JSONResponse({'success': True, 'stats': stats()})


@router.post('/api/patches/preview')
def s_pprev(payload: dict):
    return JSONResponse(preview_patch(payload))


@router.post('/api/patches/test-apply')
def s_ptest(payload: dict):
    return JSONResponse(test_apply(payload))


@router.post('/api/patches/apply')
def s_papply(payload: dict):
    log('API apply: ' + str(payload.get('patch_id', 'unknown')), 'INFO')
    r = apply_patch(payload)
    # B72 FIX (P3-25): авто-рестарт после .py-патча — создаём restart.flag для launcher.bat
    if r.get('success') and isinstance(payload, dict):
        for target in r.get('report', {}).get('files', []):
            if str(target).lower().endswith('.py'):
                try:
                    with open(RESTART_FLAG, 'w', encoding='utf-8') as _ff:
                        _ff.write(datetime.now().isoformat())
                    r['restart_scheduled'] = True
                    log('Auto-restart flag set: patch touches .py files', 'INFO')
                except OSError as _e:
                    log('Cannot write restart.flag: ' + str(_e), 'WARN')
                break
    return JSONResponse(r)


@router.get('/api/patches/verify-108')
def s_verify_108():
    """Проверка единого конвейера применения патчей.

    Конвейер теперь разнесён по api/routes_patches.py — проверяем и его,
    и main.py (B108-контракт: apply-эндпоинт использует apply_patch без обходных путей).
    """
    with open(os.path.join(BASE, 'patch_engine.py'), 'r', encoding='utf-8') as f:
        engine = f.read()
    sources = [engine]
    for rel in ('main.py', os.path.join('api', 'routes_patches.py')):
        p = os.path.join(BASE, rel)
        if os.path.exists(p):
            with open(p, 'r', encoding='utf-8') as f:
                sources.append(f.read())
    content = '\n'.join(sources)
    checks = {
        'apply_patch_exists': 'def apply_patch(raw):' in engine,
        'endpoint_uses_unified': 'return JSONResponse(apply_patch(payload))' in content,
        'rollback_mechanism': 'shutil.copy2' in engine,
        'syntax_check': 'ast.parse' in engine or 'compile(' in engine,
        'safe_path_used': 'safe_path(' in engine,
        'no_atomic_leak': 'def apply_patch_atomic' + '(data):' not in engine
    }
    passed = sum(1 for v in checks.values() if v)
    return JSONResponse({
        'success': True,
        'unified_pipeline_verified': passed == 6,
        'checks': checks,
        'passed': f'{passed}/6'
    })


@router.post('/api/patches/rollback')
def s_pback():
    return JSONResponse(rollback())


@router.post('/api/patches/manifest-reset')
def s_manifest_reset():
    # B52 FIX: управляемый выход из блокировки после повреждения манифеста
    return JSONResponse(_pe.force_unlock_manifest())


@router.post('/api/patches/archive')
def s_parch(payload: dict):
    f = payload.get('filename', '')
    if not _pe.is_patch_filename(f):
        return JSONResponse({'success': False, 'error': 'Подозрительное имя файла'})
    with _pe.TX_LOCK:
        src = find_patch_file('', f)
        if not src:
            return JSONResponse({'success': False, 'error': 'Файл не найден или не является патчем'})
        try:
            dst = _pe.archive_patch_source(src)
            return JSONResponse({'success': True, 'message': dst + ' в архиве'})
        except Exception as e:
            return JSONResponse({'success': False, 'error': str(e)})


@router.post('/api/patches/delete')
def s_pdel(payload: dict):
    f = payload.get('filename', '')
    if not _pe.is_patch_filename(f):
        return JSONResponse({'success': False, 'error': 'Подозрительное имя файла'})
    p = find_patch_file('', f)
    if not p or not os.path.exists(p):
        return JSONResponse({'success': False, 'error': 'not found'})
    allowed = {os.path.realpath(d) for d in (PATCH_DIR, getattr(_pe, 'DOWNLOADS_DIR', '')) if d and os.path.isdir(d)}
    if os.path.realpath(os.path.dirname(p)) not in allowed:
        return JSONResponse({'success': False, 'error': 'forbidden'})
    os.remove(p)
    return JSONResponse({'success': True, 'message': 'deleted'})


@router.post('/api/patches/apply-all')
def s_pall(payload: dict = {}):
    res = []
    for p in list_patches():
        if p['is_applied'] or not p['has_content']:
            continue
        try:
            d = json.loads(read_text(p['filepath']).lstrip('\ufeff'))
            r = apply_patch({**d, 'filename': p['filename']})
            res.append(dict(patch_id=p['patch_id'], **r))
            if not r.get('success'):
                break
        except Exception as e:
            res.append({'patch_id': p['patch_id'], 'success': False, 'error': str(e)})
            break
    # B63 FIX (P2-16): success НИКОГДА не ложный — отражает реальный итог apply-all
    ok = all(r.get('success') for r in res) if res else True
    return JSONResponse({'success': ok, 'results': res})


@router.post('/api/patches/save-from-console')
def s_save_patch_from_console(payload: dict):
    raw_text = str(payload.get('raw_text') or '').strip()
    if not raw_text:
        return JSONResponse({'success': False, 'error': 'Пустой текст ответа'})

    patch_obj = None
    try:
        cand = json.loads(raw_text)
        if isinstance(cand, dict) and ('operations' in cand or 'target_file' in cand):
            patch_obj = cand
    except Exception:
        pass

    if patch_obj is None:
        decoder = json.JSONDecoder()
        idx = 0
        best = None
        while idx < len(raw_text):
            brace = raw_text.find('{', idx)
            if brace == -1:
                break
            try:
                obj, end_idx = decoder.raw_decode(raw_text, brace)
                if isinstance(obj, dict) and ('operations' in obj or 'target_file' in obj):
                    best = obj
                idx = end_idx
            except Exception:
                idx = brace + 1
        patch_obj = best

    if not isinstance(patch_obj, dict):
        return JSONResponse({'success': False, 'error': 'В ответе не найден валидный JSON-патч с operations или target_file'})

    raw_pid = str(patch_obj.get('patch_id') or '').strip()
    safe_pid = re.sub(r'[^a-zA-Z0-9_-]', '', raw_pid)
    if not safe_pid:
        max_num = 160
        for d in (PATCH_DIR, ARCHIVE_DIR):
            if os.path.isdir(d):
                for fn in os.listdir(d):
                    m = re.match(r'^(\d+)\.json$', fn)
                    if m:
                        max_num = max(max_num, int(m.group(1)))
        safe_pid = str(max_num + 1)

    patch_obj['patch_id'] = safe_pid
    filename = f'{safe_pid}.json'
    dst = os.path.join(PATCH_DIR, filename)
    try:
        tmp = dst + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(patch_obj, f, indent=2, ensure_ascii=False)
        os.replace(tmp, dst)
    except Exception as e:
        return JSONResponse({'success': False, 'error': f'Ошибка записи патча: {str(e)}'})

    prev = preview_patch(patch_obj)
    log(f'Console patch exported: {filename} (preflight={prev.get("success")})', 'INFO')
    return JSONResponse({
        'success': True,
        'filename': filename,
        'patch_id': safe_pid,
        'preview': prev,
    })
