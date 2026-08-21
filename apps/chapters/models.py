"""
Chapter models for Manji with AI integration.

Architecture decisions:
- Chapter model supports both text content (novels) and image content (comics/manga)
- ChapterImage model for managing comic/manga pages with AI generation
- Proper ordering with chapter_number and page_order
- AI integration for generating chapter illustrations and comic pages
- Reading progress tracking
"""

import uuid
from django.contrib.auth import get_user_model
from django.db import models
from django.utils import timezone

User = get_user_model()


def chapter_image_upload_path(instance, filename):
    """Upload path for chapter images."""
    ext = filename.rsplit(".", 1)[-1]
    return f"chapters/{instance.chapter.story.id}/{instance.chapter.id}/{instance.page_order}.{ext}"


def ai_generation_result_path(instance, filename):
    """Upload path for AI image generation results (chapter is optional)."""
    ext = filename.rsplit(".", 1)[-1]
    story_id = getattr(instance.story, "id", "unknown")
    return f"ai-generations/{story_id}/{instance.id}.{ext}"


class Chapter(models.Model):
    """
    Story chapters supporting both text and image content.
    """
    
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"
        SCHEDULED = "scheduled", "Scheduled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    story = models.ForeignKey("stories.Story", on_delete=models.CASCADE, related_name="chapters")
    
    # Chapter details
    title = models.CharField(max_length=200)
    chapter_number = models.PositiveIntegerField(db_index=True)
    content = models.TextField(blank=True)  # For text-based content
    notes = models.TextField(max_length=1000, blank=True)  # Author notes
    
    # AI assistance
    ai_summary = models.TextField(max_length=500, blank=True, 
                                 help_text="AI-generated chapter summary")
    ai_enhanced = models.BooleanField(default=False, 
                                     help_text="Content enhanced by AI")
    
    # Publication
    status = models.CharField(
        max_length=15,
        choices=Status.choices,
        default=Status.DRAFT,
        db_index=True
    )
    is_premium = models.BooleanField(default=False, db_index=True)
    
    # Timestamps
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    published_at = models.DateTimeField(null=True, blank=True, db_index=True)
    scheduled_at = models.DateTimeField(null=True, blank=True, db_index=True)
    
    # Reading metrics
    views_count = models.PositiveIntegerField(default=0, db_index=True)
    likes_count = models.PositiveIntegerField(default=0, db_index=True)
    comments_count = models.PositiveIntegerField(default=0, db_index=True)
    word_count = models.PositiveIntegerField(default=0)
    reading_time = models.PositiveIntegerField(default=0)  # minutes
    
    class Meta:
        db_table = "chapters"
        unique_together = ("story", "chapter_number")
        ordering = ["story", "chapter_number"]
        indexes = [
            models.Index(fields=["story", "chapter_number"]),
            models.Index(fields=["status", "-published_at"]),
        ]

    def __str__(self):
        return f"Chapter {self.chapter_number}: {self.title}"

    def save(self, *args, **kwargs):
        # Set published_at when first published
        if self.status == self.Status.PUBLISHED and not self.published_at:
            self.published_at = timezone.now()
        
        # Calculate word count for text content
        if self.content:
            self.word_count = len(self.content.split())
            # Estimate reading time (average 200 words per minute)
            self.reading_time = max(1, self.word_count // 200)
        
        super().save(*args, **kwargs)

    @property
    def is_published(self):
        return self.status == self.Status.PUBLISHED

    @property
    def page_count(self):
        """Number of pages for image-based chapters."""
        return self.chapter_images.count()

    def get_absolute_url(self):
        return f"/stories/{self.story.slug}/chapters/{self.chapter_number}/"


class ChapterImage(models.Model):
    """
    Individual pages/images for comic/manga chapters with AI generation support.
    """
    
    class ImageSource(models.TextChoices):
        UPLOADED = "uploaded", "User Uploaded"
        AI_GENERATED = "ai_generated", "AI Generated"
        AI_ENHANCED = "ai_enhanced", "AI Enhanced"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    chapter = models.ForeignKey(Chapter, on_delete=models.CASCADE, related_name="chapter_images")
    
    # Image details
    image = models.ImageField(upload_to=chapter_image_upload_path)
    page_order = models.PositiveIntegerField(db_index=True)
    alt_text = models.CharField(max_length=200, blank=True)
    
    # AI generation details
    source = models.CharField(max_length=15, choices=ImageSource.choices, default=ImageSource.UPLOADED)
    ai_prompt = models.TextField(max_length=1000, blank=True)
    ai_style = models.CharField(max_length=50, blank=True)
    ai_provider = models.CharField(max_length=20, blank=True)
    
    # Image metadata
    width = models.PositiveIntegerField(null=True, blank=True)
    height = models.PositiveIntegerField(null=True, blank=True)
    file_size = models.PositiveIntegerField(null=True, blank=True)  # bytes
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "chapter_images"
        unique_together = ("chapter", "page_order")
        ordering = ["chapter", "page_order"]
        indexes = [
            models.Index(fields=["chapter", "page_order"]),
        ]

    def __str__(self):
        return f"Page {self.page_order} of {self.chapter}"

    def save(self, *args, **kwargs):
        # Auto-assign page order if not set
        if not self.page_order:
            last_page = ChapterImage.objects.filter(chapter=self.chapter).aggregate(
                models.Max('page_order')
            )['page_order__max']
            self.page_order = (last_page or 0) + 1
        
        super().save(*args, **kwargs)


class ReadingProgress(models.Model):
    """
    Track user reading progress through stories and chapters.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="reading_progress")
    story = models.ForeignKey("stories.Story", on_delete=models.CASCADE, related_name="reading_progress")
    chapter = models.ForeignKey(Chapter, on_delete=models.CASCADE, related_name="reading_progress")
    
    # Progress details
    progress_percentage = models.PositiveIntegerField(default=0)  # 0-100
    current_page = models.PositiveIntegerField(default=1)  # For image-based content
    scroll_position = models.PositiveIntegerField(default=0)  # For text-based content
    
    # Reading session
    started_at = models.DateTimeField(auto_now_add=True)
    last_read_at = models.DateTimeField(auto_now=True)
    reading_time_minutes = models.PositiveIntegerField(default=0)
    
    # Status
    completed = models.BooleanField(default=False, db_index=True)
    bookmarked_position = models.BooleanField(default=False)

    class Meta:
        db_table = "reading_progress"
        unique_together = ("user", "story", "chapter")
        indexes = [
            models.Index(fields=["user", "-last_read_at"]),
            models.Index(fields=["story", "-last_read_at"]),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.story.title} Ch.{self.chapter.chapter_number}"


class ChapterView(models.Model):
    """
    Track chapter views for analytics.
    """
    chapter = models.ForeignKey(Chapter, on_delete=models.CASCADE, related_name="chapter_views")
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField(blank=True)
    
    # Reading session details
    time_spent = models.PositiveIntegerField(default=0)  # seconds
    pages_viewed = models.PositiveIntegerField(default=1)  # for image content
    completion_rate = models.FloatField(default=0.0)  # 0.0 to 1.0
    
    viewed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "chapter_views"
        indexes = [
            models.Index(fields=["chapter", "-viewed_at"]),
        ]


class ChapterLike(models.Model):
    """
    Chapter likes from users.
    """
    chapter = models.ForeignKey(Chapter, on_delete=models.CASCADE, related_name="chapter_likes")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="liked_chapters")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "chapter_likes"
        unique_together = ("chapter", "user")
        indexes = [
            models.Index(fields=["user", "-created_at"]),
        ]


class AIImageGeneration(models.Model):
    """
    Track AI image generation requests and results for chapters.
    """
    
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    class Provider(models.TextChoices):
        DALLE = "dalle", "DALL-E"
        MIDJOURNEY = "midjourney", "Midjourney"
        STABLE_DIFFUSION = "stable_diffusion", "Stable Diffusion"
        LEONARDO = "leonardo", "Leonardo AI"
        STABILITY = "stability", "Stability AI (v2beta)"
        LOCAL = "local", "Local placeholder (development)"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="ai_generations")
    story = models.ForeignKey("stories.Story", on_delete=models.CASCADE, related_name="ai_generations")
    chapter = models.ForeignKey(Chapter, on_delete=models.CASCADE, related_name="ai_generations", null=True, blank=True)
    
    # Generation request
    prompt = models.TextField(max_length=2000)
    negative_prompt = models.TextField(max_length=1000, blank=True)
    style = models.CharField(max_length=50, blank=True)
    provider = models.CharField(max_length=20, choices=Provider.choices, default=Provider.STABLE_DIFFUSION)

    # What the finished image will be used for (cover / chapter / character / scene)
    image_type = models.CharField(
        max_length=20,
        choices=(
            ("cover", "Story Cover"),
            ("chapter", "Chapter Illustration"),
            ("character", "Character Art"),
            ("scene", "Scene Art"),
        ),
        default="cover",
        db_index=True,
    )
    
    # Generation settings
    width = models.PositiveIntegerField(default=1024)
    height = models.PositiveIntegerField(default=1024)
    steps = models.PositiveIntegerField(default=20)
    guidance_scale = models.FloatField(default=7.5)
    seed = models.CharField(max_length=50, blank=True)
    
    # Status and results
    status = models.CharField(max_length=15, choices=Status.choices, default=Status.PENDING)
    result_image = models.ImageField(upload_to=ai_generation_result_path, null=True, blank=True)
    error_message = models.TextField(blank=True)
    
    # Metadata
    generation_time = models.FloatField(null=True, blank=True)  # seconds
    cost = models.DecimalField(max_digits=8, decimal_places=4, null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "ai_image_generations"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["status", "-created_at"]),
        ]

    def __str__(self):
        return f"AI Generation for {self.story.title} by {self.user.username}"