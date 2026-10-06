FROM python:3.12-slim AS build

COPY --from=ghcr.io/astral-sh/uv:0.12.9 /uv /uvx /bin/
ENV UV_PYTHON_DOWNLOADS=0 UV_NO_DEV=1
WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN uv sync --locked --no-dev --no-editable --no-cache

FROM python:3.12-slim
WORKDIR /app
COPY --from=build /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1 FITADAPT_SOMATA_ONLY=1
USER 65532:65532
EXPOSE 8080
CMD ["sh", "-c", "exec uvicorn fitadapt.api.app:app --host 0.0.0.0 --port ${PORT:-8080} --workers 1 --limit-concurrency 20 --timeout-keep-alive 5 --no-access-log --log-level warning"]
