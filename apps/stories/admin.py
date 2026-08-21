"""
Admin registration for story models including AI-generated images and usage.
"""

from django.contrib import admin

from apps.stories.models import (
    AIGeneratedImage,
    AIUsageLog,
    Genre,
    Story,
    StoryBookmark,
    StoryFollow,
    StoryLike,
    StoryView,
    Tag,
)


@admin.register(Genre)
class GenreAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "stories_count")
    search_fields = ("name",)


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "stories_count")
    search_fields = ("name",)


@admin.register(Story)
class StoryAdmin(admin.ModelAdmin):
    list_display = ("title", "author", "content_type", "status", "views_count", "published_at")
    list_filter = ("content_type", "status", "is_featured")
    search_fields = ("title", "author__username")
    filter_horizontal = ("genres", "tags")


@admin.register(AIGeneratedImage)
class AIGeneratedImageAdmin(admin.ModelAdmin):
    list_display = ("story", "user", "image_type", "ai_provider", "is_used", "created_at")
    list_filter = ("image_type", "ai_provider", "is_used")
    search_fields = ("story__title", "prompt")


@admin.register(AIUsageLog)
class AIUsageLogAdmin(admin.ModelAdmin):
    list_display = ("user", "action", "provider", "model", "success", "cost", "created_at")
    list_filter = ("action", "success", "provider")
    search_fields = ("user__username",)


@admin.register(StoryView)
class StoryViewAdmin(admin.ModelAdmin):
    list_display = ("story", "user", "viewed_at")


@admin.register(StoryLike)
class StoryLikeAdmin(admin.ModelAdmin):
    list_display = ("story", "user", "created_at")


@admin.register(StoryBookmark)
class StoryBookmarkAdmin(admin.ModelAdmin):
    list_display = ("story", "user", "created_at")


@admin.register(StoryFollow)
class StoryFollowAdmin(admin.ModelAdmin):
    list_display = ("story", "user", "created_at")