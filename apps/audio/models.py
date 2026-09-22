"""Audio & voice domain (Phase 9).

The VOICE STUDIO lets a creator record or upload voice takes, attach a voice
to a specific character, and place audio on the timeline of a scene (and, when
a storyboard panel exists, on a specific shot).
"""

import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q

from apps.characters.models import Character
from apps.projects.models import Project
from apps.scenes.models import Scene


class VoiceRecording(models.Model):
    """A single voice take / audio clip within a project."""

    class Kind(models.TextChoices):
        DIALOGUE = "dialogue", "Dialogue"
        VOICE_OVER = "voice_over", "Voice-over"
        MUSIC = "music", "Music"
        SFX = "sfx", "Sound effect"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name="voice_recordings"
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="voice_recordings",
    )

    title = models.CharField(max_length=200, db_index=True)
    kind = models.CharField(
        max_length=20, choices=Kind.choices, default=Kind.DIALOGUE
    )
    description = models.TextField(blank=True, default="")

    file = models.FileField(upload_to="audio/%Y/%m/")
    mime_type = models.CharField(max_length=120, blank=True, default="")
    size = models.BigIntegerField(default=0)
    duration = models.FloatField(default=0, help_text="Duration in seconds.")

    scene = models.ForeignKey(
        Scene,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="voice_recordings",
        help_text="Scene this clip is placed in (timeline attachment).",
    )
    character = models.ForeignKey(
        Character,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="voice_recordings",
        help_text="Character whose voice this clip represents.",
    )
    dialogue_line = models.CharField(
        max_length=500,
        blank=True,
        default="",
        help_text="The spoken line / dialogue text this clip reads.",
    )

    order = models.PositiveIntegerField(
        default=0, db_index=True, help_text="Timeline placement order within a scene."
    )
    start_seconds = models.FloatField(
        default=0, help_text="Timeline start offset in seconds."
    )

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "voice_recordings"
        ordering = ["order", "created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=("scene", "order"),
                name="uniq_voice_scene_order",
                condition=Q(scene__isnull=False),
            )
        ]
        indexes = [
            models.Index(fields=["project", "scene", "order"], name="voice_proj_scene_idx"),
            models.Index(fields=["project", "character"], name="voice_proj_char_idx"),
        ]

    def __str__(self):
        return self.title
