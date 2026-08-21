"""URL patterns for the assets app (project-scoped list/create + tags)."""

from django.urls import path

from .views import ProjectAssetListCreateView, ProjectAssetTagListView

urlpatterns = [
    path("", ProjectAssetListCreateView.as_view(), name="project-asset-list-create"),
    path("tags/", ProjectAssetTagListView.as_view(), name="project-asset-tags"),
]