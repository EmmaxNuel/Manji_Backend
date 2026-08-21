"""Serializers for the Asset model (Phase 5)."""

from django.conf import settings
from rest_framework import serializers

from .models import Asset, AssetTag


class TagListField(serializers.ListField):
    """Accept a list of tags (JSON) or a comma-separated string (multipart)."""

    child = serializers.CharField(max_length=50)

    def to_internal_value(self, data):
        if isinstance(data, str):
            data = [data]
        flattened = []
        for item in data:
            if isinstance(item, str):
                flattened.extend(part.strip() for part in item.split(",") if part.strip())
            else:
                flattened.append(item)
        return super().to_internal_value(flattened)


def _kind_from_mime(mime_type):
    if not mime_type:
        return Asset.Kind.OTHER
    if mime_type.startswith("image/"):
        return Asset.Kind.IMAGE
    if mime_type.startswith("video/"):
        return Asset.Kind.VIDEO
    if mime_type.startswith("audio/"):
        return Asset.Kind.AUDIO
    if mime_type in (
        "application/pdf",
        "text/plain",
        "text/markdown",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ):
        return Asset.Kind.DOCUMENT
    return Asset.Kind.OTHER


class AssetTagSerializer(serializers.ModelSerializer):
    class Meta:
        model = AssetTag
        fields = ("id", "name")
        read_only_fields = ("id",)


class AssetSerializer(serializers.ModelSerializer):
    """Detail + list view of an asset."""

    url = serializers.SerializerMethodField()
    tags = serializers.SerializerMethodField()

    class Meta:
        model = Asset
        fields = (
            "id",
            "kind",
            "title",
            "description",
            "url",
            "tags",
            "mime_type",
            "size",
            "width",
            "height",
            "duration",
            "meta",
            "created_at",
        )
        read_only_fields = fields

    def get_url(self, obj):
        request = self.context.get("request")
        if request is None:
            return obj.file.url
        return request.build_absolute_uri(obj.file.url)

    def get_tags(self, obj):
        return [t.name for t in obj.tags.all()]


class AssetCreateSerializer(serializers.ModelSerializer):
    """Used for multipart upload (POST) and metadata edit (PATCH)."""

    tags = TagListField(required=False)
    kind = serializers.ChoiceField(choices=Asset.Kind.choices, required=False)

    class Meta:
        model = Asset
        fields = ("id", "file", "kind", "title", "description", "tags")
        read_only_fields = ("id",)
        extra_kwargs = {"file": {"required": False}}

    def validate_title(self, value):
        value = (value or "").strip()
        if value and len(value) > 200:
            raise serializers.ValidationError("Title must be 200 characters or fewer.")
        return value

    def validate_file(self, value):
        # Uploaded files are validated on the backend (see SECURITY): reject
        # empty uploads, enforce a size cap, and make sure an explicitly
        # requested kind matches the actual file type.
        if value is None:
            raise serializers.ValidationError("A file is required.")
        if value.size <= 0:
            raise serializers.ValidationError("The uploaded file is empty.")
        max_bytes = settings.ASSET_MAX_UPLOAD_MB * 1024 * 1024
        if value.size > max_bytes:
            raise serializers.ValidationError(
                f"Files must be {settings.ASSET_MAX_UPLOAD_MB} MB or smaller."
            )
        return value

    def validate(self, attrs):
        kind = attrs.get("kind")
        upload = attrs.get("file")
        if kind in (Asset.Kind.IMAGE, Asset.Kind.VIDEO, Asset.Kind.AUDIO) and upload:
            mime = (upload.content_type or "").lower()
            expected = {
                Asset.Kind.IMAGE: "image/",
                Asset.Kind.VIDEO: "video/",
                Asset.Kind.AUDIO: "audio/",
            }[kind]
            if not mime.startswith(expected):
                raise serializers.ValidationError(
                    {"file": f"The file type does not match the selected kind ({kind})."}
                )
        return attrs

    def _resolve_tags(self, project, tag_names):
        tags = []
        for name in dict.fromkeys(n.strip() for n in tag_names if n and n.strip()):
            tag, _ = AssetTag.objects.get_or_create(
                project=project, name__iexact=name, defaults={"name": name}
            )
            tags.append(tag)
        return tags

    def create(self, validated_data):
        project = self.context["project"]
        user = self.context["user"]
        tag_names = validated_data.pop("tags", None)
        upload = validated_data.get("file")
        asset = Asset.objects.create(
            project=project,
            owner=user,
            mime_type=(upload.content_type if upload else "") or "",
            size=(upload.size if upload else 0) or 0,
            title=validated_data.pop("title", "") or (
                upload.name.rsplit("/", 1)[-1] if upload else ""
            ),
            kind=validated_data.pop(
                "kind", _kind_from_mime(upload.content_type if upload else "")
            ),
            **validated_data,
        )
        if tag_names:
            asset.tags.set(self._resolve_tags(project, tag_names))
        return asset

    def update(self, instance, validated_data):
        tag_names = validated_data.pop("tags", None)
        upload = validated_data.pop("file", None)
        if upload:
            instance.file = upload
            instance.mime_type = upload.content_type or ""
            instance.size = upload.size or 0
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if tag_names is not None:
            instance.tags.set(self._resolve_tags(instance.project, tag_names))
        instance.save()
        return instance