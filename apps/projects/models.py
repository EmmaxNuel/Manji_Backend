"""
Project model – the central creative container for Manji Studio.

A Project represents one complete creative work (a story, comic, manga, manhua
or animation). It owns the Story, Characters, Scenes, Storyboard, Assets,
Animation and Audio that will be built up over later phases.

Design decisions:
- ``project_type`` declares the kind of work (drives layout defaults).
- ``art_style`` is stored as a preset code (CharField with choices) plus a
  free-text ``art_style_description`` for the "custom" case. New styles can be
  added by editing the Python choices alone – no schema migration required.
- ``get_art_style_context()`` produces the prompt-friendly style string that the
  AI context-building service injects into every image-generation and
  character-consistency request.
- The optional 1:1 link to an existing Story lets the platform migrate existing
  stories into Projects without destroying the current story system.
"""

import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


def project_cover_upload_path(instance, filename):
    ext = filename.rsplit(".", 1)[-1]
    return f"projects/{instance.id}/cover.{ext}"


class Project(models.Model):
    class Type(models.TextChoices):
        STORY = "story", "Story"
        COMIC = "comic", "Comic"
        MANGA = "manga", "Manga"
        MANHUA = "manhua", "Manhua"
        ANIMATION = "animation", "Animation"

    class ArtStyle(models.TextChoices):
        ANIME = "anime", "Anime"
        MANGA_BW = "manga_bw", "Manga (black & white / screentone)"
        MANHUA = "manhua", "Manhua / Manhwa"
        WESTERN = "western_cartoon", "Western cartoon"
        SEMI_REALISTIC = "semi_realistic", "Semi-realistic"
        CUSTOM = "custom", "Custom"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        ACTIVE = "active", "Active"
        COMPLETED = "completed", "Completed"
        ARCHIVED = "archived", "Archived"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="projects",
    )
    title = models.CharField(max_length=200, db_index=True)
    description = models.TextField(max_length=2000, blank=True)
    cover = models.ImageField(
        upload_to=project_cover_upload_path, null=True, blank=True
    )

    # Project kind – drives layout defaults and AI behaviour.
    project_type = models.CharField(
        max_length=20,
        choices=Type.choices,
        default=Type.STORY,
        db_index=True,
    )

    # Art style – preset code + free-text description for custom styles.
    # Adding a new preset later is a Python-level change only (no DB migration).
    art_style = models.CharField(
        max_length=30,
        choices=ArtStyle.choices,
        default=ArtStyle.ANIME,
        db_index=True,
    )
    art_style_description = models.TextField(
        max_length=1000,
        blank=True,
        help_text="Free-text style description used when art_style is Custom.",
    )

    # Optional link to the platform's existing story system (migration bridge).
    story = models.OneToOneField(
        "stories.Story",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="project",
    )

    status = models.CharField(
        max_length=15,
        choices=Status.choices,
        default=Status.ACTIVE,
        db_index=True,
    )

    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "projects"
        ordering = ["-updated_at"]
        indexes = [
            models.Index(fields=["owner", "-updated_at"]),
            models.Index(fields=["project_type", "-updated_at"]),
        ]

    def __str__(self):
        return self.title

    # ------------------------------------------------------------------
    # Art style helpers (used by the AI context builder)
    # ------------------------------------------------------------------
    @classmethod
    def art_style_prompt(cls, art_style, description=""):
        """Return a prompt-friendly description for a stored art style."""
        prompts = {
            cls.ArtStyle.ANIME: "Anime art style",
            cls.ArtStyle.MANGA_BW: (
                "Manga art style: black and white with screentone shading"
            ),
            cls.ArtStyle.MANHUA: "Manhua / manhwa art style",
            cls.ArtStyle.WESTERN: "Western cartoon art style",
            cls.ArtStyle.SEMI_REALISTIC: "Semi-realistic art style",
        }
        if art_style == cls.ArtStyle.CUSTOM:
            return (description or "").strip() or "Custom art style"
        return prompts.get(art_style, "Anime art style")

    def get_art_style_label(self):
        """Human-readable label for the stored art style code."""
        return dict(self.ArtStyle.choices).get(self.art_style, self.art_style)

    def get_art_style_context(self):
        """Prompt-friendly style string for this project's AI requests."""
        return self.art_style_prompt(self.art_style, self.art_style_description)