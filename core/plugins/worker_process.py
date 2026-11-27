"""Parent-side RPC bridge for isolated third-party Python plugins.

This is process/fault isolation, not an OS security sandbox: the child still runs
under the same OS account and must not be treated as hostile-code containment.
"""
import json
import os
import signal
import struct
import subprocess
import sys
import threading

MAX_FRAME_BYTES = 16 * 1024 * 1024
DEFAULT_CALL_TIMEOUT = 180


class PluginWorkerError(RuntimeError):
    pass


def _read_exact(stream, size):
    chunks = []
    remaining = size
    while remaining:
        chunk = stream.read(remaining)
        if not chunk:
            if not chunks:
                return None
            raise EOFError('unexpected EOF in worker protocol frame')
        chunks.append(chunk)
        remaining -= len(chunk)
    return b''.join(chunks)


def _read_frame(stream):
    header = _read_exact(stream, 4)
    if header is None:
        return None
    size = struct.unpack('!I', header)[0]
    if size <= 0 or size > MAX_FRAME_BYTES:
        raise PluginWorkerError('invalid worker frame size: %s' % size)
    payload = _read_exact(stream, size)
    if payload is None:
        raise EOFError('missing worker frame payload')
    return json.loads(payload.decode('utf-8'))


def _write_frame(stream, message):
    payload = json.dumps(message, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode('utf-8')
    if len(payload) > MAX_FRAME_BYTES:
        raise PluginWorkerError('worker message exceeds %d bytes' % MAX_FRAME_BYTES)
    data = memoryview(struct.pack('!I', len(payload)) + payload)
    while data:
        written = stream.write(data)
        if not written:
            raise BrokenPipeError('worker protocol pipe closed')
        data = data[written:]
    stream.flush()


class PluginWorker:
    def __init__(self, manager, plugin_id, plugin_dir, entry_point, api):
        self.manager = manager
        self.plugin_id = plugin_id
        self.plugin_dir = os.path.abspath(plugin_dir)
        self.entry_point = entry_point
        self.api = api
        self.process = None
        self._reader = None
        self._stderr_reader = None
        self._send_lock = threading.Lock()
        self._request_lock = threading.RLock()
        self._pending_lock = threading.Lock()
        self._pending = {}
        self._next_id = 0
        self._ready = threading.Event()
        self._ready_error = None
        self._dead_error = None
        self._stopping = False
        self._stderr_tail = ''
        self._subscriptions = []
        self.state = 'created'
        self._governor_worker_acquired = False
        self._governor_lock = threading.Lock()

    def start(self, timeout=30):
        if self.state != 'created':
            raise PluginWorkerError('invalid worker state: %s' % self.state)
        self.state = 'starting'
        governor = getattr(self.manager, 'resource_governor', None)
        if governor is not None:
            try:
                governor.acquire_worker()
                self._governor_worker_acquired = True
            except Exception as exc:
                self.state = 'failed'
                raise PluginWorkerError(str(exc))
        script = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'worker.py')
        env = {}
        for key in ('PATH', 'SYSTEMROOT', 'WINDIR', 'TEMP', 'TMP', 'HOME',
                    'USERPROFILE', 'APPDATA', 'LOCALAPPDATA'):
            if key in os.environ:
                env[key] = os.environ[key]
        flags = (getattr(subprocess, 'CREATE_NO_WINDOW', 0) | getattr(subprocess, 'CREATE_NEW_PROCESS_GROUP', 0)) if os.name == 'nt' else 0
        kwargs = {
            'stdin': subprocess.PIPE,
            'stdout': subprocess.PIPE,
            'stderr': subprocess.PIPE,
            'cwd': self.plugin_dir,
            'env': env,
            'bufsize': 0,
            'creationflags': flags,
        }
        if os.name != 'nt':
            kwargs['start_new_session'] = True
        try:
            self.process = subprocess.Popen(
                [sys.executable, '-I', script, self.plugin_id, self.plugin_dir, self.entry_point],
                **kwargs
            )
        except Exception:
            self.state = 'failed'
            self._release_governor_worker()
            raise
        self._reader = threading.Thread(target=self._reader_loop, name='plugin-rpc-' + self.plugin_id, daemon=True)
        self._stderr_reader = threading.Thread(target=self._stderr_loop, name='plugin-stderr-' + self.plugin_id, daemon=True)
        self._reader.start()
        self._stderr_reader.start()
        if not self._ready.wait(timeout):
            self.terminate()
            self.state = 'failed'
            raise PluginWorkerError('plugin worker startup timed out after %ss' % timeout)
        if self._ready_error:
            error = self._ready_error
            self.terminate()
            self.state = 'failed'
            raise PluginWorkerError('plugin worker startup failed: %s' % error)
        if self._dead_error:
            self.state = 'failed'
            self._release_governor_worker()
            raise PluginWorkerError('plugin worker exited during startup: %s' % self._dead_error)
        self.state = 'running'
        return True

    def _send(self, message):
        proc = self.process
        if proc is None or proc.poll() is not None or proc.stdin is None:
            raise PluginWorkerError('plugin worker is not running')
        with self._send_lock:
            _write_frame(proc.stdin, message)

    def _request(self, command, timeout=DEFAULT_CALL_TIMEOUT, **payload):
        with self._request_lock:
            if self._dead_error:
                raise PluginWorkerError(self._dead_error)
            governor = getattr(self.manager, 'resource_governor', None)
            call_acquired = False
            if governor is not None:
                call_acquired = governor.acquire_call(timeout)
                if not call_acquired:
                    raise PluginWorkerError('plugin RPC concurrency limit reached')
            self._next_id += 1
            request_id = self._next_id
            event = threading.Event()
            result = {}
            with self._pending_lock:
                self._pending[request_id] = (event, result)
            try:
                self._send({'type': command, 'id': request_id, **payload})
                if not event.wait(timeout):
                    self._dead_error = 'plugin worker request timed out: %s' % command
                    self.terminate()
                    self.manager._worker_crashed(self.plugin_id, self._dead_error)
                    raise PluginWorkerError(self._dead_error)
                if not result.get('ok'):
                    raise PluginWorkerError(result.get('error') or 'plugin worker request failed')
                return result.get('result')
            finally:
                with self._pending_lock:
                    self._pending.pop(request_id, None)
                if call_acquired:
                    governor.release_call()

    def invoke(self, capability, params):
        return self._request('invoke', capability=capability, params=params or {})

    def health(self):
        result = self._request('health', timeout=10)
        return result if isinstance(result, dict) else {}

    def uninstall(self):
        return self._request('uninstall', timeout=10)

    def stop(self):
        if self.process is None:
            return
        self._stopping = True
        self.state = 'stopping'
        try:
            self._request('stop', timeout=10)
        except Exception:
            pass
        self.terminate()
        for callback in self._subscriptions:
            try:
                self.manager.events.unsubscribe(callback)
            except Exception:
                pass
        self._subscriptions.clear()

    def _release_governor_worker(self):
        with self._governor_lock:
            if not self._governor_worker_acquired:
                return
            self._governor_worker_acquired = False
        governor = getattr(self.manager, 'resource_governor', None)
        if governor is not None:
            governor.release_worker()

    def _terminate_process_tree(self, proc):
        if os.name != 'nt':
            # Process group can outlive its leader; kill it even when proc.poll() is set.
            try:
                os.killpg(proc.pid, signal.SIGTERM)
            except ProcessLookupError:
                return
            except Exception:
                pass
            try:
                proc.wait(timeout=3)
            except Exception:
                pass
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            except Exception:
                try:
                    proc.kill()
                    proc.wait(timeout=3)
                except Exception:
                    pass
            return
        if proc.poll() is not None:
            return
        try:
            subprocess.run(
                ['taskkill', '/PID', str(proc.pid), '/T', '/F'],
                capture_output=True, timeout=5, check=False,
            )
            proc.wait(timeout=3)
            return
        except Exception:
            pass
        try:
            proc.kill()
            proc.wait(timeout=3)
        except Exception:
            pass

    def terminate(self):
        proc = self.process
        if proc is None:
            self._release_governor_worker()
            if self.state not in ('failed', 'stopped'):
                self.state = 'stopped'
            return
        self._terminate_process_tree(proc)
        for stream in (proc.stdin, proc.stdout, proc.stderr):
            try:
                if stream:
                    stream.close()
            except OSError:
                pass
        self._release_governor_worker()
        self.state = 'failed' if self._dead_error and not self._stopping else 'stopped'

    def _handle_rpc(self, message):
        method = message.get('method')
        args = message.get('args') or {}
        if method == 'register_capability':
            name = args['name']
            self.api.register_capability(
                name,
                args['permission'],
                lambda params, capability=name: self.invoke(capability, params),
                args.get('confirmation', 'auto'),
                args.get('description', ''),
            )
            return True
        if method == 'log':
            self.api.log(args.get('kind', 'info'), args.get('event', 'worker_log'), **(args.get('details') or {}))
            return True
        if method == 'settings':
            return self.api.settings()
        if method == 'set_settings':
            self.api.set_settings(args.get('updates') or {})
            return True
        if method == 'get_secret':
            return self.api.get_secret(args['key'])
        if method == 'set_secret':
            self.api.set_secret(args['key'], args['value'])
            return True
        if method == 'remove_secret':
            self.api.remove_secret(args['key'])
            return True
        if method == 'delete_secrets':
            self.api.delete_secrets()
            return True
        if method == 'publish':
            self.api.publish(args['event'], **(args.get('payload') or {}))
            return True
        if method == 'subscribe':
            callback_id = args['callback_id']
            callback = lambda event, payload, cid=callback_id: self._send({
                'type': 'event', 'callback_id': cid, 'event': event, 'payload': payload,
            })
            self._subscriptions.append(callback)
            self.api.subscribe(callback)
            return True
        if method == 'capabilities':
            return self.api.capabilities()
        raise PluginWorkerError('unsupported worker API method: %s' % method)

    def _reader_loop(self):
        try:
            while self.process and self.process.stdout:
                message = _read_frame(self.process.stdout)
                if message is None:
                    break
                kind = message.get('type')
                if kind == 'rpc_request':
                    try:
                        result = self._handle_rpc(message)
                        response = {'type': 'rpc_response', 'id': message.get('id'), 'ok': True, 'result': result}
                    except Exception as e:
                        response = {'type': 'rpc_response', 'id': message.get('id'), 'ok': False, 'error': str(e)}
                    self._send(response)
                elif kind == 'response':
                    with self._pending_lock:
                        pending = self._pending.get(message.get('id'))
                    if pending:
                        event, result = pending
                        result.update(message)
                        event.set()
                elif kind == 'ready':
                    self._ready.set()
                elif kind == 'startup_error':
                    self._ready_error = message.get('error') or 'unknown startup error'
                    self._ready.set()
        except Exception as e:
            self._dead_error = str(e)
        finally:
            if self.process and self.process.poll() is None and not self._stopping:
                try:
                    self.process.wait(timeout=0.2)
                except Exception:
                    self._terminate_process_tree(self.process)
            if self.process and self.process.poll() is not None and not self._stopping:
                self._dead_error = self._dead_error or ('worker exited with code %s' % self.process.returncode)
                self.manager._worker_crashed(self.plugin_id, self._dead_error)
            self._ready.set()
            self._release_governor_worker()
            if self.state not in ('stopping', 'stopped'):
                self.state = 'failed' if self._dead_error else 'stopped'
            with self._pending_lock:
                pending = list(self._pending.values())
            for event, result in pending:
                result.update({'ok': False, 'error': self._dead_error or 'worker stopped'})
                event.set()

    def _stderr_loop(self):
        try:
            while self.process and self.process.stderr:
                chunk = self.process.stderr.read(4096)
                if not chunk:
                    break
                self._stderr_tail = (self._stderr_tail + chunk.decode('utf-8', errors='replace'))[-8000:]
        except Exception:
            pass
