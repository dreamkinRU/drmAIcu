"""Child process entry point for third-party Python plugins.

Protocol: 4-byte network-order length + UTF-8 JSON payload. Plugin stdout is
redirected to stderr so print() cannot corrupt the RPC channel.
"""
import json
import os
import queue
import struct
import sys
import threading
import traceback

MAX_FRAME_BYTES = 16 * 1024 * 1024
RPC_TIMEOUT = 30


def _read_exact(stream, size):
    chunks = []
    remaining = size
    while remaining:
        chunk = stream.read(remaining)
        if not chunk:
            if not chunks:
                return None
            raise EOFError('unexpected EOF in worker protocol')
        chunks.append(chunk)
        remaining -= len(chunk)
    return b''.join(chunks)


def _read_frame(stream):
    header = _read_exact(stream, 4)
    if header is None:
        return None
    size = struct.unpack('!I', header)[0]
    if size <= 0 or size > MAX_FRAME_BYTES:
        raise RuntimeError('invalid RPC frame size')
    payload = _read_exact(stream, size)
    if payload is None:
        raise EOFError('missing RPC payload')
    return json.loads(payload.decode('utf-8'))


def _write_frame(stream, message):
    payload = json.dumps(message, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode('utf-8')
    if len(payload) > MAX_FRAME_BYTES:
        raise RuntimeError('RPC message too large')
    data = memoryview(struct.pack('!I', len(payload)) + payload)
    while data:
        written = stream.write(data)
        if not written:
            raise BrokenPipeError('worker protocol pipe closed')
        data = data[written:]
    stream.flush()


class WorkerContext:
    def __init__(self, send, pending, pending_lock):
        self._send = send
        self._pending = pending
        self._pending_lock = pending_lock
        self._next_id = 0
        self._rpc_lock = threading.RLock()
        self._handlers = {}
        self._callbacks = {}
        self._next_callback = 0
        self._commands = queue.Queue()

    def _rpc(self, method, **args):
        with self._rpc_lock:
            self._next_id += 1
            request_id = self._next_id
            event = threading.Event()
            result = {}
            with self._pending_lock:
                self._pending[request_id] = (event, result)
            try:
                self._send({'type': 'rpc_request', 'id': request_id, 'method': method, 'args': args})
                if not event.wait(RPC_TIMEOUT):
                    raise RuntimeError('Plugin API request timed out: %s' % method)
                if not result.get('ok'):
                    raise RuntimeError(result.get('error') or 'Plugin API request failed')
                return result.get('result')
            finally:
                with self._pending_lock:
                    self._pending.pop(request_id, None)

    def log(self, kind, event, **details):
        return self._rpc('log', kind=kind, event=event, details=details)

    def settings(self):
        return self._rpc('settings')

    def set_settings(self, updates):
        return self._rpc('set_settings', updates=updates)

    def get_secret(self, key):
        return self._rpc('get_secret', key=key)

    def set_secret(self, key, value):
        return self._rpc('set_secret', key=key, value=value)

    def remove_secret(self, key):
        return self._rpc('remove_secret', key=key)

    def delete_secrets(self):
        return self._rpc('delete_secrets')

    def publish(self, event, **payload):
        return self._rpc('publish', event=event, payload=payload)

    def subscribe(self, fn):
        self._next_callback += 1
        callback_id = self._next_callback
        self._callbacks[callback_id] = fn
        self._rpc('subscribe', callback_id=callback_id)
        return callback_id

    def register_capability(self, name, permission, handler, confirmation='auto', description=''):
        self._handlers[name] = handler
        return self._rpc(
            'register_capability', name=name, permission=permission,
            confirmation=confirmation, description=description,
        )

    def capabilities(self):
        return self._rpc('capabilities')

    def _dispatch_event(self, message):
        callback = self._callbacks.get(message.get('callback_id'))
        if callback:
            try:
                callback(message.get('event'), message.get('payload') or {})
            except Exception:
                self.log('error', 'event_callback_failed', error=traceback.format_exc()[-2000:])


def _main():
    if len(sys.argv) != 4:
        raise SystemExit('worker requires plugin_id, plugin_dir, entry_point')
    plugin_id, plugin_dir, entry_point = sys.argv[1:]
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    sys.path.insert(0, root)
    sys.stdout = sys.stderr

    from core.plugins.loader import load_entry

    stdin = sys.stdin.buffer
    stdout = sys.__stdout__.buffer
    send_lock = threading.Lock()

    def send(message):
        with send_lock:
            _write_frame(stdout, message)

    pending = {}
    pending_lock = threading.Lock()
    commands = queue.Queue()
    context = WorkerContext(send, pending, pending_lock)

    def reader_loop():
        try:
            while True:
                message = _read_frame(stdin)
                if message is None:
                    commands.put({'type': 'eof'})
                    return
                if message.get('type') == 'rpc_response':
                    with pending_lock:
                        item = pending.get(message.get('id'))
                    if item:
                        event, result = item
                        result.update(message)
                        event.set()
                else:
                    commands.put(message)
        except Exception as e:
            commands.put({'type': 'eof', 'error': str(e)})

    reader = threading.Thread(target=reader_loop, name='plugin-parent-reader', daemon=True)
    reader.start()

    module = None
    try:
        module = load_entry(plugin_id, plugin_dir, entry_point)
        if not hasattr(module, 'initialize'):
            raise ImportError('entry_point does not define initialize(ctx)')
        initialized = module.initialize(context)
        if initialized is False:
            raise RuntimeError('initialize() returned False')
        if hasattr(module, 'start'):
            module.start()
        send({'type': 'ready', 'plugin': plugin_id})
    except BaseException as e:
        send({'type': 'startup_error', 'error': '%s\n%s' % (e, traceback.format_exc()[-4000:])})
        return 1

    while True:
        command = commands.get()
        kind = command.get('type')
        request_id = command.get('id')
        if kind == 'eof':
            break
        if kind == 'event':
            context._dispatch_event(command)
            continue
        if kind == 'invoke':
            try:
                handler = context._handlers.get(command.get('capability'))
                if handler is None:
                    raise KeyError('unknown capability: %s' % command.get('capability'))
                result = handler(command.get('params') or {})
                send({'type': 'response', 'id': request_id, 'ok': True, 'result': result})
            except BaseException as e:
                try:
                    send({'type': 'response', 'id': request_id, 'ok': False,
                          'error': '%s' % e})
                except Exception:
                    break
        elif kind == 'health':
            try:
                result = module.health() if hasattr(module, 'health') else {}
                send({'type': 'response', 'id': request_id, 'ok': True, 'result': result or {}})
            except BaseException as e:
                send({'type': 'response', 'id': request_id, 'ok': False, 'error': str(e)})
        elif kind == 'uninstall':
            try:
                if hasattr(module, 'uninstall'):
                    module.uninstall()
                send({'type': 'response', 'id': request_id, 'ok': True, 'result': True})
            except BaseException as e:
                send({'type': 'response', 'id': request_id, 'ok': False, 'error': str(e)})
        elif kind == 'stop':
            try:
                if hasattr(module, 'stop'):
                    module.stop()
                send({'type': 'response', 'id': request_id, 'ok': True, 'result': True})
            except BaseException as e:
                send({'type': 'response', 'id': request_id, 'ok': False, 'error': str(e)})
            break
    return 0


if __name__ == '__main__':
    raise SystemExit(_main())
