# Generated migration to add custom permissions for official content management.

from django.db import migrations


def add_manage_permission(apps, schema_editor):
    """
    Add 'manage_official_content' permission to content types.
    """
    ContentType = apps.get_model('contenttypes', 'ContentType')
    Permission = apps.get_model('auth', 'Permission')

    official_models = [
        'officialseries', 'officialseason', 'officialarc', 'officialstory',
        'officialchapter', 'officialscene', 'officialanimation',
        'officialepisode', 'officialanimationscene',
    ]

    for model_name in official_models:
        try:
            ct = ContentType.objects.get(app_label='official', model=model_name)
            Permission.objects.get_or_create(
                codename='manage_official_content',
                name='Can manage official content',
                content_type=ct,
            )
        except ContentType.DoesNotExist:
            pass


def remove_manage_permission(apps, schema_editor):
    Permission = apps.get_model('auth', 'Permission')
    Permission.objects.filter(codename='manage_official_content').delete()


class Migration(migrations.Migration):
    dependencies = [
        ('official', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(add_manage_permission, remove_manage_permission),
    ]