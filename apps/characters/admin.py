from django.contrib import admin

from .models import Character, CharacterRelationship


class CharacterRelationshipInline(admin.TabularInline):
    model = CharacterRelationship
    fk_name = "from_character"
    extra = 0


@admin.register(Character)
class CharacterAdmin(admin.ModelAdmin):
    list_display = ("name", "project", "role", "order", "updated_at")
    list_filter = ("project", "role")
    search_fields = ("name", "bio", "personality", "appearance", "backstory")
    readonly_fields = ("id", "created_at", "updated_at")
    inlines = [CharacterRelationshipInline]


@admin.register(CharacterRelationship)
class CharacterRelationshipAdmin(admin.ModelAdmin):
    list_display = ("from_character", "to_character", "relationship_type", "created_at")
    list_filter = ("relationship_type",)
    search_fields = ("from_character__name", "to_character__name", "description")
    readonly_fields = ("id", "created_at")