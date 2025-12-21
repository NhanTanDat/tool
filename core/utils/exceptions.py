"""
core.utils.exceptions - Custom exception types

Replaces 139+ bare `except Exception:` handlers with specific exception types.
"""

from typing import Optional, Any


class ToolError(Exception):
    """
    Base exception for all tool errors.

    All custom exceptions inherit from this.
    """

    def __init__(self, message: str, details: Optional[Any] = None):
        super().__init__(message)
        self.message = message
        self.details = details

    def __str__(self) -> str:
        if self.details:
            return f"{self.message} | Details: {self.details}"
        return self.message


class ConfigError(ToolError):
    """
    Configuration-related errors.

    Examples:
        - Missing path.txt
        - Invalid config format
        - Missing required config value
    """
    pass


class ValidationError(ToolError):
    """
    Data validation errors.

    Examples:
        - Invalid JSON format
        - Missing required fields
        - Invalid data types
    """
    pass


class APIError(ToolError):
    """
    External API errors.

    Examples:
        - Gemini API failure
        - YouTube API rate limit
        - Network timeout
    """

    def __init__(
        self,
        message: str,
        api_name: str = "",
        status_code: Optional[int] = None,
        details: Optional[Any] = None
    ):
        super().__init__(message, details)
        self.api_name = api_name
        self.status_code = status_code

    def __str__(self) -> str:
        parts = [self.message]
        if self.api_name:
            parts.insert(0, f"[{self.api_name}]")
        if self.status_code:
            parts.append(f"(Status: {self.status_code})")
        if self.details:
            parts.append(f"| Details: {self.details}")
        return " ".join(parts)


class GeminiError(APIError):
    """
    Gemini AI API specific errors.
    """

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        details: Optional[Any] = None
    ):
        super().__init__(message, "Gemini", status_code, details)


class PremiereError(ToolError):
    """
    Adobe Premiere Pro related errors.

    Examples:
        - JSX script execution failure
        - COM interface error
        - Sequence not found
        - Track not available
    """

    def __init__(
        self,
        message: str,
        script_name: str = "",
        details: Optional[Any] = None
    ):
        super().__init__(message, details)
        self.script_name = script_name

    def __str__(self) -> str:
        parts = [self.message]
        if self.script_name:
            parts.insert(0, f"[{self.script_name}]")
        if self.details:
            parts.append(f"| Details: {self.details}")
        return " ".join(parts)


class DownloadError(ToolError):
    """
    Download-related errors.

    Examples:
        - Video not found
        - Rate limited
        - Network failure
        - Invalid URL
    """

    def __init__(
        self,
        message: str,
        url: str = "",
        details: Optional[Any] = None
    ):
        super().__init__(message, details)
        self.url = url

    def __str__(self) -> str:
        parts = [self.message]
        if self.url:
            parts.append(f"URL: {self.url[:50]}...")
        if self.details:
            parts.append(f"| Details: {self.details}")
        return " ".join(parts)


class WorkflowError(ToolError):
    """
    Workflow execution errors.

    Examples:
        - Step failed
        - Missing prerequisites
        - Invalid state
    """

    def __init__(
        self,
        message: str,
        step_name: str = "",
        details: Optional[Any] = None
    ):
        super().__init__(message, details)
        self.step_name = step_name

    def __str__(self) -> str:
        parts = [self.message]
        if self.step_name:
            parts.insert(0, f"[Step: {self.step_name}]")
        if self.details:
            parts.append(f"| Details: {self.details}")
        return " ".join(parts)


class FileOperationError(ToolError):
    """
    File system operation errors.

    Examples:
        - File not found
        - Permission denied
        - Disk full
    """

    def __init__(
        self,
        message: str,
        file_path: str = "",
        operation: str = "",
        details: Optional[Any] = None
    ):
        super().__init__(message, details)
        self.file_path = file_path
        self.operation = operation

    def __str__(self) -> str:
        parts = [self.message]
        if self.operation:
            parts.insert(0, f"[{self.operation}]")
        if self.file_path:
            parts.append(f"File: {self.file_path}")
        if self.details:
            parts.append(f"| Details: {self.details}")
        return " ".join(parts)
