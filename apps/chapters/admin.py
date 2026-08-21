"""
Admin registration for chapter models including AI image generations.
"""

from django.contrib import admin

from apps.chapters.models import (
    AIImageGeneration,
    Chapter,
    ChapterImage,
    ChapterLike,
    ChapterView,
    ReadingProgress,
)


@admin.register(Chapter)
class ChapterAdmin(admin.ModelAdmin):
    list_display = ("title", "story", "chapter_number", "status", "published_at")
    list_filter = ("status",)
    search_fields = ("title", "story__title")


@admin.register(ChapterImage)
class ChapterImageAdmin(admin.ModelAdmin):
    list_display = ("chapter", "page_order", "source", "width", "height")
    list_filter = ("source",)


@admin.register(AIImageGeneration)
class AIImageGenerationAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "story", "provider", "image_type", "status", "created_at")
    list_filter = ("status", "provider", "image_type")
    search_fields = ("user__username", "story__title", "prompt")
    readonly_fields = ("id", "created_at", "completed_at")


@admin.register(ReadingProgress)
class ReadingProgressAdmin(admin.ModelAdmin):
    list_display = ("user", "story", "chapter", "progress_percentage", "last_read_at")


@admin.register(ChapterView)
class ChapterViewAdmin(admin.ModelAdmin):
    list_display = ("chapter", "user", "viewed_at")


@admin.register(ChapterLike)
class ChapterLikeAdmin(admin.ModelAdmin):
    list_display = ("chapter", "user", "created_at")