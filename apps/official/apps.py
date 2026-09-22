from django.apps import AppConfig


class OfficialConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.official'
    verbose_name = 'Official Content'