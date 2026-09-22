"""
Scene model – the bridge between the written story and production.

A Scene belongs to a Project and optionally to a Chapter (scenes that are not
attached to a chapter are project-level planning beats). Scenes are the
junction where story, characters, storyboard, assets, voice and animation all
connect in later phases.

Design decisions:
- ``characters`` is stored as a JSON list of names in Phase 2 so the scene
  can reference characters before the Character system (Phase 3) exists. A
  later migration can replace it with a real ManyToMany field.
- ``story`` is denormalised onto the scene so the AI context builder can pull
  the right story without a second join.
"""

import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class Scene(models.Model):
    class CameraType(models.TextChoices):
        WIDE = "wide_shot", "Wide Shot"
        MEDIUM = "medium_shot", "Medium Shot"
        CLOSE_UP = "close_up", "Close-Up"
        EXTREME_CLOSE_UP = "extreme_close_up", "Extreme Close-Up"
        OVER_SHOULDER = "over_the_shoulder", "Over-the-Shoulder"
        POV = "pov", "POV"
        ESTABLISHING = "establishing_shot", "Establishing Shot"
        TRACKING = "tracking_shot", "Tracking Shot"
        AERIAL = "aerial", "Aerial"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.CASCADE,
        related_name="scenes",
    )
    chapter = models.ForeignKey(
        "chapters.Chapter",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="scenes",
    )
    story = models.ForeignKey(
        "stories.Story",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="scenes",
    )

    title = models.CharField(max_length=200, db_index=True)
    description = models.TextField(blank=True)
    location = models.CharField(max_length=200, blank=True)

    characters = models.JSONField(default=list, blank=True)
    cast = models.ManyToManyField(
        "characters.Character",
        related_name="scenes",
        blank=True,
    )

    dialogue = models.TextField(blank=True)
    narration = models.TextField(blank=True)

    camera_type = models.CharField(
        max_length=30,
        choices=CameraType.choices,
        blank=True,
        db_index=True,
    )
    camera_notes = models.TextField(blank=True)
    mood = models.CharField(max_length=100, blank=True)
    duration = models.PositiveIntegerField(
        null=True, blank=True, help_text="Approximate duration in seconds."
    )

    # Ordering within the chapter / project
    order = models.PositiveIntegerField(default=0, db_index=True)

    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "scenes"
        ordering = ["order", "created_at"]
        indexes = [
            models.Index(fields=["project", "order"]),
            models.Index(fields=["chapter", "order"]),
        ]

    def __str__(self):
        return self.title

def save(self, *args, **kwargs):
        if not self.order:
            last = (
                Scene.objects.filter(project=self.project)
                .aggregate(models.Max("order"))["order__max"]
            )
            self.order = (last or 0) + 1
        if self.chapter_id and not self.story_id:
            self.story = self.chapter.story
        super().save(*args, **kwargs)