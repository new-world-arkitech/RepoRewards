import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from repo_investigator.config import (
    FlowMindSettings,
    StateBusBackendType,
    SandboxProviderType,
    ModelProviderType,
    get_settings,
)

def test_config_defaults():
    settings = FlowMindSettings()
    assert settings.state_bus_backend == StateBusBackendType.IN_MEMORY
    assert settings.sandbox_provider == SandboxProviderType.LOCAL
    assert settings.cache_ttl_seconds == 3600
    assert settings.max_stint_steps == 15
    assert settings.gemma_model == "gemma:3b"
    assert settings.gemma_endpoint == "http://localhost:11434/v1"

def test_config_env_overrides(monkeypatch):
    monkeypatch.setenv("FLOWMIND_STATE_BUS_BACKEND", "redis")
    monkeypatch.setenv("FLOWMIND_SANDBOX_PROVIDER", "docker")
    monkeypatch.setenv("FLOWMIND_MAX_STINT_STEPS", "20")
    monkeypatch.setenv("FLOWMIND_MODEL_PROVIDER", "gemma")
    monkeypatch.setenv("GEMMA_MODEL", "gemma-3-3b-it")
    monkeypatch.setenv("GEMMA_ENDPOINT", "http://localhost:8000/v1")

    settings = FlowMindSettings()
    assert settings.state_bus_backend == StateBusBackendType.REDIS
    assert settings.sandbox_provider == SandboxProviderType.DOCKER
    assert settings.max_stint_steps == 20
    assert settings.default_model_provider == ModelProviderType.GEMMA
    assert settings.gemma_model == "gemma-3-3b-it"
    assert settings.gemma_endpoint == "http://localhost:8000/v1"

if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-vv"]))

