"""URL patterns for the storyboard app (project-scoped)."""

from django.urls import path

from .views import (
    ProjectStoryboardReorderView,
    ProjectStoryboardView,
    StoryboardPanelDetailView,
)

urlpatterns = [
    path("", ProjectStoryboardView.as_view(), name="project-storyboard"),
    path("reorder/", ProjectStoryboardReorderView.as_view(), name="project-storyboard-reorder"),
]