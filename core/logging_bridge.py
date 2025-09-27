"""Lightweight logging bridge to route print output to GUI log.

Usage:
  from core import logging_bridge as lb
  lb.register_gui_logger(gui.log)  # supply a function(str)
  lb.activate()                    # replace sys.stdout/sys.stderr

All subsequent print() calls in any module will be mirrored to gui.log.
Thread-safe (simple lock). Lines are split so partial buffers don't spam.
"""
from __future__ import annotations

import sys
import io
import threading
from typing import Callable, Optional

_lock = threading.Lock()
_gui_sink: Optional[Callable[[str], None]] = None
_orig_stdout = sys.stdout
_orig_stderr = sys.stderr
_activated = False

def register_gui_logger(func: Callable[[str], None]):
    """Register the GUI sink (callable receiving a text line)."""
    global _gui_sink
    with _lock:
        _gui_sink = func

def is_active() -> bool:
    return _activated

class _GuiStream(io.TextIOBase):
    def __init__(self, underlying):
        self._under = underlying
        self._buffer = ""

    def write(self, s):  # type: ignore[override]
        if not isinstance(s, str):
            s = str(s)
        if not s:
            return 0
        self._buffer += s
        # Flush on newlines
        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)
            _emit(line)
        # Always mirror to original stream
        try:
            self._under.write(s)
        except Exception:
            pass
        return len(s)

    def flush(self):  # type: ignore[override]
        if self._buffer:
            _emit(self._buffer)
            self._buffer = ""
        try:
            self._under.flush()
        except Exception:
            pass

def _emit(line: str):
    line = line.rstrip("\r")
    if not line.strip():
        return
    sink = _gui_sink
    if sink:
        try:
            sink(line)
        except Exception:
            # Never let GUI logging crash the app
            pass

def activate(mirror_to_console: bool = True):
    """Activate global redirection.

    mirror_to_console: if False, suppress writing to original stdout/stderr.
    """
    global _activated, _orig_stdout, _orig_stderr
    with _lock:
        if _activated:
            return
        if not mirror_to_console:
            # replace underlying with dummy to suppress console output
            class _Null(io.TextIOBase):
                def write(self, s): return len(s)
            under = _Null()
        else:
            under = _orig_stdout
        sys.stdout = _GuiStream(under)  # type: ignore
        sys.stderr = _GuiStream(_orig_stderr if mirror_to_console else under)  # type: ignore
        _activated = True

def deactivate():
    global _activated
    with _lock:
        if not _activated:
            return
        sys.stdout = _orig_stdout
        sys.stderr = _orig_stderr
        _activated = False

def log(msg: str):
    """Explicit logging helper (bypass buffering)."""
    _emit(msg)
