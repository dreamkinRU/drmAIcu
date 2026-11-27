"""Bounded resource admission for third-party plugin workers.

This is an application-level governor, not an OS CPU/RAM sandbox.
"""
import threading
from contextlib import contextmanager


class PluginResourceLimitError(RuntimeError):
    pass


class PluginResourceGovernor:
    """Bounds worker count and concurrent RPC work across the PluginManager."""

    def __init__(self, max_workers=8, max_concurrent_calls=16):
        if max_workers < 1 or max_concurrent_calls < 1:
            raise ValueError('resource limits must be positive')
        self.max_workers = int(max_workers)
        self.max_concurrent_calls = int(max_concurrent_calls)
        self._lock = threading.Lock()
        self._workers = 0
        self._calls = threading.BoundedSemaphore(self.max_concurrent_calls)

    @property
    def worker_count(self):
        with self._lock:
            return self._workers

    def acquire_worker(self):
        with self._lock:
            if self._workers >= self.max_workers:
                raise PluginResourceLimitError(
                    'plugin worker limit reached (%d)' % self.max_workers
                )
            self._workers += 1

    def release_worker(self):
        with self._lock:
            if self._workers:
                self._workers -= 1

    def acquire_call(self, timeout):
        return self._calls.acquire(timeout=max(0, float(timeout)))

    def release_call(self):
        self._calls.release()

    @contextmanager
    def call_slot(self, timeout):
        acquired = self.acquire_call(timeout)
        if not acquired:
            raise PluginResourceLimitError(
                'plugin RPC concurrency limit reached (%d)' % self.max_concurrent_calls
            )
        try:
            yield
        finally:
            self.release_call()
