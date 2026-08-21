from django.contrib import admin

from .models import Project


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("title", "owner", "project_type", "art_style", "status", "updated_at")
    list_filter = ("project_type", "art_style", "status")
    search_fields = ("title", "owner__username", "owner__email")
    readonly_fields = ("id", "created_at", "updated_at")