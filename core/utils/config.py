"""
core.utils.config - Unified configuration management

Handles:
- path.txt (Python ↔ JSX communication)
- Project-specific config
- GUI config.json
"""

import json
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass, field

from .paths import DATA_DIR, ROOT_DIR


@dataclass
class ProjectConfig:
    """Configuration for a specific project."""

    project_path: str = ""
    data_folder: str = ""
    resource_folder: str = ""
    sequence_name: str = ""

    # Optional fields
    gemini_api_key: str = ""
    videos_per_keyword: int = 3
    max_segments: int = 10

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "project_path": self.project_path,
            "data_folder": self.data_folder,
            "resource_folder": self.resource_folder,
            "sequence_name": self.sequence_name,
            "gemini_api_key": self.gemini_api_key,
            "videos_per_keyword": self.videos_per_keyword,
            "max_segments": self.max_segments,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProjectConfig":
        """Create from dictionary."""
        return cls(
            project_path=data.get("project_path", ""),
            data_folder=data.get("data_folder", ""),
            resource_folder=data.get("resource_folder", ""),
            sequence_name=data.get("sequence_name", ""),
            gemini_api_key=data.get("gemini_api_key", ""),
            videos_per_keyword=data.get("videos_per_keyword", 3),
            max_segments=data.get("max_segments", 10),
        )


class ConfigManager:
    """
    Unified configuration manager.

    Handles reading/writing:
    - path.txt (for JSX scripts)
    - config.json (GUI preferences)
    - Project-specific settings
    """

    def __init__(self, data_dir: Optional[Path] = None):
        """
        Initialize ConfigManager.

        Args:
            data_dir: Data directory path (default: ROOT_DIR/data)
        """
        self.data_dir = Path(data_dir) if data_dir else DATA_DIR
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self._path_txt = self.data_dir / "path.txt"
        self._config_json = ROOT_DIR / "GUI" / "config.json"
        self._current_project_txt = self.data_dir / "_current_project.txt"

        self._cache: Dict[str, Any] = {}

    # ==================== path.txt (JSX communication) ====================

    def read_path_config(self) -> Dict[str, str]:
        """
        Read path.txt configuration file.

        Returns:
            Dictionary of key=value pairs

        Example:
            >>> cfg = manager.read_path_config()
            >>> cfg["data_folder"]
            '/path/to/data'
        """
        if not self._path_txt.exists():
            return {}

        config = {}
        try:
            with open(self._path_txt, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue

                    if "=" not in line:
                        continue

                    key, _, value = line.partition("=")
                    key = key.strip()
                    value = value.strip()

                    if key:
                        config[key] = value

        except Exception:
            return {}

        return config

    def write_path_config(self, config: Dict[str, str]) -> bool:
        """
        Write path.txt configuration file.

        Args:
            config: Dictionary of key=value pairs

        Returns:
            True if successful, False otherwise
        """
        try:
            lines = []
            for key, value in config.items():
                if key and value is not None:
                    lines.append(f"{key}={value}")

            with open(self._path_txt, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))

            return True
        except Exception:
            return False

    def get_path_value(self, key: str, default: str = "") -> str:
        """
        Get single value from path.txt.

        Args:
            key: Configuration key
            default: Default value if not found

        Returns:
            Value string or default
        """
        config = self.read_path_config()
        return config.get(key, default)

    def set_path_value(self, key: str, value: str) -> bool:
        """
        Set single value in path.txt.

        Args:
            key: Configuration key
            value: Value to set

        Returns:
            True if successful
        """
        config = self.read_path_config()
        config[key] = value
        return self.write_path_config(config)

    # ==================== GUI config.json ====================

    def read_gui_config(self) -> Dict[str, Any]:
        """Read GUI configuration from config.json."""
        if not self._config_json.exists():
            return {}

        try:
            with open(self._config_json, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def write_gui_config(self, config: Dict[str, Any]) -> bool:
        """Write GUI configuration to config.json."""
        try:
            self._config_json.parent.mkdir(parents=True, exist_ok=True)
            with open(self._config_json, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            return True
        except Exception:
            return False

    # ==================== Project management ====================

    def get_current_project(self) -> str:
        """Get current project path from _current_project.txt."""
        if not self._current_project_txt.exists():
            return ""
        try:
            return self._current_project_txt.read_text(encoding="utf-8").strip()
        except Exception:
            return ""

    def set_current_project(self, project_path: str) -> bool:
        """Set current project path."""
        try:
            self._current_project_txt.write_text(project_path, encoding="utf-8")
            return True
        except Exception:
            return False

    def get_project_config(self) -> ProjectConfig:
        """
        Get current project configuration from path.txt.

        Returns:
            ProjectConfig with values from path.txt
        """
        cfg = self.read_path_config()
        return ProjectConfig(
            project_path=cfg.get("project_path", ""),
            data_folder=cfg.get("data_folder", ""),
            resource_folder=cfg.get("resource_folder", ""),
            sequence_name=cfg.get("sequence_name", ""),
        )

    def set_project_config(self, config: ProjectConfig) -> bool:
        """
        Save project configuration to path.txt.

        Args:
            config: ProjectConfig to save

        Returns:
            True if successful
        """
        return self.write_path_config({
            "project_path": config.project_path,
            "data_folder": config.data_folder,
            "resource_folder": config.resource_folder,
            "sequence_name": config.sequence_name,
        })


# Global instance
_config_manager: Optional[ConfigManager] = None


def get_config() -> ConfigManager:
    """
    Get global ConfigManager instance.

    Returns:
        ConfigManager singleton
    """
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager
