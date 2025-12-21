"""
core.utils.paths - Centralized path management

Replaces 55+ occurrences of:
    THIS_DIR = Path(__file__).parent.resolve()
    CORE_DIR = THIS_DIR.parent
    ROOT_DIR = CORE_DIR.parent
    sys.path.insert(0, str(ROOT_DIR))
"""

import sys
from pathlib import Path
from typing import Optional

# Calculate paths once at import time
_THIS_FILE = Path(__file__).resolve()
UTILS_DIR = _THIS_FILE.parent
CORE_DIR = UTILS_DIR.parent
ROOT_DIR = CORE_DIR.parent
DATA_DIR = ROOT_DIR / "data"
GUI_DIR = ROOT_DIR / "GUI"

# Common subdirectories
PREMIER_CORE_DIR = CORE_DIR / "premierCore"
AI_DIR = CORE_DIR / "ai"
DOWNLOAD_DIR = CORE_DIR / "downloadTool"

_paths_initialized = False


def setup_paths() -> None:
    """
    Add ROOT_DIR to sys.path if not already present.

    Call this at the start of any module that needs to import from the project.
    Safe to call multiple times.

    Example:
        from core.utils import setup_paths
        setup_paths()

        # Now can import from anywhere in project
        from core.ai import some_module
    """
    global _paths_initialized

    if _paths_initialized:
        return

    root_str = str(ROOT_DIR)
    if root_str not in sys.path:
        sys.path.insert(0, root_str)

    _paths_initialized = True


def get_project_path(relative_path: str) -> Path:
    """
    Get absolute path relative to project root.

    Args:
        relative_path: Path relative to ROOT_DIR (e.g., "data/markers.json")

    Returns:
        Absolute Path object

    Example:
        >>> get_project_path("data/markers.json")
        PosixPath('/home/user/tool/data/markers.json')
    """
    return ROOT_DIR / relative_path


def get_data_path(filename: str) -> Path:
    """
    Get path to file in data directory.

    Args:
        filename: Filename or relative path within data dir

    Returns:
        Absolute Path object
    """
    return DATA_DIR / filename


def ensure_dir(path: Path) -> Path:
    """
    Create directory if it doesn't exist.

    Args:
        path: Directory path to create

    Returns:
        The same path (for chaining)
    """
    path.mkdir(parents=True, exist_ok=True)
    return path


def normalize_path(path: str) -> str:
    """
    Normalize path separators (convert backslashes to forward slashes).

    Useful for cross-platform compatibility and matching paths.

    Args:
        path: Path string to normalize

    Returns:
        Normalized path string
    """
    if not path:
        return ""
    return path.replace("\\", "/").replace("//", "/")


def get_env_path() -> Path:
    """Get path to .env file in project root."""
    return ROOT_DIR / ".env"


# Auto-setup paths when this module is imported
setup_paths()
