"""
core.logging_config - Unified logging configuration

Provides:
- Centralized logging setup
- Colored console output
- File logging with rotation
- GUI log integration
"""

import logging
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional, Callable, List
from logging.handlers import RotatingFileHandler

# Try to import colorama for colored output
try:
    from colorama import init as colorama_init, Fore, Style
    colorama_init()
    HAS_COLORAMA = True
except ImportError:
    HAS_COLORAMA = False
    Fore = None
    Style = None


# =====================================================================
# CONSTANTS
# =====================================================================

LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
LOG_FILE_MAX_SIZE = 10 * 1024 * 1024  # 10 MB
LOG_FILE_BACKUP_COUNT = 5

# Color mapping for log levels
LEVEL_COLORS = {
    "DEBUG": Fore.CYAN if HAS_COLORAMA else "",
    "INFO": Fore.GREEN if HAS_COLORAMA else "",
    "WARNING": Fore.YELLOW if HAS_COLORAMA else "",
    "ERROR": Fore.RED if HAS_COLORAMA else "",
    "CRITICAL": Fore.MAGENTA if HAS_COLORAMA else "",
}
RESET = Style.RESET_ALL if HAS_COLORAMA else ""


# =====================================================================
# COLORED FORMATTER
# =====================================================================

class ColoredFormatter(logging.Formatter):
    """Formatter that adds colors to log levels."""

    def format(self, record: logging.LogRecord) -> str:
        # Get color for level
        color = LEVEL_COLORS.get(record.levelname, "")
        reset = RESET

        # Format message
        formatted = super().format(record)

        # Add color if available
        if color:
            # Color only the level name
            formatted = formatted.replace(
                record.levelname,
                f"{color}{record.levelname}{reset}",
                1
            )

        return formatted


# =====================================================================
# GUI LOG HANDLER
# =====================================================================

class GUILogHandler(logging.Handler):
    """
    Log handler that sends logs to GUI callback.

    Usage:
        handler = GUILogHandler(gui.log)
        logging.getLogger().addHandler(handler)
    """

    def __init__(self, callback: Callable[[str], None]):
        super().__init__()
        self.callback = callback

    def emit(self, record: logging.LogRecord):
        try:
            msg = self.format(record)
            self.callback(msg)
        except Exception:
            self.handleError(record)


# =====================================================================
# SETUP FUNCTIONS
# =====================================================================

_initialized = False
_gui_handlers: List[GUILogHandler] = []


def setup_logging(
    level: str = "INFO",
    log_file: Optional[Path] = None,
    colored: bool = True,
    quiet_libs: bool = True,
) -> logging.Logger:
    """
    Setup logging configuration.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional path to log file
        colored: Enable colored console output
        quiet_libs: Reduce noise from third-party libraries

    Returns:
        Root logger instance
    """
    global _initialized

    # Get root logger
    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Remove existing handlers
    root.handlers.clear()

    # Console handler
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.DEBUG)

    if colored and HAS_COLORAMA:
        console.setFormatter(ColoredFormatter(LOG_FORMAT, LOG_DATE_FORMAT))
    else:
        console.setFormatter(logging.Formatter(LOG_FORMAT, LOG_DATE_FORMAT))

    root.addHandler(console)

    # File handler (optional)
    if log_file:
        log_file = Path(log_file)
        log_file.parent.mkdir(parents=True, exist_ok=True)

        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=LOG_FILE_MAX_SIZE,
            backupCount=LOG_FILE_BACKUP_COUNT,
            encoding="utf-8",
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(logging.Formatter(LOG_FORMAT, LOG_DATE_FORMAT))
        root.addHandler(file_handler)

    # Quiet noisy libraries
    if quiet_libs:
        noisy_loggers = [
            "httpx", "httpcore", "urllib3", "google", "grpc",
            "numba", "absl", "selenium", "PIL", "asyncio",
        ]
        for name in noisy_loggers:
            try:
                logging.getLogger(name).setLevel(logging.WARNING)
            except Exception:
                pass

    _initialized = True
    return root


def get_logger(name: str) -> logging.Logger:
    """
    Get or create a logger with the given name.

    Args:
        name: Logger name (usually __name__)

    Returns:
        Logger instance
    """
    if not _initialized:
        setup_logging()

    return logging.getLogger(name)


def add_gui_handler(callback: Callable[[str], None]) -> GUILogHandler:
    """
    Add a GUI log handler.

    Args:
        callback: Function to call with log messages

    Returns:
        The created handler
    """
    handler = GUILogHandler(callback)
    handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))

    root = logging.getLogger()
    root.addHandler(handler)

    _gui_handlers.append(handler)
    return handler


def remove_gui_handler(handler: GUILogHandler) -> None:
    """
    Remove a GUI log handler.

    Args:
        handler: Handler to remove
    """
    root = logging.getLogger()
    root.removeHandler(handler)

    if handler in _gui_handlers:
        _gui_handlers.remove(handler)


# =====================================================================
# CONVENIENCE FUNCTIONS
# =====================================================================

def log_exception(logger: logging.Logger, msg: str, exc: Exception) -> None:
    """
    Log an exception with full traceback.

    Args:
        logger: Logger instance
        msg: Error message
        exc: Exception instance
    """
    logger.error(f"{msg}: {exc}", exc_info=True)


def create_session_log_file() -> Path:
    """
    Create a new log file for this session.

    Returns:
        Path to log file
    """
    from core.utils.paths import ROOT_DIR

    logs_dir = ROOT_DIR / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return logs_dir / f"session_{timestamp}.log"
