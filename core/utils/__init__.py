"""
core.utils - Shared utilities for the entire codebase

This module provides:
- Path management (ROOT_DIR, setup_paths)
- Environment variable handling (load_env, get_env_*, get_gemini_api_key)
- Configuration management (ConfigManager)
- Custom exceptions (ToolError, ConfigError, etc.)
"""

from .paths import ROOT_DIR, CORE_DIR, DATA_DIR, setup_paths
from .env import (
    load_env,
    get_env_str,
    get_env_int,
    get_env_float,
    get_env_bool,
    get_gemini_api_key,
)
from .config import ConfigManager, get_config
from .exceptions import (
    ToolError,
    ConfigError,
    ValidationError,
    APIError,
    PremiereError,
    DownloadError,
)

__all__ = [
    # Paths
    "ROOT_DIR",
    "CORE_DIR",
    "DATA_DIR",
    "setup_paths",
    # Environment
    "load_env",
    "get_env_str",
    "get_env_int",
    "get_env_float",
    "get_env_bool",
    "get_gemini_api_key",
    # Config
    "ConfigManager",
    "get_config",
    # Exceptions
    "ToolError",
    "ConfigError",
    "ValidationError",
    "APIError",
    "PremiereError",
    "DownloadError",
]
