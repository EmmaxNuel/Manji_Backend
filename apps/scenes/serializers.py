"""Serializers for the Scene model."""

from django.db import models
from rest_framework import serializers

from .models import Scene


class SceneListSerializer(serializers.ModelSerializer):
    """Lightweight card view for scene lists."""

    chapter = serializers.SerializerMethodField()
    story = serializers.SerializerMethodField()
    cast = serializers.SerializerMethodField()

    class Meta:
        model = Scene
        fields = (
            "id",
            "title",
            "description",
            "location",
            "characters",
            "cast",
            "mood",
            "duration",
            "camera_type",
            "order",
            "chapter",
            "story",
            "updated_at",
        )
        read_only_fields = fields

    def get_chapter(self, obj):
        if obj.chapter_id:
            return {
                "id": str(obj.chapter_id),
                "title": obj.chapter.title,
                "chapter_number": obj.chapter.chapter_number,
            }
        return None

    def get_story(self, obj):
        if obj.story_id:
            return {"id": str(obj.story_id), "title": obj.story.title}
        return None

    def get_cast(self, obj):
        return [
            {
                "id": str(c.id),
                "name": c.name,
                "role": c.role,
            }
            for c in obj.cast.all()
        ]


class SceneDetailSerializer(SceneListSerializer):
    """Full detail for the workspace scene editor."""

    class Meta(SceneListSerializer.Meta):
        fields = SceneListSerializer.Meta.fields + (
            "dialogue",
            "narration",
            "camera_notes",
            "camera_type",
        )


class SceneCreateUpdateSerializer(serializers.ModelSerializer):
    """Used for POST (create) and PATCH (update)."""

    cast = serializers.ListField(
        child=serializers.UUIDField(), required=False, write_only=True
    )

    class Meta:
        model = Scene
        fields = (
            "id",
            "title",
            "description",
            "location",
            "characters",
            "cast",
            "dialogue",
            "narration",
            "camera_type",
            "camera_notes",
            "mood",
            "duration",
            "order",
            "chapter",
        )
        read_only_fields = ("id",)
        extra_kwargs = {"chapter": {"required": False, "allow_null": True}}

    def validate_title(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Title is required.")
        return value

    def validate_chapter(self, value):
        if value is None:
            return value
        project = self.context.get("project")
        if project is None:
            raise serializers.ValidationError("Project context is required.")
        if value.story_id != project.story_id:
            raise serializers.ValidationError(
                "The chapter must belong to this project's story."
            )
        return value

    def _apply_cast(self, scene, cast_ids):
        """Set the cast from a list of character UUIDs and sync names."""
        from apps.characters.models import Character

        if cast_ids is None:
            return
        chars = Character.objects.filter(id__in=cast_ids, project=scene.project)
        scene.cast.set(chars)
        scene.characters = [c.name for c in chars]

    def create(self, validated_data):
        cast_ids = validated_data.pop("cast", None)
        project = self.context["project"]
        if not validated_data.get("order"):
            last = (
                Scene.objects.filter(project=project)
                .aggregate(models.Max("order"))["order__max"]
            )
            validated_data["order"] = (last or 0) + 1
        chapter = validated_data.get("chapter")
        if chapter is None:
            validated_data["story"] = project.story
        scene = Scene.objects.create(project=project, **validated_data)
        self._apply_cast(scene, cast_ids)
        return scene

    def update(self, instance, validated_data):
        cast_ids = validated_data.pop("cast", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        self._apply_cast(instance, cast_ids)
        return instance