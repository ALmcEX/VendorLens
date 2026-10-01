FROM ghcr.io/astral-sh/uv:0.12.21 AS uv
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH"

COPY --from=uv /uv /usr/local/bin/uv
WORKDIR /app

COPY pyproject.toml uv.lock .python-version ./
COPY apps/api/pyproject.toml apps/api/pyproject.toml
COPY apps/worker/pyproject.toml apps/worker/pyproject.toml
COPY packages/vendorlens-core/pyproject.toml packages/vendorlens-core/pyproject.toml
RUN uv sync --frozen --no-dev --no-install-workspace

COPY apps/api apps/api
COPY apps/worker apps/worker
COPY packages/vendorlens-core packages/vendorlens-core
RUN uv sync --frozen --no-dev --package vendorlens-api

RUN useradd --create-home --uid 10001 vendorlens
USER vendorlens
EXPOSE 8000
CMD ["python", "-m", "vendorlens_api"]
