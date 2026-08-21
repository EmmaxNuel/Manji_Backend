"""
Chapter serializers.
"""
from django.db import models
from rest_framework import serializers
from .models import Chapter, ChapterImage


class ChapterImageSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = ChapterImage
        fields = ("id", "image_url", "page_order", "alt_text", "width", "height", "file_size")
        read_only_fields = ("id",)

    def get_image_url(self, obj):
        if obj.image:
            request = self.context.get("request")
            if request:
                return request.build_absolute_uri(obj.image.url)
            return obj.image.url
        return None


class ChapterListSerializer(serializers.ModelSerializer):
    """Lightweight – used in chapter lists / table of contents."""

    class Meta:
        model = Chapter
        fields = (
            "id",
            "title",
            "chapter_number",
            "status",
            "is_premium",
            "word_count",
            "reading_time",
            "views_count",
            "likes_count",
            "published_at",
            "created_at",
        )
        read_only_fields = fields


class ChapterDetailSerializer(serializers.ModelSerializer):
    """Full detail – includes content/images."""
    images = ChapterImageSerializer(source="chapter_images", many=True, read_only=True)
    story = serializers.SerializerMethodField()

    class Meta:
        model = Chapter
        fields = (
            "id",
            "title",
            "chapter_number",
            "content",
            "notes",
            "status",
            "is_premium",
            "word_count",
            "reading_time",
            "views_count",
            "likes_count",
            "comments_count",
            "published_at",
            "created_at",
            "updated_at",
            "images",
            "story",
        )
        read_only_fields = (
            "id", "word_count", "reading_time",
            "views_count", "likes_count", "comments_count",
            "published_at", "created_at", "updated_at", "images", "story",
        )

    def get_story(self, obj):
        story = obj.story
        cover = None
        if story.cover:
            request = self.context.get("request")
            if request:
                cover = request.build_absolute_uri(story.cover.url)
            else:
                cover = story.cover.url
        return {
            "id": str(story.id),
            "title": story.title,
            "slug": story.slug,
            "cover": cover,
            "content_type": story.content_type,
            "status": story.status,
            "is_official": story.is_official,
            "author": {
                "id": str(story.author.id),
                "username": story.author.username,
            },
        }


class ChapterCreateUpdateSerializer(serializers.ModelSerializer):
    """Used for POST (create) and PUT/PATCH (update)."""

    class Meta:
        model = Chapter
        fields = (
            "id",
            "title",
            "chapter_number",
            "content",
            "notes",
            "status",
            "is_premium",
        )
        read_only_fields = ("id",)
        extra_kwargs = {"chapter_number": {"required": False}}

    def validate_chapter_number(self, value):
        if value < 1:
            raise serializers.ValidationError("Chapter number must be at least 1.")
        return value

    def create(self, validated_data):
        story = self.context["story"]
        chapter_number = validated_data.pop("chapter_number", None)

        # Auto-assign the next free number when the client did not provide one
        # or when the requested number is already taken (prevents confusing
        # "Chapter already exists" failures during rapid creation).
        if chapter_number is None or Chapter.objects.filter(
            story=story, chapter_number=chapter_number
        ).exists():
            last = (
                Chapter.objects.filter(story=story)
                .aggregate(models.Max("chapter_number"))["chapter_number__max"]
            )
            chapter_number = (last or 0) + 1

        chapter = Chapter.objects.create(story=story, chapter_number=chapter_number, **validated_data)
        # Update story's chapter count and updated_at
        from apps.stories.models import Story
        Story.objects.filter(pk=story.pk).update(
            chapters_count=story.chapters.filter(status="published").count()
        )
        return chapter

    def update(self, instance, validated_data):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance
