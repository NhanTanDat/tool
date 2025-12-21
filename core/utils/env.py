"""
core.utils.env - Unified environment variable handling

Replaces 4 duplicate implementations:
- get_link.py: _env_int, _env_str, _env_bool
- genmini_analyze.py: _safe_int_env, _safe_float_env
- auto_v4_workflow.py: _load_env_file
- marker_based_workflow.py: _load_env_file
"""

import os
from pathlib import Path
from typing import Optional, Any

from .paths import get_env_path

_env_loaded = False


def load_env(env_path: Optional[Path] = None, override: bool = False) -> bool:
    """
    Load environment variables from .env file.

    Args:
        env_path: Path to .env file (default: ROOT_DIR/.env)
        override: If True, override existing env vars. If False, use setdefault.

    Returns:
        True if file was loaded successfully, False otherwise

    Example:
        >>> load_env()
        True
        >>> os.environ.get("GEMINI_API_KEY")
        'your-api-key-here'
    """
    global _env_loaded

    if _env_loaded and not override:
        return True

    if env_path is None:
        env_path = get_env_path()

    if not env_path.exists():
        return False

    try:
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()

                # Skip empty lines and comments
                if not line or line.startswith("#"):
                    continue

                # Parse key=value
                if "=" not in line:
                    continue

                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip()

                # Remove surrounding quotes
                if len(value) >= 2:
                    if (value[0] == '"' and value[-1] == '"') or \
                       (value[0] == "'" and value[-1] == "'"):
                        value = value[1:-1]

                if not key:
                    continue

                if override:
                    os.environ[key] = value
                else:
                    os.environ.setdefault(key, value)

        _env_loaded = True
        return True

    except Exception:
        return False


def get_env_str(name: str, default: str = "") -> str:
    """
    Get environment variable as string.

    Args:
        name: Environment variable name
        default: Default value if not set

    Returns:
        Environment variable value or default
    """
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip()


def get_env_int(name: str, default: int = 0) -> int:
    """
    Get environment variable as integer.

    Args:
        name: Environment variable name
        default: Default value if not set or invalid

    Returns:
        Environment variable as int or default
    """
    value = os.environ.get(name)
    if value is None:
        return default
    try:
        return int(value.strip())
    except (ValueError, TypeError):
        return default


def get_env_float(name: str, default: float = 0.0) -> float:
    """
    Get environment variable as float.

    Args:
        name: Environment variable name
        default: Default value if not set or invalid

    Returns:
        Environment variable as float or default
    """
    value = os.environ.get(name)
    if value is None:
        return default
    try:
        return float(value.strip())
    except (ValueError, TypeError):
        return default


def get_env_bool(name: str, default: bool = False) -> bool:
    """
    Get environment variable as boolean.

    Truthy values: "1", "true", "yes", "on" (case-insensitive)
    Falsy values: "0", "false", "no", "off", "" (case-insensitive)

    Args:
        name: Environment variable name
        default: Default value if not set

    Returns:
        Environment variable as bool or default
    """
    value = os.environ.get(name)
    if value is None:
        return default

    value = value.strip().lower()
    if value in ("1", "true", "yes", "on"):
        return True
    if value in ("0", "false", "no", "off", ""):
        return False

    return default


def require_env(name: str) -> str:
    """
    Get required environment variable.

    Args:
        name: Environment variable name

    Returns:
        Environment variable value

    Raises:
        EnvironmentError: If variable is not set
    """
    value = os.environ.get(name)
    if value is None or value.strip() == "":
        raise EnvironmentError(f"Required environment variable '{name}' is not set")
    return value.strip()


def get_gemini_api_key(fallback: Optional[str] = None) -> Optional[str]:
    """
    Get Gemini API key from environment.

    Checks in order:
    1. GEMINI_API_KEY environment variable
    2. Fallback value if provided

    Args:
        fallback: Optional fallback API key

    Returns:
        API key string or None
    """
    # Try loading .env first
    load_env()

    key = get_env_str("GEMINI_API_KEY", "")
    if key:
        return key

    return fallback if fallback else None


# Auto-load .env when module is imported
load_env()
