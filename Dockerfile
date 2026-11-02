# ==============================================================================
# Multi-Stage Production Dockerfile for FlowMind & A2A Bench Rotation Runtime
# ==============================================================================

# Build Stage
FROM python:3.12-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY repo_investigator ./repo_investigator

RUN pip install --no-cache-dir --upgrade pip wheel build && \
    python -m build --wheel --outdir /build/dist

# Final Runtime Stage
FROM python:3.12-slim AS runner

LABEL maintainer="DeepMind Systems Architect <team@flowmind.ai>"
LABEL description="FlowMind Autonomous Multi-Agent Cognitive Architecture & A2A Bench Rotation Runtime"

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    FLOWMIND_SANDBOX_PROVIDER=local \
    FLOWMIND_STATE_BUS_BACKEND=in_memory

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Create unprivileged production user
RUN useradd -m -u 1000 -s /bin/bash flowmind && \
    chown -R flowmind:flowmind /app

COPY --from=builder /build/dist/*.whl /tmp/
RUN pip install --no-cache-dir /tmp/*.whl && rm -rf /tmp/*.whl

USER flowmind

ENTRYPOINT ["flowmind"]
CMD ["--help"]

