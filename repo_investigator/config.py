from __future__ import annotations

import os
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field

class StateBusBackendType(str, Enum):
    IN_MEMORY = "in_memory"
    REDIS = "redis"
    NATS = "nats"

class SandboxProviderType(str, Enum):
    LOCAL = "local"
    DOCKER = "docker"
    FIRECRACKER_VSOCK = "firecracker_vsock"

class ModelProviderType(str, Enum):
    SIMULATED = "simulated"
    OPENAI = "openai"
    GEMINI = "gemini"
    ANTHROPIC = "anthropic"
    SGLANG = "sglang"
    VLLM = "vllm"
    GEMMA = "gemma"

class TelemetrySinkType(str, Enum):
    LOCAL = "local"
    OPENTELEMETRY = "opentelemetry"
    PROMETHEUS = "prometheus"

class FlowMindSettings(BaseModel):
    """
    Production Configuration Settings for FlowMind & A2A Bench Rotation Runtime.
    Automatically reads environment variables with safe production defaults.
    """
    # Distributed State Bus Settings
    state_bus_backend: StateBusBackendType = Field(
        default_factory=lambda: StateBusBackendType(os.getenv("FLOWMIND_STATE_BUS_BACKEND", "in_memory").lower())
    )
    redis_url: str = Field(
        default_factory=lambda: os.getenv("FLOWMIND_REDIS_URL", "redis://localhost:6379/0")
    )
    nats_url: str = Field(
        default_factory=lambda: os.getenv("FLOWMIND_NATS_URL", "nats://localhost:4222")
    )
    nats_bucket: str = Field(
        default_factory=lambda: os.getenv("FLOWMIND_NATS_BUCKET", "flowmind_state_bus")
    )

    # Sandbox Isolation Settings
    sandbox_provider: SandboxProviderType = Field(
        default_factory=lambda: SandboxProviderType(os.getenv("FLOWMIND_SANDBOX_PROVIDER", "local").lower())
    )
    docker_image: str = Field(
        default_factory=lambda: os.getenv("FLOWMIND_DOCKER_IMAGE", "python:3.12-slim")
    )
    vsock_port: int = Field(
        default_factory=lambda: int(os.getenv("FLOWMIND_VSOCK_PORT", "1024"))
    )

    # LLM Carriers & Cache Breakpoints
    default_model_provider: ModelProviderType = Field(
        default_factory=lambda: ModelProviderType(os.getenv("FLOWMIND_MODEL_PROVIDER", "simulated").lower())
    )
    openai_api_key: Optional[str] = Field(
        default_factory=lambda: os.getenv("OPENAI_API_KEY")
    )
    anthropic_api_key: Optional[str] = Field(
        default_factory=lambda: os.getenv("ANTHROPIC_API_KEY")
    )
    gemini_api_key: Optional[str] = Field(
        default_factory=lambda: os.getenv("GEMINI_API_KEY")
    )
    sglang_endpoint: Optional[str] = Field(
        default_factory=lambda: os.getenv("SGLANG_ENDPOINT", "http://localhost:30000/v1")
    )
    vllm_endpoint: Optional[str] = Field(
        default_factory=lambda: os.getenv("VLLM_ENDPOINT", "http://localhost:8000/v1")
    )
    gemma_model: str = Field(
        default_factory=lambda: os.getenv("GEMMA_MODEL", "gemma:3b")
    )
    gemma_endpoint: str = Field(
        default_factory=lambda: os.getenv("GEMMA_ENDPOINT", "http://localhost:11434/v1")
    )
    gemma_api_key: Optional[str] = Field(
        default_factory=lambda: os.getenv("GEMMA_API_KEY")
    )

    # Stint & Cache Parameters
    cache_ttl_seconds: int = Field(
        default_factory=lambda: int(os.getenv("FLOWMIND_CACHE_TTL_SECONDS", "3600"))
    )
    max_stint_steps: int = Field(
        default_factory=lambda: int(os.getenv("FLOWMIND_MAX_STINT_STEPS", "15"))
    )

    # Observability & Metrics
    telemetry_sink: TelemetrySinkType = Field(
        default_factory=lambda: TelemetrySinkType(os.getenv("FLOWMIND_TELEMETRY_SINK", "local").lower())
    )
    otel_endpoint: Optional[str] = Field(
        default_factory=lambda: os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
    )

_settings_instance: Optional[FlowMindSettings] = None

def get_settings(reload: bool = False) -> FlowMindSettings:
    """Returns the singleton application settings instance."""
    global _settings_instance
    if _settings_instance is None or reload:
        _settings_instance = FlowMindSettings()
    return _settings_instance

