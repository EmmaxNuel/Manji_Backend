"""
Serializers for Official Content API.
"""

from rest_framework import serializers
from django.contrib.auth import get_user_model

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

User = get_user_model()


class OfficialSeriesSerializer(serializers.ModelSerializer):
    class Meta:
        model = OfficialSeries
        fields = (
            "id", "title", "slug", "description", "cover", "tagline",
            "order", "is_active", "created_at", "updated_at",
        )
        read_only_fields = ("id", "slug", "created_at", "updated_at")


class OfficialSeriesListSerializer(OfficialSeriesSerializer):
    seasons_count = serializers.SerializerMethodField()
    animations_count = serializers.SerializerMethodField()

    class Meta(OfficialSeriesSerializer.Meta):
        fields = OfficialSeriesSerializer.Meta.fields + ("seasons_count", "animations_count")

    def get_seasons_count(self, obj):
        return obj.seasons.filter(is_published=True).count()

    def get_animations_count(self, obj):
        return obj.animations.filter(is_published=True).count()


class OfficialSeasonSerializer(serializers.ModelSerializer):
    series = OfficialSeriesSerializer(read_only=True)

    class Meta:
        model = OfficialSeason
        fields = (
            "id", "series", "season_number", "title", "description", "cover",
            "order", "is_published", "published_at", "created_at", "updated_at",
        )
        read_only_fields = ("id", "published_at", "created_at", "updated_at")


class OfficialSeasonListSerializer(OfficialSeasonSerializer):
    arcs_count = serializers.SerializerMethodField()

    class Meta(OfficialSeasonSerializer.Meta):
        fields = OfficialSeasonSerializer.Meta.fields + ("arcs_count",)

    def get_arcs_count(self, obj):
        return obj.arcs.filter(is_published=True).count()


class OfficialArcSerializer(serializers.ModelSerializer):
    season = OfficialSeasonListSerializer(read_only=True)

    class Meta:
        model = OfficialArc
        fields = (
            "id", "season", "title", "slug", "description", "cover",
            "order", "is_published", "published_at", "created_at", "updated_at",
        )
        read_only_fields = ("id", "slug", "published_at", "created_at", "updated_at")


class OfficialArcListSerializer(OfficialArcSerializer):
    stories_count = serializers.SerializerMethodField()
    animations_count = serializers.SerializerMethodField()

    class Meta(OfficialArcSerializer.Meta):
        fields = OfficialArcSerializer.Meta.fields + ("stories_count", "animations_count")

    def get_stories_count(self, obj):
        return obj.official_stories.count()

    def get_animations_count(self, obj):
        return obj.animations.filter(is_published=True).count()


class OfficialStorySerializer(serializers.ModelSerializer):
    arc = OfficialArcListSerializer(read_only=True)

    class Meta:
        model = OfficialStory
        fields = (
            "id", "arc", "order", "is_canon", "created_at", "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")


class OfficialStoryDetailSerializer(OfficialStorySerializer):
    story = serializers.SerializerMethodField()
    official_chapters = serializers.SerializerMethodField()

    class Meta(OfficialStorySerializer.Meta):
        fields = OfficialStorySerializer.Meta.fields + ("story", "official_chapters")

    def get_story(self, obj):
        # Import here to avoid circular imports
        from apps.stories.serializers import StoryDetailSerializer
        from rest_framework.request import Request
        request = self.context.get('request')
        return StoryDetailSerializer(obj.story, context={"request": request}).data

    def get_official_chapters(self, obj):
        chapters = obj.official_chapters.filter(is_published=True).order_by("order")
        return OfficialChapterListSerializer(chapters, many=True, context=self.context).data


class OfficialChapterSerializer(serializers.ModelSerializer):
    official_story = OfficialStorySerializer(read_only=True)
    animation_episode = serializers.SerializerMethodField()

    class Meta:
        model = OfficialChapter
        fields = (
            "id", "official_story", "chapter", "animation_episode",
            "order", "is_published", "published_at", "created_at", "updated_at",
        )
        read_only_fields = ("id", "published_at", "created_at", "updated_at")


