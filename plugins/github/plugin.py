"""GitHub Plugin v1.1 — точка входа (контракт docs/PLUGIN_API_CONTRACT.md).

Стратегия отказа (degraded mode): если модули клиента недоступны (нет
зависимости `pyjwt`/`requests` или ошибка импорта), плагин ВСЁ РАВНО
стартует, но только с локальными capability (diagnostics). Операции,
требующие клиента, не регистрируются, а `github.test_connection` и
`health()` честно сообщают причину. Заместителей работающего клиента
не создаётся — никакого fake-успеха.
"""
import os

_STATE = {'ctx': None, 'client': None, 'client_error': ''}


def initialize(ctx):
    try:
        from .client import GitHubAppClient
        client = GitHubAppClient(ctx)
    except Exception as e:
        ctx.log('error', 'module_import_failed', error=str(e))
        _STATE['ctx'] = ctx
        _STATE['client'] = None
        _STATE['client_error'] = str(e)

        def _git_ok(params):
            from . import git_service
            return {'git': git_service.is_git_available(), 'version': git_service.git_version()}

        def _test_connection_degraded(params):
            return {'ok': False, 'configured': False,
                    'error': 'клиент GitHub недоступен: %s' % _STATE['client_error'],
                    'hint': 'установите зависимости: pip install -r requirements.txt'}

        ctx.register_capability('github.diagnostics', 'github.repositories.read', _git_ok, 'auto',
                                'Локальный Git CLI: доступность и версия')
        ctx.register_capability('github.test_connection', 'github.repositories.read', _test_connection_degraded, 'auto',
                                'Проверка подключения GitHub App (клиент недоступен)')
        ctx.log('warn', 'degraded_mode', reason=str(e))
        return True

    def _test_connection(params):
        return _STATE['client'].test_connection()

    def _list_repositories(params):
        return _STATE['client'].list_repositories(params or {})

    def _get_repository(params):
        return _STATE['client'].get_repository(params or {})

    def _get_tree(params):
        return _STATE['client'].get_tree(params or {})

    def _get_file(params):
        return _STATE['client'].get_file(params or {})

    def _list_branches(params):
        return _STATE['client'].list_branches(params or {})

    def _create_branch(params):
        return _STATE['client'].create_branch(params or {})

    def _compare(params):
        return _STATE['client'].compare(params or {})

    def _git_ok(params):
        from . import git_service
        return {'git': git_service.is_git_available(), 'version': git_service.git_version()}

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
    _STATE['client'] = client
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
    if client is None:
        return {'settings_configured': bool(s.get('app_id')) and bool(s.get('installation_id')),
                'private_key_stored': ctx.get_secret('private_key') is not None,
                'auth_configured': False,
                'client_error': _STATE.get('client_error', 'client unavailable'),
                'hint': 'pip install -r requirements.txt'}
    return {
        'settings_configured': bool(s.get('app_id')) and bool(s.get('installation_id')),
        'private_key_stored': ctx.get_secret('private_key') is not None,
        'auth_configured': client.auth_configured() if client else False,
    }


def uninstall():
    ctx = _STATE.get('ctx')
    if ctx is not None:
        ctx.log('action', 'plugin_uninstalled')
