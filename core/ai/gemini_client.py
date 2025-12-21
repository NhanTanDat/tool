"""
core.ai.gemini_client - Unified Gemini AI Client

Replaces duplicate Gemini API initialization in:
- genmini_analyze.py
- video_scene_matcher.py

Features:
- Singleton client instance
- Automatic API key handling
- Request retry logic
- Rate limiting
- Error handling
"""

import logging
import time
from pathlib import Path
from typing import Optional, Any, Dict, List, Union
from dataclasses import dataclass

# Import utils
import sys
_THIS_DIR = Path(__file__).parent.resolve()
_CORE_DIR = _THIS_DIR.parent
_ROOT_DIR = _CORE_DIR.parent
if str(_ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(_ROOT_DIR))

from core.utils.env import get_gemini_api_key, get_env_str, get_env_int, get_env_float, get_env_bool
from core.utils.exceptions import GeminiError

# Try to import google.generativeai
try:
    import google.generativeai as genai
    from google.generativeai.types import HarmCategory, HarmBlockThreshold
    HAS_GEMINI = True
except ImportError:
    genai = None
    HarmCategory = None
    HarmBlockThreshold = None
    HAS_GEMINI = False

LOG = logging.getLogger("gemini_client")


@dataclass
class GeminiConfig:
    """Configuration for Gemini client."""

    model_name: str = "gemini-2.0-flash"
    temperature: float = 0.7
    max_output_tokens: int = 8192
    timeout_seconds: int = 60

    # Retry settings
    max_retries: int = 3
    retry_delay: float = 1.0
    retry_backoff: float = 2.0

    # Rate limiting
    requests_per_minute: int = 60
    min_request_interval: float = 0.1

    @classmethod
    def from_env(cls) -> "GeminiConfig":
        """Create config from environment variables."""
        return cls(
            model_name=get_env_str("GEMINI_MODEL", "gemini-2.0-flash"),
            temperature=get_env_float("GEMINI_TEMPERATURE", 0.7),
            max_output_tokens=get_env_int("GEMINI_MAX_TOKENS", 8192),
            timeout_seconds=get_env_int("GEMINI_TIMEOUT", 60),
            max_retries=get_env_int("GEMINI_MAX_RETRIES", 3),
            retry_delay=get_env_float("GEMINI_RETRY_DELAY", 1.0),
            requests_per_minute=get_env_int("GEMINI_RPM", 60),
        )


