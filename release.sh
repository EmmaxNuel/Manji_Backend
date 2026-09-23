#!/bin/bash
set -e
python manage.py migrate --settings=config.settings.prod --noinput
python manage.py seed_official_content --settings=config.settings.prod || true
python manage.py collectstatic --noinput --settings=config.settings.prod || true
