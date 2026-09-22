"""
Official Content Models for MANJI.

This app provides the platform's official/canonical content system:
- OfficialSeries: Top-level grouping (e.g., "MANJI")
- OfficialSeason: Season within a series
- OfficialArc: Story arc within a season
- OfficialStory: The main narrative work (reuses Story model with official flag)
- OfficialChapter: Chapter within an official story
- OfficialScene: Scene within an official chapter
- OfficialAnimation: Animation series
- OfficialEpisode: Episode within an animation
- OfficialAnimationScene: Scene within an episode

Relationships between story and animation are explicit so users can navigate
between reading and watching.
"""

import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.text import slugify

from apps.stories.models import Story
from apps.chapters.models import Chapter
from apps.scenes.models import Scene
from apps.characters.models import Character
from apps.animation.models import AnimationProject, Episode


def official_cover_upload_path(instance, filename):
    ext = filename.rsplit(".", 1)[-1].lower()
    return f"official/{instance._meta.model_name}/{instance.id}/cover.{ext}"


def official_thumbnail_upload_path(instance, filename):
    ext = filename.rsplit(".", 1)[-1].lower()
    return f"official/{instance._meta.model_name}/{instance.id}/thumb.{ext}"


def official_video_upload_path(instance, filename):
    ext = filename.rsplit(".", 1)[-1].lower()
    return f"official/episode/{instance.id}/video.{ext}"


class OfficialSeries(models.Model):
    """
    Top-level official content grouping (e.g., "MANJI").
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200, unique=True)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    description = models.TextField(max_length=3000, blank=True)
    cover = models.ImageField(upload_to=official_cover_upload_path, null=True, blank=True)
    tagline = models.CharField(max_length=300, blank=True)
    order = models.PositiveIntegerField(default=0, db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "official_series"
        ordering = ["order", "title"]
        indexes = [
            models.Index(fields=["is_active", "order"]),
        ]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)


class OfficialSeason(models.Model):
    """
    A season within an official series.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    series = models.ForeignKey(OfficialSeries, on_delete=models.CASCADE, related_name="seasons")
    season_number = models.PositiveIntegerField(db_index=True)
    title = models.CharField(max_length=200, blank=True)
    description = models.TextField(max_length=2000, blank=True)
    cover = models.ImageField(upload_to=official_cover_upload_path, null=True, blank=True)
    order = models.PositiveIntegerField(default=0, db_index=True)
    is_published = models.BooleanField(default=False, db_index=True)
    published_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "official_seasons"
        ordering = ["series", "season_number"]
        constraints = [
            models.UniqueConstraint(fields=["series", "season_number"], name="unique_season_per_series"),
        ]
        indexes = [
            models.Index(fields=["series", "is_published", "season_number"]),
        ]

    def __str__(self):
        return f"{self.series.title} — Season {self.season_number}"

    def save(self, *args, **kwargs):
        if not self.order:
            self.order = self.season_number
        if self.is_published and not self.published_at:
            self.published_at = timezone.now()
        super().save(*args, **kwargs)


class OfficialArc(models.Model):
    """
    A story arc within a season (e.g., "The World Beyond").
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    season = models.ForeignKey(OfficialSeason, on_delete=models.CASCADE, related_name="arcs")
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, blank=True)
    description = models.TextField(max_length=3000, blank=True)
    cover = models.ImageField(upload_to=official_cover_upload_path, null=True, blank=True)
    order = models.PositiveIntegerField(default=0, db_index=True)
    is_published = models.BooleanField(default=False, db_index=True)
    published_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "official_arcs"
        ordering = ["season", "order"]
        indexes = [
            models.Index(fields=["season", "is_published", "order"]),
        ]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        if self.is_published and not self.published_at:
            self.published_at = timezone.now()
        super().save(*args, **kwargs)


class OfficialStory(models.Model):
    """
    An official story - links to the platform's Story model but adds
    official-specific metadata and relationships.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    arc = models.ForeignKey(OfficialArc, on_delete=models.CASCADE, related_name="official_stories")
    story = models.OneToOneField(
        Story,
        on_delete=models.CASCADE,
        related_name="official_story_meta",
        help_text="The underlying Story record (read-only for normal users)."
    )
    order = models.PositiveIntegerField(default=0, db_index=True)
    is_canon = models.BooleanField(default=True, help_text="Part of main continuity")
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "official_stories"
        ordering = ["arc", "order"]
        indexes = [
            models.Index(fields=["arc", "order"]),
        ]

    def __str__(self):
        return f"{self.arc.title} — {self.story.title}"

    @property
    def title(self):
        return self.story.title

    @property
    def slug(self):
        return self.story.slug

    @property
    def description(self):
        return self.story.description

    @property
    def cover(self):
        return self.story.cover


