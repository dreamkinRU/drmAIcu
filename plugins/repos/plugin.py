"""Repos Plugin v1.2.0 — точка входа (контракт docs/PLUGIN_API_CONTRACT.md).

Политика автоматизации (замороженная, §2): READ-операции со статусом/историей/
ветками выполняются автоматически; любые изменения (add/commit/pull/push/fetch/
checkout/sync) — WRITE с подтверждением пользователя на каждое действие.
Авторизация в удалённых репозиториях — как в локальном git (Credential Manager /
SSH): плагин не хранит и не запросает токены. CRITICAL-операций нет.
"""
from datetime import datetime

from . import git_service, repos_service

_STATE = {'ctx': None}


def _sc(params, key, required=True, default=''):
    v = (params or {}).get(key, default)
    if required and (v is None or not str(v).strip()):
        raise ValueError('требуется параметр: %s' % key)
    return v


def initialize(ctx):
    _STATE['ctx'] = ctx

    def _diagnostics(params):
        return repos_service.diagnostics()

    def _status(params):
        return repos_service.repo_status(_sc(params, 'path'))

    def _log(params):
        return repos_service.repo_log(_sc(params, 'path'), limit=_sc(params, 'limit', required=False, default=30))

    def _branches(params):
        return repos_service.repo_branches(_sc(params, 'path'))

    def _remote(params):
        return repos_service.repo_remote(_sc(params, 'path'))

    def _diff(params):
        return repos_service.repo_diff(_sc(params, 'path'), staged=bool((params or {}).get('staged')))

    def _read_file(params):
        return repos_service.read_file(_sc(params, 'path'), _sc(params, 'rel'))

    def _add(params):
        return repos_service.repo_add(_sc(params, 'path'))

    def _commit(params):
        return repos_service.repo_commit(_sc(params, 'path'), _sc(params, 'message'))

    def _push(params):
        return repos_service.repo_push(_sc(params, 'path'))

    def _pull(params):
        return repos_service.repo_pull(_sc(params, 'path'),
                                       rebase=bool((params or {}).get('rebase', True)))

    def _fetch(params):
        return repos_service.repo_fetch(_sc(params, 'path'))

    def _checkout(params):
        return repos_service.repo_checkout(_sc(params, 'path'), _sc(params, 'branch'),
                                           create=bool((params or {}).get('create')))

    def _sync_preview(params):
        return repos_service.repo_sync_preview(_sc(params, 'path'))

    def _remember_sync(path, res):
        # Последний результат Sync сохраняется персистентно в state плагина
        # (data/plugins/state/repos/state.json, §9.1), чтобы UI показывал его
        # даже после обновления страницы или перезапуска панели.
        try:
            state = ctx.load_state()
            by_path = state.get('last_sync_by_path')
            if not isinstance(by_path, dict):
                by_path = {}
            by_path[str(path)] = {
                'path': str(path),
                'finished_at': datetime.now().astimezone().isoformat(timespec='seconds'),
                'result': res,
            }
            if len(by_path) > 20:  # ограничение роста: последние 20 репозиториев
                for k in sorted(by_path)[:-20]:
                    by_path.pop(k, None)
            state['last_sync_by_path'] = by_path
            ctx.save_state(state)
        except Exception as e:  # сбой хранения не отменяет уже выполненный Sync
            ctx.log('warn', 'last_sync_store_failed', error=str(e))

    def _sync(params):
        path = _sc(params, 'path')
        res = repos_service.repo_sync(path, _sc(params, 'message', required=False), _sc(params, 'snapshot'))
        _remember_sync(path, res)
        return res

    def _last_sync(params):
        path = _sc(params, 'path')
        repos_service.validate(path)
        rec = (ctx.load_state().get('last_sync_by_path') or {}).get(str(path))
        if not isinstance(rec, dict):
            return {'found': False}
        return {'found': True, 'path': rec.get('path'),
                'finished_at': rec.get('finished_at'), 'result': rec.get('result')}

    def _rebase_state(params):
        return repos_service.repo_rebase_state(_sc(params, 'path'))

    def _rebase_continue(params):
        return repos_service.repo_rebase_continue(_sc(params, 'path'))

    def _rebase_abort(params):
        return repos_service.repo_rebase_abort(_sc(params, 'path'))

    reg = ctx.register_capability
    reg('repos.diagnostics', 'repos.read', _diagnostics, 'auto',
        'Доступность Git CLI и версия')
    reg('repos.status', 'repos.read', _status, 'auto',
        'Статус репозитория: ветка, upstream, ahead/behind, изменённые файлы')
    reg('repos.log', 'repos.read', _log, 'auto',
        'История коммитов (до 200)')
    reg('repos.branches', 'repos.read', _branches, 'auto',
        'Список веток (локальные и удалённые)')
    reg('repos.remote', 'repos.read', _remote, 'auto',
        'Удалённые репозитории (remote -v)')
    reg('repos.diff', 'repos.read', _diff, 'auto',
        'git diff (staged или unstaged, --stat)')
    reg('repos.read_file', 'repos.read', _read_file, 'auto',
        'Чтение файла репозитория (до 512 КБ, защита выхода за пределы каталога)')
    reg('repos.add', 'repos.write', _add, 'confirm',
        'git add -A (WRITE, подтверждение)')
    reg('repos.commit', 'repos.write', _commit, 'confirm',
        'git commit (WRITE, подтверждение; пустое сообщение отклоняется)')
    reg('repos.push', 'repos.write', _push, 'confirm',
        'git push origin <ветка> (WRITE, подтверждение)')
    reg('repos.pull', 'repos.write', _pull, 'confirm',
        'git pull --rebase (WRITE, подтверждение)')
    reg('repos.fetch', 'repos.write', _fetch, 'confirm',
        'git fetch --all --prune (WRITE, подтверждение)')
    reg('repos.checkout', 'repos.write', _checkout, 'confirm',
        'Переключение/создание ветки (WRITE, подтверждение)')
    reg('repos.sync_preview', 'repos.read', _sync_preview, 'auto',
        'Полный предварительный diff Sync без изменения index/worktree')
    reg('repos.sync', 'repos.sync', _sync, 'confirm',
        'Кнопка «Синхронизировать»: add -A -> commit -> pull --rebase -> push (одно подтверждение на весь пакет, замена sync.bat)')
    reg('repos.rebase_state', 'repos.read', _rebase_state, 'auto',
        'Диагностика активного rebase и конфликтующих файлов (READ)')
    reg('repos.rebase_continue', 'repos.write', _rebase_continue, 'confirm',
        'git rebase --continue после разрешения конфликтов (WRITE, подтверждение)')
    reg('repos.rebase_abort', 'repos.write', _rebase_abort, 'confirm',
        'git rebase --abort — отмена незавершённого rebase (WRITE, подтверждение)')
    reg('repos.last_sync', 'repos.read', _last_sync, 'auto',
        'Последний результат Sync для репозитория (персистентно в state плагина — переживает обновление страницы)')
    return True


def health():
    return {
        'status': 'running',
        'git_available': git_service.is_git_available(),
        'git_version': git_service.git_version(),
        'default_path': bool(((_STATE['ctx'].settings() or {}).get('default_path') or '').strip()) if _STATE['ctx'] else False,
    }


def stop():
    _STATE['ctx'] = None
    return True
