from django.contrib import admin

from .models import VoiceRecording


@admin.register(VoiceRecording)
class VoiceRecordingAdmin(admin.ModelAdmin):
    list_display = ("title", "kind", "project", "scene", "character", "created_at")
    list_filter = ("kind",)
    search_fields = ("title", "dialogue_line", "description")
