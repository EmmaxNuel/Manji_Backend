#!/bin/bash
set -e
python manage.py migrate --settings=config.settings.prod --noinput
python manage.py seed_official_content --settings=config.settings.prod || true
exec gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 3 --timeout 120 --access-logfile - --error-logfile -
