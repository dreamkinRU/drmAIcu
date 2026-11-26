# -*- coding: utf-8 -*-
"""api.routes_project — аналитика проекта, очистка, архив, история и восстановление."""
import hashlib
import json
import os
import re
import shutil
from datetime import datetime, timedelta

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from patch_engine import backup, safe_path, read_text
from guards import is_critical_rel
from .shared import BASE, PROJ_ARCHIVE, IMPORTANT, SKIP, log, human

router = APIRouter()


@router.post('/api/project/smart-cleanup')
def s_smart_cleanup():
    """Возвращает список файлов, которые безопасно удалить (мусор), исключая важные."""
    try:
        files = smart_cleanup_scan()
        return {'success': True, 'files': files, 'count': len(files)}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def important_set():
    if os.path.exists(IMPORTANT):
        try:
            with open(IMPORTANT, 'r', encoding='utf-8') as f:
                return set(json.load(f).get('important', []))
        except Exception:
            pass
    return set()


def _archive_parts(rel_path):
    safe_rel = str(rel_path).replace(chr(92), '/').strip('/')
    return [q for q in safe_rel.split('/') if q and q not in ('.', '..')]


def _archive_rel_entry(archive_full):
    parts = os.path.abspath(archive_full).replace(chr(92), '/').split('/')
    for i, q in enumerate(parts):
        if q == 'project_archive':
            return '/'.join(parts[i + 1:])
    return None


def classify_file(name, rel, size):
    r = rel.replace('\\', '/').lower()
    n = name.lower()
    # Критическое ядро
    if is_critical_rel(rel):
        return {'category': 'critical', 'risk': 'critical', 'icon': 'lock',
                'reason': 'Критическое ядро системы. Удаление сломает приложение.', 'action': 'keep'}
    # Одноразовые скрипты миграции/фиксов — мусор
    if re.match(r'^(apply|fix|emergency|clean|restore|patch)_.*\.py$', n):
        return {'category': 'trash', 'risk': 'low', 'icon': 'trash',
                'reason': 'Одноразовый скрипт миграции/фикса. Безопасно к удалению.', 'action': 'delete'}
    if n.startswith('diag_') or n.startswith('auto_fix') or n.startswith('final_') or n.startswith('make_perfect') or n.startswith('fix_all') or n.startswith('fix_backend') or n.startswith('create_audit') or n.startswith('generate_and_check') or n.startswith('patch_dryrun'):
        return {'category': 'trash', 'risk': 'low', 'icon': 'trash',
                'reason': 'Вспомогательный скрипт диагностики. Безопасно к удалению.', 'action': 'delete'}
    # Резервные копии
    if n.endswith('.bak'):
        return {'category': 'backup', 'risk': 'medium', 'icon': 'archive',
                'reason': 'Резервная копия. Можно архивировать.', 'action': 'archive'}
    # Мусор по размеру/расширению
    if size == 0 or n.endswith(('.tmp', '.pyc')) or n in ('.ds_store', 'thumbs.db', 'desktop.ini'):
        return {'category': 'trash', 'risk': 'low', 'icon': 'trash',
                'reason': 'Пустой файл или временный артефакт. Безопасно к удалению.', 'action': 'delete'}
    # Логи
    if n.endswith(('.log', '.txt')) and not n.endswith('requirements.txt'):
        return {'category': 'logs', 'risk': 'low', 'icon': 'file',
                'reason': 'Лог/текстовый артефакт.', 'action': 'archive'}
    # Документация
    if n.endswith('.md'):
        return {'category': 'docs', 'risk': 'low', 'icon': 'book',
                'reason': 'Документация.', 'action': 'keep'}
    # Код
    if n.endswith(('.py', '.tsx', '.ts', '.jsx', '.js')):
        return {'category': 'code', 'risk': 'medium', 'icon': 'code',
                'reason': 'Исходный код. Проверить перед удалением.', 'action': 'keep'}
    # Конфиг
    if n.endswith(('.json', '.yaml', '.yml', '.ini', '.cfg')):
        return {'category': 'config', 'risk': 'medium', 'icon': 'gear',
                'reason': 'Конфигурация. Проверить перед удалением.', 'action': 'keep'}
    # Скрипты запуска
    if n.endswith(('.bat', '.cmd', '.sh')):
        return {'category': 'scripts', 'risk': 'medium', 'icon': 'terminal',
                'reason': 'Скрипт запуска.', 'action': 'keep'}
    if n.endswith(('.html', '.css')):
        return {'category': 'web', 'risk': 'low', 'icon': 'globe',
                'reason': 'Веб-ресурс.', 'action': 'keep'}
    return {'category': 'other', 'risk': 'low', 'icon': 'file',
            'reason': 'Неизвестный тип файла.', 'action': 'keep'}


