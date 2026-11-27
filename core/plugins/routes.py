"""REST-маршруты Plugin System (§10.2 контракта). Монтируется в main.py одной строкой."""
import os

from fastapi import APIRouter, Request, Depends, HTTPException
from urllib.parse import urlsplit
from fastapi.responses import JSONResponse

from .api import GatewayBlocked, PendingConfirmation
from .confirmations import ConfirmationError
from .manager import PluginInstallError, PluginManager, PluginNotRunningError
from .models import PLUGIN_API_VERSION

def validate_local_browser_origin(request: Request):
    """Блокирует cross-origin browser mutations и DNS-rebinding Host names.

    Отсутствующий Origin остаётся допустимым для локальных CLI/API-клиентов.
    Это CSRF/origin guard, а не аутентификация пользователя или OS sandbox.
    """
    if request.method in ('GET', 'HEAD', 'OPTIONS'):
        return
    origin = request.headers.get('origin')
    if not origin:
        return
    try:
        parsed = urlsplit(origin)
        origin_host = (parsed.hostname or '').lower()
        origin_port = parsed.port or (443 if parsed.scheme == 'https' else 80)
        request_host = (request.url.hostname or '').lower()
        request_port = request.url.port or (443 if request.url.scheme == 'https' else 80)
    except ValueError:
        raise HTTPException(status_code=403, detail='Invalid Origin header')
    allowed_hosts = {'localhost', '127.0.0.1', '::1'}
    allowed_ports = {5173, 8080}
    fetch_site = request.headers.get('sec-fetch-site', '').lower()
    if (parsed.username or parsed.password or parsed.path not in ('', '/') or parsed.query or parsed.fragment
            or parsed.scheme not in ('http', 'https')
            or origin_host not in allowed_hosts
            or request_host not in allowed_hosts
            or origin_port not in allowed_ports
            or request_port not in allowed_ports
            or fetch_site == 'cross-site'):
        raise HTTPException(status_code=403, detail='Cross-origin plugin mutation rejected')
    # UI dev server (:5173) and local backend (:8080) are the only browser origins.
    if origin_host != request_host and not ({origin_host, request_host} <= allowed_hosts):
        raise HTTPException(status_code=403, detail='Origin host mismatch')


plugin_router = APIRouter(prefix='/api/plugins', dependencies=[Depends(validate_local_browser_origin)])

_manager = None


def get_manager():
    """Ленивая инициализация; тесты подменяют manager через set_manager()."""
    global _manager
    if _manager is None:
        base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        _manager = PluginManager(base)
    return _manager


def set_manager(m):
    global _manager
    _manager = m


def ok(**payload):
    return JSONResponse({'success': True, **payload})


def err(message, code='error', status=400, **extra):
    return JSONResponse({'success': False, 'error': message, 'code': code, **extra},
                        status_code=status)


@plugin_router.get('')
def list_plugins():
    return ok(plugins=get_manager().list_plugins(),
              data_warnings=get_manager().data_warnings(),
              api_version=PLUGIN_API_VERSION)


@plugin_router.get('/catalog')
def catalog():
    return ok(catalog=get_manager().catalog())


@plugin_router.get('/confirmations')
def pending_confirmations():
    return ok(confirmations=get_manager().pending_confirmations())


@plugin_router.get('/activity')
def activity(request: Request):
    q = request.query_params
    return ok(activity=get_manager().activity_read(
        pid=q.get('plugin'), limit=int(q.get('limit', 200)),
        level=q.get('level'), search=q.get('search')))


@plugin_router.post('/install')
async def install(request: Request):
    try:
        body = await _json(request)
        source = body.get('source')
        if not isinstance(source, str) or not source.strip():
            return err('source required (builtin:<id>, path to dir or archive)', 'invalid_source')
        info = get_manager().install(source.strip())
        return ok(plugin=info)
    except PluginInstallError as e:
        return err(str(e), 'install_rejected', 422)
    except Exception as e:
        return err('install failed: %s' % e, 'install_failed', 500)


@plugin_router.post('/confirmations/{cid}/approve')
async def approve_confirmation(cid: str, request: Request):
    try:
        result = get_manager().confirm(cid, True)
        return ok(**result)
    except (ConfirmationError, GatewayBlocked, PluginNotRunningError) as e:
        code = getattr(e, 'code', 'confirmation_invalid')
        return err(str(e), code, 409)
    except Exception as e:
        return err('approval failed: %s' % e, 'approval_failed', 500)


@plugin_router.post('/confirmations/{cid}/reject')
def reject_confirmation(cid: str):
    try:
        return ok(**get_manager().confirm(cid, False))
    except ConfirmationError as e:
        return err(str(e), 'confirmation_invalid', 409)


@plugin_router.get('/{pid}')
def plugin_info(pid: str):
    try:
        return ok(plugin=get_manager().info(pid, details=True))
    except KeyError:
        return err('plugin not found: %s' % pid, 'not_found', 404)


