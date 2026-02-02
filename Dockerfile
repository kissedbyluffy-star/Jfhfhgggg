FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml README.md /app/
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir .

COPY trustora /app/trustora
COPY app /app/app
COPY services /app/services
COPY scripts /app/scripts
COPY alembic /app/alembic
COPY alembic.ini /app/alembic.ini

ENV PYTHONUNBUFFERED=1

CMD ["python", "-m", "app.main"]