def category(name, rel, size):
    return classify_file(name, rel, size)['category']


def load_important():
    if os.path.exists(IMPORTANT):
        try:
            with open(IMPORTANT, 'r', encoding='utf-8') as f:
                return set(json.load(f).get('important', []))
        except Exception:
            pass
    return set()


def save_important(items):
    try:
        with open(IMPORTANT, 'w', encoding='utf-8') as f:
            json.dump({'important': sorted(list(items))}, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False


def smart_cleanup_scan():
    important = important_set()
    result = []
    for root, dirs, files in os.walk(BASE):
        dirs[:] = [d for d in dirs if d not in ('node_modules', '.git', '__pycache__', 'backups', 'project_archive')]
        for fn in files:
            fp = os.path.join(root, fn)
            rel = os.path.relpath(fp, BASE).replace('\\', '/')
            if rel in important:
                continue
            try:
                size = os.path.getsize(fp)
            except Exception:
                size = 0
            info = classify_file(fn, rel, size)
            if info['action'] == 'delete':
                result.append({'target_file': rel, 'size': size, **info})
    return result


ICONS = {'.py': 'PY', '.tsx': 'TSX', '.ts': 'TS', '.js': 'JS', '.json': 'CFG',
         '.md': 'MD', '.bat': 'BAT', '.html': 'HTML', '.css': 'CSS', '.bak': 'BAK'}


def get_cleanup_recommendation(f):
    name = f.get('filename', '')
    rel = f.get('path', '')
    size = f.get('size', 0)
    ext = f.get('extension', '')
    size_human = f.get('size_human', human(size))
    is_dup = f.get('is_duplicate', False)
    dups = f.get('duplicates', [])
    is_critical = f.get('is_critical', False)
    is_important = f.get('is_important', False)
    if is_critical or is_important:
        return {'action': 'keep', 'reason': 'Критичный или помеченный как важный'}
    if size == 0 and ext not in ('.gitkeep', '.keep'):
        return {'action': 'delete', 'reason': 'Пустой файл (0 байт)'}
    if name in ('.DS_Store', 'Thumbs.db', 'desktop.ini', 'ehthumbs.db'):
        return {'action': 'delete', 'reason': 'Системный мусор ОС'}
    if ext in ('.tmp', '.pyc', '.pyo') or '__pycache__' in rel or '.vite' in rel:
        return {'action': 'delete', 'reason': 'Временный файл или кэш'}
    if re.search(r'_(old|backup|v\d+|copy|fixed|ru)\.', name, re.IGNORECASE):
        return {'action': 'delete', 'reason': 'Устаревшая/тестовая версия файла'}
    if rel.startswith('backups/') and ext == '.bak':
        try:
            mt = datetime.fromisoformat(f.get('modified', ''))
            if datetime.now() - mt > timedelta(days=7):
                return {'action': 'delete', 'reason': 'Старый бэкап (>7 дней)'}
        except Exception:
            pass
        return {'action': 'review', 'reason': 'Свежий бэкап. Проверить перед удалением'}
    if ext in ('.log', '.txt') and size > 5 * 1024 * 1024:
        return {'action': 'review', 'reason': 'Большой файл (' + size_human + ')'}
    if is_dup and dups:
        primary = dups[0]
        if len(rel) > len(primary):
            return {'action': 'delete', 'reason': 'Дубликат. Оригинал: ' + primary}
        else:
            return {'action': 'review', 'reason': 'Дубликат в: ' + ', '.join(dups[:2])}
    if re.match(r'^(test|temp|tmp|untitled|new_file|copy)\..+', name, re.IGNORECASE) and '/' not in rel:
        return {'action': 'review', 'reason': 'Подозрительное временное имя'}
    return {'action': 'keep', 'reason': 'Файл корректен'}


def scan_project():
    files = []
    hashes = {}
    imp = important_set()
    for root, dirs, names in os.walk(BASE):
        dirs[:] = [d for d in dirs if d not in SKIP]
        for n in names:
            p = os.path.join(root, n)
            rel = os.path.relpath(p, BASE).replace('\\', '/')
            try:
                stt = os.stat(p)
                h = ''
                try:
                    with open(p, 'rb') as f:
                        h = hashlib.md5(f.read()).hexdigest()
                except Exception:
                    pass
                cat = category(n, rel, stt.st_size)
                files.append({'path': rel, 'filename': n, 'size': stt.st_size,
                              'size_human': human(stt.st_size),
                              'modified': datetime.fromtimestamp(stt.st_mtime).isoformat(),
                              'category': cat, 'hash': h,
                              'is_critical': cat == 'critical', 'is_important': rel in imp,
                              'extension': os.path.splitext(n)[1].lower(),
                              'icon': ICONS.get(os.path.splitext(n)[1].lower(), 'FILE'),
                              'is_duplicate': False, 'duplicates': []})
                if h:
                    hashes.setdefault(h, []).append(rel)
            except Exception:
                continue
    for f in files:
        g = hashes.get(f['hash'], [])
        if len(g) > 1:
            f['is_duplicate'] = True
            f['duplicates'] = [x for x in g if x != f['path']]
    for f in files:
        f['cleanup'] = get_cleanup_recommendation(f)
    total = sum(f['size'] for f in files)
    st = {'total': len(files), 'total_size': total, 'total_size_human': human(total),
          'by_category': {}, 'by_extension': {},
          'duplicates_count': len([f for f in files if f['is_duplicate']]),
          'duplicates_groups': len([v for v in hashes.values() if len(v) > 1]),
          'critical_count': len([f for f in files if f['is_critical']]),
          'important_count': len([f for f in files if f['is_important']]),
          'trash_count': len([f for f in files if f['category'] == 'trash']),
          'backup_count': len([f for f in files if f['category'] == 'backup']),
          'cleanup_delete_count': len([f for f in files if f['cleanup']['action'] == 'delete']),
          'cleanup_review_count': len([f for f in files if f['cleanup']['action'] == 'review'])}
    for f in files:
        st['by_category'][f['category']] = st['by_category'].get(f['category'], 0) + 1
        st['by_extension'][f['extension']] = st['by_extension'].get(f['extension'], 0) + 1
    return {'files': files, 'stats': st}


# ============================================================================
# Project History & Bulk Operations
# ============================================================================

MAX_HISTORY = 50
PROJECT_HISTORY_FILE = os.path.join(BASE, '.project-history.json')
PROJECT_HISTORY = []


def _load_project_history():
    try:
        if os.path.exists(PROJECT_HISTORY_FILE):
            with open(PROJECT_HISTORY_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
        else:
            data = []
    except Exception as e:
        log('History load error: ' + str(e), 'ERROR')
        data = []
    if not isinstance(data, list):
        data = []
    return [h for h in data if isinstance(h, dict) and h.get('action') and isinstance(h.get('paths'), list)]


def _save_project_history():
    try:
        tmp = PROJECT_HISTORY_FILE + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(PROJECT_HISTORY, f, indent=2, ensure_ascii=False)
        os.replace(tmp, PROJECT_HISTORY_FILE)
    except Exception as e:
        log('History save error: ' + str(e), 'ERROR')


def _load_state_snapshot(path):
    try:
        if not os.path.exists(path):
            return {'exists': False, 'important': []}
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        items = data.get('important', []) if isinstance(data, dict) else []
        return {'exists': True, 'important': [str(x) for x in items]}
    except Exception as e:
        log('Important load error: ' + str(e), 'ERROR')
        return {'exists': False, 'important': []}


def _parse_state_snapshot(snap):
    if not isinstance(snap, dict):
        return None
    items = snap.get('important')
    if not isinstance(items, list):
        return None
    return set(items)


PROJECT_HISTORY = _load_project_history()


def log_action(action, paths, backups, important_before=None, important_after=None):
    PROJECT_HISTORY.append({
        'action': action,
        'paths': paths,
        'backups': backups,
        'important_before': important_before,
        'important_after': important_after,
        'timestamp': datetime.now().isoformat()
    })
    if len(PROJECT_HISTORY) > MAX_HISTORY:
        PROJECT_HISTORY.pop(0)
    _save_project_history()


@router.get('/api/project/scan')
def s_scan():
    try:
        return JSONResponse(scan_project())
    except Exception as e:
        log('Scan error: ' + str(e), 'ERROR')
        return JSONResponse({'success': False, 'error': str(e), 'files': [], 'stats': {}})


@router.get('/api/project/file')
def s_pfile(path: str):
    p = safe_path(path)
    if p is None:
        return JSONResponse({'success': False, 'error': 'forbidden'})
    if not os.path.exists(p):
        return JSONResponse({'success': False, 'error': 'not found'})
    c = read_text(p)
    return JSONResponse({'success': True, 'content': c, 'size': len(c)})


def _archive_paths(archive_dir, rel_path):
    safe_rel = str(rel_path).replace(chr(92), '/').strip('/')
    parts = [q for q in safe_rel.split('/') if q and q not in ('.', '..')]
    return os.path.join(archive_dir, *parts)


@router.post('/api/project/archive')
def s_proj_arch(payload: dict):
    rel = payload.get('path', '')
    p = safe_path(rel)
    if p is None:
        return JSONResponse({'success': False, 'error': 'forbidden'})
    if not os.path.exists(p):
        return JSONResponse({'success': False, 'error': 'not found'})
    if is_critical_rel(rel):
        return JSONResponse({'success': False, 'error': 'Критичный файл'})
    folder = datetime.now().strftime('%Y%m%d_%H%M%S')
    archive_dir = os.path.join(PROJ_ARCHIVE, folder)
    dst = _archive_paths(archive_dir, rel)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    before = _load_state_snapshot(IMPORTANT)
    shutil.move(p, dst)
    after = _load_state_snapshot(IMPORTANT)
    log_action('archive', [rel], [dst], before, after)
    entry = '/'.join(['project_archive', folder] + _archive_parts(rel))
    return JSONResponse({
        'success': True,
        'message': 'Архив: project_archive/' + folder,
        'paths': [rel],
        'backups': [dst],
        'archive': {rel: entry}
    })


@router.post('/api/project/delete')
def s_proj_del(payload: dict):
    rel = payload.get('path', '')
    p = safe_path(rel)
    if p is None:
        return JSONResponse({'success': False, 'error': 'forbidden'})
    if not os.path.exists(p):
        return JSONResponse({'success': False, 'error': 'not found'})
    if is_critical_rel(rel):
        return JSONResponse({'success': False, 'error': 'Критичный файл'})
    b = backup(p)
    if not b:
        return JSONResponse({'success': False, 'error': 'Не удалось создать резервную копию — удаление запрещено'})
    os.remove(p)
    return JSONResponse({'success': True, 'message': 'Удалён: ' + rel})


@router.post('/api/project/important')
def s_proj_imp(payload: dict):
    s = important_set()
    path = payload.get('path', '')
    if path in s:
        s.discard(path)
    else:
        s.add(path)
    with open(IMPORTANT, 'w', encoding='utf-8') as f:
        json.dump({'important': list(s)}, f, indent=2)
    return JSONResponse({'success': True, 'important': list(s)})


@router.post('/api/project/bulk')
def s_project_bulk(payload: dict):
    action = payload.get('action', '')
    paths = payload.get('paths', [])
    if not paths:
        return JSONResponse({'success': False, 'error': 'Нет выбранных файлов'})
    important_before = None
    if action == 'important':
        important_before = _load_state_snapshot(IMPORTANT)
    important_state = important_set()
    backups = []
    processed = []
    skipped = []
    archive_map = {}
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    archive_dir = os.path.join(PROJ_ARCHIVE, stamp)
    for rel_path in paths:
        full_path = safe_path(rel_path)
        if not full_path or not os.path.exists(full_path):
            continue
        if action in ('archive', 'delete') and is_critical_rel(rel_path):
            skipped.append(rel_path)
            continue
        if action == 'archive':
            b = backup(full_path)
            if not b:
                skipped.append(rel_path)
                continue
            backups.append(b[0])
            adst = _archive_paths(archive_dir, rel_path)
            os.makedirs(os.path.dirname(adst), exist_ok=True)
            shutil.move(full_path, adst)
            archive_map[rel_path] = '/'.join(['project_archive', stamp] + _archive_parts(rel_path))
            processed.append(rel_path)
        elif action == 'important':
            if rel_path in important_state:
                important_state.remove(rel_path)
            else:
                important_state.add(rel_path)
            save_important(important_state)
            processed.append(rel_path)
        elif action == 'delete':
            b = backup(full_path)
            if not b:
                skipped.append(rel_path)
                continue
            backups.append(b[0])
            os.remove(full_path)
            processed.append(rel_path)
    if processed:
        important_after = None
        if action == 'important':
            important_after = _load_state_snapshot(IMPORTANT)
        log_action(action, processed, backups, important_before, important_after)
    return JSONResponse({'success': True, 'processed': len(processed), 'skipped': len(skipped), 'archive': archive_map})


@router.post('/api/project/restore')
def s_project_restore(payload: dict):
    archive_path = payload.get('archive_path', '')
    archive_full = safe_path(archive_path)
    if not archive_full or not os.path.exists(archive_full):
        return JSONResponse({'success': False, 'error': 'Файл не найден в архиве'})
    if not archive_path.replace(chr(92), '/').startswith('project_archive/'):
        return JSONResponse({'success': False, 'error': 'Файл не из project_archive'})
    entry = _archive_rel_entry(archive_full)
    if not entry or len(entry.split('/')) < 2:
        return JSONResponse({'success': False, 'error': ' некорректный путь архива'})
    target_rel = '/'.join(entry.split('/')[1:])
    if not target_rel:
        return JSONResponse({'success': False, 'error': ' некорректный путь архива'})
    if is_critical_rel(target_rel):
        return JSONResponse({'success': False, 'error': 'Восстановление критичного файла запрещено'})
    target = safe_path(target_rel)
    if target is None:
        return JSONResponse({'success': False, 'error': 'Восстановление в критичный путь запрещено'})
    if os.path.exists(target):
        return JSONResponse({'success': False, 'error': f'Файл {target_rel} уже существует'})
    os.makedirs(os.path.dirname(target), exist_ok=True)
    shutil.copy2(archive_full, target)
    return JSONResponse({'success': True, 'message': f'Восстановлен {target_rel}'})


@router.post('/api/project/rollback')
def s_project_rollback():
    if not PROJECT_HISTORY:
        return JSONResponse({'success': False, 'error': 'История пуста'})
    last = PROJECT_HISTORY.pop()
    restored = 0
    errors = []
    for backup_path, original_path in zip(last['backups'], last['paths']):
        if backup_path and os.path.exists(backup_path):
            dest = safe_path(original_path)
            if dest is None:
                errors.append(f'{original_path}: восстановление в критичный путь запрещено')
                continue
            try:
                os.makedirs(os.path.dirname(dest) or BASE, exist_ok=True)
                shutil.copy2(backup_path, dest)
                restored += 1
            except Exception as e:
                errors.append(f'{original_path}: {e}')
        else:
            errors.append(f'{original_path}: резервная копия не найдена')
    before = _parse_state_snapshot(last.get('important_before'))
    after = _parse_state_snapshot(last.get('important_after'))
    imp_restored = 0
    if before is not None and after is not None and before != after:
        save_important(before)
        imp_restored = len(before ^ after)
    _save_project_history()
    msg = f'Откат: {last["action"]} ({restored} файлов)' + (f', important: {imp_restored}' if imp_restored else '')
    if errors:
        return JSONResponse({'success': True, 'message': msg + ' (с ошибками: ' + '; '.join(errors) + ')', 'errors': errors})
    return JSONResponse({'success': True, 'message': msg})


@router.get('/api/project/history')
def s_project_history():
    return JSONResponse({'history': PROJECT_HISTORY})


@router.get('/api/project/archive-list')
def s_project_archive_list():
    archive_dir = os.path.join(BASE, 'project_archive')
    if not os.path.exists(archive_dir):
        return JSONResponse({'files': []})
    files = []
    for root, dirs, filenames in os.walk(archive_dir):
        for f in filenames:
            full = os.path.join(root, f)
            rel = os.path.relpath(full, BASE)
            files.append({
                'path': rel,
                'filename': f,
                'size': os.path.getsize(full),
                'modified': datetime.fromtimestamp(os.path.getmtime(full)).isoformat()
            })
    return JSONResponse({'files': files})
