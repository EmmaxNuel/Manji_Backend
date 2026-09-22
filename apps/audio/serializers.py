"""Serializers for voice recordings (Phase 9)."""

import uuid

from django.conf import settings
from rest_framework import serializers

from apps.scenes.models import Scene
from apps.characters.models import Character
from .models import VoiceRecording


class VoiceRecordingSerializer(serializers.ModelSerializer):
    """Detail + list view of a voice recording."""

    url = serializers.SerializerMethodField()
    character = serializers.SerializerMethodField()
    scene_title = serializers.SerializerMethodField()
    character_name = serializers.SerializerMethodField()
    scene = serializers.SerializerMethodField()

    class Meta:
        model = VoiceRecording
        fields = (
            "id",
            "title",
            "kind",
            "description",
            "url",
            "mime_type",
            "size",
            "duration",
            "scene",
            "scene_title",
            "character",
            "character_name",
            "dialogue_line",
            "order",
            "start_seconds",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields

    def get_url(self, obj):
        request = self.context.get("request")
        url = obj.file.url
        return request.build_absolute_uri(url) if request else url

    def get_character(self, obj):
        return str(obj.character_id) if obj.character_id else None

    def get_character_name(self, obj):
        return obj.character.name if obj.character else None

    def get_scene_title(self, obj):
        return obj.scene.title if obj.scene else None

    def get_scene(self, obj):
        return str(obj.scene_id) if obj.scene_id else None


class VoiceRecordingCreateSerializer(serializers.ModelSerializer):
    """Used for multipart upload (POST) and metadata edit (PATCH)."""

    title = serializers.CharField(required=False, allow_blank=True, max_length=200)

    class Meta:
        model = VoiceRecording
        fields = (
            "id",
            "file",
            "title",
            "kind",
            "description",
            "duration",
            "dialogue_line",
            "order",
            "start_seconds",
        )
        read_only_fields = ("id",)
        extra_kwargs = {
            "file": {"required": False},
            "title": {"required": False, "allow_blank": True},
        }

    def validate_title(self, value):
        value = (value or "").strip()
        if value and len(value) > 200:
            raise serializers.ValidationError("Title must be 200 characters or fewer.")
        return value

    def validate_file(self, value):
        if value is None:
            raise serializers.ValidationError("A file is required.")
        if value.size <= 0:
            raise serializers.ValidationError("The uploaded file is empty.")
        max_bytes = settings.AUDIO_MAX_UPLOAD_MB * 1024 * 1024
        if value.size > max_bytes:
            raise serializers.ValidationError(
                f"Audio files must be {settings.AUDIO_MAX_UPLOAD_MB} MB or smaller."
            )
        mime = (value.content_type or "").lower()
        if not mime.startswith("audio/"):
            raise serializers.ValidationError("Only audio files are allowed.")
        return value

    def create(self, validated_data):
        project = self.context["project"]
        request = self.context["request"]
        upload = validated_data.pop("file", None)
        scene_id = request.data.get("scene")
        character_id = request.data.get("character")
        scene = Scene.objects.get(id=scene_id) if scene_id else None
        character = Character.objects.get(id=character_id) if character_id else None
        recording = VoiceRecording.objects.create(
            project=project,
            owner=self.context["user"],
            file=upload,
            mime_type=(upload.content_type if upload else "") or "",
            size=(upload.size if upload else 0) or 0,
            title=validated_data.pop("title", "")
            or ((upload.name.rsplit("/", 1)[-1] if upload else "") or "Untitled voice"),
            scene=scene,
            character=character,
            **validated_data,
        )
        return recording

    def update(self, instance, validated_data):
        request = self.context["request"]
        upload = validated_data.pop("file", None)
        scene_id = request.data.get("scene")
        character_id = request.data.get("character")
        if upload:
            instance.file = upload
            instance.mime_type = upload.content_type or ""
            instance.size = upload.size or 0
        if scene_id is not None:
            instance.scene = Scene.objects.get(id=scene_id) if scene_id else None
        if character_id is not None:
            instance.character = Character.objects.get(id=character_id) if character_id else None
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance


class VoiceTimelineSerializer(serializers.ModelSerializer):
    """A per-scene timeline row: the clip plus its placement metadata."""

    url = serializers.SerializerMethodField()
    character_name = serializers.SerializerMethodField()

    class Meta:
        model = VoiceRecording
        fields = (
            "id",
            "title",
            "kind",
            "url",
            "duration",
            "character_name",
            "dialogue_line",
            "order",
            "start_seconds",
        )
        read_only_fields = fields

    def get_url(self, obj):
        request = self.context.get("request")
        url = obj.file.url
        return request.build_absolute_uri(url) if request else url

    def get_character_name(self, obj):
        return obj.character.name if obj.character else None
