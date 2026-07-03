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

# Claude CLI resolves its config/session dirs from HOME (Node os.homedir()).
# gosu does not rewrite HOME when dropping root->cronos, so set it explicitly;
# otherwise it stays /root and the unprivileged user can't create its
# ~/.claude/session-env dir (Bash tool) -> "Bash tool is broken".
ENV HOME=/home/cronos

WORKDIR /app

# NOTE: the build context is the repo root (see docker-compose.yml) so we can
# also ship the sibling packages/delivery-workflow package below. All COPY
# sources are therefore repo-root-relative (backend/…, packages/…).

# Python deps (copy pyproject first for layer cache)
COPY backend/pyproject.toml ./
RUN pip install --upgrade pip && pip install .

# App source
COPY backend/app ./app

# Portable delivery-workflow package (src layout: src/delivery_workflow with
# runner/lib/adapters + data assets). Installed as a real pip package (R10a) —
# `import delivery_workflow` works with zero path shims. The editable install
# keeps the shipped source tree as the single copy, so the canonical spec at
# packages/delivery-workflow/src/delivery_workflow/delivery.workflow.yaml
# stays resolvable by path too.
COPY packages/delivery-workflow ./packages/delivery-workflow
RUN pip install -e ./packages/delivery-workflow

# Ensure /app and /data are owned by cronos so the non-root process can
# write there. /data is a bind-mount at runtime; the entrypoint re-chowns
# it idempotently to handle host root-owned directories.
RUN mkdir -p /data && chown -R cronos:cronos /app /data

# Restore /home/cronos/.claude.json from backup on start (see script).
COPY backend/docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
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
