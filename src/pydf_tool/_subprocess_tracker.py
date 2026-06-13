from __future__ import annotations

import atexit
import os
import signal
import subprocess
import threading

_lock = threading.Lock()
_active: set[subprocess.Popen] = set()
_atexit_registered = False


def register(proc: subprocess.Popen) -> None:
    global _atexit_registered
    with _lock:
        _active.add(proc)
        if not _atexit_registered:
            atexit.register(terminate_all)
            _atexit_registered = True


def unregister(proc: subprocess.Popen) -> None:
    with _lock:
        _active.discard(proc)


def terminate_all() -> None:
    with _lock:
        procs = list(_active)
        _active.clear()
    for proc in procs:
        _terminate(proc)


def _terminate(proc: subprocess.Popen) -> None:
    if proc.poll() is not None:
        return
    _signal_group(proc, signal.SIGTERM)
    try:
        proc.wait(timeout=2)
        return
    except subprocess.TimeoutExpired:
        pass
    _signal_group(proc, signal.SIGKILL)
    try:
        proc.wait(timeout=1)
    except subprocess.TimeoutExpired:
        pass


def _signal_group(proc: subprocess.Popen, sig: int) -> None:
    try:
        os.killpg(os.getpgid(proc.pid), sig)
    except (ProcessLookupError, PermissionError, OSError):
        try:
            if sig == signal.SIGKILL:
                proc.kill()
            else:
                proc.terminate()
        except (ProcessLookupError, OSError):
            pass
