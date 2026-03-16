FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc libpq-dev && \
    rm -rf /var/lib/apt/lists/*

# Reutiliza o mesmo pyproject.toml do core
COPY ../core/pyproject.toml .
RUN pip install --no-cache-dir -e "."

COPY ../core/ .

CMD ["celery", "-A", "config.celery", "worker", "-l", "info", "-Q", "default,recordings,analytics"]
