"""
Asset model – the project's media library (Phase 5).

An Asset is any file a creator uploads to a Project for use across the
production pipeline: concept art, reference images, video plates, audio
scratch takes, font files, documents, and more. Assets are project-scoped and
private to the project owner.

- ``kind`` drives how the workspace renders the asset (thumbnail / player /
  icon) and which future tooling (storyboard, animation, audio) can consume it.
- ``tags`` are a lightweight, project-scoped vocabulary so creators can group
  assets (e.g. "kaia", "key art", "Chapter 3") without a heavy taxonomy.
- ``meta`` stores file-derived details (image dimensions, video duration)
  that are cheap to compute at upload time and useful to the UI and the AI.
"""

import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


def asset_upload_path(instance, filename):
    ext = filename.rsplit(".", 1)[-1].lower()
    return f"projects/{instance.project_id}/assets/{instance.id or 'new'}.{ext}"


class AssetTag(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(
        "projects.Project", on_delete=models.CASCADE, related_name="asset_tags"
    )
    name = models.CharField(max_length=50)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "asset_tags"
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["project", "name"], name="uniq_asset_tag_per_project"
            )
        ]

    def __str__(self):
        return self.name


class Asset(models.Model):
    class Kind(models.TextChoices):
        IMAGE = "image", "Image"
        VIDEO = "video", "Video"
        AUDIO = "audio", "Audio"
        DOCUMENT = "document", "Document"
        OTHER = "other", "Other"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(
        "projects.Project", on_delete=models.CASCADE, related_name="assets"
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="project_assets",
    )
    file = models.FileField(upload_to=asset_upload_path)
    kind = models.CharField(
        max_length=20, choices=Kind.choices, default=Kind.OTHER, db_index=True
    )
    title = models.CharField(max_length=200, blank=True)
    description = models.TextField(blank=True)
    tags = models.ManyToManyField(AssetTag, related_name="assets", blank=True)
    meta = models.JSONField(default=dict, blank=True)
    mime_type = models.CharField(max_length=120, blank=True)
    size = models.PositiveBigIntegerField(default=0)
    width = models.PositiveIntegerField(null=True, blank=True)
    height = models.PositiveIntegerField(null=True, blank=True)
    duration = models.FloatField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "assets"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["project", "kind", "-created_at"]),
            models.Index(fields=["project", "-created_at"]),
        ]

    def __str__(self):
        return self.title or self.file.name