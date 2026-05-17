# Backend image: Python + Node (for @anthropic-ai/claude-code CLI)
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# System deps + Node + npm (Debian-shipped node 20 is fine for claude CLI).
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates curl git nodejs npm \
    && rm -rf /var/lib/apt/lists/*

# Claude Code CLI
RUN npm install -g @anthropic-ai/claude-code

WORKDIR /app

# Python deps (copy pyproject first for layer cache)
COPY pyproject.toml ./
RUN pip install --upgrade pip && pip install .

# App source
COPY app ./app

# Restore /root/.claude.json from backup on start (see script for rationale).
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
