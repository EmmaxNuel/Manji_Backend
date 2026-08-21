"""
Project serializers.

Split into:
- ProjectListSerializer          (lightweight card view for the Projects page)
- ProjectDetailSerializer        (full detail for the workspace)
- ProjectCreateUpdateSerializer  (write – used for POST/PATCH)
"""

from rest_framework import serializers

from apps.users.serializers import UserPublicSerializer
from .models import Project


class ProjectListSerializer(serializers.ModelSerializer):
    """Lightweight serializer used in lists and cards."""

    owner = serializers.SerializerMethodField()
    cover = serializers.SerializerMethodField()
    story = serializers.SerializerMethodField()

    class Meta:
        model = Project
        fields = (
            "id",
            "title",
            "description",
            "cover",
            "project_type",
            "art_style",
            "status",
            "owner",
            "story",
            "created_at",
            "updated_at",
        )

    def get_owner(self, obj):
        return {
            "id": str(obj.owner.id),
            "username": obj.owner.username,
        }

    def get_cover(self, obj):
        if obj.cover:
            request = self.context.get("request")
            if request:
                return request.build_absolute_uri(obj.cover.url)
            return obj.cover.url
        return None

    def get_story(self, obj):
        story = obj.story
        if story is None:
            return None
        return {
            "id": str(story.id),
            "title": story.title,
            "slug": story.slug,
            "content_type": story.content_type,
        }


class ProjectDetailSerializer(ProjectListSerializer):
    """Full project detail for the workspace overview."""

    owner = UserPublicSerializer(read_only=True)
    art_style_label = serializers.SerializerMethodField()
    art_style_context = serializers.SerializerMethodField()

    class Meta(ProjectListSerializer.Meta):
        fields = ProjectListSerializer.Meta.fields + (
            "art_style_description",
            "art_style_label",
            "art_style_context",
        )

    def get_art_style_label(self, obj):
        return obj.get_art_style_label() if hasattr(obj, "get_art_style_label") else ""

    def get_art_style_context(self, obj):
        return obj.get_art_style_context()


class ProjectCreateUpdateSerializer(serializers.ModelSerializer):
    """Used for POST (create) and PATCH (update)."""

    class Meta:
        model = Project
        fields = (
            "id",
            "title",
            "description",
            "cover",
            "project_type",
            "art_style",
            "art_style_description",
            "status",
            "story",
        )
        read_only_fields = ("id",)
        extra_kwargs = {"story": {"required": False, "allow_null": True}}

    def validate_title(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Title is required.")
        return value

    def validate_art_style(self, value):
        valid = {choice[0] for choice in Project.ArtStyle.choices}
        if value not in valid:
            raise serializers.ValidationError(
                f"Unsupported art style '{value}'. "
                f"Supported: {', '.join(sorted(valid))}."
            )
        return value

    def validate(self, attrs):
        if (
            attrs.get("art_style") == Project.ArtStyle.CUSTOM
            and not (attrs.get("art_style_description") or "").strip()
        ):
            raise serializers.ValidationError(
                {"art_style_description": "Describe your custom art style."}
            )
        return attrs

    def create(self, validated_data):
        validated_data["owner"] = self.context["request"].user
        return Project.objects.create(**validated_data)