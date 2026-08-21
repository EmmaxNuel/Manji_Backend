"""Serializers for the StoryboardPanel model (Phase 6)."""

from django.db import models
from rest_framework import serializers

from .models import StoryboardPanel


class StoryboardPanelSerializer(serializers.ModelSerializer):
    """List + detail view of a storyboard panel."""

    scene_title = serializers.CharField(source="scene.title", read_only=True)
    image_url = serializers.SerializerMethodField()
    asset_url = serializers.SerializerMethodField()

    class Meta:
        model = StoryboardPanel
        fields = (
            "id",
            "scene",
            "scene_title",
            "shot",
            "camera_movement",
            "aspect_ratio",
            "duration",
            "dialogue",
            "narration",
            "notes",
            "order",
            "asset",
            "asset_url",
            "image",
            "image_url",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "scene_title", "asset_url", "image_url", "image")

    def get_image_url(self, obj):
        request = self.context.get("request")
        if not obj.image:
            return None
        if request is None:
            return obj.image.url
        return request.build_absolute_uri(obj.image.url)

    def get_asset_url(self, obj):
        request = self.context.get("request")
        if not obj.asset_id:
            return None
        return request.build_absolute_uri(obj.asset.file.url)

    def validate_duration(self, value):
        if value is not None and value <= 0:
            raise serializers.ValidationError("Duration must be a positive number of seconds.")
        return value


class StoryboardPanelCreateSerializer(StoryboardPanelSerializer):
    """Used for multipart upload (POST) and metadata edit (PATCH)."""

    image = serializers.ImageField(required=False, allow_null=True)

    class Meta(StoryboardPanelSerializer.Meta):
        read_only_fields = ("id", "scene", "scene_title", "asset_url", "image_url")

    def create(self, validated_data):
        scene = self.context["scene"]
        if not validated_data.get("order"):
            last = (
                StoryboardPanel.objects.filter(scene=scene)
                .aggregate(models.Max("order"))["order__max"]
            )
            validated_data["order"] = (last or 0) + 1
        return StoryboardPanel.objects.create(scene=scene, **validated_data)