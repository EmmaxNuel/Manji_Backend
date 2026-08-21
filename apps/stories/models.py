"""
Story, Genre, and Tag models for Manji with AI integration.

Architecture decisions:
- Story is the main content model supporting novels, comics, manga, etc.
- Genre and Tag use many-to-many relationships for flexible categorization
- ContentType enum distinguishes between text-based and image-based content
- AI integration for generating covers and chapter images
- Status tracking for publication workflow
- Slug field for SEO-friendly URLs
- Denormalized counts for performance
"""

import uuid
from django.contrib.auth import get_user_model
from django.db import models
from django.utils import timezone
from django.utils.text import slugify

User = get_user_model()


def story_cover_upload_path(instance, filename):
    """Upload path for story covers."""
    ext = filename.rsplit(".", 1)[-1]
    return f"covers/{instance.id}.{ext}"


def ai_generated_image_path(instance, filename):
    """Upload path for AI-generated images."""
    ext = filename.rsplit(".", 1)[-1]
    return f"ai-generated/{instance.story.id}/{instance.id}.{ext}"


class Genre(models.Model):
    """
    Story genres like Fantasy, Romance, Action, etc.
    """
    name = models.CharField(max_length=50, unique=True)
    slug = models.SlugField(max_length=50, unique=True, blank=True)
    description = models.TextField(max_length=500, blank=True)
    color = models.CharField(max_length=7, default="#6b7280")  # Hex color for UI
    created_at = models.DateTimeField(auto_now_add=True)
    
    # Denormalized counts
    stories_count = models.PositiveIntegerField(default=0, db_index=True)

    class Meta:
        db_table = "genres"
        ordering = ["name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class Tag(models.Model):
    """
    Flexible tagging system for stories.
    """
    name = models.CharField(max_length=30, unique=True)
    slug = models.SlugField(max_length=30, unique=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    # Denormalized counts
    stories_count = models.PositiveIntegerField(default=0, db_index=True)

    class Meta:
        db_table = "tags"
        ordering = ["name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class Story(models.Model):
    """
    Main story model supporting all content types with AI integration.
    """
    
    class ContentType(models.TextChoices):
        NOVEL = "novel", "Novel"
        SHORT_STORY = "short_story", "Short Story"
        WEB_NOVEL = "web_novel", "Web Novel"
        COMIC = "comic", "Comic"
        MANGA = "manga", "Manga"
        MANHUA = "manhua", "Manhua"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"
        COMPLETED = "completed", "Completed"
        HIATUS = "hiatus", "On Hiatus"
        DISCONTINUED = "discontinued", "Discontinued"

    class Language(models.TextChoices):
        EN = "en", "English"
        ES = "es", "Spanish"
        FR = "fr", "French"
        DE = "de", "German"
        JA = "ja", "Japanese"
        KO = "ko", "Korean"
        ZH = "zh", "Chinese"
        PT = "pt", "Portuguese"
        RU = "ru", "Russian"
        AR = "ar", "Arabic"

    # Core fields
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200, db_index=True)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    description = models.TextField(max_length=2000)
    cover = models.ImageField(upload_to=story_cover_upload_path, null=True, blank=True)
    
    # AI-generated cover options
    ai_cover_prompt = models.TextField(max_length=1000, blank=True, 
                                      help_text="Prompt for AI cover generation")
    ai_cover_style = models.CharField(max_length=50, blank=True, 
                                     help_text="AI art style (realistic, anime, comic, etc.)")
    
    # Content classification
    content_type = models.CharField(
        max_length=20,
        choices=ContentType.choices,
        db_index=True
    )
    language = models.CharField(
        max_length=5,
        choices=Language.choices,
        default=Language.EN,
        db_index=True
    )
    
    # Relationships
    author = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="authored_stories"
    )
    genres = models.ManyToManyField(Genre, related_name="stories", blank=True)
    tags = models.ManyToManyField(Tag, related_name="stories", blank=True)
    
    # Status and publication
    status = models.CharField(
        max_length=15,
        choices=Status.choices,
        default=Status.DRAFT,
        db_index=True
    )
    is_featured = models.BooleanField(default=False, db_index=True)
    is_premium = models.BooleanField(default=False, db_index=True)
    is_official = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Official Manji platform story (e.g. the MANJI welcome story).",
    )
    
    # AI settings
    ai_assistance_enabled = models.BooleanField(default=True, 
                                               help_text="Allow AI to help with content generation")
    
    # Timestamps
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    published_at = models.DateTimeField(null=True, blank=True, db_index=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    # Denormalized counts and metrics
    chapters_count = models.PositiveIntegerField(default=0, db_index=True)
    views_count = models.PositiveIntegerField(default=0, db_index=True)
    likes_count = models.PositiveIntegerField(default=0, db_index=True)
    bookmarks_count = models.PositiveIntegerField(default=0, db_index=True)
    followers_count = models.PositiveIntegerField(default=0, db_index=True)
    comments_count = models.PositiveIntegerField(default=0, db_index=True)
    
    # Reading metrics
    avg_reading_time = models.PositiveIntegerField(default=0)  # minutes
    word_count = models.PositiveIntegerField(default=0, db_index=True)
    
    class Meta:
        db_table = "stories"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["author", "-created_at"]),
            models.Index(fields=["content_type", "-published_at"]),
            models.Index(fields=["status", "-views_count"]),
            models.Index(fields=["-likes_count"]),
            models.Index(fields=["-followers_count"]),
        ]

    def __str__(self):
        return f"{self.title} by {self.author.username}"

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.title)
            slug = base_slug
            counter = 1
            while Story.objects.filter(slug=slug).exclude(id=self.id).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        
        # Set published_at when first published
        if self.status == self.Status.PUBLISHED and not self.published_at:
            self.published_at = timezone.now()
        
        # Set completed_at when marked as completed
        if self.status == self.Status.COMPLETED and not self.completed_at:
            self.completed_at = timezone.now()
        
        super().save(*args, **kwargs)

    @property
    def is_published(self):
        return self.status in (self.Status.PUBLISHED, self.Status.COMPLETED)

    @property
    def is_text_based(self):
        return self.content_type in (
            self.ContentType.NOVEL,
            self.ContentType.SHORT_STORY,
            self.ContentType.WEB_NOVEL
        )

    @property
    def is_image_based(self):
        return self.content_type in (
            self.ContentType.COMIC,
            self.ContentType.MANGA,
            self.ContentType.MANHUA
        )

    @property
    def reading_time_display(self):
        """Human readable reading time."""
        if self.avg_reading_time < 60:
            return f"{self.avg_reading_time} min"
        hours = self.avg_reading_time // 60
        minutes = self.avg_reading_time % 60
        return f"{hours}h {minutes}m" if minutes else f"{hours}h"

    def get_absolute_url(self):
        return f"/stories/{self.slug}/"


