from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.infrastructure.llm.llm_client import LLMClient
from app.infrastructure.llm.types import LLMProvider


def test_provider_parse_aliases():
    assert LLMProvider.parse("gpt") is LLMProvider.OPENAI
    assert LLMProvider.parse("chatgpt") is LLMProvider.OPENAI
    assert LLMProvider.parse("claude") is LLMProvider.ANTHROPIC
    assert LLMProvider.parse("gemini") is LLMProvider.GEMINI


def test_provider_parse_unknown_raises():
    with pytest.raises(ValueError, match="Unknown LLM provider"):
        LLMProvider.parse("unknown-vendor")


def test_client_default_provider_is_gemini():
    client = LLMClient(provider="gemini", api_key="test-key")
    assert client.provider is LLMProvider.GEMINI


def test_client_from_ai_config_openai():
    client = LLMClient.from_ai_config(
        {"provider": "openai", "model": "gpt-4o", "temperature": 0.1}
    )
    assert client.provider is LLMProvider.OPENAI
    assert client.model == "gpt-4o"
    assert client.temperature == 0.1


@patch("app.infrastructure.llm.providers.gemini.generate_content")
def test_gemini_chat_success(mock_generate):
    mock_generate.return_value = {
        "text": "Hello report",
        "finish_reason": "STOP",
        "raw": {"usageMetadata": {"promptTokenCount": 10, "candidatesTokenCount": 20}},
    }
    client = LLMClient(provider="gemini", api_key="secret")
    result = client.chat(system_prompt="sys", user_message="user")
    assert result.text == "Hello report"
    assert result.provider is LLMProvider.GEMINI
    assert result.tokens_in == 10
    assert result.tokens_out == 20


def test_gemini_missing_key_raises():
    client = LLMClient(provider="gemini", api_key="")
    with pytest.raises(ValueError, match="gemini_api_key_missing"):
        client.chat(system_prompt="s", user_message="u")


@patch("app.infrastructure.llm.providers.openai.httpx.Client")
def test_openai_chat_success(mock_client_cls):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [{"message": {"content": "GPT output"}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 5, "completion_tokens": 7},
    }
    mock_client = MagicMock()
    mock_client.__enter__.return_value = mock_client
    mock_client.post.return_value = mock_response
    mock_client_cls.return_value = mock_client

    client = LLMClient(provider="openai", api_key="sk-test", model="gpt-4o-mini")
    result = client.chat(system_prompt="sys", user_message="user")
    assert result.text == "GPT output"
    assert result.provider is LLMProvider.OPENAI


def test_anthropic_not_implemented_yet():
    client = LLMClient(provider="anthropic", api_key="k")
    with pytest.raises(NotImplementedError, match="Anthropic provider not wired"):
        client.chat(system_prompt="s", user_message="u")


@patch("app.infrastructure.llm.providers.gemini.generate_content")
@patch("app.infrastructure.llm.providers.openai.httpx.Client")
def test_fallback_to_openai_when_gemini_fails(mock_openai_client_cls, mock_gemini):
    mock_gemini.side_effect = RuntimeError("gemini down")

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [{"message": {"content": "fallback ok"}, "finish_reason": "stop"}],
        "usage": {},
    }
    mock_client = MagicMock()
    mock_client.__enter__.return_value = mock_client
    mock_client.post.return_value = mock_response
    mock_openai_client_cls.return_value = mock_client

    client = LLMClient(
        provider="gemini",
        api_key="g-key",
        fallback_provider="openai",
    )
    # Inject openai key on fallback adapter path — reuse api_key for primary only;
    # fallback builds fresh OpenAIAdapter; patch env for key.
    import os

    os.environ["OPENAI_API_KEY"] = "sk-fallback"
    result = client.chat(system_prompt="s", user_message="u")
    assert result.text == "fallback ok"
    assert result.provider is LLMProvider.OPENAI
