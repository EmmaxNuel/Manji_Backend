"""
StoryboardPanel model – the visual breakdown of a scene (Phase 6).

A StoryboardPanel represents one shot of a Scene: a thumbnail, the camera
setup (shot size, movement), its on-screen dialogue/narration and the timing.
Panels belong to a Project through their Scene, and are ordered within the
scene. Later phases (animation, audio) read panels as their shot list.

Design decisions:
- Panels attach to a Scene, not directly to a project, so the board follows
  the scene structure already built in Phase 2.
- ``image`` is the panel thumbnail; the creator can also reference a library
  Asset (Phase 5) via ``asset`` for concept plates or backgrounds.
- Camera/shot values are fixed choices so the animation and storyboard
  tooling can rely on a stable vocabulary.
"""

import uuid

from django.db import models
from django.utils import timezone


def panel_image_upload_path(instance, filename):
    ext = filename.rsplit(".", 1)[-1].lower()
    return f"projects/{instance.scene.project_id}/storyboard/{instance.id or 'new'}.{ext}"


class StoryboardPanel(models.Model):
    # The camera-type vocabulary is shared with the Scene.camera_type field
    # (SCENE FORM): same option list on both so AI context-building and the
    # animation tooling rely on one consistent set of values. Tracking Shot and
    # Aerial are part of the standard vocabulary; Two-shot is kept for
    # backward compatibility with panels created before the vocabulary aligned.
    class Shot(models.TextChoices):
        WIDE = "wide", "Wide Shot"
        MEDIUM = "medium", "Medium Shot"
        CLOSE_UP = "close_up", "Close-Up"
        EXTREME_CLOSE_UP = "extreme_close_up", "Extreme Close-Up"
        OVER_SHOULDER = "over_shoulder", "Over-the-Shoulder"
        POV = "pov", "POV"
        ESTABLISHING = "establishing", "Establishing Shot"
        TRACKING = "tracking", "Tracking Shot"
        AERIAL = "aerial", "Aerial"
        TWO_SHOT = "two_shot", "Two-shot"

    class CameraMovement(models.TextChoices):
        STATIC = "static", "Static"
        PAN = "pan", "Pan"
        TILT = "tilt", "Tilt"
        TRACKING = "tracking", "Tracking"
        ZOOM = "zoom", "Zoom"
        DOLLY = "dolly", "Dolly"
        HANDHELD = "handheld", "Handheld"

    class AspectRatio(models.TextChoices):
        SQUARE = "1:1", "Square (1:1)"
        STANDARD = "16:9", "Standard (16:9)"
        TALL = "9:16", "Tall (9:16)"
        MANGA = "portrait", "Manga page (portrait)"
        WIDE = "21:9", "Ultrawide (21:9)"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    scene = models.ForeignKey(
        "scenes.Scene", on_delete=models.CASCADE, related_name="panels"
    )
    asset = models.ForeignKey(
        "assets.Asset",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="storyboard_panels",
        help_text="Optional library asset to use as the plate/background.",
    )

    image = models.ImageField(
        upload_to=panel_image_upload_path, null=True, blank=True
    )
    shot = models.CharField(
        max_length=30, choices=Shot.choices, default=Shot.MEDIUM
    )
    camera_movement = models.CharField(
        max_length=20, choices=CameraMovement.choices, default=CameraMovement.STATIC
    )
    aspect_ratio = models.CharField(
        max_length=10, choices=AspectRatio.choices, default=AspectRatio.STANDARD
    )
    duration = models.PositiveIntegerField(
        null=True, blank=True, help_text="Approximate shot length in seconds."
    )
    dialogue = models.TextField(blank=True)
    narration = models.TextField(blank=True)
    notes = models.TextField(blank=True)

    order = models.PositiveIntegerField(default=0, db_index=True)

    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "storyboard_panels"
        ordering = ["order", "created_at"]
        indexes = [
            models.Index(fields=["scene", "order"]),
        ]

    def __str__(self):
        return f"{self.scene.title} — shot {self.order}"