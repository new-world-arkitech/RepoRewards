import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from repo_investigator.llm.base import (
    AnthropicCarrierEngine,
    SGLangRadixCarrierEngine,
    GemmaCarrierEngine,
    SimulatedCognitiveEngine,
    get_default_engine,
)
from repo_investigator.config import ModelProviderType, FlowMindSettings

def test_anthropic_carrier_initialization():
    engine = AnthropicCarrierEngine(api_key="mock-key", model="claude-3-5-sonnet-20241022")
    assert engine.api_key == "mock-key"
    assert engine.model == "claude-3-5-sonnet-20241022"

def test_sglang_carrier_initialization():
    engine = SGLangRadixCarrierEngine(endpoint="http://localhost:30000/v1")
    assert engine.endpoint == "http://localhost:30000/v1"

def test_simulated_cognitive_engine():
    engine = SimulatedCognitiveEngine()
    resp = engine.reason("Analyze architecture", response_format="json")
    assert "ANALYZED" in resp

def test_gemma_carrier_initialization():
    engine = GemmaCarrierEngine(
        model="gemma:3b",
        endpoint="http://localhost:11434/v1",
        api_key="test-key",
    )
    assert engine.model == "gemma:3b"
    assert engine.endpoint == "http://localhost:11434/v1"
    assert engine.api_key == "test-key"

def test_gemma_carrier_mock_openai_compatible():
    engine = GemmaCarrierEngine(model="gemma:3b", endpoint="http://localhost:11434/v1")

    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps({
        "choices": [{"message": {"content": "Gemma 3B synthesized response"}}]
    }).encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_resp):
        res = engine.reason("Design an invariant", system_prompt="Strict typing required")
        assert res == "Gemma 3B synthesized response"

def test_gemma_carrier_mock_ollama_native():
    engine = GemmaCarrierEngine(model="gemma:3b", endpoint="http://localhost:11434/api/chat")

    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps({
        "message": {"content": "Ollama Gemma 3B response"}
    }).encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_resp):
        res = engine.reason("Optimize call graph")
        assert res == "Ollama Gemma 3B response"

def test_gemma_carrier_mock_google_generative_api():
    engine = GemmaCarrierEngine(
        model="gemma-3-3b-it",
        endpoint="https://generativelanguage.googleapis.com",
        api_key="fake-gemini-key",
    )

    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps({
        "candidates": [{"content": {"parts": [{"text": "Google AI Studio Gemma 3B response"}]}}]
    }).encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_resp):
        res = engine.reason("Synthesize adapter protocol", system_prompt="Preserve INV-001")
        assert res == "Google AI Studio Gemma 3B response"

def test_gemma_config_integration(monkeypatch):
    monkeypatch.setenv("FLOWMIND_MODEL_PROVIDER", "gemma")
    monkeypatch.setenv("GEMMA_MODEL", "gemma:3b")
    monkeypatch.setenv("GEMMA_ENDPOINT", "http://localhost:11434/v1")

    engine = get_default_engine()
    assert isinstance(engine, GemmaCarrierEngine)
    assert engine.model == "gemma:3b"
    assert engine.endpoint == "http://localhost:11434/v1"

if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-vv"]))
