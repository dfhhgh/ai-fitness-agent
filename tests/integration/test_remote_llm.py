"""Optional remote integration test for the remote LLM inference server.

This test is marked with @pytest.mark.integration and is excluded from
normal offline test runs by default.

To run this test explicitly:
    pytest -m integration
or:
    pytest tests/integration/test_remote_llm.py -m integration

It skips gracefully if AI_FITNESS_LLM_BASE_URL is not configured in the environment.
If configured, it connects to the real endpoint and verifies Arabic text generation.
"""

import os
import re
import pytest
from dotenv import load_dotenv

from app.llm.client import LLMClient
from app.llm.config import DEFAULT_MODEL, DEFAULT_TIMEOUT

# Load variables from .env if present
load_dotenv()


@pytest.mark.integration
def test_remote_llm_arabic_response():
    """Verify live connectivity and Arabic text response from remote LLM server."""
    base_url = os.getenv("AI_FITNESS_LLM_BASE_URL", "").strip()
    if not base_url:
        pytest.skip("AI_FITNESS_LLM_BASE_URL is not set — skipping remote integration test.")

    model = os.getenv("AI_FITNESS_LLM_MODEL", "").strip() or DEFAULT_MODEL
    timeout_raw = os.getenv("AI_FITNESS_LLM_TIMEOUT", "").strip()
    timeout = float(timeout_raw) if timeout_raw else DEFAULT_TIMEOUT

    # Construct the real LLMClient
    client = LLMClient(base_url=base_url, model=model, timeout=timeout)

    messages = [
        {"role": "system", "content": "Return exactly the Arabic phrase: أهلاً بيك"},
        {"role": "user", "content": "قول العبارة المطلوبة."},
    ]

    # HTTP request succeeds (if server fails, this raises LLMConnectionError / LLMResponseError)
    response_text = client.chat(messages, max_tokens=100)

    # 1. Returned content is non-empty string
    assert isinstance(response_text, str)
    assert len(response_text.strip()) > 0

    # 2. Arabic text is returned (check for Arabic Unicode block \u0600-\u06FF)
    arabic_pattern = re.compile(r"[\u0600-\u06FF]")
    assert arabic_pattern.search(response_text) is not None, (
        f"Expected Arabic characters in response, got: {response_text!r}"
    )

    # 3. No Unicode replacement corruption occurs
    assert "\ufffd" not in response_text, "Response contains Unicode replacement character (corruption)"