class AIGeneratedImage(models.Model):
    """
    Track AI-generated images for stories and chapters.
    """
    class ImageType(models.TextChoices):
        COVER = "cover", "Story Cover"
        CHAPTER_ILLUSTRATION = "chapter", "Chapter Illustration"
        CHARACTER_ART = "character", "Character Art"
        SCENE_ART = "scene", "Scene Art"

    class AIProvider(models.TextChoices):
        DALLE = "dalle", "DALL-E"
        MIDJOURNEY = "midjourney", "Midjourney"
        STABLE_DIFFUSION = "stable_diffusion", "Stable Diffusion"
        LEONARDO = "leonardo", "Leonardo AI"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    story = models.ForeignKey("stories.Story", on_delete=models.CASCADE, related_name="ai_images")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="generated_images")
    
    # AI generation details
    prompt = models.TextField(max_length=2000)
    negative_prompt = models.TextField(max_length=1000, blank=True)
    style = models.CharField(max_length=50, blank=True)
    ai_provider = models.CharField(max_length=20, choices=AIProvider.choices, default=AIProvider.STABLE_DIFFUSION)
    
    # Image details
    image_type = models.CharField(max_length=20, choices=ImageType.choices)
    image = models.ImageField(upload_to=ai_generated_image_path)
    width = models.PositiveIntegerField()
    height = models.PositiveIntegerField()
    
    # Generation metadata
    seed = models.CharField(max_length=50, blank=True)
    model_version = models.CharField(max_length=50, blank=True)
    generation_time = models.FloatField(null=True, blank=True)  # seconds
    cost = models.DecimalField(max_digits=8, decimal_places=4, null=True, blank=True)
    
    # Status
    is_approved = models.BooleanField(default=False)
    is_used = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "ai_generated_images"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["story", "-created_at"]),
            models.Index(fields=["user", "-created_at"]),
        ]

    def __str__(self):
        return f"AI {self.image_type} for {self.story.title}"


class StoryView(models.Model):
    """
    Track story views for analytics.
    """
    story = models.ForeignKey(Story, on_delete=models.CASCADE, related_name="story_views")
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField(blank=True)
    viewed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "story_views"
        indexes = [
            models.Index(fields=["story", "-viewed_at"]),
        ]


class StoryLike(models.Model):
    """
    Story likes/hearts from users.
    """
    story = models.ForeignKey(Story, on_delete=models.CASCADE, related_name="story_likes")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="liked_stories")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "story_likes"
        unique_together = ("story", "user")
        indexes = [
            models.Index(fields=["user", "-created_at"]),
        ]


class StoryBookmark(models.Model):
    """
    User bookmarks for stories.
    """
    story = models.ForeignKey(Story, on_delete=models.CASCADE, related_name="story_bookmarks")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="bookmarked_stories")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "story_bookmarks"
        unique_together = ("story", "user")
        indexes = [
            models.Index(fields=["user", "-created_at"]),
        ]


class StoryFollow(models.Model):
    """
    Users following stories for updates.
    """
    story = models.ForeignKey(Story, on_delete=models.CASCADE, related_name="story_follows")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="followed_stories")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "story_follows"
        unique_together = ("story", "user")
        indexes = [
            models.Index(fields=["user", "-created_at"]),
        ]


class AIUsageLog(models.Model):
    """
    Track AI API usage for billing and monitoring.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="ai_usage")
    story = models.ForeignKey("stories.Story", on_delete=models.CASCADE, related_name="ai_usage", null=True, blank=True)
    project = models.ForeignKey("projects.Project", on_delete=models.CASCADE, related_name="ai_usage", null=True, blank=True)
    
    # Request details
    action = models.CharField(max_length=50)  # generate_image, enhance_text, etc.
    provider = models.CharField(max_length=20)
    model = models.CharField(max_length=50, blank=True)
    
    # Usage metrics
    tokens_used = models.PositiveIntegerField(default=0)
    cost = models.DecimalField(max_digits=8, decimal_places=4, default=0)
    processing_time = models.FloatField(null=True, blank=True)
    
    # Request/response data
    request_data = models.JSONField(default=dict, blank=True)
    response_data = models.JSONField(default=dict, blank=True)
    
    # Status
    success = models.BooleanField(default=True)
    error_message = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "ai_usage_logs"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["action", "-created_at"]),
        ]