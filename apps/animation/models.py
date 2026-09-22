"""
Animation models – the frame-based 2D animation studio (Phase 8).

An AnimationProject belongs to a Project and links back to its source Scene
(optional), so playback and export always have story context available. It owns
a timeline of frames and a stack of layers:

    Animation Project
        ├── Timeline (Frames, ordered by index)
        │       └── Layers (drawings keyed by layer)
        └── Layers (background / character / effects)

Design decisions:
- Frames are shared across the timeline (a flipbook), not per-layer. Each
  AnimationFrame stores a JSON ``layers`` dict keyed by layer UUID whose values
  hold the drawing strokes for that layer at that frame. This keeps the
  timeline trivially indexable while still letting every layer animate
  independently.
- Drawing is stored as opaque JSON (a stroke list: tool, color, size, points).
  The browser draws locally on a canvas and only the finished frame data is
  sent to Django on explicit save — individual brush movements never hit the
  API (see PERFORMANCE).
- ``fps`` drives playback speed; ``width``/``height`` define the canvas size so
  the editor renders at a stable aspect ratio regardless of the container.
"""

import uuid

from django.db import models
from django.utils import timezone


class AnimationProject(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(
        "projects.Project", on_delete=models.CASCADE, related_name="animations"
    )
    scene = models.ForeignKey(
        "scenes.Scene",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="animations",
        help_text="The source scene this animation is built from.",
    )
    title = models.CharField(max_length=200, db_index=True)
    fps = models.PositiveSmallIntegerField(
        default=12, help_text="Playback frame rate (frames per second)."
    )
    width = models.PositiveIntegerField(default=960)
    height = models.PositiveIntegerField(default=540)

    order = models.PositiveIntegerField(default=0, db_index=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "animation_projects"
        ordering = ["order", "created_at"]
        indexes = [
            models.Index(fields=["project", "order"]),
        ]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.order:
            last = (
                AnimationProject.objects.filter(project=self.project)
                .aggregate(models.Max("order"))["order__max"]
            )
            self.order = (last or 0) + 1
        super().save(*args, **kwargs)


class AnimationLayer(models.Model):
    class Kind(models.TextChoices):
        BACKGROUND = "background", "Background"
        CHARACTER = "character", "Character"
        EFFECTS = "effects", "Effects"
        SCENE = "scene", "Scene"
        CAMERA = "camera", "Camera"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    animation = models.ForeignKey(
        AnimationProject, on_delete=models.CASCADE, related_name="layers"
    )
    name = models.CharField(max_length=100)
    kind = models.CharField(
        max_length=20, choices=Kind.choices, default=Kind.CHARACTER
    )
    visible = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0, db_index=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "animation_layers"
        ordering = ["order", "created_at"]
        indexes = [
            models.Index(fields=["animation", "order"]),
        ]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.order:
            last = (
                AnimationLayer.objects.filter(animation=self.animation)
                .aggregate(models.Max("order"))["order__max"]
            )
            self.order = (last or 0) + 1
        super().save(*args, **kwargs)


class AnimationFrame(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    animation = models.ForeignKey(
        AnimationProject, on_delete=models.CASCADE, related_name="frames"
    )
    index = models.PositiveIntegerField(db_index=True)
    # {"<layer_id>": {"strokes": [{tool, color, size, points}, ...]}}
    layers = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "animation_frames"
        ordering = ["index"]
        constraints = [
            models.UniqueConstraint(
                fields=["animation", "index"], name="uniq_animation_frame_index"
            )
        ]

    def __str__(self):
        return f"{self.animation.title} — frame {self.index}"

    def scrub_layer(self, layer_id):
        """Remove a layer's drawing data from this frame (on layer delete)."""
        key = str(layer_id)
        if key in (self.layers or {}):
            self.layers.pop(key)
            self.save(update_fields=["layers", "updated_at"])


class Episode(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"
        ARCHIVED = "archived", "Archived"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    animation = models.ForeignKey(
        AnimationProject, on_delete=models.CASCADE, related_name="episodes"
    )
    episode_number = models.PositiveIntegerField(db_index=True)
    title = models.CharField(max_length=200, db_index=True)
    description = models.TextField(max_length=2000, blank=True)
    thumbnail = models.ImageField(upload_to="episodes/", null=True, blank=True)
    duration = models.PositiveIntegerField(
        null=True, blank=True, help_text="Approximate duration in seconds."
    )
    status = models.CharField(
        max_length=15,
        choices=Status.choices,
        default=Status.DRAFT,
        db_index=True,
    )
    published_at = models.DateTimeField(null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "animation_episodes"
        ordering = ["episode_number"]
        constraints = [
            models.UniqueConstraint(
                fields=["animation", "episode_number"],
                name="uniq_episode_animation_number",
            )
        ]

    def __str__(self):
        return f"{self.animation.title} — Ep. {self.episode_number}: {self.title}"

    def save(self, *args, **kwargs):
        if self.status == self.Status.PUBLISHED and not self.published_at:
            self.published_at = timezone.now()
        super().save(*args, **kwargs)