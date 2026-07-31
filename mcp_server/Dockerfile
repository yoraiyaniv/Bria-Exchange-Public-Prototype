FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends pandoc && rm -rf /var/lib/apt/lists/*

RUN pip install uv

WORKDIR /app

# Install dependencies first (cached layer)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Copy source
COPY *.py ./
COPY corpus_matching/ ./corpus_matching/

ENV PATH="/app/.venv/bin:$PATH"