@plugin_router.post('/{pid}/enable')
def enable(pid: str):
    try:
        return ok(plugin=get_manager().enable(pid))
    except PluginInstallError as e:
        return err(str(e), 'incompatible', 422)
    except Exception as e:
        return err('enable failed: %s' % e, 'enable_failed', 500)


@plugin_router.post('/{pid}/disable')
def disable(pid: str):
    try:
        return ok(plugin=get_manager().disable(pid))
    except Exception as e:
        return err('disable failed: %s' % e, 'disable_failed', 500)


@plugin_router.delete('/{pid}')
def uninstall(pid: str):
    try:
        get_manager().uninstall(pid)
        return ok(deleted=pid)
    except Exception as e:
        return err('uninstall failed: %s' % e, 'uninstall_failed', 500)


@plugin_router.get('/{pid}/permissions')
def permissions_get(pid: str):
    try:
        return ok(**get_manager().permissions_status(pid))
    except KeyError:
        return err('plugin not found: %s' % pid, 'not_found', 404)


@plugin_router.put('/{pid}/permissions')
async def permissions_put(pid: str, request: Request):
    try:
        body = await _json(request)
        return ok(**get_manager().permissions_put(pid, body.get('grants')))
    except KeyError:
        return err('plugin not found: %s' % pid, 'not_found', 404)
    except ValueError as e:
        return err(str(e), 'invalid_grants', 422)


@plugin_router.get('/{pid}/settings')
def settings_get(pid: str):
    try:
        return ok(**get_manager().settings_get(pid))
    except KeyError:
        return err('plugin not found: %s' % pid, 'not_found', 404)


@plugin_router.put('/{pid}/settings')
async def settings_put(pid: str, request: Request):
    try:
        body = await _json(request)
        return ok(**get_manager().settings_put(pid, body.get('settings')))
    except KeyError:
        return err('plugin not found: %s' % pid, 'not_found', 404)
    except PluginInstallError as e:
        return err(str(e), 'invalid_settings', 422)


@plugin_router.get('/{pid}/secrets')
def secrets_get(pid: str):
    """Только имена секретов; значения не возвращаются никогда (§8)."""
    try:
        return ok(**get_manager().secret_keys(pid))
    except KeyError:
        return err('plugin not found: %s' % pid, 'not_found', 404)


@plugin_router.put('/{pid}/secrets')
async def secrets_put(pid: str, request: Request):
    """Запись секретов плагина. Только запись: значения не возвращаются никогда."""
    try:
        body = await _json(request)
        updates = body.get('secrets')
        if updates is None and isinstance(body.get('key'), str) and isinstance(body.get('value'), str):
            updates = {body['key']: body['value']}
        result = get_manager().secrets_put(pid, updates)
        return ok(**result)
    except KeyError:
        return err('plugin not found: %s' % pid, 'not_found', 404)
    except ValueError as e:
        return err(str(e), 'invalid_secrets', 422)
    except Exception as e:
        return err('secrets write failed: %s' % e, 'secrets_failed', 500)


@plugin_router.delete('/{pid}/secrets/{key}')
def secret_delete(pid: str, key: str):
    try:
        return ok(**get_manager().secret_delete(pid, key))
    except KeyError:
        return err('plugin not found: %s' % pid, 'not_found', 404)
    except ValueError as e:
        return err(str(e), 'invalid_secrets', 422)
    except Exception as e:
        return err('secret delete failed: %s' % e, 'secrets_failed', 500)


@plugin_router.get('/{pid}/capabilities')
def capabilities(pid: str):
    try:
        return ok(plugin=pid, capabilities=get_manager().info(pid).get('capabilities', []))
    except KeyError:
        return err('plugin not found: %s' % pid, 'not_found', 404)


@plugin_router.post('/{pid}/exec')
async def exec_capability(pid: str, request: Request):
    try:
        body = await _json(request)
        capability = body.get('capability')
        if not isinstance(capability, str) or not capability:
            return err('capability required', 'invalid_capability')
        result = get_manager().exec(pid, capability, params=body.get('params'),
                                    confirmation_token=body.get('confirmation_token'))
        return ok(**result)
    except KeyError:
        return err('plugin not found: %s' % pid, 'not_found', 404)
    except GatewayBlocked as e:
        return err(e.message, e.code, 409)
    except PluginNotRunningError as e:
        return err(str(e), 'plugin_not_running', 409)
    except PendingConfirmation as e:
        return ok(status='confirmation_required', confirmation=e.confirmation)
    except Exception as e:
        return err('execution failed: %s' % e, 'exec_failed', 500)


@plugin_router.get('/{pid}/confirmations')
def plugin_confirmations(pid: str):
    return ok(confirmations=get_manager().pending_confirmations(pid))


@plugin_router.get('/{pid}/health')
def health(pid: str):
    try:
        return ok(health=get_manager().health(pid))
    except KeyError:
        return err('plugin not found: %s' % pid, 'not_found', 404)


async def _json(request: Request):
    try:
        return await request.json()
    except Exception:
        return {}


def startup_plugins():
    """Запуск включённых плагинов при старте приложения (ошибки изолированы)."""
    try:
        get_manager().load_all()
    except Exception:
        pass
