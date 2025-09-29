"""project_data.py
Utility helpers to manage per-project data subfolders and marker file `_current_project.txt`.
The marker lets ExtendScript files (`getTimeline.jsx`, `cutAndPush.jsx`) know which subfolder
inside `data/` should contain exports.
"""
from __future__ import annotations
import os
from typing import Optional

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
DATA_DIR = os.path.join(ROOT_DIR, 'data')
MARKER_FILENAME = '_current_project.txt'

__all__ = [
    'ensure_project_data_dir',
    'write_current_project_marker',
    'read_current_project_marker',
    'project_subdir',
]

def _sanitize(name: str) -> str:
    return ''.join(ch if ch.isalnum() or ch in ('-', '_') else '_' for ch in name)

def project_subdir(project_name: str) -> str:
    os.makedirs(DATA_DIR, exist_ok=True)
    safe = _sanitize(project_name)
    path = os.path.join(DATA_DIR, safe)
    os.makedirs(path, exist_ok=True)
    return path

def ensure_project_data_dir(project_name: str) -> str:
    return project_subdir(project_name)

def write_current_project_marker(project_name: str) -> str:
    os.makedirs(DATA_DIR, exist_ok=True)
    marker_path = os.path.join(DATA_DIR, MARKER_FILENAME)
    with open(marker_path, 'w', encoding='utf-8') as f:
        f.write(_sanitize(project_name))
    return marker_path

def read_current_project_marker() -> Optional[str]:
    marker_path = os.path.join(DATA_DIR, MARKER_FILENAME)
    if not os.path.isfile(marker_path):
        return None
    try:
        with open(marker_path, 'r', encoding='utf-8') as f:
            return f.read().strip() or None
    except Exception:
        return None