class OfficialChapterListSerializer(serializers.ModelSerializer):
    chapter = serializers.SerializerMethodField()
    animation_episode = serializers.SerializerMethodField()

    class Meta:
        model = OfficialChapter
        fields = (
            "id", "chapter", "animation_episode", "order", "is_published", "published_at",
        )

    def get_chapter(self, obj):
        from apps.chapters.serializers import ChapterDetailSerializer
        return ChapterDetailSerializer(obj.chapter, context=self.context).data

    def get_animation_episode(self, obj):
        if obj.animation_episode:
            return OfficialEpisodeListSerializer(obj.animation_episode, context=self.context).data
        return None


class OfficialSceneSerializer(serializers.ModelSerializer):
    official_chapter = OfficialChapterSerializer(read_only=True)
    animation_scene = serializers.SerializerMethodField()

    class Meta:
        model = OfficialScene
        fields = (
            "id", "official_chapter", "scene", "animation_scene",
            "order", "created_at", "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")

    def get_animation_scene(self, obj):
        if obj.animation_scene:
            return OfficialAnimationSceneSerializer(obj.animation_scene, context=self.context).data
        return None


class OfficialAnimationSerializer(serializers.ModelSerializer):
    series = OfficialSeriesListSerializer(read_only=True)
    arc = OfficialArcListSerializer(read_only=True)

    class Meta:
        model = OfficialAnimation
        fields = (
            "id", "series", "arc", "title", "slug", "description", "cover",
            "trailer_url", "order", "is_published", "published_at", "created_at", "updated_at",
        )
        read_only_fields = ("id", "slug", "published_at", "created_at", "updated_at")


class OfficialAnimationListSerializer(OfficialAnimationSerializer):
    episodes_count = serializers.SerializerMethodField()

    class Meta(OfficialAnimationSerializer.Meta):
        fields = OfficialAnimationSerializer.Meta.fields + ("episodes_count",)

    def get_episodes_count(self, obj):
        return obj.episodes.filter(is_published=True).count()


class OfficialEpisodeSerializer(serializers.ModelSerializer):
    animation = OfficialAnimationListSerializer(read_only=True)
    linked_official_chapters = serializers.SerializerMethodField()

    class Meta:
        model = OfficialEpisode
        fields = (
            "id", "animation", "episode_number", "title", "description", "thumbnail",
            "video_file", "video_url", "duration", "order",
            "is_published", "published_at", "created_at", "updated_at",
            "linked_official_chapters",
        )
        read_only_fields = ("id", "published_at", "created_at", "updated_at")


class OfficialEpisodeListSerializer(serializers.ModelSerializer):
    animation = serializers.SerializerMethodField()
    linked_official_chapters = serializers.SerializerMethodField()

    class Meta:
        model = OfficialEpisode
        fields = (
            "id", "animation", "episode_number", "title", "description", "thumbnail",
            "video_file", "video_url", "duration", "order", "is_published", "published_at",
            "linked_official_chapters",
        )

    def get_animation(self, obj):
        return {"id": str(obj.animation.id), "title": obj.animation.title, "slug": obj.animation.slug}

    def get_linked_official_chapters(self, obj):
        chapters = obj.linked_official_chapters.filter(is_published=True).order_by("order")
        return OfficialChapterListSerializer(chapters, many=True, context=self.context).data


class OfficialAnimationSceneSerializer(serializers.ModelSerializer):
    episode = OfficialEpisodeListSerializer(read_only=True)
    linked_official_scenes = serializers.SerializerMethodField()

    class Meta:
        model = OfficialAnimationScene
        fields = (
            "id", "episode", "title", "description", "start_time", "end_time",
            "thumbnail", "order", "linked_official_scenes", "created_at", "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")

    def get_linked_official_scenes(self, obj):
        scenes = obj.linked_official_scenes.all().order_by("order")
        return OfficialSceneSerializer(scenes, many=True, context=self.context).data


class OfficialContentProgressSerializer(serializers.ModelSerializer):
    class Meta:
        model = OfficialContentProgress
        fields = (
            "id", "content_type", "content_id", "progress_percentage",
            "current_position", "completed", "last_accessed_at", "created_at",
        )
        read_only_fields = ("id", "user", "last_accessed_at", "created_at")


class OfficialBookmarkSerializer(serializers.ModelSerializer):
    class Meta:
        model = OfficialBookmark
        fields = ("id", "content_type", "content_id", "created_at")
        read_only_fields = ("id", "user", "created_at")


class OfficialContentViewSerializer(serializers.ModelSerializer):
    class Meta:
        model = OfficialContentView
        fields = ("id", "content_type", "content_id", "time_spent", "viewed_at")
        read_only_fields = ("id", "user", "viewed_at")