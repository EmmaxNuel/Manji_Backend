"""
Story, Genre, and Tag serializers.

Split into:
- GenreSerializer / TagSerializer  (simple read-only)
- StoryListSerializer              (lightweight card view)
- StoryDetailSerializer            (full detail with counts)
- StoryCreateUpdateSerializer      (write – used for POST/PUT/PATCH)
"""

from django.contrib.auth import get_user_model
from rest_framework import serializers

from apps.users.serializers import UserPublicSerializer
from .models import Genre, Tag, Story, StoryLike, StoryBookmark, StoryFollow

User = get_user_model()


# ---------------------------------------------------------------------------
# Genre & Tag
# ---------------------------------------------------------------------------

class GenreSerializer(serializers.ModelSerializer):
    class Meta:
        model = Genre
        fields = ("id", "name", "slug", "description", "color", "stories_count")
        read_only_fields = ("id", "slug", "stories_count")


class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ("id", "name", "slug", "stories_count")
        read_only_fields = ("id", "slug", "stories_count")


# ---------------------------------------------------------------------------
# Story – List (card view)
# ---------------------------------------------------------------------------

class StoryListSerializer(serializers.ModelSerializer):
    """Lightweight serializer used in lists and search results."""
    author = serializers.SerializerMethodField()
    genres = GenreSerializer(many=True, read_only=True)
    tags = TagSerializer(many=True, read_only=True)
    cover = serializers.SerializerMethodField()
    is_liked = serializers.SerializerMethodField()
    is_bookmarked = serializers.SerializerMethodField()
    is_following = serializers.SerializerMethodField()

    class Meta:
        model = Story
        fields = (
            "id",
            "title",
            "slug",
            "description",
            "cover",
            "content_type",
            "language",
            "status",
            "author",
            "genres",
            "tags",
            "chapters_count",
            "views_count",
            "likes_count",
            "bookmarks_count",
            "followers_count",
            "is_featured",
            "is_premium",
            "is_official",
            "published_at",
            "updated_at",
            "is_liked",
            "is_bookmarked",
            "is_following",
        )

    def get_author(self, obj):
        return {
            "id": str(obj.author.id),
            "username": obj.author.username,
            "avatar": self._get_avatar(obj.author),
        }

    def _get_avatar(self, user):
        try:
            profile = user.profile
            if profile.avatar:
                request = self.context.get("request")
                if request:
                    return request.build_absolute_uri(profile.avatar.url)
                return profile.avatar.url
        except Exception:
            pass
        return None

    def get_cover(self, obj):
        if obj.cover:
            request = self.context.get("request")
            if request:
                return request.build_absolute_uri(obj.cover.url)
            return obj.cover.url
        return None

    def _get_user(self):
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            return request.user
        return None

    def get_is_liked(self, obj):
        user = self._get_user()
        if user:
            return StoryLike.objects.filter(story=obj, user=user).exists()
        return False

    def get_is_bookmarked(self, obj):
        user = self._get_user()
        if user:
            return StoryBookmark.objects.filter(story=obj, user=user).exists()
        return False

    def get_is_following(self, obj):
        user = self._get_user()
        if user:
            return StoryFollow.objects.filter(story=obj, user=user).exists()
        return False


# ---------------------------------------------------------------------------
# Story – Detail (full page)
# ---------------------------------------------------------------------------

class StoryDetailSerializer(StoryListSerializer):
    """Full detail – includes word_count, avg_reading_time, AI fields."""
    author = UserPublicSerializer(read_only=True)

    class Meta(StoryListSerializer.Meta):
        fields = StoryListSerializer.Meta.fields + (
            "word_count",
            "avg_reading_time",
            "comments_count",
            "created_at",
            "completed_at",
        )


# ---------------------------------------------------------------------------
# Story – Create / Update
# ---------------------------------------------------------------------------

class StoryCreateUpdateSerializer(serializers.ModelSerializer):
    """Used for POST (create) and PUT/PATCH (update)."""
    genres = serializers.PrimaryKeyRelatedField(
        queryset=Genre.objects.all(), many=True, required=False
    )
    tags = serializers.PrimaryKeyRelatedField(
        queryset=Tag.objects.all(), many=True, required=False
    )
    # Allow tag creation by name
    tag_names = serializers.ListField(
        child=serializers.CharField(max_length=30), write_only=True, required=False
    )

    class Meta:
        model = Story
        fields = (
            "id",
            "title",
            "description",
            "cover",
            "content_type",
            "language",
            "status",
            "genres",
            "tags",
            "tag_names",
        )
        read_only_fields = ("id",)

    def validate_title(self, value):
        return value.strip()

    def validate(self, attrs):
        # Creators can only publish; readers cannot create stories at all
        # (view layer enforces IsCreatorOrReadOnly, this is an extra guard)
        return attrs

    def _handle_tag_names(self, tag_names):
        """Get-or-create tags by name and return their instances."""
        tags = []
        for name in tag_names:
            name = name.strip().lower()
            if name:
                tag, _ = Tag.objects.get_or_create(
                    name=name,
                    defaults={"name": name}
                )
                tags.append(tag)
        return tags

    def create(self, validated_data):
        genres = validated_data.pop("genres", [])
        tags = validated_data.pop("tags", [])
        tag_names = validated_data.pop("tag_names", [])

        story = Story.objects.create(
            author=self.context["request"].user,
            **validated_data
        )

        story.genres.set(genres)
        all_tags = list(tags) + self._handle_tag_names(tag_names)
        story.tags.set(all_tags)

        return story

    def update(self, instance, validated_data):
        genres = validated_data.pop("genres", None)
        tags = validated_data.pop("tags", None)
        tag_names = validated_data.pop("tag_names", [])

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if genres is not None:
            instance.genres.set(genres)

        extra_tags = self._handle_tag_names(tag_names)
        if tags is not None:
            instance.tags.set(list(tags) + extra_tags)
        elif extra_tags:
            instance.tags.add(*extra_tags)

        return instance