class OfficialChapter(models.Model):
    """
    An official chapter - links to the platform's Chapter model with official metadata.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    official_story = models.ForeignKey(OfficialStory, on_delete=models.CASCADE, related_name="official_chapters")
    chapter = models.OneToOneField(
        Chapter,
        on_delete=models.CASCADE,
        related_name="official_chapter_meta",
    )
    animation_episode = models.ForeignKey(
        "OfficialEpisode",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="linked_official_chapters",
        help_text="Corresponding animation episode, if adapted."
    )
    order = models.PositiveIntegerField(default=0, db_index=True)
    is_published = models.BooleanField(default=False, db_index=True)
    published_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "official_chapters"
        ordering = ["official_story", "order"]
        indexes = [
            models.Index(fields=["official_story", "is_published", "order"]),
        ]

    def __str__(self):
        return f"{self.official_story} — Ch. {self.chapter.chapter_number}"

    @property
    def title(self):
        return self.chapter.title

    @property
    def chapter_number(self):
        return self.chapter.chapter_number

    def save(self, *args, **kwargs):
        if not self.order:
            self.order = self.chapter.chapter_number
        if self.is_published and not self.published_at:
            self.published_at = timezone.now()
        super().save(*args, **kwargs)


class OfficialScene(models.Model):
    """
    An official scene - links to the platform's Scene model with official metadata.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    official_chapter = models.ForeignKey(OfficialChapter, on_delete=models.CASCADE, related_name="official_scenes")
    scene = models.OneToOneField(
        Scene,
        on_delete=models.CASCADE,
        related_name="official_scene_meta",
    )
    animation_scene = models.ForeignKey(
        "OfficialAnimationScene",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="linked_official_scenes",
        help_text="Corresponding animation scene, if adapted."
    )
    order = models.PositiveIntegerField(default=0, db_index=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "official_scenes"
        ordering = ["official_chapter", "order"]
        indexes = [
            models.Index(fields=["official_chapter", "order"]),
        ]

    def __str__(self):
        return f"{self.official_chapter} — Scene {self.order}"

    @property
    def title(self):
        return self.scene.title


class OfficialAnimation(models.Model):
    """
    An official animation series (e.g., "MANJI: The World Beyond").
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    series = models.ForeignKey(OfficialSeries, on_delete=models.CASCADE, related_name="animations")
    arc = models.ForeignKey(OfficialArc, on_delete=models.SET_NULL, null=True, blank=True, related_name="animations")
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    description = models.TextField(max_length=3000, blank=True)
    cover = models.ImageField(upload_to=official_cover_upload_path, null=True, blank=True)
    trailer_url = models.URLField(max_length=500, blank=True)
    order = models.PositiveIntegerField(default=0, db_index=True)
    is_published = models.BooleanField(default=False, db_index=True)
    published_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "official_animations"
        ordering = ["order", "title"]
        indexes = [
            models.Index(fields=["is_published", "order"]),
        ]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        if self.is_published and not self.published_at:
            self.published_at = timezone.now()
        super().save(*args, **kwargs)


class OfficialEpisode(models.Model):
    """
    An official animation episode.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    animation = models.ForeignKey(OfficialAnimation, on_delete=models.CASCADE, related_name="episodes")
    episode_number = models.PositiveIntegerField(db_index=True)
    title = models.CharField(max_length=200)
    description = models.TextField(max_length=2000, blank=True)
    thumbnail = models.ImageField(upload_to=official_thumbnail_upload_path, null=True, blank=True)
    video_file = models.FileField(upload_to=official_video_upload_path, null=True, blank=True)
    video_url = models.URLField(max_length=500, blank=True, help_text="External video URL (YouTube, CDN, etc.)")
    duration = models.PositiveIntegerField(null=True, blank=True, help_text="Duration in seconds")
    order = models.PositiveIntegerField(default=0, db_index=True)
    is_published = models.BooleanField(default=False, db_index=True)
    published_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "official_episodes"
        ordering = ["animation", "episode_number"]
        constraints = [
            models.UniqueConstraint(fields=["animation", "episode_number"], name="unique_episode_per_animation"),
        ]
        indexes = [
            models.Index(fields=["animation", "is_published", "episode_number"]),
        ]

    def __str__(self):
        return f"{self.animation.title} — Ep. {self.episode_number}: {self.title}"

    def save(self, *args, **kwargs):
        if not self.order:
            self.order = self.episode_number
        if self.is_published and not self.published_at:
            self.published_at = timezone.now()
        super().save(*args, **kwargs)


class OfficialAnimationScene(models.Model):
    """
    A scene within an official animation episode.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    episode = models.ForeignKey(OfficialEpisode, on_delete=models.CASCADE, related_name="animation_scenes")
    title = models.CharField(max_length=200)
    description = models.TextField(max_length=2000, blank=True)
    start_time = models.PositiveIntegerField(help_text="Start time in seconds from episode start")
    end_time = models.PositiveIntegerField(null=True, blank=True, help_text="End time in seconds")
    thumbnail = models.ImageField(upload_to=official_thumbnail_upload_path, null=True, blank=True)
    order = models.PositiveIntegerField(default=0, db_index=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "official_animation_scenes"
        ordering = ["episode", "order"]
        indexes = [
            models.Index(fields=["episode", "order"]),
        ]

    def __str__(self):
        return f"{self.episode} — Scene {self.order}: {self.title}"


class OfficialContentProgress(models.Model):
    """
    Track user progress through official content (both story and animation).
    """
    class ContentType(models.TextChoices):
        CHAPTER = "chapter", "Official Chapter"
        EPISODE = "episode", "Official Episode"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="official_progress")
    content_type = models.CharField(max_length=10, choices=ContentType.choices, db_index=True)
    content_id = models.UUIDField(db_index=True)  # OfficialChapter.id or OfficialEpisode.id

    progress_percentage = models.PositiveIntegerField(default=0)
    current_position = models.PositiveIntegerField(default=0, help_text="Seconds for video, scroll for text")
    completed = models.BooleanField(default=False, db_index=True)
    last_accessed_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "official_content_progress"
        unique_together = ("user", "content_type", "content_id")
        indexes = [
            models.Index(fields=["user", "content_type", "completed"]),
        ]

    def __str__(self):
        return f"{self.user.username} — {self.content_type} {self.content_id} ({self.progress_percentage}%)"


class OfficialBookmark(models.Model):
    """
    User bookmarks for official content.
    """
    class ContentType(models.TextChoices):
        CHAPTER = "chapter", "Official Chapter"
        EPISODE = "episode", "Official Episode"
        ARC = "arc", "Official Arc"
        STORY = "story", "Official Story"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="official_bookmarks")
    content_type = models.CharField(max_length=10, choices=ContentType.choices, db_index=True)
    content_id = models.UUIDField(db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "official_bookmarks"
        unique_together = ("user", "content_type", "content_id")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "content_type"]),
        ]

    def __str__(self):
        return f"{self.user.username} bookmarked {self.content_type} {self.content_id}"


class OfficialContentView(models.Model):
    """
    Analytics for official content views.
    """
    class ContentType(models.TextChoices):
        SERIES = "series", "Official Series"
        SEASON = "season", "Official Season"
        ARC = "arc", "Official Arc"
        STORY = "story", "Official Story"
        CHAPTER = "chapter", "Official Chapter"
        ANIMATION = "animation", "Official Animation"
        EPISODE = "episode", "Official Episode"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    content_type = models.CharField(max_length=15, choices=ContentType.choices, db_index=True)
    content_id = models.UUIDField(db_index=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField(blank=True)
    viewed_at = models.DateTimeField(auto_now_add=True)
    time_spent = models.PositiveIntegerField(default=0, help_text="Seconds spent viewing")

    class Meta:
        db_table = "official_content_views"
        ordering = ["-viewed_at"]
        indexes = [
            models.Index(fields=["content_type", "content_id", "-viewed_at"]),
            models.Index(fields=["user", "-viewed_at"]),
        ]

    def __str__(self):
        return f"View: {self.content_type} {self.content_id}"