FROM python:3.13-slim
COPY --from=ghcr.io/astral-sh/uv:0.12.12 /uv /usr/local/bin/uv
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 UV_COMPILE_BYTECODE=1
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --extra dev --no-install-project
COPY . .
RUN uv sync --frozen --extra dev && useradd --create-home app && chown -R app:app /app
USER app
ENV PATH="/app/.venv/bin:$PATH" PREFECT_SERVER_ANALYTICS_ENABLED=false
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
