FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    build-essential \
    gettext \
    wget \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements/ ./requirements/
RUN pip install --upgrade pip && pip install -r requirements/prod.txt

COPY . .

RUN DJANGO_SETTINGS_MODULE=config.settings.dev SECRET_KEY=build-only-key DEBUG=False python manage.py collectstatic --noinput || true

RUN chmod +x /app/start.sh /app/release.sh

EXPOSE 8000

CMD ["/app/start.sh"]