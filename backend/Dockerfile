# Backend image: Python + Node (for @anthropic-ai/claude-code CLI)
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# System deps + Node + npm (Debian-shipped node 20 is fine for claude CLI).
# gosu: used in docker-entrypoint.sh to drop from root to cronos after
# runtime chowns (cap_drop:[ALL] + no-new-privileges blocks setuid AFTER
# the boundary; the initial root→cronos drop in the entrypoint is allowed).
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates curl git gosu nodejs npm \
    && rm -rf /var/lib/apt/lists/*

# Claude Code CLI
RUN npm install -g @anthropic-ai/claude-code \
    && chmod -R o+rX /usr/local/lib/node_modules/@anthropic-ai/claude-code \
    && chmod o+rx /usr/local/bin/claude

# Non-root user for the application process.
# UID 1001 avoids collision with common host UIDs (0=root, 1000=typical dev).
# The final Dockerfile USER stays root so docker-entrypoint.sh can chown
# /data at runtime before dropping to cronos via gosu.
RUN useradd -m -u 1001 -s /bin/sh cronos

WORKDIR /app

# Python deps (copy pyproject first for layer cache)
COPY pyproject.toml ./
RUN pip install --upgrade pip && pip install .

# App source
COPY app ./app

# Ensure /app and /data are owned by cronos so the non-root process can
# write there. /data is a bind-mount at runtime; the entrypoint re-chowns
# it idempotently to handle host root-owned directories.
RUN mkdir -p /data && chown -R cronos:cronos /app /data

# Restore /home/cronos/.claude.json from backup on start (see script).
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

EXPOSE 8000

# Build-time metadata — values injected by upgrade.sh via --build-arg.
# Defaults are empty so local dev and CI work without these args.
ARG BUILD_COMMIT
ARG BUILD_TIME
ARG BUILD_REPO_URL
ENV BUILD_COMMIT=$BUILD_COMMIT \
    BUILD_TIME=$BUILD_TIME \
    BUILD_REPO_URL=$BUILD_REPO_URL

ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
