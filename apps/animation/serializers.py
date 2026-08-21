"""Serializers for the Animation domain (Phase 8)."""

from rest_framework import serializers

from .models import AnimationFrame, AnimationLayer, AnimationProject


def _layer_identity(layer):
    return {"id": str(layer.id), "name": layer.name, "kind": layer.kind}


class AnimationProjectListSerializer(serializers.ModelSerializer):
    """Lightweight card view for the animation list."""

    scene = serializers.SerializerMethodField()
    layer_count = serializers.SerializerMethodField()
    frame_count = serializers.SerializerMethodField()

    class Meta:
        model = AnimationProject
        fields = (
            "id",
            "title",
            "fps",
            "width",
            "height",
            "scene",
            "layer_count",
            "frame_count",
            "order",
            "updated_at",
        )
        read_only_fields = fields

    def get_scene(self, obj):
        if not obj.scene_id:
            return None
        return {"id": str(obj.scene_id), "title": obj.scene.title}

    def get_layer_count(self, obj):
        return obj.layers.count()

    def get_frame_count(self, obj):
        return obj.frames.count()


class AnimationProjectDetailSerializer(AnimationProjectListSerializer):
    layers = serializers.SerializerMethodField()
    frames = serializers.SerializerMethodField()

    class Meta(AnimationProjectListSerializer.Meta):
        fields = AnimationProjectListSerializer.Meta.fields + ("layers", "frames")

    def get_layers(self, obj):
        return [
            {
                "id": str(layer.id),
                "name": layer.name,
                "kind": layer.kind,
                "visible": layer.visible,
                "order": layer.order,
            }
            for layer in obj.layers.all()
        ]

    def get_frames(self, obj):
        return [
            {
                "id": str(frame.id),
                "index": frame.index,
                "layers": frame.layers,
            }
            for frame in obj.frames.all()
        ]


class AnimationProjectCreateUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = AnimationProject
        fields = ("id", "title", "scene", "fps", "width", "height")
        read_only_fields = ("id",)
        extra_kwargs = {
            "title": {"required": False},
            "fps": {"required": False},
            "width": {"required": False},
            "height": {"required": False},
            "scene": {"required": False},
        }

    def validate_title(self, value):
        value = (value or "").strip()
        if not value:
            raise serializers.ValidationError("Give this animation a title.")
        return value

    def validate_fps(self, value):
        if value is not None and (value < 1 or value > 60):
            raise serializers.ValidationError("FPS must be between 1 and 60.")
        return value

    def validate_scene(self, value):
        if value is not None:
            project = self.context.get("project")
            if project is not None and value.project_id != project.id:
                raise serializers.ValidationError(
                    "The scene must belong to this project."
                )
        return value

    def create(self, validated_data):
        project = self.context["project"]
        title = validated_data.pop("title", None) or project.title
        instance = AnimationProject.objects.create(
            project=project, title=title, **validated_data
        )
        return instance


class AnimationLayerSerializer(serializers.ModelSerializer):
    class Meta:
        model = AnimationLayer
        fields = ("id", "animation", "name", "kind", "visible", "order")
        read_only_fields = ("id", "animation")

    def validate_name(self, value):
        value = (value or "").strip()
        if not value:
            raise serializers.ValidationError("Give this layer a name.")
        return value


class AnimationLayerCreateSerializer(AnimationLayerSerializer):
    def create(self, validated_data):
        animation = self.context["animation"]
        return AnimationLayer.objects.create(animation=animation, **validated_data)


class AnimationFrameSerializer(serializers.ModelSerializer):
    class Meta:
        model = AnimationFrame
        fields = ("id", "animation", "index", "layers")
        read_only_fields = ("id", "animation")

    def validate_layers(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError("Frame data must be an object.")
        return value


class AnimationFrameCreateSerializer(serializers.ModelSerializer):
    """Create a frame at an index (inserting, shifting later frames up) with
    optional duplication of an existing frame's drawing data."""

    duplicate_from = serializers.UUIDField(write_only=True, required=False)

    class Meta:
        model = AnimationFrame
        fields = ("id", "index", "layers", "duplicate_from")
        read_only_fields = ("id",)

    def validate(self, attrs):
        index = attrs.get("index")
        if index is None:
            raise serializers.ValidationError({"index": "A frame index is required."})
        if index < 0:
            raise serializers.ValidationError(
                {"index": "Frame index must be zero or greater."}
            )
        return attrs

    def create(self, validated_data):
        animation = self.context["animation"]
        index = validated_data["index"]
        duplicate_from = validated_data.pop("duplicate_from", None)
        layers = validated_data.get("layers", {})

        # Shift existing frames at/above this index up by one, highest first so
        # the unique (animation, index) constraint is never transiently hit.
        targets = AnimationFrame.objects.filter(
            animation=animation, index__gte=index
        ).order_by("-index")
        for frame in targets:
            AnimationFrame.objects.filter(pk=frame.pk).update(
                index=frame.index + 1
            )

        if duplicate_from is not None:
            source = AnimationFrame.objects.filter(
                animation=animation, id=duplicate_from
            ).first()
            if source is not None:
                layers = source.layers

        return AnimationFrame.objects.create(
            animation=animation, index=index, layers=layers
        )


class AnimationFrameUpdateSerializer(serializers.ModelSerializer):
    """Update frame drawing data. Index changes are not allowed here so the
    timeline can only be rearranged through insert/delete."""

    class Meta:
        model = AnimationFrame
        fields = ("id", "layers")
        read_only_fields = ("id",)

    def validate_layers(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError("Frame data must be an object.")
        return value