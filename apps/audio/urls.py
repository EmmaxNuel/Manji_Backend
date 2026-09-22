"""URL routing for the audio & voice app (Phase 9)."""

from django.urls import path

from . import views

urlpatterns = [
    path(
        "projects/<uuid:project_id>/audio/",
        views.VoiceRecordingListView.as_view(),
        name="voice-list",
    ),
    path(
        "projects/<uuid:project_id>/audio/timeline/<uuid:scene_id>/",
        views.VoiceTimelineView.as_view(),
        name="voice-timeline",
    ),
    path("audio/<uuid:pk>/", views.VoiceRecordingDetailView.as_view(), name="voice-detail"),
]
