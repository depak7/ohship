FROM python:3.12-slim

WORKDIR /app

RUN pip install uv

COPY pyproject.toml uv.lock* ./
COPY src ./src
COPY alembic.ini ./
COPY alembic ./alembic

RUN uv sync

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app/src"

EXPOSE 8000

CMD ["uvicorn", "ohship.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
