from django.contrib import admin
from .models import (
    OfficialSeries,
    OfficialSeason,
    OfficialArc,
    OfficialStory,
    OfficialChapter,
    OfficialScene,
    OfficialAnimation,
    OfficialEpisode,
    OfficialAnimationScene,
    OfficialContentProgress,
    OfficialBookmark,
    OfficialContentView,
)


@admin.register(OfficialSeries)
class OfficialSeriesAdmin(admin.ModelAdmin):
    list_display = ("title", "slug", "order", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("title", "slug")
    prepopulated_fields = {"slug": ("title",)}
    ordering = ("order", "title")


@admin.register(OfficialSeason)
class OfficialSeasonAdmin(admin.ModelAdmin):
    list_display = ("series", "season_number", "title", "order", "is_published", "published_at")
    list_filter = ("series", "is_published")
    search_fields = ("title", "series__title")
    ordering = ("series", "season_number")


@admin.register(OfficialArc)
class OfficialArcAdmin(admin.ModelAdmin):
    list_display = ("season", "title", "slug", "order", "is_published", "published_at")
    list_filter = ("season", "is_published")
    search_fields = ("title", "season__title")
    prepopulated_fields = {"slug": ("title",)}
    ordering = ("season", "order")


@admin.register(OfficialStory)
class OfficialStoryAdmin(admin.ModelAdmin):
    list_display = ("arc", "story", "order", "is_canon", "created_at")
    list_filter = ("arc", "is_canon")
    search_fields = ("story__title", "arc__title")
    ordering = ("arc", "order")


@admin.register(OfficialChapter)
class OfficialChapterAdmin(admin.ModelAdmin):
    list_display = ("official_story", "chapter", "animation_episode", "order", "is_published", "published_at")
    list_filter = ("official_story", "is_published")
    search_fields = ("chapter__title", "official_story__story__title")
    ordering = ("official_story", "order")


@admin.register(OfficialScene)
class OfficialSceneAdmin(admin.ModelAdmin):
    list_display = ("official_chapter", "scene", "animation_scene", "order")
    list_filter = ("official_chapter",)
    search_fields = ("scene__title", "official_chapter__chapter__title")
    ordering = ("official_chapter", "order")


@admin.register(OfficialAnimation)
class OfficialAnimationAdmin(admin.ModelAdmin):
    list_display = ("series", "arc", "title", "slug", "order", "is_published", "published_at")
    list_filter = ("series", "arc", "is_published")
    search_fields = ("title", "series__title")
    prepopulated_fields = {"slug": ("title",)}
    ordering = ("order", "title")


@admin.register(OfficialEpisode)
class OfficialEpisodeAdmin(admin.ModelAdmin):
    list_display = ("animation", "episode_number", "title", "duration", "is_published", "published_at")
    list_filter = ("animation", "is_published")
    search_fields = ("title", "animation__title")
    ordering = ("animation", "episode_number")


@admin.register(OfficialAnimationScene)
class OfficialAnimationSceneAdmin(admin.ModelAdmin):
    list_display = ("episode", "title", "start_time", "end_time", "order")
    list_filter = ("episode",)
    search_fields = ("title", "episode__title")
    ordering = ("episode", "order")


@admin.register(OfficialContentProgress)
class OfficialContentProgressAdmin(admin.ModelAdmin):
    list_display = ("user", "content_type", "content_id", "progress_percentage", "completed", "last_accessed_at")
    list_filter = ("content_type", "completed")
    search_fields = ("user__username", "content_id")
    ordering = ("-last_accessed_at",)


@admin.register(OfficialBookmark)
class OfficialBookmarkAdmin(admin.ModelAdmin):
    list_display = ("user", "content_type", "content_id", "created_at")
    list_filter = ("content_type",)
    search_fields = ("user__username", "content_id")
    ordering = ("-created_at",)


@admin.register(OfficialContentView)
class OfficialContentViewAdmin(admin.ModelAdmin):
    list_display = ("content_type", "content_id", "user", "viewed_at", "time_spent")
    list_filter = ("content_type",)
    search_fields = ("content_id", "user__username")
    ordering = ("-viewed_at",)