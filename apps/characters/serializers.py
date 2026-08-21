"""Serializers for the Character and CharacterRelationship models."""

import json

from django.db import models, transaction
from rest_framework import serializers

from .models import Character, CharacterRelationship


class CharacterRelationshipSerializer(serializers.ModelSerializer):
    """Read representation of one relationship link (outgoing or incoming)."""

    character = serializers.SerializerMethodField()

    class Meta:
        model = CharacterRelationship
        fields = ("id", "character", "relationship_type", "description", "created_at")

    def get_character(self, obj):
        other = obj.to_character
        if self.context.get("direction") == "incoming":
            other = obj.from_character
        return {"id": str(other.id), "name": other.name}


class CharacterRelationshipWriteSerializer(serializers.ModelSerializer):
    """Write representation for creating/updating a relationship link."""

    to_character_id = serializers.UUIDField(write_only=True)

    class Meta:
        model = CharacterRelationship
        fields = ("id", "to_character_id", "relationship_type", "description")

    def validate_to_character_id(self, value):
        try:
            to_character = Character.objects.get(id=value)
        except Character.DoesNotExist:
            raise serializers.ValidationError("Character not found.")
        return to_character


class CharacterListSerializer(serializers.ModelSerializer):
    """Lightweight card view for character lists."""

    avatar = serializers.SerializerMethodField()
    role_label = serializers.SerializerMethodField()

    class Meta:
        model = Character
        fields = (
            "id",
            "name",
            "role",
            "role_label",
            "avatar",
            "order",
            "updated_at",
        )
        read_only_fields = fields

    def get_avatar(self, obj):
        if obj.avatar:
            request = self.context.get("request")
            if request:
                return request.build_absolute_uri(obj.avatar.url)
            return obj.avatar.url
        return None

    def get_role_label(self, obj):
        return dict(Character.Role.choices).get(obj.role, obj.role)


class CharacterDetailSerializer(CharacterListSerializer):
    """Full detail for the workspace character editor."""

    relationships = serializers.SerializerMethodField()

    class Meta(CharacterListSerializer.Meta):
        fields = CharacterListSerializer.Meta.fields + (
            "age",
            "bio",
            "personality",
            "backstory",
            "notes",
            "appearance",
            "relationships",
            "created_at",
        )

    def get_relationships(self, obj):
        outgoing = []
        for rel in obj.outgoing_relationships.select_related("to_character").all():
            outgoing.append(
                {
                    "id": str(rel.id),
                    "character": {"id": str(rel.to_character_id), "name": rel.to_character.name},
                    "relationship_type": rel.relationship_type,
                    "description": rel.description,
                }
            )
        incoming = []
        for rel in obj.incoming_relationships.select_related("from_character").all():
            incoming.append(
                {
                    "id": str(rel.id),
                    "character": {"id": str(rel.from_character_id), "name": rel.from_character.name},
                    "relationship_type": rel.relationship_type,
                    "description": rel.description,
                }
            )
        return {"outgoing": outgoing, "incoming": incoming}


class RelationshipListField(serializers.ListField):
    """List of relationship objects that also accepts a JSON string body.

    Multipart form data delivers nested structures as strings, so a raw
    ListField would reject the avatar-upload flow. This field parses the
    string back into a list while still accepting a normal JSON array.
    """

    def to_internal_value(self, data):
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except (ValueError, TypeError):
                raise serializers.ValidationError("Invalid relationships payload.")
        if not isinstance(data, list):
            raise serializers.ValidationError("Expected a list of relationships.")
        return super().to_internal_value(data)


class CharacterCreateUpdateSerializer(serializers.ModelSerializer):
    """Used for POST (create) and PATCH (update)."""

    relationships = RelationshipListField(
        child=CharacterRelationshipWriteSerializer(), required=False, write_only=True
    )

    class Meta:
        model = Character
        fields = (
            "id",
            "name",
            "role",
            "age",
            "bio",
            "personality",
            "backstory",
            "notes",
            "appearance",
            "avatar",
            "order",
            "relationships",
        )
        read_only_fields = ("id",)
        extra_kwargs = {
            "avatar": {"required": False, "allow_null": True},
            "age": {"required": False, "allow_null": True},
        }

    def validate_name(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Name is required.")
        return value

    def _sync_relationships(self, instance, relationships, direction="outgoing"):
        """Replace the outgoing relationship links for a character."""
        for rel_data in relationships or []:
            to_character = rel_data.get("to_character_id")
            if to_character is None:
                continue
            if to_character.id == instance.id:
                raise serializers.ValidationError(
                    {"relationships": "A character cannot be related to itself."}
                )
            CharacterRelationship.objects.update_or_create(
                from_character=instance,
                to_character=to_character,
                defaults={
                    "relationship_type": rel_data.get("relationship_type", CharacterRelationship.RelationshipType.NEUTRAL),
                    "description": rel_data.get("description", ""),
                },
            )

    def create(self, validated_data):
        relationships = validated_data.pop("relationships", [])
        project = self.context["project"]
        if not validated_data.get("order"):
            last = (
                Character.objects.filter(project=project)
                .aggregate(models.Max("order"))["order__max"]
            )
            validated_data["order"] = (last or 0) + 1
        with transaction.atomic():
            instance = Character.objects.create(project=project, **validated_data)
            self._sync_relationships(instance, relationships)
        return instance

    def update(self, instance, validated_data):
        relationships = validated_data.pop("relationships", None)
        for rel_data in relationships or []:
            to_character = rel_data.get("to_character_id")
            if to_character is not None and to_character.id == instance.id:
                raise serializers.ValidationError(
                    {"relationships": "A character cannot be related to itself."}
                )
        with transaction.atomic():
            for attr, value in validated_data.items():
                setattr(instance, attr, value)
            instance.save()
            if relationships is not None:
                CharacterRelationship.objects.filter(from_character=instance).delete()
                self._sync_relationships(instance, relationships)
        return instance