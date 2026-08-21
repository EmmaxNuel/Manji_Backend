"""
Character model – the cast of a Project (Phase 3).

A Character belongs to a single Project and holds everything an artist, writer
or AI needs to keep the person consistent across story, scenes, storyboard,
animation and audio:

- Identity (name, role in the story)
- Bio / personality / backstory (text the AI context builder injects)
- Appearance (the visual description used for image generation)
- Avatar (a reference portrait)
- Relationships to other characters (who they know and how)

Relationships use a self-referential ManyToMany with an explicit through model
so each link can carry its own type and description.

Design decisions:
- ``characters`` (the JSON name list on Scene, Phase 2) remains intact for
  backward compatibility; the real link is the Scene.cast M2M added in Phase 3.
- New roles can be added to the TextChoices without a migration.
"""

import uuid

from django.db import models
from django.utils import timezone


def character_avatar_upload_path(instance, filename):
    ext = filename.rsplit(".", 1)[-1]
    return f"characters/{instance.project_id}/avatar.{ext}"


class Character(models.Model):
    class Role(models.TextChoices):
        PROTAGONIST = "protagonist", "Protagonist"
        ANTAGONIST = "antagonist", "Antagonist"
        SUPPORTING = "supporting", "Supporting"
        MENTOR = "mentor", "Mentor"
        VILLAIN = "villain", "Villain"
        MINOR = "minor", "Minor"
        OTHER = "other", "Other"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.CASCADE,
        related_name="characters",
    )

    name = models.CharField(max_length=100, db_index=True)
    role = models.CharField(
        max_length=30,
        choices=Role.choices,
        default=Role.SUPPORTING,
    )

    age = models.PositiveIntegerField(
        null=True, blank=True, help_text="Approximate age of the character."
    )

    # Writing
    bio = models.TextField(blank=True)
    personality = models.TextField(blank=True)
    backstory = models.TextField(blank=True)
    notes = models.TextField(
        blank=True,
        help_text="Free-form character notes kept out of the AI context prompt.",
    )

    # Visual identity
    appearance = models.TextField(blank=True)
    avatar = models.ImageField(
        upload_to=character_avatar_upload_path, null=True, blank=True
    )

    # Relationships (self-referential M2M through CharacterRelationship)
    relationships = models.ManyToManyField(
        "self",
        through="CharacterRelationship",
        symmetrical=False,
        related_name="+",
        blank=True,
    )

    order = models.PositiveIntegerField(default=0, db_index=True)

    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "characters"
        ordering = ["order", "name"]
        indexes = [
            models.Index(fields=["project", "order"]),
            models.Index(fields=["project", "role"]),
        ]

    def __str__(self):
        return self.name


class CharacterRelationship(models.Model):
    class RelationshipType(models.TextChoices):
        FAMILY = "family", "Family"
        FRIEND = "friend", "Friend"
        ENEMY = "enemy", "Enemy"
        LOVE = "love", "Love interest"
        RIVAL = "rival", "Rival"
        ALLY = "ally", "Ally"
        MENTOR = "mentor", "Mentor"
        MENTEE = "mentee", "Mentee"
        NEUTRAL = "neutral", "Neutral"
        CUSTOM = "custom", "Custom"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    from_character = models.ForeignKey(
        Character,
        on_delete=models.CASCADE,
        related_name="outgoing_relationships",
    )
    to_character = models.ForeignKey(
        Character,
        on_delete=models.CASCADE,
        related_name="incoming_relationships",
    )
    relationship_type = models.CharField(
        max_length=30,
        choices=RelationshipType.choices,
        default=RelationshipType.NEUTRAL,
    )
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "character_relationships"
        ordering = ["created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["from_character", "to_character"],
                name="unique_character_relationship",
            )
        ]

    def __str__(self):
        return f"{self.from_character} -> {self.to_character} ({self.get_relationship_type_display()})"