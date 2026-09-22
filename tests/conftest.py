import os
import sys

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

import django
django.setup()

import pytest
from django.conf import settings

pytest_plugins = ["pytest_django"]