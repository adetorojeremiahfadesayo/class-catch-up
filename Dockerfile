FROM oven/bun:1.4 AS web-build
WORKDIR /build/apps/web
COPY apps/web/package.json apps/web/bun.lock ./
RUN bun install --frozen-lockfile
COPY apps/web/ ./
RUN bun run build

FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim AS runtime
WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    APP_ENVIRONMENT=production \
    DEMO_MODE=true \
    COOKIE_SECURE=true \
    DATABASE_URL=sqlite+pysqlite:////data/class-catch-up.db \
    MATERIAL_STORAGE_ROOT=/data/materials-private

COPY services/api/pyproject.toml services/api/uv.lock /app/services/api/
RUN cd /app/services/api && uv sync --frozen --no-dev

COPY services/api/ /app/services/api/
COPY fixtures/ /app/fixtures/
COPY --from=web-build /build/apps/web/dist /app/apps/web/dist
COPY deploy/start.sh /app/deploy/start.sh

RUN mkdir -p /data/materials-private && chmod +x /app/deploy/start.sh

EXPOSE 8080
CMD ["/app/deploy/start.sh"]