class GeminiClient:
    """
    Unified Gemini AI client with retry logic and rate limiting.

    Usage:
        client = GeminiClient()  # Uses GEMINI_API_KEY from environment
        result = client.generate("What is 2+2?")
        print(result)

        # Or with custom config
        client = GeminiClient(api_key="your-key", model="gemini-pro")
    """

    _instance: Optional["GeminiClient"] = None

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        config: Optional[GeminiConfig] = None,
    ):
        """
        Initialize Gemini client.

        Args:
            api_key: Gemini API key (default: from environment)
            model: Model name (default: from config)
            config: Full configuration object
        """
        if not HAS_GEMINI:
            raise GeminiError(
                "google-generativeai package not installed. "
                "Run: pip install google-generativeai"
            )

        self.config = config or GeminiConfig.from_env()

        # Get API key
        self.api_key = api_key or get_gemini_api_key()
        if not self.api_key:
            raise GeminiError(
                "GEMINI_API_KEY not found. "
                "Set it in .env file or pass to constructor."
            )

        # Configure genai
        genai.configure(api_key=self.api_key)

        # Model name
        self.model_name = model or self.config.model_name

        # Create model instance
        self.model = genai.GenerativeModel(
            model_name=self.model_name,
            generation_config={
                "temperature": self.config.temperature,
                "max_output_tokens": self.config.max_output_tokens,
            },
        )

        # Rate limiting state
        self._last_request_time = 0.0
        self._request_count = 0

        LOG.info(f"GeminiClient initialized with model: {self.model_name}")

    @classmethod
    def get_instance(cls, **kwargs) -> "GeminiClient":
        """
        Get singleton instance of GeminiClient.

        Args:
            **kwargs: Passed to constructor if creating new instance

        Returns:
            GeminiClient instance
        """
        if cls._instance is None:
            cls._instance = cls(**kwargs)
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset singleton instance (useful for testing)."""
        cls._instance = None

    def _wait_for_rate_limit(self) -> None:
        """Wait if needed to respect rate limits."""
        now = time.time()
        elapsed = now - self._last_request_time

        min_interval = self.config.min_request_interval
        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)

        self._last_request_time = time.time()

    def generate(
        self,
        prompt: str,
        safety_settings: Optional[Dict] = None,
        stream: bool = False,
    ) -> str:
        """
        Generate text from prompt.

        Args:
            prompt: Input prompt text
            safety_settings: Optional safety settings override
            stream: Whether to stream response

        Returns:
            Generated text string

        Raises:
            GeminiError: On API failure after retries
        """
        if not prompt or not prompt.strip():
            raise GeminiError("Empty prompt provided")

        # Default safety settings (permissive for video analysis)
        if safety_settings is None and HarmCategory and HarmBlockThreshold:
            safety_settings = {
                HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
            }

        last_error = None
        delay = self.config.retry_delay

        for attempt in range(self.config.max_retries):
            try:
                self._wait_for_rate_limit()

                response = self.model.generate_content(
                    prompt,
                    safety_settings=safety_settings,
                    stream=stream,
                )

                if stream:
                    # For streaming, return generator
                    return response

                # Extract text from response
                if hasattr(response, "text"):
                    return response.text
                elif hasattr(response, "parts") and response.parts:
                    return "".join(part.text for part in response.parts if hasattr(part, "text"))
                else:
                    raise GeminiError("Empty response from Gemini API")

            except Exception as e:
                last_error = e
                error_str = str(e).lower()

                # Check if retryable
                if any(x in error_str for x in ["rate", "quota", "resource", "timeout", "503", "429"]):
                    LOG.warning(f"Gemini API error (attempt {attempt + 1}): {e}")
                    time.sleep(delay)
                    delay *= self.config.retry_backoff
                    continue
                else:
                    # Non-retryable error
                    raise GeminiError(f"Gemini API error: {e}", details=str(e))

        raise GeminiError(
            f"Gemini API failed after {self.config.max_retries} retries",
            details=str(last_error)
        )

    def generate_with_video(
        self,
        prompt: str,
        video_path: str,
        safety_settings: Optional[Dict] = None,
    ) -> str:
        """
        Generate text from prompt with video input.

        Args:
            prompt: Input prompt text
            video_path: Path to video file
            safety_settings: Optional safety settings override

        Returns:
            Generated text string

        Raises:
            GeminiError: On API failure
        """
        video_path = Path(video_path)
        if not video_path.exists():
            raise GeminiError(f"Video file not found: {video_path}")

        # Default safety settings
        if safety_settings is None and HarmCategory and HarmBlockThreshold:
            safety_settings = {
                HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
            }

        last_error = None
        delay = self.config.retry_delay

        for attempt in range(self.config.max_retries):
            try:
                self._wait_for_rate_limit()

                # Upload video file
                LOG.info(f"Uploading video: {video_path.name}")
                video_file = genai.upload_file(str(video_path))

                # Wait for processing
                while video_file.state.name == "PROCESSING":
                    LOG.debug("Waiting for video processing...")
                    time.sleep(2)
                    video_file = genai.get_file(video_file.name)

                if video_file.state.name != "ACTIVE":
                    raise GeminiError(f"Video processing failed: {video_file.state.name}")

                # Generate with video
                response = self.model.generate_content(
                    [video_file, prompt],
                    safety_settings=safety_settings,
                )

                # Clean up uploaded file
                try:
                    genai.delete_file(video_file.name)
                except Exception:
                    pass

                # Extract text
                if hasattr(response, "text"):
                    return response.text
                elif hasattr(response, "parts") and response.parts:
                    return "".join(part.text for part in response.parts if hasattr(part, "text"))
                else:
                    raise GeminiError("Empty response from Gemini API")

            except Exception as e:
                last_error = e
                error_str = str(e).lower()

                if any(x in error_str for x in ["rate", "quota", "resource", "timeout", "503", "429"]):
                    LOG.warning(f"Gemini API error (attempt {attempt + 1}): {e}")
                    time.sleep(delay)
                    delay *= self.config.retry_backoff
                    continue
                else:
                    raise GeminiError(f"Gemini API error: {e}", details=str(e))

        raise GeminiError(
            f"Gemini API failed after {self.config.max_retries} retries",
            details=str(last_error)
        )

    def is_available(self) -> bool:
        """Check if Gemini API is available."""
        try:
            self.generate("Hello")
            return True
        except Exception:
            return False


# Convenience function
def get_gemini_client(**kwargs) -> GeminiClient:
    """
    Get or create Gemini client instance.

    Args:
        **kwargs: Passed to GeminiClient constructor

    Returns:
        GeminiClient singleton instance
    """
    return GeminiClient.get_instance(**kwargs)
