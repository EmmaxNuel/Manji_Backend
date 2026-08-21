"""
AI serializers for image and idea generation.
"""

from django.conf import settings
from rest_framework import serializers

from apps.chapters.models import AIImageGeneration
from .models import AIGeneratedImage, AIUsageLog


class AIGeneratedImageSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = AIGeneratedImage
        fields = (
            "id",
            "image_url",
            "image_type",
            "ai_provider",
            "style",
            "prompt",
            "width",
            "height",
            "is_used",
            "created_at",
        )
        read_only_fields = fields

    def get_image_url(self, obj):
        if obj.image:
            request = self.context.get("request")
            if request:
                return request.build_absolute_uri(obj.image.url)
            return obj.image.url
        return None


class AIImageGenerationSerializer(serializers.ModelSerializer):
    result_image_url = serializers.SerializerMethodField()
    image_type = serializers.CharField(read_only=True)

    class Meta:
        model = AIImageGeneration
        fields = (
            "id",
            "result_image_url",
            "status",
            "provider",
            "image_type",
            "prompt",
            "negative_prompt",
            "style",
            "width",
            "height",
            "steps",
            "guidance_scale",
            "seed",
            "error_message",
            "generation_time",
            "cost",
            "created_at",
            "completed_at",
        )
        read_only_fields = fields

    def get_result_image_url(self, obj):
        if obj.result_image:
            request = self.context.get("request")
            if request:
                return request.build_absolute_uri(obj.result_image.url)
            return obj.result_image.url
        return None


class AIImageGenerationCreateSerializer(serializers.Serializer):
    """Payload for requesting a new AI image generation."""

    prompt = serializers.CharField(max_length=2000, required=True)
    negative_prompt = serializers.CharField(max_length=1000, required=False, allow_blank=True)
    style = serializers.CharField(max_length=50, required=False, allow_blank=True)
    provider = serializers.ChoiceField(
        choices=AIImageGeneration.Provider.choices,
        default=settings.AI_IMAGE_PROVIDER_DEFAULT,
    )
    width = serializers.IntegerField(default=1024, min_value=256, max_value=2048)
    height = serializers.IntegerField(default=1024, min_value=256, max_value=2048)
    steps = serializers.IntegerField(default=20, min_value=1, max_value=150)
    guidance_scale = serializers.FloatField(default=7.5, min_value=1.0, max_value=30.0)
    seed = serializers.CharField(max_length=50, required=False, allow_blank=True)
    image_type = serializers.ChoiceField(
        choices=AIGeneratedImage.ImageType.choices,
        default=AIGeneratedImage.ImageType.COVER,
    )
    story_id = serializers.UUIDField(required=True)
    chapter_id = serializers.UUIDField(required=False, allow_null=True)


class AIImageApplySerializer(serializers.Serializer):
    """Apply a completed AI image to a story cover or a chapter page."""

    target = serializers.ChoiceField(choices=["cover", "chapter"])
    story_id = serializers.UUIDField(required=False, allow_null=True)
    chapter_id = serializers.UUIDField(required=False, allow_null=True)
    page_order = serializers.IntegerField(required=False, allow_null=True, min_value=1)


class AIStoryIdeasSerializer(serializers.Serializer):
    genre = serializers.CharField(max_length=50, required=False, allow_blank=True)
    content_type = serializers.CharField(max_length=20, required=False, allow_blank=True)
    themes = serializers.CharField(max_length=500, required=False, allow_blank=True)
    tone = serializers.CharField(max_length=50, required=False, allow_blank=True)
    count = serializers.IntegerField(default=5, min_value=1, max_value=10)
    language = serializers.CharField(max_length=5, required=False, default="en")
    story_id = serializers.UUIDField(required=False, allow_null=True)


class AITitlesSerializer(serializers.Serializer):
    premise = serializers.CharField(max_length=2000, required=True)
    style = serializers.CharField(max_length=100, required=False, allow_blank=True)
    count = serializers.IntegerField(default=8, min_value=1, max_value=12)
    language = serializers.CharField(max_length=5, required=False, default="en")
    story_id = serializers.UUIDField(required=False, allow_null=True)


class AIOutlineSerializer(serializers.Serializer):
    premise = serializers.CharField(max_length=2000, required=True)
    chapter_count = serializers.IntegerField(default=8, min_value=1, max_value=60)
    language = serializers.CharField(max_length=5, required=False, default="en")
    story_id = serializers.UUIDField(required=False, allow_null=True)


class AIUsageLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = AIUsageLog
        fields = (
            "id",
            "action",
            "provider",
            "model",
            "tokens_used",
            "cost",
            "processing_time",
            "success",
            "error_message",
            "created_at",
        )
        read_only_fields = fields