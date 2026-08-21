from django.contrib import admin

from .models import Scene


@admin.register(Scene)
class SceneAdmin(admin.ModelAdmin):
    list_display = ("title", "project", "chapter", "order", "mood", "duration", "updated_at")
    list_filter = ("project", "chapter", "mood")
    search_fields = ("title", "description", "location")
    readonly_fields = ("id", "created_at", "updated_at")