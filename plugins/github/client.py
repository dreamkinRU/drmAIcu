"""GitHub App клиент: JWT → Installation Access Token → REST (§6).

- Private Key запрашивается из Secret Manager непосредственно перед подписью
  и никогда не возвращается наружу и не логируется.
- Installation Token кэшируется в памяти с учётом expires_at; 401 → один рефреш.
"""
import threading
import time

import jwt
import requests

API_BASE = 'https://api.github.com'
JWT_TTL = 540
REQUEST_TIMEOUT = 15.0


class GitHubAuthError(Exception):
    pass


class GitHubAPIError(Exception):
    def __init__(self, status, message, url=''):
        super().__init__('%s %s: %s' % (status, url, message))
        self.status = status
        self.message = message
        self.url = url


class GitHubAppClient:
    def __init__(self, ctx):
        self._ctx = ctx
        self._lock = threading.Lock()
        self._token = None
        self._token_expires = 0.0
        self._jwt_cache = None
        self._jwt_expires = 0.0

    # ---------------- auth ----------------

    def _config(self):
        s = self._ctx.settings()
        app_id = str(s.get('app_id') or '').strip()
        installation_id = str(s.get('installation_id') or '').strip()
        if not app_id or not installation_id:
            raise GitHubAuthError('не настроен GitHub App (app_id / installation_id в настройках плагина)')
        return app_id, installation_id

    def _app_jwt(self):
        with self._lock:
            now = time.time()
            if self._jwt_cache and now < self._jwt_expires:
                return self._jwt_cache
            key = self._ctx.get_secret('private_key')
            if not key:
                raise GitHubAuthError('Private Key не найден в хранилище секретов (Secret Manager)')
            app_id, _ = self._config()
            payload = {'iat': int(now) - 60, 'exp': int(now) + JWT_TTL, 'iss': app_id}
            self._jwt_cache = jwt.encode(payload, key, algorithm='RS256')
            self._jwt_expires = now + JWT_TTL - 60
            return self._jwt_cache

    def _fetch_installation_token(self):
        _, installation_id = self._config()
        headers = {'Authorization': 'Bearer %s' % self._app_jwt(),
                   'Accept': 'application/vnd.github+json'}
        r = requests.post('%s/app/installations/%s/access_tokens' % (API_BASE, installation_id),
                          headers=headers, timeout=REQUEST_TIMEOUT)
        if r.status_code != 201:
            raise GitHubAuthError('installation token failed: HTTP %s' % r.status_code)
        data = r.json()
        token = data.get('token')
        if not token:
            raise GitHubAuthError('installation token response missing token')
        expires = data.get('expires_at')
        return token, expires

    def token(self, force=False):
        with self._lock:
            now = time.time()
            if not force and self._token and now < self._token_expires:
                return self._token
            tok, expires_at = self._fetch_installation_token()
            self._token = tok
            self._token_expires = now + 3000
            return self._token

    def reset_token(self):
        with self._lock:
            self._token = None
            self._token_expires = 0.0
            self._jwt_cache = None
            self._jwt_expires = 0.0

    def auth_configured(self):
        try:
            self._config()
            return True
        except GitHubAuthError:
            return False

    def test_connection(self):
        """Диагностика авторизации (§6.3). Не выбрасывает секреты в исключения."""
        try:
            app_id, installation_id = self._config()
        except GitHubAuthError as e:
            return {'ok': False, 'configured': False, 'error': str(e)}
        try:
            token = self.token(force=True)
        except GitHubAuthError as e:
            return {'ok': False, 'configured': True, 'app_id_set': bool(app_id),
                    'installation_id_set': bool(installation_id), 'error': str(e)}
        headers = {'Authorization': 'Bearer %s' % token, 'Accept': 'application/vnd.github+json'}
        r = requests.get('%s/installation/repositories?per_page=1' % API_BASE, headers=headers,
                         timeout=REQUEST_TIMEOUT)
        if r.status_code == 200:
            total = r.json().get('total_count', 0)
            return {'ok': True, 'configured': True, 'repositories_total': total}
        return {'ok': False, 'configured': True, 'error': 'installation check failed: HTTP %s' % r.status_code}

    # ---------------- REST ----------------

    def _get(self, url, params=None):
        headers = {'Authorization': 'Bearer %s' % self.token(), 'Accept': 'application/vnd.github+json'}
        r = requests.get(url, headers=headers, params=params, timeout=REQUEST_TIMEOUT)
        if r.status_code == 401:
            headers['Authorization'] = 'Bearer %s' % self.token(force=True)
            r = requests.get(url, headers=headers, params=params, timeout=REQUEST_TIMEOUT)
        if r.status_code >= 400:
            try:
                msg = r.json().get('message', '')
            except ValueError:
                msg = r.text[:200]
            raise GitHubAPIError(r.status_code, msg, url)
        return r

    def _repo_full(self, params, key='repository'):
        full = str(params.get(key) or '').strip().strip('/')
        if not full or '/' != full.count('/') or any(s in ('..', '') for s in full.split('/')):
            raise ValueError('params.%s must be "owner/repo"' % key)
        return full

    def list_repositories(self, params=None):
        params = params or {}
        page = int(params.get('page', 1))
        out = []
        r = self._get('%s/installation/repositories' % API_BASE, params={'per_page': 50, 'page': page})
        data = r.json()
        for repo in data.get('repositories', []):
            out.append({
                'full_name': repo.get('full_name'), 'private': repo.get('private'),
                'default_branch': repo.get('default_branch'), 'html_url': repo.get('html_url'),
                'description': repo.get('description'), 'updated_at': repo.get('updated_at'),
                'permissions': repo.get('permissions', {}),
            })
        return {'page': page, 'total_count': data.get('total_count', len(out)), 'repositories': out}

    def get_repository(self, params=None):
        full = self._repo_full(params or {})
        r = self._get('%s/repos/%s' % (API_BASE, full))
        d = r.json()
        return {'full_name': d.get('full_name'), 'private': d.get('private'),
                'default_branch': d.get('default_branch'), 'html_url': d.get('html_url'),
                'description': d.get('description'), 'size': d.get('size'),
                'updated_at': d.get('updated_at'), 'permissions': d.get('permissions', {})}

    def get_tree(self, params=None):
        p = params or {}
        full = self._repo_full(p)
        ref = str(p.get('ref') or '').strip()
        if not ref or any(c in ref for c in ('..', '\x00', '\n')):
            raise ValueError('invalid ref')
        r = self._get('%s/repos/%s/git/trees/%s' % (API_BASE, full, ref),
                      params={'recursive': '1'} if p.get('recursive') else None)
        d = r.json()
        return {'sha': d.get('sha'), 'truncated': d.get('truncated', False),
                'tree': [{'path': t.get('path'), 'type': t.get('type'), 'size': t.get('size')}
                         for t in d.get('tree', [])]}

    def get_file(self, params=None):
        p = params or {}
        full = self._repo_full(p)
        path = str(p.get('path') or '').strip()
        if not path or path.startswith('/') or '..' in path.split('/'):
            raise ValueError('invalid path')
        ref = str(p.get('ref') or '').strip() or None
        r = self._get('%s/repos/%s/contents/%s' % (API_BASE, full, path),
                      params={'ref': ref} if ref else None)
        d = r.json()
        if isinstance(d, list):
            return {'type': 'dir', 'entries': [
                {'name': e.get('name'), 'path': e.get('path'), 'type': e.get('type'), 'size': e.get('size')}
                for e in d]}
        return {'type': 'file', 'path': d.get('path'), 'size': d.get('size'),
                'encoding': d.get('encoding'), 'content': d.get('content', ''),
                'sha': d.get('sha')}

    # ---------------- branches (REST Git Data) ----------------

    def list_branches(self, params=None):
        p = params or {}
        full = self._repo_full(p)
        page = int(p.get('page', 1))
        r = self._get('%s/repos/%s/branches' % (API_BASE, full), params={'per_page': 50, 'page': page})
        return {'page': page, 'branches': [
            {'name': b.get('name'), 'sha': (b.get('commit') or {}).get('sha'),
             'protected': b.get('protected')} for b in r.json()]}

    def create_branch(self, params=None):
        """Рефакторинг ref: из существующего SHA. WRITE + подтверждение."""
        p = params or {}
        full = self._repo_full(p)
        branch = str(p.get('branch') or '').strip()
        if not branch or branch.startswith('-') or any(c in branch for c in ('..', ' ', '\x00', '\n')):
            raise ValueError('invalid branch name')
        sha = str(p.get('sha') or '').strip()
        if not _is_sha(sha):
            raise ValueError('valid source sha required')
        headers = {'Authorization': 'Bearer %s' % self.token(), 'Accept': 'application/vnd.github+json'}
        r = requests.post('%s/repos/%s/git/refs' % (API_BASE, full), headers=headers,
                          json={'ref': 'refs/heads/%s' % branch, 'sha': sha}, timeout=REQUEST_TIMEOUT)
        if r.status_code not in (201,):
            raise GitHubAPIError(r.status_code, 'create branch failed', full)
        return {'branch': branch, 'sha': sha}

    def compare(self, params=None):
        p = params or {}
        full = self._repo_full(p)
        base = str(p.get('base') or '').strip()
        head = str(p.get('head') or '').strip()
        if not base or not head or '..' in base + head:
            raise ValueError('base/head refs required')
        r = self._get('%s/repos/%s/compare/%s...%s' % (API_BASE, full, base, head))
        d = r.json()
        return {'status': d.get('status'), 'ahead_by': d.get('ahead_by'), 'behind_by': d.get('behind_by'),
                'total_commits': d.get('total_commits'),
                'files': [{'filename': f.get('filename'), 'status': f.get('status'),
                           'additions': f.get('additions'), 'deletions': f.get('deletions')}
                          for f in d.get('files', [])]}


def _is_sha(value):
    return len(value) in (7, 8, 40, 64) and all(c in '0123456789abcdef' for c in value.lower())
