"""GitHub Plugin v1.0 — точка входа (контракт docs/PLUGIN_API_CONTRACT.md).

Этап 4–5 scope в этом релизе: GitHub App auth, Repository Manager, Branch Manager,
Commit/PR/Issues/Actions/Sync подключаются по мере реализации соответствующих
модулей (регистрируются как отдельные capabilities).
"""
import os

_STATE = {'ctx': None, 'client': None}


def initialize(ctx):
    try:
        from .client import GitHubAppClient
    except Exception as e:
        ctx.log('error', 'module_import_failed', error=str(e))
        return False

    def _git_ok(params):
        from . import git_service
        return {'git': git_service.is_git_available(), 'version': git_service.git_version()}

    def _test_connection(params):
        client = _STATE['client']
        return client.test_connection()

    def _list_repositories(params):
        client = _STATE['client']
        return client.list_repositories(params or {})

    def _get_repository(params):
        client = _STATE['client']
        return client.get_repository(params or {})

    def _get_tree(params):
        client = _STATE['client']
        return client.get_tree(params or {})

    def _get_file(params):
        client = _STATE['client']
        return client.get_file(params or {})

    def _list_branches(params):
        client = _STATE['client']
        return client.list_branches(params or {})

    def _create_branch(params):
        client = _STATE['client']
        return client.create_branch(params or {})

    def _compare(params):
        client = _STATE['client']
        return client.compare(params or {})

    ctx.register_capability('github.diagnostics', 'github.repositories.read', _git_ok, 'auto',
                            'Локальный Git CLI: доступность и версия')
    ctx.register_capability('github.test_connection', 'github.repositories.read', _test_connection, 'auto',
                            'Проверка подключения GitHub App')
    ctx.register_capability('github.list_repositories', 'github.repositories.read', _list_repositories, 'auto',
                            'Список репозиториев установки')
    ctx.register_capability('github.get_repository', 'github.repositories.read', _get_repository, 'auto',
                            'Метаданные репозитория')
    ctx.register_capability('github.get_tree', 'github.contents.read', _get_tree, 'auto',
                            'Дерево файлов')
    ctx.register_capability('github.get_file', 'github.contents.read', _get_file, 'auto',
                            'Чтение исходников')
    ctx.register_capability('github.list_branches', 'github.branches.read', _list_branches, 'auto',
                            'Список веток')
    ctx.register_capability('github.create_branch', 'github.branches.write', _create_branch, 'confirm',
                            'Создание ветки в GitHub')
    ctx.register_capability('github.compare', 'github.commits.read', _compare, 'auto',
                            'Сравнение веток')

    ctx.log('info', 'initialized', git=_git_ok({}).get('git'), os=os.name)
    _STATE['ctx'] = ctx
    _STATE['client'] = GitHubAppClient(ctx)
    return True


def start():
    pass


def stop():
    pass


def health():
    ctx = _STATE.get('ctx')
    if ctx is None:
        return {'ok': False}
    s = ctx.settings()
    client = _STATE.get('client')
    has_key = ctx.get_secret('private_key') is not None
    return {
        'settings_configured': bool(s.get('app_id')) and bool(s.get('installation_id')),
        'private_key_stored': has_key,
        'auth_configured': client.auth_configured() if client else False,
    }


def uninstall():
    ctx = _STATE.get('ctx')
    if ctx is not None:
        ctx.log('action', 'plugin_uninstalled')
