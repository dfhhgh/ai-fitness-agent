"""Tests for app.llm.config — environment variable loading and factory function."""

import os
from unittest.mock import patch
import pytest

from app.llm.client import LLMClient
from app.llm.config import (
    DEFAULT_MODEL,
    DEFAULT_TIMEOUT,
    LLMConfig,
    create_llm_client,
    get_llm_config,
)


class TestLLMConfig:
    """Tests for get_llm_config()."""

    def test_missing_base_url_raises_value_error(self):
        """Missing AI_FITNESS_LLM_BASE_URL raises a clear ValueError."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="AI_FITNESS_LLM_BASE_URL environment variable is required"):
                get_llm_config()

    def test_empty_base_url_raises_value_error(self):
        """Empty or whitespace-only AI_FITNESS_LLM_BASE_URL raises ValueError."""
        with patch.dict(os.environ, {"AI_FITNESS_LLM_BASE_URL": "   "}, clear=True):
            with pytest.raises(ValueError, match="AI_FITNESS_LLM_BASE_URL environment variable is required"):
                get_llm_config()

    def test_default_model_and_timeout(self):
        """When only base_url is provided, sensible defaults are applied."""
        env = {"AI_FITNESS_LLM_BASE_URL": "https://example-llm.ngrok-free.dev"}
        with patch.dict(os.environ, env, clear=True):
            config = get_llm_config()

        assert config.base_url == "https://example-llm.ngrok-free.dev"
        assert config.model == DEFAULT_MODEL
        assert config.timeout == DEFAULT_TIMEOUT

    def test_explicit_env_vars_parsed(self):
        """Explicit model and timeout values are parsed correctly."""
        env = {
            "AI_FITNESS_LLM_BASE_URL": "http://127.0.0.1:8080",
            "AI_FITNESS_LLM_MODEL": "Custom/Model-7B",
            "AI_FITNESS_LLM_TIMEOUT": "45.5",
        }
        with patch.dict(os.environ, env, clear=True):
            config = get_llm_config()

        assert config.base_url == "http://127.0.0.1:8080"
        assert config.model == "Custom/Model-7B"
        assert config.timeout == 45.5

    def test_invalid_timeout_raises_value_error(self):
        """Non-numeric timeout raises a clear ValueError."""
        env = {
            "AI_FITNESS_LLM_BASE_URL": "http://127.0.0.1:8080",
            "AI_FITNESS_LLM_TIMEOUT": "not_a_number",
        }
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(ValueError, match="AI_FITNESS_LLM_TIMEOUT must be a valid number"):
                get_llm_config()


class TestCreateLLMClient:
    """Tests for create_llm_client() factory."""

    def test_create_from_env(self):
        """Factory creates LLMClient using environment variables."""
        env = {
            "AI_FITNESS_LLM_BASE_URL": "https://api.example.com",
            "AI_FITNESS_LLM_MODEL": "TestModel",
            "AI_FITNESS_LLM_TIMEOUT": "30",
        }
        with patch.dict(os.environ, env, clear=True):
            client = create_llm_client()

        assert isinstance(client, LLMClient)
        assert client.base_url == "https://api.example.com"
        assert client.model == "TestModel"

    def test_create_from_explicit_config(self):
        """Factory creates LLMClient using passed LLMConfig."""
        config = LLMConfig(
            base_url="https://direct.example.com",
            model="ExplicitModel",
            timeout=15.0,
        )
        client = create_llm_client(config=config)

        assert isinstance(client, LLMClient)
        assert client.base_url == "https://direct.example.com"
        assert client.model == "ExplicitModel"
