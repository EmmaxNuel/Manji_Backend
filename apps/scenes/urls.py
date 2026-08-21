"""URL patterns for the scenes app (project-scoped)."""

from django.urls import path

from .views import (
    ProjectSceneListCreateView,
    ProjectSceneReorderView,
)

urlpatterns = [
    path("", ProjectSceneListCreateView.as_view(), name="project-scene-list-create"),
    path("reorder/", ProjectSceneReorderView.as_view(), name="project-scene-reorder"),
]