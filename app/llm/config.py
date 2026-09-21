"""Configuration and factory for LLMClient.

Reads configuration from environment variables and constructs LLMClient instances.
"""

from dataclasses import dataclass
import os
from typing import Optional

from dotenv import load_dotenv

from app.llm.client import LLMClient

# Load variables from .env if present
load_dotenv()

DEFAULT_MODEL = "Qwen/Qwen3-8B"
DEFAULT_TIMEOUT = 60.0


@dataclass(frozen=True)
class LLMConfig:
    """Configuration settings for LLM client."""

    base_url: str
    model: str = DEFAULT_MODEL
    timeout: float = DEFAULT_TIMEOUT


def get_llm_config() -> LLMConfig:
    """Read LLM configuration from environment variables.

    Supported environment variables:
        AI_FITNESS_LLM_BASE_URL: Required URL of the LLM inference server.
        AI_FITNESS_LLM_MODEL: Model identifier (default: 'Qwen/Qwen3-8B').
        AI_FITNESS_LLM_TIMEOUT: Request timeout in seconds (default: 60.0).

    Returns:
        LLMConfig instance.

    Raises:
        ValueError: If AI_FITNESS_LLM_BASE_URL is missing or empty.
    """
    base_url = os.getenv("AI_FITNESS_LLM_BASE_URL", "").strip()
    if not base_url:
        raise ValueError(
            "AI_FITNESS_LLM_BASE_URL environment variable is required. "
            "Set it in your environment or .env file."
        )

    model = os.getenv("AI_FITNESS_LLM_MODEL", "").strip() or DEFAULT_MODEL

    timeout_raw = os.getenv("AI_FITNESS_LLM_TIMEOUT", "").strip()
    if timeout_raw:
        try:
            timeout = float(timeout_raw)
        except ValueError as exc:
            raise ValueError(
                f"AI_FITNESS_LLM_TIMEOUT must be a valid number, got: {timeout_raw!r}"
            ) from exc
    else:
        timeout = DEFAULT_TIMEOUT

    return LLMConfig(base_url=base_url, model=model, timeout=timeout)


def create_llm_client(config: Optional[LLMConfig] = None) -> LLMClient:
    """Factory function to construct an LLMClient.

    If *config* is not provided, it is loaded from environment variables via ``get_llm_config()``.

    Args:
        config: Optional pre-constructed LLMConfig.

    Returns:
        Configured LLMClient instance.
    """
    cfg = config or get_llm_config()
    return LLMClient(
        base_url=cfg.base_url,
        model=cfg.model,
        timeout=cfg.timeout,
    )
