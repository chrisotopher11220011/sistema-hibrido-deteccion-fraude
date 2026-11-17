FROM python:3.12.12-slim-bookworm

# Imagen unica para `api` y `tareas`. Dependencias bloqueadas en uv.lock.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_NO_CACHE=1 \
    PATH=/opt/venv/bin:$PATH \
    HOME=/tmp \
    FRAUDE_RAIZ=/trabajo \
    PYTHON_IMAGEN=python:3.12.12-slim-bookworm

RUN pip install --no-cache-dir uv==0.11.32

WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN uv sync --frozen --no-dev --no-editable

WORKDIR /trabajo
EXPOSE 8000
CMD ["uvicorn", "fraude.api:app", "--host", "0.0.0.0", "--port", "8000"]
