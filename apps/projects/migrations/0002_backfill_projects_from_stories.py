"""
Data migration: back-fill a Project for every existing Story.

This bridges the existing story system into the new Project-centric model.
Each existing Story gets one owning Project (project_type mapped from the
story's content_type, art_style defaulted to anime). Existing stories continue
to work exactly as before – the Project is a wrapper container.
"""

from django.db import migrations

_TYPE_MAP = {
    "novel": "story",
    "short_story": "story",
    "web_novel": "story",
    "comic": "comic",
    "manga": "manga",
    "manhua": "manhua",
}


def backfill_projects(apps, schema_editor):
    Story = apps.get_model("stories", "Story")
    Project = apps.get_model("projects", "Project")
    for story in Story.objects.all().iterator():
        Project.objects.get_or_create(
            story=story,
            defaults={
                "owner": story.author,
                "title": story.title,
                "description": story.description,
                "project_type": _TYPE_MAP.get(story.content_type, "story"),
                "art_style": "anime",
                "status": "active",
                "created_at": story.created_at,
                "updated_at": story.updated_at,
            },
        )


def reverse_backfill(apps, schema_editor):
    Project = apps.get_model("projects", "Project")
    Project.objects.filter(story__isnull=False).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("projects", "0001_initial"),
        ("stories", "0002_story_is_official"),
    ]

    operations = [
        migrations.RunPython(backfill_projects, reverse_backfill),
    ]